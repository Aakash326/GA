"""Freeze targeted held-out protocols before predictions; public dataset audio only."""
import argparse,csv,hashlib,io,json,random,re,sys
from datetime import datetime,timezone
from pathlib import Path
import soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'scripts'))
from analyze_report4 import read,write,dump
D=P/'data/report4'
TERMS=['RBI','SEBI','SBI','HDFC','ICICI','NSE','BSE','NIFTY','SENSEX','UPI','NEFT','RTGS','IMPS','KYC','EMI','SIP','bank','currency','rupees','dollars','interest','loan','shares','stock','account']
REVISION='74f17ec92f0654860c160029d3542199626f63ef'


def freeze():
    D.mkdir(parents=True,exist_ok=True)
    policy=dict(version=1,keyterms=TERMS,keyterm_origin='Generic Indian financial-service vocabulary, fixed before new clip selection; not derived from held-out errors.',
                normalization_rules=['Verbalize minus explicitly','Preserve identifier leading zeros with digit words','Expand amounts and fractional currency units',
                                     'Use written month names and explicit spoken times','Preserve negation and quantity association'],
                language='en-IN',asr_model='prisma-v3.0',asr_output='transcribe',seed=4104,
                intended_clips=15,tts_rewrite_model='timbre-v2.5',tts_rewrite_voice='Kaveri',
                required_human_review='No new listening score exists until independently supplied; blank rows are not evidence.')
    path=D/'frozen_policy.json'
    if path.exists():
        existing=json.loads(path.read_text(encoding='utf8'))
        if {k:v for k,v in existing.items() if k!='frozen_at_utc'}!=policy:raise ValueError('Frozen policy changed')
        return existing
    policy['frozen_at_utc']=datetime.now(timezone.utc).isoformat();dump(path,policy);return policy


def prepare_tts():
    pairs=[
      ('negative','The return was -3.75 percent.','The return was minus three point seven five percent.','minus 3.75 percent'),
      ('currency','The balance is ₹24,680.50.','The balance is twenty four thousand six hundred eighty rupees and fifty paise.','24680 rupees and 50 paise'),
      ('identifier','Your PIN is 0048.','Your PIN is zero zero four eight.','0 0 4 8 in order'),
      ('identifier','Your reference number is 001026.','Your reference number is zero zero one zero two six.','0 0 1 0 2 6 in order'),
      ('date','The payment date is 17/04/2027.','The payment date is the seventeenth of April, twenty twenty seven.','17 April 2027'),
      ('time','Your appointment starts at 9:07 AM.','Your appointment starts at nine oh seven A M.','09:07 AM'),
      ('time','The transfer closes at 12:05 PM.','The transfer closes at twelve oh five P M.','12:05 PM'),
      ('currency','The refund is ₹8,240.','The refund is eight thousand two hundred forty rupees.','8240 rupees'),
      ('negation','Buy 12 shares. Do not buy 21 shares.','Buy twelve shares. Do not buy twenty one shares.','buy 12; prohibit buying 21'),
      ('negation','Do not transfer ₹950. Keep ₹1,250 in the account.','Do not transfer nine hundred fifty rupees. Keep one thousand two hundred fifty rupees in the account.','prohibit transfer 950; retain 1250')]
    rewrite=[]
    for i,(category,raw,spoken,target) in enumerate(pairs,1):
        for variant,text in [('raw',raw),('rewrite',spoken)]:
            rewrite.append(dict(case_id=f'R4-N-{i:02d}-{variant}',pair_id=f'R4-N-{i:02d}',category=category,variant=variant,
                                text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),language='en-IN',model='timbre-v2.5',voice='Kaveri',
                                expected_meaning=target,score_status='awaiting_new_human_listening'))
    write(D/'tts_rewrite_manifest.csv',rewrite)
    prompts=[
      ('neutral','Your account details have been updated. Please review the confirmation.',None),
      ('neutral','The next available appointment is on Monday morning.',None),
      ('question','Would you like me to repeat the reference number?',None),
      ('question','Which account should receive the refund?',None),
      ('sympathetic','I am sorry this has been frustrating. Let us work through it together.',None),
      ('sympathetic','Take your time. I can explain each step again if that would help.',None),
      ('hesitant','Well... let me check that detail once more before we continue.',None),
      ('hesitant','I think... we should verify the amount before confirming the transfer.',None),
      ('excited','Your application has been approved. That is wonderful news!','excited'),
      ('excited','You have reached your savings goal. Congratulations on your progress!','excited'),
      ('controlled_pause','Please check the amount. We can continue when you are ready.','pauses'),
      ('controlled_pause','Keep your reference number ready. I will wait while you find it.','pauses'),
      ('neutral','The support team will review your request and reply tomorrow.',None),
      ('neutral','Please read the details carefully before you confirm.',None),
      ('neutral','Your receipt is available in the documents section.',None),
      ('neutral','You can return to the previous step to correct the information.',None)]
    quality=[]
    for i,(intent,text,tag) in enumerate(prompts,1):
        for key,model,voice in [('3','timbre-v3.0','Tarika'),('25','timbre-v2.5','Kaveri')]:
            quality.append(dict(case_id=f'R4-Q-{i:02d}-{key}-neutral',prompt_id=f'R4-Q-{i:02d}',condition='version_neutral',intent=intent,
                                text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),language='en-IN',model=model,voice=voice,tag=''))
        if tag and i in [9,11]:
            tagged=text.replace('. ','. <'+tag+'> ',1)
            quality.append(dict(case_id=f'R4-Q-{i:02d}-3-tagged',prompt_id=f'R4-Q-{i:02d}',condition='tagged_v3',intent=intent,
                                text=tagged,text_sha256=hashlib.sha256(tagged.encode()).hexdigest(),language='en-IN',model='timbre-v3.0',voice='Tarika',tag=tag))
    write(D/'tts_quality_manifest.csv',quality)
    print('Frozen TTS plan:',len(rewrite),'raw/rewrite cases and',len(quality),'quality clips over 16 distinct texts',flush=True)


