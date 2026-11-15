"""Expand prepared inputs only. No Gnani API requests or credential access."""
from pathlib import Path
from collections import Counter
import csv, hashlib, io, json, random, re, shutil, sys
import numpy as np
import pandas as pd
import soundfile as sf

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
import prepare_asr_data as prep

SEED = 20261114
randomizer = random.Random(SEED)
BACKUP = PROJECT / 'results' / 'before_expansion'
BACKUP.mkdir(exist_ok=True)

def read(name):
    with (PROJECT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write(name, rows, fields):
    path = PROJECT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    temp.replace(path)

def backup(name):
    src = PROJECT / name
    dst = BACKUP / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists() and not dst.exists(): shutil.copy2(src, dst)

for name in ['data/asr_manifest.csv','data/tts_cases.csv','TESTING_STAGES.md','results/pilot_and_budget.md']:
    backup(name)

old_asr = read('data/asr_manifest.csv')
old_by_id = {r['clip_id']:r for r in old_asr}
base = [r for r in old_asr if not r['clip_id'].startswith('EXP-')]
assert len(base) == 64, f'Unexpected pre-expansion size: {len(base)}'
index = pd.read_csv(PROJECT / 'data/sources/svq_index_in.csv')
used_ids = {r['source_ref'].split('#')[-1] for r in base if 'svq' in r['source_dataset']}
used_text = {(r['language'],r['reference_transcript'].strip().casefold()) for r in base if r['reference_transcript']}
speaker_counts = Counter(r['speaker_id'] for r in base if r['source_id']==r['clip_id'] and r['speaker_id'])

selection_path = PROJECT / 'data/expanded_svq_selection.csv'
if selection_path.exists():
    picks = pd.read_csv(selection_path).to_dict('records')
else:
    picks = []
    for locale, short in [('en_in','EN'),('hi_in','HI'),('te_in','TE')]:
        # 12 clean, 6 numeric, 12 real-noise recordings per language.
        groups = [('clean',False,'CL',12),('clean',True,'NUM',6),('background_speech',None,'BG',4),('media_noise',None,'MEDIA',4),('traffic_noise',None,'TRAFFIC',4)]
        for environment, numeric, tag, n in groups:
            pool = index[(index.locale==locale)&(index.environment==environment)]
            if numeric is not None:
                has_digit = pool.text.str.contains(r'\d')
                pool = pool[has_digit if numeric else ~has_digit]
            candidates = pool.to_dict('records')
            randomizer.shuffle(candidates)
            for k in range(1,n+1):
                eligible = [r for r in candidates if r['utt_id'] not in used_ids and (prep.LANG[locale],r['text'].strip().casefold()) not in used_text]
                if not eligible: raise RuntimeError(f'Not enough distinct source texts for {locale}/{tag}')
                chosen = min(eligible, key=lambda r:speaker_counts[r['speaker_id']])
                chosen = {**chosen,'clip_id':f'EXP-{tag}-{short}-{k:02d}', 'category':f'clean_{short.lower()}' if tag=='CL' else ('numbers' if tag=='NUM' else 'real_noise')}
                picks.append(chosen)
                used_ids.add(chosen['utt_id']);used_text.add((prep.LANG[locale],chosen['text'].strip().casefold()))
                speaker_counts[chosen['speaker_id']]+=1
    assert len(picks)==90
    write('data/expanded_svq_selection.csv', picks, list(picks[0]))

print('Frozen 90 new source selections before model outputs; downloading missing public audio.', flush=True)
blobs = prep.fetch_svq_audio([pd.Series(r) for r in picks])
new = []
for r in picks:
    cid=r['clip_id']; out=prep.AUDIO/f'{cid}.wav'
    if not out.exists(): prep.write_wav(out, prep.load_mono(io.BytesIO(blobs[r['utt_id']])), prep.TARGET_SR)
    new.append(prep.row(clip_id=cid, category=r['category'],tags=f"expanded;{r['environment']};{r['locale']}",source_id=cid,speaker_id=r['speaker_id'],language=prep.LANG[r['locale']],input_path=f'data/audio/{cid}.wav',source_dataset='google/svq 1.0.0',source_ref=f"{r['file']}#{r['utt_id']}",source_or_prompt=r['text'],reference_transcript=r['text'],reference_origin='dataset text; human listening required',license_or_consent=prep.SVQ_LICENSE,notes=f"New source; {r['environment']}; speaker-balanced seeded selection, not a representative population sample."))

by_id={r['clip_id']:r for r in new}
sources=[by_id[f'EXP-CL-{lang}-{i:02d}'] for lang in ['EN','HI','TE'] for i in [1,2]]
noise_id='noise-free-sound-0110'
noise=prep.load_mono(prep.CACHE/'musan'/f'{noise_id}.wav')
for number, src in enumerate(sources,1):
    sid=src['clip_id']; speech=prep.load_mono(PROJECT/src['input_path'])
    common=dict(speaker_id=src['speaker_id'],language=src['language'],source_dataset=src['source_dataset'],source_ref=src['source_ref'],source_or_prompt=src['source_or_prompt'],reference_transcript=src['reference_transcript'],reference_origin=f'Inherited from {sid}; source and transformation require listening',license_or_consent=src['license_or_consent'])
    for snr in [20,10,0]:
        cid=f'EXP-SNR-{number:02d}-{snr:02d}'
        mixed,meta=prep.mix_at_snr(speech,noise,snr)
        if not (prep.AUDIO/f'{cid}.wav').exists():
            prep.write_wav(prep.AUDIO/f'{cid}.wav',mixed,prep.TARGET_SR)
        row=prep.row(clip_id=cid,category='synthetic_noise',tags=f'expanded;synthetic_noise;snr{snr}',source_id=sid,noise_snr_db=snr,input_path=f'data/audio/{cid}.wav',derivation_json=json.dumps({'noise':noise_id,**meta}),notes='Matched source/noise, fixed SNR. Background asset must be audited for intelligible speech.',**common)
        row['license_or_consent']+=' + MUSAN (CC-BY-4.0 corpus; retain asset-specific attribution)'
        new.append(row)
    outs={tag:prep.AUDIO/f'EXP-TEL-{number:02d}-{tag}.wav' for tag in ['8K','ALAW','ULAW']}
    if not all(path.exists() for path in outs.values()):
        outs=prep.telephone_chain(PROJECT/src['input_path'],f'EXP-TEL-{number:02d}')
    for tag,path in outs.items():
        new.append(prep.row(clip_id=path.stem,category='telephony_sim',tags=f'expanded;telephony_sim;{tag}',source_id=sid if tag=='8K' else f'EXP-TEL-{number:02d}-8K',input_path=path.relative_to(PROJECT).as_posix(),codec={'8K':'8 kHz PCM','ALAW':'G.711 A-law round trip','ULAW':'G.711 mu-law round trip'}[tag],derivation_json=json.dumps({'source':sid,'filter':'highpass 300 Hz, lowpass 3400 Hz; resample to 8 kHz','codec':tag}),notes='Use the paired 8K control for codec-only deltas.',**common))
    cid=f'EXP-PAUSE-{number:02d}'
    paused,meta=prep.insert_pause(speech)
    if not (prep.AUDIO/f'{cid}.wav').exists():
        prep.write_wav(prep.AUDIO/f'{cid}.wav',paused,prep.TARGET_SR)
    new.append(prep.row(clip_id=cid,category='pause',tags='expanded;pause',source_id=sid,input_path=f'data/audio/{cid}.wav',derivation_json=json.dumps(meta),notes='Heuristic low-energy insertion: manually verify it is between words and does not damage a phoneme; repair before scoring if needed.',**common))

for k,duration in [(1,2),(2,8)]:
    cid=f'EXP-NS-{k:02d}'
    if not (prep.AUDIO/f'{cid}.wav').exists():
        prep.write_wav(prep.AUDIO/f'{cid}.wav',np.zeros(duration*prep.TARGET_SR),prep.TARGET_SR)
    new.append(prep.row(clip_id=cid,category='no_speech',tags='expanded;silence',source_id=cid,input_path=f'data/audio/{cid}.wav',source_dataset='generated',source_or_prompt=f'{duration} seconds of digital silence',reference_origin='empty by construction',is_no_speech='true',human_reference_verified='true',license_or_consent='generated'))
for k,duration in [(3,6),(4,8)]:
    cid=f'EXP-NS-{k:02d}'
    segment=np.tile(noise,4)[(k*2)*prep.TARGET_SR:(k*2+duration)*prep.TARGET_SR]
    segment=segment*(10**(-26/20)/np.sqrt(np.mean(segment**2)))
    peak=float(np.abs(segment).max());segment*=min(1,0.98/max(peak,1e-12))
    if not (prep.AUDIO/f'{cid}.wav').exists():
        prep.write_wav(prep.AUDIO/f'{cid}.wav',segment,prep.TARGET_SR)
    new.append(prep.row(clip_id=cid,category='no_speech',tags='expanded;ambient_noise',source_id=cid,input_path=f'data/audio/{cid}.wav',source_dataset='MUSAN',source_ref=noise_id,source_or_prompt=f'{duration} seconds ambient noise',reference_origin='empty expected; must verify no intelligible speech',is_no_speech='true',license_or_consent='MUSAN CC-BY-4.0 corpus; retain asset-specific attribution',derivation_json=json.dumps({'noise':noise_id,'offset_s':k*2,'duration_s':duration})))

assert len(new)==136
expanded=base+[old_by_id.get(r['clip_id'],r) for r in new]
assert len(expanded)==200 and len({r['clip_id'] for r in expanded})==200
for r in expanded:
    assert (PROJECT/r['input_path']).is_file()
    assert 0<float(r['duration_s'])<=30,(r['clip_id'],r['duration_s'])
    # Speaker groups and all descendants stay together for optional mitigation holdout.
    group=r['speaker_id'] or ('call:'+str(Path(r['source_ref']).parent) if r['category']=='real_telephony' else r['source_id'])
    r['evaluation_group']=group
    r['evaluation_split']='holdout' if int(hashlib.sha256(group.encode()).hexdigest()[:8],16)%5==0 else 'exploration'
fields=list(base[0])
for key in ['evaluation_group','evaluation_split']:
    if key not in fields: fields.append(key)
write('data/asr_manifest.csv',expanded,fields)
print('Saved 200 ASR rows with existing reviews preserved.',flush=True)

tts=read('data/tts_cases.csv')
old_tts={r['case_id']:r for r in tts}
tts=[r for r in tts if int(r['case_id'][1:])<39]
assert len(tts)==30
short_passage='Your payment has been received. Please check your account details and keep the confirmation message. Our team will contact you if further information is required.'
medium_passage='Your request has been received and is now under review. Please check the details shown in your account before you confirm the next step. If any information is wrong, contact our support team so we can help you update it. We will send a message when the review is complete. You do not need to submit the same request again. Keep your reference number safe and use it when you ask us for an update.'
long_passage=medium_passage+' Before placing an order, review the company name, quantity, and price carefully. The amount shown on the confirmation screen may include charges that were not included in an earlier estimate. If you decide to change the order, return to the details page and check the updated information before confirming. Do not share your password or verification code with anyone who contacts you unexpectedly. You can find the official support contact details inside your account. Once the request is complete, save the receipt for your records.'
for r in tts:
    if r['case_id'] in ['T21','T23','T25'] and not r['input_text'].strip():
        r['input_text']={'T21':short_passage,'T23':medium_passage,'T25':long_passage}[r['case_id']]
        r['target_word_count']=str(len(r['input_text'].split()))
        r['prompt_status']='review_targets'
        r['notes']+=' | Full passage supplied during expansion; target count is actual whitespace word count.'

groups=[
('numeric','en-IN',[
 'Your available balance is ₹0.05.',
 'The adjustment is −₹250.50, not ₹250.50.',
 'The quantity is 15, not 50.',
 'The interest rate changed from 7.05% to 7.50%.',
 'Please pay ₹10,00,000 before the due date.',
 'The meeting starts at 9:05 AM and ends at 12:30 PM.',
 'The payment date is 03 November 2026, not 30 November 2026.',
 'Your delivery window is 3–5 working days.',
 'The exchange value is 0.125 units per point.',
 'You hold 101 shares, and 11 shares are pending.'
]),
('identifiers','en-IN',[
 'Your reference number is 000042.',
 'Your verification code is 448822.',
 'Your reference number is AB10O0.',
 'The last four digits are 0070.',
 'Please use reference ZX-204-009.',
 'Your ticket number is 100100.',
 'Your order code is A1B2C3.',
 'Please read the digits separately: 0 0 4 2 9 1.',
 'Your reference is 1234567890123456.',
 'The account ending in 4821 is selected; the account ending in 4812 is not.'
]),
('code_switching','auto',[
 'आपका भुगतान पूरा हो गया है। कृपया रसीद सुरक्षित रखें।',
 'आपका balance ₹1,250 है और अगली payment कल होगी।',
 'कृपया order cancel करें, confirm नहीं।',
 'Aapka payment mil gaya hai. Kripya receipt sambhal kar rakhen.',
 'Your refund अभी pending है; कृपया कल फिर check करें।',
 'KYC complete होने के बाद account activate होगा।',
 'దయచేసి మీ ఖాతా వివరాలను మరోసారి తనిఖీ చేయండి.',
 'మీ payment complete అయింది. Receipt save చేసుకోండి.',
 'నా order cancel చేయండి, confirm చేయవద్దు.',
 'कल सुबह नौ बजे support team आपको call करेगी।'
]),
('names_abbreviations','en-IN',[
 'Please ask Dr. Meera Rao to review the request.',
 'Your NEFT transfer is pending, but your UPI payment is complete.',
 'The RTGS and IMPS services have different limits.',
 'Please check the PAN and GST details on the form.',
 'Your EMI is due, and your SIP will continue unchanged.',
 'Shanmugapriya will contact Srinivasan tomorrow.',
 'Satinder Kaur will visit the Bengaluru office.',
 'The appointment is at St. Johns Road near the main branch.',
 'Please download the PDF and scan the QR code.',
 'The report includes NAV, ISIN, and KYC information.'
]),
('prosody','en-IN',[
 'Did you say fifteen shares or fifty shares?',
 'Do not cancel the payment. Cancel only the duplicate request.',
 'Please record the message. The record is now complete.',
 'Your request is approved; however, the transfer is still pending.',
 'First, verify the name; second, check the amount; finally, confirm only if both are correct.'
]),
('length','en-IN',[
 'Your request is saved. Check the name, amount, and date before you continue. If anything is wrong, go back and edit the details.',
 'We have received your application. Our team will review the details and contact you if more information is needed. Please keep your reference number available. You do not need to create another application while this review is in progress.',
 'Your statement shows the opening balance, completed payments, and closing balance for the selected period. A pending transaction may appear separately until processing is complete. Check the date and amount of each entry before raising a query. If an entry looks unfamiliar, note its reference number and contact support through the application. Do not share passwords or verification codes.',
 short_passage+' '+medium_passage,
 long_passage+' If you have more than one account, check which account is selected before downloading a statement. Choose the required date range and confirm that the file contains the expected entries. A downloaded statement is a record of completed activity; it does not guarantee that a pending request will succeed. Contact support if the status remains unclear.'
])]
cid=39
for category,language,texts in groups:
    for text in texts:
        case=f'T{cid:02d}';cid+=1
        row={k:'' for k in tts[0]}
        row.update(case_id=case,selected='true',category=category,input_text=text,prompt_status='review_targets',target_word_count=str(len(text.split())),language=language,speed='1.0',audio_format='wav',notes='Expanded prompt. Freeze semantic/pronunciation targets and accepted variants before synthesis; use a language-competent listener. Fictional identifiers. Voice/model/limits require validation.')
        tts.append(old_tts.get(case,row))
assert len(tts)==80 and len({r['case_id'] for r in tts})==80
assert all(r['input_text'].strip() for r in tts)
write('data/tts_cases.csv',tts,list(tts[0]))

seconds=sum(float(r['duration_s']) for r in expanded)
characters=sum(len(r['input_text']) for r in tts)
repeats=['T31','T33','T21','T85','T23','T25']
by_tts={r['case_id']:r for r in tts}
extra_chars=4*sum(len(by_tts[c]['input_text']) for c in repeats)
mid=seconds*.03/3.6+(characters+extra_chars)*.11/61
upper=seconds*.035/3.6+(characters+extra_chars)*.115/61
summary={'asr_cases':len(expanded),'tts_cases':len(tts),'audio_seconds':round(seconds,3),'tts_characters':characters,'asr_known_speakers':len({r['speaker_id'] for r in expanded if r['speaker_id']}),'asr_verified_cases':sum(r['human_reference_verified']=='true' for r in expanded),'tts_prompts_requiring_review':sum(r['prompt_status']!='ready' for r in tts),'latency_repeat_ids':repeats,'trials_per_prompt_including_core':5,'additional_tts_characters_for_repeats':extra_chars,'estimated_future_base_cost_inr':round(mid,4),'upper_rate_scenario_future_base_inr':round(upper,4),'upper_rate_scenario_with_20pct_and_pilots_inr':round(.14+upper*1.2,4),'authorized_total_ceiling_inr':500,'paid_calls_during_preparation':0,'source_seed':SEED}
(PROJECT/'results/expanded_dataset_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2),flush=True)
assert .14+upper*1.2<500
print('Prepared expanded datasets; no Gnani API calls made.',flush=True)
