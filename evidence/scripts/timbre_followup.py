"""Bounded Timbre REST/gap/tag follow-up; live generation and judging are explicit.

The audio-model screen is separate from human listening results and is not MOS.
"""
import argparse,csv,hashlib,json,os,re,statistics,sys,time
from pathlib import Path
import numpy as np
import soundfile as sf

P=Path(__file__).resolve().parents[1]
OUT=P/'results/timbre_followup'
sys.path.insert(0,str(P))


def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def write(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)


def dump(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


TAGS=['laugh','giggle','sigh','exhales','sniffles','yawns','coughs','clears throat','whispers','shouting','excited','slow','pauses']
EN='Your request is ready. Please continue when you are ready.'
HI='आपका अनुरोध तैयार है। जब आप तैयार हों तो कृपया आगे बढ़ें।'


def cases():
    text={r['case_id']:r['input_text'] for r in read(P/'data/tts_cases.csv')};rows=[]
    def add(cid,section,model,voice,language,sentence,**kw):
        row=dict(case_id=cid,section=section,transport='REST',model=model,voice=voice,language=language,
                 sample_rate_hz=24000,speed=1.0,repetition=1,length='',input_text=sentence,
                 clean_text=re.sub(r'<[^>]+>\s*','',sentence),tag='',expected_policy='',neutral_case_id='',expected_http=200)
        row.update(kw);rows.append(row)
    configs=[('3','timbre-v3.0','Tarika'),('25','timbre-v2.5','Kaveri')]
    for length,cid in [('short','T31'),('medium','T23'),('long','T25')]:
        for repeat in range(1,4):
            for key,model,voice in configs:
                add(f'NF-R-{key}-{length}-{repeat}','rest_latency',model,voice,'en-IN',text[cid],length=length,repetition=repeat)
        for key,model,voice in configs:
            add(f'NF-S-{key}-{length}','stream_control',model,voice,'en-IN',text[cid],length=length,transport='SSE')
    for key,model,voice in configs:
        neutral=f'NF-N-{key}-en';add(neutral,'neutral_style',model,voice,'en-IN',EN)
        for tag in TAGS if key=='3' else ['excited','whispers','pauses']:
            sentence=EN.replace('. ',f'. <{tag}> ',1)
            add(f'NF-T-{key}-en-{tag.replace(" ","_")}','tag',model,voice,'en-IN',sentence,
                tag=tag,expected_policy='render_tag' if key=='3' else 'strip_tag',neutral_case_id=neutral)
        for tag in ['happy','Excited']:
            add(f'NF-I-{key}-{tag}','invalid_tag',model,voice,'en-IN',EN.replace('. ',f'. <{tag}> ',1),tag=tag,expected_policy='strip_unknown',neutral_case_id=neutral)
        for speed in [.85,1.15]:
            add(f'NF-V-{key}-{str(speed).replace(".","_")}','speed',model,voice,'en-IN',EN,speed=speed,neutral_case_id=neutral,expected_policy='speed_control')
        add(f'NF-F-{key}-48000','sample_rate',model,voice,'en-IN',text['T23'],sample_rate_hz=48000,length='medium')
        raw='The change was -2.5 percent. The PIN is 0070. The call starts at 9:05 AM.'
        spoken='The change was minus two point five percent. The PIN is zero zero seven zero. The call starts at nine oh five A M.'
        add(f'NF-C-{key}-raw','normalization',model,voice,'en-IN',raw)
        add(f'NF-C-{key}-spoken','normalization',model,voice,'en-IN',spoken,neutral_case_id=f'NF-C-{key}-raw',expected_policy='spoken_rewrite')
    for key,model,voice in [('3','timbre-v3.0','Shivani'),('25','timbre-v2.5','Nalini')]:
        neutral=f'NF-N-{key}-hi';add(neutral,'neutral_style',model,voice,'hi-IN',HI)
        for tag in ['excited','whispers','slow','pauses'] if key=='3' else ['excited','pauses']:
            add(f'NF-T-{key}-hi-{tag}','tag',model,voice,'hi-IN',HI.replace('। ',f'। <{tag}> ',1),
                tag=tag,expected_policy='render_tag' if key=='3' else 'strip_tag',neutral_case_id=neutral)
    add('NF-ONLY-25','tag_only','timbre-v2.5','Kaveri','en-IN','<excited>',tag='excited',expected_policy='reject_tag_only',expected_http=400)
    # Prespecified bounded rechecks after the first batch returned 44-byte,
    # header-only HTTP-200 WAVs for sigh, yawns and raw critical-number input.
    originals={r['case_id']:r for r in rows}
    for original in ['NF-T-3-en-sigh','NF-T-3-en-yawns','NF-C-3-raw','NF-N-3-hi']:
        for rate in [24000,48000]:
            row={**originals[original],'case_id':original+'-recheck-'+str(rate),
                 'section':'empty_audio_recheck','sample_rate_hz':rate,'repetition':2,
                 'neutral_case_id':'','expected_policy':'recheck_header_only_response'}
            rows.append(row)
    for row in rows:
        if row['section']=='tag' and row['model']=='timbre-v3.0' and row['language']=='hi-IN':
            row['neutral_original_case_id']=row['neutral_case_id']
            row['neutral_case_id']='NF-N-3-hi-recheck-24000'
    assert len({r['case_id'] for r in rows})==len(rows)
    return rows


def attempts():
    path=OUT/'attempts.jsonl'
    return [json.loads(l) for l in path.read_text(encoding='utf8').splitlines() if l.strip()] if path.exists() else []


def collect(rows,limit=None):
    import gnani_api as g
    g.ATTEMPTS=OUT/'attempts.jsonl';g.RAW=OUT/'raw';g.TTS_AUDIO=OUT/'audio'
    prior_path=P/'results/reconciliation/user_reported_spend.json'
    if not os.getenv('GNANI_SPENT_TO_DATE_INR') and prior_path.exists():
        prior=json.loads(prior_path.read_text())
        os.environ['GNANI_SPENT_TO_DATE_INR']=str(prior['amount_inr'])
    count=0
    for r in rows:
        kind='tts' if r['transport']=='REST' else 'tts_stream'
        _,settings,fp=g.tts_request(r['input_text'],r['language'],r['voice'],r['model'],r['speed'],r['sample_rate_hz'],
                                  container='wav' if kind=='tts' else 'raw',endpoint=None if kind=='tts' else g.TTS_SSE_ENDPOINT)
        existing=[a for a in attempts() if a.get('case_id')==r['case_id'] and a.get('fingerprint')==fp]
        if any(a.get('ok') and a.get('audio_path') for a in existing) or any(a.get('http_status')==400 for a in existing):continue
        if existing:
            print('Existing failed trial retained:',r['case_id'],flush=True);continue
        if limit is not None and count>=limit:break
        if kind=='tts':
            result=g.synthesize(r['case_id'],r['input_text'],r['language'],model=r['model'],voice=r['voice'],speed=r['speed'],sample_rate=r['sample_rate_hz'],live=True)
        else:
            result=g.synthesize_stream(r['case_id'],r['input_text'],r['language'],model=r['model'],voice=r['voice'],speed=r['speed'],sample_rate=r['sample_rate_hz'],live=True)
        count+=1
        print('Synthesis',r['case_id'],result.get('http_status'),result.get('ok'),result.get('latency_ms'),flush=True)
        # Avoid artificial account-concurrency pressure in this quality/latency study.
        time.sleep(.15)


def chosen(rows):
    records=attempts();result={}
    for r in rows:
        matches=[a for a in records if a.get('case_id')==r['case_id']]
        if matches:result[r['case_id']]=matches[-1]
    return result


def acoustic(path):
    samples,rate=sf.read(path,dtype='float32',always_2d=True)
    if samples.shape[1]!=1 or not len(samples):raise ValueError('Invalid mono audio')
    x=samples[:,0];size=round(rate*.01);padding=(-len(x))%size
    blocks=np.pad(x,(0,padding)).reshape(-1,size)
    rms=np.sqrt(np.mean(blocks.astype(np.float64)**2,axis=1));views={}
    for threshold in [-35,-45,-55]:
        active=rms>=10**(threshold/20);idx=np.flatnonzero(active);segments=[];start=None
        for i,value in enumerate(list(active)+[False]):
            if value and start is None:start=i
            if not value and start is not None:segments.append((start*.01,min(i*.01,len(x)/rate)));start=None
        first=segments[0] if segments else (0,0);gaps=[(a[1],b[0]-a[1]) for a,b in zip(segments,segments[1:])]
        candidate=bool(len(segments)>1 and first[1]-first[0]<=.3 and segments[1][0]-first[1]>=.5 and first[0]<=1)
        views[str(threshold)]=dict(first_activity_s=float(idx[0]*.01) if len(idx) else None,
                                  first_burst_duration_s=first[1]-first[0],early_gap_candidate=candidate,
                                  early_gap_s=segments[1][0]-first[1] if candidate else 0,
                                  longest_internal_low_energy_s=max((g[1] for g in gaps),default=0))
    return dict(duration_s=len(x)/rate,rate=rate,peak=float(np.max(np.abs(x))),views=views),samples


BLIND_PROMPT='''Listen to the AUDIO without a reference transcript, model name, or requested delivery label. Assess only what is audible. Return compact JSON:
{"heard":str,"naturalness_1to5":int,"prosody_1to5":int,"intelligibility_1to5":int,"observed_delivery":[str],"nonverbal_events":[str],"tag_words_spoken":bool,"initial_sound_then_unexpected_silence":bool,"gap_start_s":number|null,"gap_duration_s":number|null,"leading_silence_description":str,"artifacts":[str],"confidence":"high|medium|low","reason":str}.
Use 1=severe/robotic/inappropriate or unintelligible, 3=understandable with noticeable issues, 5=natural/appropriate/clear. Prosody means rhythm, stress and phrase timing. Describe whispering, shouting, excitement, slow pace, laughter, breathing or deliberate pauses ONLY when audible. Distinguish an initial click/noise from actual words; don't call ordinary sentence pauses a delivery stall. Times are approximate listening judgments. If unsure say so; these are provisional model ratings, not human MOS. Keep reasons brief.'''


def judge_request(task,key,parts,prompt,model,live):
    import gemini_judge as j
    from google.genai import types
    hashes=[hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in parts]
    fp=hashlib.sha256(json.dumps([model,task,hashes,prompt],ensure_ascii=False).encode()).hexdigest()
    cache=OUT/'judge'/task/(key+'__'+fp[:16]+'.json')
    if cache.exists():return json.loads(cache.read_text(encoding='utf8'))
    if not live:return None
    contents=[types.Part.from_bytes(data=Path(p).read_bytes(),mime_type='audio/wav') for p in parts]+[prompt]
    last=None
    for attempt in range(3):
        try:
            response=j.client().models.generate_content(model=model,contents=contents,
                config=types.GenerateContentConfig(temperature=0,max_output_tokens=2048,response_mime_type='application/json'))
            reply=json.loads(response.text or '')
            usage=getattr(response,'usage_metadata',None)
            result=dict(task=task,id=key,model=model,returned_model=getattr(response,'model_version',None),fingerprint=fp,prompt=prompt,
                        input_sha256=hashes,audio_paths=[str(Path(p).relative_to(P).as_posix()) for p in parts],reply=reply,
                        prompt_tokens=getattr(usage,'prompt_token_count',None),output_tokens=getattr(usage,'candidates_token_count',None),
                        thought_tokens=getattr(usage,'thoughts_token_count',None),assessor='audio_model_provisional',human_verified=False)
            dump(cache,result);return result
        except Exception as e:
            last=e
            if '404' in str(e) or 'NOT_FOUND' in str(e) or 'API_KEY' in str(e):break
            time.sleep(1+attempt)
    raise RuntimeError(f'Audio judge failed for {key}: {type(last).__name__}: {str(last)[:220]}')


def prepare_audio(rows,records):
    metrics=[]
    for r in rows:
        a=records.get(r['case_id'])
        if not a or not a.get('ok') or not a.get('audio_path'):continue
        raw=P/a['audio_path'];stats,samples=acoustic(raw)
        canonical=OUT/'listen'/(r['case_id']+'.wav');canonical.parent.mkdir(parents=True,exist_ok=True)
        if not canonical.exists():sf.write(canonical,samples,stats['rate'],subtype='PCM_16')
        metrics.append(dict(**r,http_status=a.get('http_status'),latency_ms=a.get('latency_ms'),ttfa_ms=a.get('ttfa_ms'),
                            stalls=a.get('stalls'),stall_s=a.get('stall_s'),duration_s=stats['duration_s'],
                            rtf=a.get('latency_ms',0)/1000/stats['duration_s'],
                            raw_audio_path=a['audio_path'],raw_audio_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                            audio_path=canonical.relative_to(P).as_posix(),audio_sha256=hashlib.sha256(canonical.read_bytes()).hexdigest(),
                            first_activity_s=stats['views']['-45']['first_activity_s'],
                            early_gap_candidate=stats['views']['-45']['early_gap_candidate'],early_gap_s=stats['views']['-45']['early_gap_s'],
                            longest_internal_low_energy_s=stats['views']['-45']['longest_internal_low_energy_s'],acoustic_sensitivity=json.dumps(stats['views'])))
    write(OUT/'audio_results.csv',metrics);return metrics


def assess(metrics,model,live,limit=None):
    complete=[];count=0
    for r in metrics:
        # Streaming sound quality duplicates the same text; include the six saved streams too.
        result=judge_request('blind',r['case_id'],[P/r['audio_path']],BLIND_PROMPT,model,False)
        if result is None and live and (limit is None or count<limit):
            result=judge_request('blind',r['case_id'],[P/r['audio_path']],BLIND_PROMPT,model,True);count+=1
        if result:
            rep=result['reply']
            for field in ['naturalness_1to5','prosody_1to5','intelligibility_1to5']:
                if not isinstance(rep.get(field),int) or not 1<=rep[field]<=5:raise ValueError('Invalid audio-model score')
            complete.append(dict(case_id=r['case_id'],model=r['model'],section=r['section'],language=r['language'],
                                 **rep,assessor='audio_model_provisional',judge_model=result['model'],audio_sha256=r['audio_sha256']))
            print('Blind audio assessment',r['case_id'],rep['naturalness_1to5'],rep['prosody_1to5'],flush=True)
    write(OUT/'blind_ratings.csv',complete)
    by_id={r['case_id']:r for r in metrics};pairs=[]
    for r in metrics:
        if not r['neutral_case_id'] or r['neutral_case_id'] not in by_id:continue
        baseline=by_id[r['neutral_case_id']]
        reverse=int(hashlib.sha256(r['case_id'].encode()).hexdigest()[:2],16)%2==1
        ordered=[r,baseline] if reverse else [baseline,r];condition='A' if reverse else 'B'
        prompt=('Two audio clips A then B use the same voice and underlying message. Model/version and condition order are hidden. '
                f'The intended comparison is {r["tag"] or r["expected_policy"]}. Listen to both, compare audible delivery and retained content. '
                'Do not prefer a clip merely because an effect is expected. Decide which more clearly demonstrates the requested cue, '
                'or say indistinguishable/uncertain. Detect literal tag words and changed/missing spoken content. '
                'For speed compare pacing; for a rewrite compare the sign, zeros and time values actually heard. JSON only: '
                '{"more_cue":"A|B|indistinguishable|uncertain","cue_audible_A":bool,"cue_audible_B":bool,"content_preserved_A":bool,"content_preserved_B":bool,"literal_tag_spoken_A":bool,"literal_tag_spoken_B":bool,"confidence":"high|medium|low","reason":str}.')
        paths=[P/x['audio_path'] for x in ordered]
        result=judge_request('pair',r['case_id'],paths,prompt,model,False)
        if result is None and live and (limit is None or count<limit):
            result=judge_request('pair',r['case_id'],paths,prompt,model,True);count+=1
            print('Paired audio assessment',r['case_id'],result['reply'].get('more_cue'),flush=True)
        if result:pairs.append(dict(case_id=r['case_id'],control_case_id=baseline['case_id'],condition_side=condition,
                                    expected_policy=r['expected_policy'],tag=r['tag'],model=r['model'],language=r['language'],
                                    **result['reply'],assessor='audio_model_provisional'))
    write(OUT/'pair_ratings.csv',pairs)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');ap.add_argument('--judge-live',action='store_true')
    ap.add_argument('--limit',type=int);ap.add_argument('--judge-limit',type=int);ap.add_argument('--judge-model');args=ap.parse_args()
    rows=cases();write(P/'data/timbre_followup_cases.csv',rows)
    if args.live:collect(rows,args.limit)
    records=chosen(rows);metrics=prepare_audio(rows,records)
    model=args.judge_model or os.getenv('GEMINI_JUDGE_MODEL')
    if not model:
        from dotenv import dotenv_values
        model=dotenv_values(P/'.env').get('GEMINI_JUDGE_MODEL') or 'gemini-3.8-flash'
    assess(metrics,model,args.judge_live,args.judge_limit)
    print('Follow-up:',len(rows),'planned,',len(records),'attempted,',len(metrics),'valid clips',flush=True)


if __name__=='__main__':main()