def select_asr(download=False):
    path=D/'asr_heldout_manifest.csv'
    if path.exists():return read(path)
    used_ids=set();used_text=set();used_hashes=set()
    manifests=['data/asr_manifest.csv','data/next/asr_next_manifest.csv','data/next/asr_dataset_replacement.csv']
    for name in manifests:
        for row in read(P/name):
            used_ids.update(re.findall(r'utt_\d+',row.get('source_ref','')))
            used_text.add(' '.join((row.get('reference_transcript') or row.get('source_or_prompt') or '').casefold().split()))
            if row.get('input_sha256'):used_hashes.add(row['input_sha256'])
    pattern=re.compile(r'\b(?:'+ '|'.join(re.escape(t) for t in TERMS)+r')\b',re.I)
    pool=[r for r in read(P/'data/sources/svq_index_in.csv') if r['locale']=='en_in' and r['environment']=='clean' and r['utt_id'] not in used_ids and
          ' '.join(r['text'].casefold().split()) not in used_text and pattern.search(r['text'])]
    random.Random(4104).shuffle(pool);picks=[];speakers=set();texts=set()
    for row in pool:
        key=' '.join(row['text'].casefold().split())
        if key in texts or row['speaker_id'] in speakers:continue
        speakers.add(row['speaker_id']);texts.add(key);picks.append(row)
        if len(picks)==15:break
    if len(picks)<15:raise ValueError(f'Only {len(picks)} unused distinct-speaker clean financial-term recordings available')
    frozen_selection=D/'asr_selection.json'
    if frozen_selection.exists():
        if json.loads(frozen_selection.read_text())!=picks:raise ValueError('Held-out selection changed')
    else:dump(frozen_selection,picks)
    if not download:
        print('ASR held-out source selection frozen; use --download for public audio',flush=True);return []
    import pandas as pd
    import prepare_asr_data as prep
    prep.SVQ_BASE=f'https://huggingface.co/datasets/google/svq/resolve/{REVISION}/1.0.0/audio/'
    audio=prep.fetch_svq_audio([pd.Series({**r,'row':int(r['row'])}) for r in picks]);out=[]
    for i,row in enumerate(picks,1):
        dest=D/'audio'/f'R4-ASR-{i:02d}.wav';dest.parent.mkdir(exist_ok=True)
        samples,sr=sf.read(io.BytesIO(audio[row['utt_id']]),dtype='int16',always_2d=True)
        if sr!=16000 or samples.shape[1]!=1:raise ValueError('Unexpected SVQ audio format')
        sf.write(dest,samples,sr,subtype='PCM_16');digest=hashlib.sha256(dest.read_bytes()).hexdigest()
        if digest in used_hashes:raise ValueError('Held-out audio repeats benchmark audio')
        out.append(dict(clip_id=f'R4-ASR-{i:02d}',input_path=dest.relative_to(P).as_posix(),input_sha256=digest,
                        language='en-IN',duration_s=len(samples)/sr,source_dataset='google/svq',source_revision=REVISION,
                        source_ref=row['file']+'#'+row['utt_id'],speaker_id=row['speaker_id'],reference_transcript=row['text'],
                        reference_basis='original public dataset text, not human independently verified',license='CC-BY-4.0',
                        target_terms_json=json.dumps(sorted(set(m.group(0).casefold() for m in pattern.finditer(row['text'])))),
                        frozen_vocabulary_sha256=hashlib.sha256((D/'frozen_policy.json').read_bytes()).hexdigest(),status='prepared_not_run'))
    write(path,out);print('Prepared 15 unused public ASR recordings',flush=True);return out


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--download',action='store_true');args=ap.parse_args()
    freeze();prepare_tts();select_asr(args.download)
