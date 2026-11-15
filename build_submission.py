"""Build the detailed offline submission from privacy-filtered saved evidence only."""
import argparse,csv,difflib,hashlib,html,json,re,sys,wave
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import soundfile as sf


def read(path):
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def load(path):return json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def write(path,rows):
    if not rows:return
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows([{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows])
def yes(x):return str(x).lower()=='true'
def number(x):return float(x) if str(x).strip() not in ['','None','nan'] else None

def playout_timeline(rows,buffer_ms=0):
    """Place every saved PCM chunk on the same sample clock as its replay WAV."""
    if not rows:raise ValueError('Missing saved chunk events')
    rows=sorted(rows,key=lambda r:int(r['chunk_index']))
    rate=int(rows[0]['sample_rate']);cursor=int(rows[0]['arrival_sample'])+round(buffer_ms*rate/1000)
    first=cursor;offset=0;chunks=[];previous=-1
    for i,r in enumerate(rows):
        arrival=int(r['arrival_sample']);n=int(r['pcm_samples'])
        if arrival<previous or n<=0 or int(r['sample_rate'])!=rate:raise ValueError('Invalid chunk sequence')
        start=max(cursor,arrival);gap=max(0,arrival-cursor) if i else 0
        chunks.append(dict(index=i+1,received_s=float(r['arrival_s']),received_sample=arrival,
                           audio_offset_s=offset/rate,duration_s=n/rate,pcm_samples=n,
                           play_start_s=start/rate,play_start_sample=start,play_end_s=(start+n)/rate,
                           queue_wait_s=(start-arrival)/rate,gap_before_s=gap/rate))
        cursor=start+n;offset+=n;previous=arrival
    return dict(sample_rate=rate,buffer_ms=buffer_ms,chunks=chunks,first_play_s=first/rate,
                end_s=cursor/rate,audio_duration_s=offset/rate)
def journal(path):
    unique={}
    if path.exists():
        for line in path.read_text(encoding='utf8').splitlines():
            if line.strip():
                r=json.loads(line);key=r.get('request_id') or (r.get('kind'),r.get('case_id'),r.get('run_tag'))
                unique[key]={**unique.get(key,{}),**r}
    return list(unique.values())


class Audio:
    def __init__(self,root):self.root=root;self.e=root/'evidence';self.memo={};self.records=[]
    def get(self,relative):
        if not relative:return ''
        relative=str(relative).replace('\\','/')
        if relative in self.memo:return self.memo[relative]
        path=(self.e/relative).resolve()
        if not path.is_relative_to(self.e.resolve()) or not path.is_file():return ''
        if re.search(r'CALL-\d{2}|/call/',relative):raise ValueError('Private audio was selected')
        data,rate=sf.read(path,dtype='int16',always_2d=True)
        if not len(data):return ''
        original=hashlib.sha256(path.read_bytes()).hexdigest();pcm=hashlib.sha256(data.astype('<i2').tobytes()).hexdigest()
        finite=False
        try:
            with wave.open(str(path),'rb') as w:finite=w.getcomptype()=='NONE' and w.getsampwidth()==2 and w.getnframes()==len(data)
        except (wave.Error,EOFError):pass
        output=path
        if not finite:
            output=self.root/'media'/f'{rate}_{data.shape[1]}_{pcm[:20]}.wav';output.parent.mkdir(exist_ok=True)
            if not output.exists():sf.write(output,data,rate,subtype='PCM_16')
            check,sr=sf.read(output,dtype='int16',always_2d=True)
            if sr!=rate or not np.array_equal(check,data):raise ValueError('Display remux changed PCM')
        url=output.relative_to(self.root).as_posix();self.memo[relative]=url
        self.records.append(dict(source_path=relative,source_sha256=original,display_path=url,display_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),pcm_sha256=pcm,sample_rate=rate,frames=len(data),channels=data.shape[1],duration_s=len(data)/rate,remuxed=not finite))
        return url


def build(root):
    root=Path(root).resolve();e=root/'evidence';s=load(e/'results/submission/summary.json');audio=Audio(root)
    catalog=[];by_key={};asr_primary={};tts={};tts_seen=set()
    def add(row):
        row={k:v for k,v in row.items() if v is not None};row['uid']='c'+str(len(catalog));row.setdefault('language','');row.setdefault('model','');row.setdefault('voice','');row.setdefault('status','unscored');row.setdefault('category','');row.setdefault('cohort','')
        row['audio']=audio.get(row.get('source_audio',''));catalog.append(row);by_key[row['uid']]=row;return row
    # Primary ASR: use frozen source references, not adjudicated alternatives.
    for r in read(e/'results/submission/asr_results.csv'):
        row=add(dict(kind='ASR',id=r['clip_id'],cohort=r['cohort'],language=r['language'],category=r['category'],model=r['model'],
            reference=r['reference'],hypothesis=r['hypothesis'],wer=number(r['wer']),cer=number(r['cer']),word_edits=int(r['word_edits']),ref_words=int(r['ref_word_count']),
            status='no-speech control' if yes(r['is_no_speech']) else 'transcription edits' if int(r['word_edits']) else 'exact normalized match',
            source_audio=r['input_path'],source_dataset=r['source_dataset'],source_ref=r['source_ref'],latency_ms=number(r['latency_ms']),
            response='evidence/'+r['raw_response_path'],basis='Original dataset transcript; normalized corpus scoring'))
        asr_primary[r['clip_id']]=row
    paired=[]
    for r in read(e/'results/submission/paired_model_keyterm_streaming.csv'):
        base=asr_primary.get(r['clip_id'])
        if not base:continue
        settings=json.loads(r['request_settings'] or '{}');label={'v25':'Prisma v2.5','keyterms':'Error-selected keyterms','ws':'ASR streaming'}.get(r['experiment'],r['experiment'])
        comparison=add(dict(kind='ASR',id=r['clip_id']+' / '+r['experiment'],cohort='paired_'+r['experiment'],language=base['language'],category=label,model=settings.get('model','prisma-v3.0'),source_audio=base['source_audio'],reference=r['reference'],hypothesis=r['comparison_hypothesis'],
            word_edits=int(r['comparison_word_edits']),ref_words=int(r['ref_word_count']),wer=int(r['comparison_word_edits'])/int(r['ref_word_count']),
            status='transcription edits' if int(r['comparison_word_edits']) else 'exact normalized match',request_settings=settings,basis='Same audio/source reference; paired public experiment'))
        paired.append(dict(group=label,id=r['clip_id'],before=base['uid'],after=comparison['uid'],note='Error-selected hints used observed errors; this is not a held-out benefit estimate.' if r['experiment']=='keyterms' else 'Same source audio and reference; model/transport condition changes.'))
    for r in read(e/'results/submission/paired_acoustic_conditions.csv'):
        a=asr_primary.get(r['parent_clip_id']);b=asr_primary.get(r['clip_id'])
        if a and b:paired.append(dict(group=r['condition'],id=r['clip_id'],before=a['uid'],after=b['uid'],note='Matched source/derivative. Audio transformations are not new speakers.'))
    held=read(e/'results/report4_quality/asr_heldout_keyterm_results.csv');held_map={}
    for r in held:
        item=add(dict(kind='ASR',id=r['clip_id']+' / '+r['condition'],cohort='held-out keyterms',language='en-IN',category=r['condition'],model='prisma-v3.0',source_audio=r['input_path'],reference=r['reference'],hypothesis=r['hypothesis'],wer=number(r['wer']),cer=number(r['cer']),word_edits=int(r['word_edits']),ref_words=int(r['ref_word_count']),status='transcription edits' if int(r['word_edits']) else 'exact normalized match',response='evidence/'+r['response_path'],basis='Frozen vocabulary; original MInDS-14 transcript; 8 kHz US English; target term coverage only account'))
        held_map[r['clip_id'],r['condition']]=item
    for cid in sorted({r['clip_id'] for r in held}):
        if (cid,'baseline') in held_map and (cid,'hinted') in held_map:paired.append(dict(group='Held-out keyterms',id=cid,before=held_map[cid,'baseline']['uid'],after=held_map[cid,'hinted']['uid'],note='Frozen generic vocabulary. All 15 target-word occurrences are account; no bank-name/acronym benefit is established.'))
    # Format experiments: retain actual output, do not grade intentional script changes with headline WER.
    formats=[]
    next_records=journal(e/'results/next/attempts.jsonl')
    for a in next_records:
        if a.get('kind')!='asr' or a.get('run_tag') not in ['verbatim','codemix'] or not a.get('ok'):continue
        base=asr_primary.get(a['case_id']);path=e/a.get('raw_path','')
        if not base or not path.is_file():continue
        body=load(path);r=add(dict(kind='ASR',id=a['case_id']+' / '+a['run_tag'],cohort='output format exploration',language=base['language'],category=a['run_tag'],model=a['settings']['model'],source_audio=base['source_audio'],reference=base['reference'],hypothesis=body.get('transcript',''),status='format output; unscored',basis='Rendering diagnostic, not a script-aware accuracy benchmark',response='evidence/'+a['raw_path'],latency_ms=a['latency_ms']))
        formats.append(dict(case_id=a['case_id'],format=a['run_tag'],reference=base['reference'],transcript=body.get('transcript',''),uid=r['uid'],model=a['settings']['model']))
    # TTS original 164 clips: retain all frozen target definitions, with explicit human marks only.
    marks=defaultdict(list)
    for r in read(e/'results/submission/tts_results.csv'):marks[r['case_id']].append(r)
    qc={r['case_id']:r for r in read(e/'results/submission/tts_audio_quality.csv')}
    definitions={}
    for name in ['data/tts_cases.csv','data/next/tts_next_cases.csv','data/tts_mitigation_cases.csv','data/tts_voice_bank.csv']:
        for r in read(e/name):definitions[r['case_id']]=r
    for cid,r in qc.items():
        m=definitions.get(cid,{})
        human=marks[cid];values=[x['result'] for x in human];targets=[]
        for target in json.loads(m.get('expected_targets_json') or '[]'):
            mark=next((x for x in human if x['target_id']==str(target.get('id'))),{})
            targets.append(dict(id=target.get('id'),expected=target.get('must_hear',target.get('written','')),critical=target.get('critical',False),mark=mark.get('result','unscored')))
        status='human target wrong' if 'wrong' in values else 'human target ambiguous' if 'ambiguous' in values else 'human-marked targets correct' if values else 'unscored'
        item=add(dict(kind='TTS',id=cid,cohort='original baseline' if cid.startswith('T') else 'original targeted',language=r['language'],category=m.get('category',''),model=r['model'],voice=r['voice'],source_audio=r['audio_path'],prompt=m.get('input_text',''),targets=targets,status=status,basis='Explicit human target marks; unmarked targets excluded',duration_s=number(r['decoded_duration_s']),waveform_note='Valid PCM; original WAV length fields are placeholders',near_full_scale_samples=int(r['near_full_scale_samples']),longest_internal_low_energy_s=number(r['longest_internal_low_energy_s'])))
        tts[cid]=item;tts_seen.add((cid,'run1',r['model'],r['voice']))
    blind={r['case_id']:r for r in read(e/'results/timbre_followup/blind_ratings.csv')}
    for r in read(e/'results/timbre_followup/audio_results.csv'):
        b=blind.get(r['case_id'],{})
        item=add(dict(kind='TTS',id=r['case_id'],cohort='earlier version/functionality follow-up',language=r['language'],category=r['section'],model=r['model'],voice=r['voice'],source_audio=r['audio_path'],prompt=r['input_text'],status='unscored functionality output',basis='Functionality/latency sample; separate from original human correctness cohort',duration_s=number(r['duration_s']),latency_ms=number(r['latency_ms']),machine_transcript=b.get('heard',''),machine_reason=b.get('reason',''),machine_assessor='Audio-model provisional; not a human transcript or MOS'))
        tts[r['case_id']]=item;tts_seen.add((r['case_id'],'run1',r['model'],r['voice']))
    controlled=[]
    for r in read(e/'results/report4/rest_latency_trials.csv'):
        if not yes(r['eligible_primary']):continue
        item=add(dict(kind='TTS',id=r['case_id'],cohort='controlled REST timing: 30 measured',language=r['language'],category=r['length'],model=r['version'],voice=r['voice_id'],source_audio=r['audio_path'],prompt=r['input_text'],status='unscored timing output',duration_s=number(r['duration_s']),latency_ms=number(r['request_total_ms']),rtf=number(r['rtf_client']),basis='One of 30 measured requests; one text/length, five repeats/version/text'))
        tts[r['case_id']]=item;controlled.append(dict(case_id=r['case_id'],uid=item['uid'],length=r['length'],model=r['version'],latency_ms=float(r['request_total_ms'])))
        tts_seen.add((r['case_id'],'report4',r['version'],r['voice_id']))
    for r in read(e/'results/report4_quality/tts_audio_manifest.csv'):
        item=add(dict(kind='TTS',id=r['case_id'],cohort='prepared held-out listening / rewrites',language=r['language'],category=r.get('category') or r.get('intent') or r.get('condition'),model=r['model'],voice=r['voice'],source_audio=r['audio_path'],prompt=r['text'],status='awaiting new human rating',duration_s=number(r['audio_duration_s']),expected_meaning=r.get('expected_meaning',''),basis='New audio only; human quality/correctness remains unscored'))
        tts[r['case_id']]=item;tts_seen.add((r['case_id'],'report4_quality',r['model'],r['voice']))
    # Additional successful public timing, voice and streaming runs remain auditable.
    known_text={cid:r.get('input_text','') for cid,r in definitions.items()}
    for r in read(e/'results/tts_voice_comparison.csv'):known_text[r['case_id']]=r['input']
    for r in read(e/'results/tts_roundtrip_15_50.csv'):known_text[r['case_id']]=r['input_text']
    for name in ['data/timbre_followup_cases.csv','data/report4/tts_quality_manifest.csv','data/report4/tts_rewrite_manifest.csv']:
        for r in read(e/name):known_text[r['case_id']]=r.get('input_text') or r.get('text','')
    extras=[]
    sources=['results/attempts.jsonl','results/next/attempts.jsonl','results/report4/attempts.jsonl']
    for filename in sources:
        for a in journal(e/filename):
            if a.get('kind') not in ['tts','tts_stream','tts_ws'] or not a.get('ok'):continue
            cid=a['case_id'];settings=a.get('settings',{});model=settings.get('model','');voice=settings.get('voice','');tag=a.get('run_tag','run1')
            identity=(cid,tag,model,voice)
            if identity in tts_seen:continue
            folder='results/next/audio' if '/next/' in filename else 'results/tts_audio'
            candidates=[a.get('audio_path',''),f'{folder}/{cid}.wav' if tag=='run1' else f'{folder}/{cid}__{tag}.wav']
            path=next((p for p in candidates if p and (e/p).is_file()),'')
            if not path:continue
            item=add(dict(kind='TTS',id=cid+' / '+tag,case_id=cid,cohort='additional public timing / voice / stream runs',language=settings.get('language',''),category=a['kind'],model=model,voice=voice,source_audio=path,prompt=a.get('input_text') or known_text.get(cid,''),status='exploratory; no new human mark',latency_ms=a.get('latency_ms'),ttfa_ms=a.get('ttfa_ms'),basis='Saved public exploratory output; not pooled into primary human correctness or controlled timing'))
            extras.append(item['uid']);tts_seen.add(identity)
    # Streaming player pairs: raw concatenated PCM versus reconstructed arrival-timed playback.
    streams=[];chunk_rows=read(e/'results/report4/stream_chunk_timeline.csv');playout_exports=[];playout_keys=set()
    def timeline_for(case_id,buffer_ms=0):
        timeline=playout_timeline([c for c in chunk_rows if c['cohort']=='fresh_SSE' and c['case_id']==case_id],buffer_ms)
        if (case_id,buffer_ms) not in playout_keys:
            playout_exports.extend(dict(case_id=case_id,buffer_ms=buffer_ms,sample_rate=timeline['sample_rate'],**c) for c in timeline['chunks'])
            playout_keys.add((case_id,buffer_ms))
        return timeline
    for r in read(e/'results/timbre_followup/stream_playback.csv'):
        item=tts.get(r['case_id']);replay=audio.get('results/timbre_followup/'+r['immediate_path'])
        if item:streams.append(dict(id=r['case_id'],model=r['model'],voice=r['voice'],raw=item['audio'],replay=replay,prompt=item.get('prompt',''),first_audio_ms=number(r['first_audio_ms']),underruns=int(r['underruns']),starvation_s=float(r['starvation_s']),gaps=json.loads(r['gaps']),timeline=timeline_for(r['case_id'])))
    rewrites=[]
    for r in read(e/'results/submission/tts_human_rewrite_pairs.csv'):
        if r['raw_case_id'] in tts and r['rewritten_case_id'] in tts:rewrites.append(dict(id=r['pair_id'],before=tts[r['raw_case_id']]['uid'],after=tts[r['rewritten_case_id']]['uid'],outcome=r['outcome'],basis='Complete human marks on both variants; failure-enriched selection'))
    for r in read(e/'results/report4_quality/tts_rewrite_pairs.csv'):
        if r['raw_case_id'] in tts and r['rewrite_case_id'] in tts:rewrites.append(dict(id=r['pair_id'],before=tts[r['raw_case_id']]['uid'],after=tts[r['rewrite_case_id']]['uid'],outcome='unscored',basis='Frozen new English v2.5 pairs; no human correctness marks'))
    tags=[]
    for r in read(e/'data/timbre_followup_cases.csv'):
        if r['section']=='tag' and r['model']=='timbre-v3.0' and r['language']=='en-IN':tags.append(dict(tag=r['tag'],case_id=r['case_id'],uid=tts.get(r['case_id'],{}).get('uid',''),status='valid audio; expression not independently verified' if r['case_id'] in tts else 'HTTP 200, zero PCM on initial trial'))
    alltags=load(e/'results/all_tags_demo/metadata.json')
    demo={}
    if alltags:
        demo=dict(audio=audio.get(alltags['audio_path']),duration_s=alltags['duration_s'],prompt=(e/alltags['prompt_path']).read_text(encoding='utf8'),tags=alltags['tags'],voice=alltags['voice'])
    failures=[r for r in read(e/'results/report4/tts_http_attempts.csv') if r['attempt_outcome']!='valid_pcm']
    # Full public trial tables for the notebook and evidence browser.
    table_paths={
        'primary_asr':'results/submission/asr_results.csv','human_tts_targets':'results/submission/tts_results.csv',
        'tts_audio_quality':'results/submission/tts_audio_quality.csv','paired_asr':'results/submission/paired_model_keyterm_streaming.csv',
        'paired_acoustics':'results/submission/paired_acoustic_conditions.csv','original_timing':'results/tts_timing_repeats.csv',
        'voice_comparison':'results/tts_voice_comparison.csv','roundtrip':'results/tts_roundtrip_15_50.csv',
        'stream_voices':'results/tts_streaming_voices.csv','connections':'results/tts_ws_vs_sse.csv',
        'old_streams':'results/submission/streaming_diagnostics.csv','old_playback':'results/playback_validation/playback_validation.csv',
        'controlled':'results/report4/rest_latency_trials.csv','http_outcomes':'results/report4/tts_http_attempts.csv',
        'buffers':'results/report4/buffer_summary.csv','stream_trials':'results/report4/stream_trials.csv',
        'heldout_asr':'results/report4_quality/asr_heldout_keyterm_results.csv',
        'asr_heldout_pairs':'results/report4_quality/asr_heldout_pairs.csv',
        'cohort_membership':'results/submission/rest_cohort_membership.csv',
        'provisional_ratings':'results/timbre_followup/blind_ratings.csv','tag_pairs':'results/timbre_followup/tag_evidence.csv',
        'judge_controls':'results/timbre_followup/playback_judge_checks.csv','human_naturalness':'results/submission/tts_human_quality_ratings.csv'}
    tables={key:read(e/path) for key,path in table_paths.items()}
    outcome_examples=[]
    for r in s['report4']['streaming']['playback_examples']:outcome_examples.append({**r,'audio':audio.get('results/report4/'+r['path']),'timeline':timeline_for(r['case_id'],r['buffer_ms'])})
    data=dict(summary=s,catalog=catalog,paired=paired,formats=formats,controlled=controlled,streams=streams,rewrites=rewrites,tags=tags,all_tags=demo,failures=failures,
              tables=tables,table_paths={k:'evidence/'+v for k,v in table_paths.items()},buffer_examples=outcome_examples,extra_tts_uids=extras,
              links=dict(comparison='evidence/timbre_comparison.html',controlled='evidence/results/report4/index.html',listening='evidence/results/report4_quality/listening.html',rewrites='evidence/results/report4_quality/rewrites.html'))
    dump(root/'assets/submission_data.json',data);write(root/'assets/clip_catalog.csv',catalog);dump(root/'assets/audio_manifest.json',audio.records)
    write(root/'assets/stream_playout_timeline.csv',playout_exports)
    template=(root/'assets/submission_template.html').read_text(encoding='utf8')
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    (root/'submission.html').write_text(template.replace('__DATA__',payload),encoding='utf8')
    print('Detailed HTML built:',len(catalog),'catalog records;',len(audio.records),'audio sources;',len(paired),'ASR pairs;',len(rewrites),'rewrite pairs')
    return data


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);args=ap.parse_args();build(args.root)
