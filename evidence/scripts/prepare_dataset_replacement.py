"""Replace custom recording collection with 24 public recordings. Downloads only; no paid APIs."""
import hashlib,io,json,random,re,sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import fsspec
import pandas as pd
import pyarrow.parquet as pq
import soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'scripts'))
import prepare_asr_data as prep
SEED=20261114
SVQ_SHA='74f17ec92f0654860c160029d3542199626f63ef'
MUCS_SHA='3c66ee127a7b0e0a746d4df1002858567135edc1'
OUT=P/'data/next/dataset_replacement'
def remote_table(url,columns=None):
    with fsspec.open(url,'rb',block_size=2**20) as f:return pq.ParquetFile(f).read(columns=columns).to_pandas()
def finance_picks():
    d=pd.read_csv(P/'data/sources/svq_index_in.csv');used=set();texts=set()
    for name in ['data/asr_manifest.csv','data/next/asr_next_manifest.csv']:
        old=pd.read_csv(P/name,keep_default_na=False);used.update(old.source_ref.str.split('#').str[-1]);texts.update(' '.join(t.casefold().split()) for t in old.reference_transcript)
    patterns={'en_in':r'\b(?:currency|money|tax|credit|investment|insurance|bank|banking|financial|economy)\b',
              'hi_in':'बैंक|मुद्रा|रुपय|वित्त|ऋण|ब्याज',
              'te_in':'బ్యాంక|రూపాయ|కరెన్సీ|ఆర్థిక|వడ్డీ|డబ్బు|ఏటీఎం'}
    rng=random.Random(SEED);selected=[];speakers=Counter()
    for locale,pattern in patterns.items():
        pool=d[(d.locale==locale)&d.text.str.contains(pattern,case=False,regex=True)&~d.utt_id.isin(used)]
        candidates=[(rng.random(),r) for _,r in pool.iterrows() if ' '.join(r.text.casefold().split()) not in texts]
        envs=Counter()
        for i in range(4):
            candidates.sort(key=lambda item:(speakers[item[1].speaker_id],envs[item[1].environment],item[0]))
            if not candidates:raise ValueError('Not enough unused finance-related sentences')
            _,r=candidates.pop(0);key=' '.join(r.text.casefold().split());texts.add(key);speakers[r.speaker_id]+=1;envs[r.environment]+=1
            selected.append(dict(r,clip_id=f'DS-FIN-{locale[:2].upper()}-{i+1:02d}',language=locale.replace('_','-').replace('-in','-IN'),
                                 cohort='finance_related_questions',revision=SVQ_SHA,
                                 url=f'https://huggingface.co/datasets/google/svq/resolve/{SVQ_SHA}/1.0.0/audio/{r.file}'))
            candidates=[x for x in candidates if ' '.join(x[1].text.casefold().split()) not in texts]
    return selected
def code_picks():
    frames=[]
    for i in range(2):
        filename=f'data/test-{i:05d}-of-00002.parquet'
        url=f'https://huggingface.co/datasets/dianavdavidson/MUCS-Hinglish/resolve/{MUCS_SHA}/{filename}'
        metadata=remote_table(url,['segment_id','transcript','speaker_id','count_english_words','count_dev_words'])
        metadata['file']=filename;metadata['row']=range(len(metadata));metadata['url']=url;frames.append(metadata)
    d=pd.concat(frames);d=d[(d.count_english_words>=2)&(d.count_dev_words>=3)&d.transcript.str.split().str.len().between(8,30)]
    d=d.sample(frac=1,random_state=SEED);selected=[];groups=set()
    for _,r in d.iterrows():
        if r.speaker_id in groups:continue
        groups.add(r.speaker_id);selected.append(dict(r,clip_id=f'DS-CS-HI-{len(selected)+1:02d}',language='hi-IN,en-IN',
                                  cohort='technical_hindi_english_codeswitch',text=r.transcript,revision=MUCS_SHA))
        if len(selected)==12:break
    if len(selected)!=12:raise ValueError('Insufficient distinct MUCS source groups')
    return selected
def download_group(group):
    url=group[0]['url']
    with fsspec.open(url,'rb',block_size=2**20) as f:
        pf=pq.ParquetFile(f);bounds=[];start=0
        for i in range(pf.metadata.num_row_groups):
            size=pf.metadata.row_group(i).num_rows;bounds.append((i,start,start+size));start+=size
        for gi,lo,hi in bounds:
            wanted=[r for r in group if lo<=r['row']<hi]
            if not wanted:continue
            column='waveform' if wanted[0]['cohort']=='finance_related_questions' else 'audio'
            table=pf.read_row_group(gi,columns=[column]);values=table.column(column).to_pylist()
            for r in wanted:
                dest=OUT/(r['clip_id']+'.wav')
                if not dest.exists():prep.write_wav(dest,prep.load_mono(io.BytesIO(values[int(r['row'])-lo]['bytes'])),16000)
                print('Audio ready:',r['clip_id'],flush=True)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    selection=OUT/'selection.json'
    if not selection.exists():selection.write_text(json.dumps(finance_picks()+code_picks(),ensure_ascii=False,indent=2,default=str),encoding='utf8')
    picks=json.loads(selection.read_text(encoding='utf8'))
    missing=[r for r in picks if not (OUT/(r['clip_id']+'.wav')).exists()]
    groups=[[r for r in missing if r['url']==url] for url in sorted({r['url'] for r in missing})]
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(download_group,groups))
    rows=[]
    for r in picks:
        path=OUT/(r['clip_id']+'.wav');info=sf.info(path)
        if info.samplerate!=16000 or info.channels!=1 or info.duration<=0:raise ValueError('Invalid prepared audio')
        finance=r['cohort']=='finance_related_questions'
        rows.append(dict(clip_id=r['clip_id'],selected='true',category=r['cohort'],language=r['language'],speaker_id=r['speaker_id'],
            duration_s=round(info.duration,3),sample_rate_hz=16000,input_path=path.relative_to(P).as_posix(),
            input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),reference_transcript=r['text'],
            reference_status='dataset_reference_provisional',human_reference_verified='false',
            source_dataset='google/svq' if finance else 'MUCS 2021 / OpenSLR 104 (HF conversion)',
            source_ref=r['file']+'#'+str(r.get('utt_id') if finance else r['segment_id']),source_revision=r['revision'],
            source_url=r['url'],license_or_consent='CC-BY-4.0' if finance else 'CC-BY-SA-4.0 upstream; preserve upstream terms (mirror card says CC-BY-4.0)',
            expected_entities_json='{}',evaluation_group=str(r['speaker_id']),
            notes='Finance-related read question, not a customer transaction instruction' if finance else 'Hindi-English technical tutorial; source speaker IDs as provided, identity not independently verified',
            status='prepared_not_run'))
    pd.DataFrame(rows).to_csv(P/'data/next/asr_dataset_replacement.csv',index=False,encoding='utf-8-sig')
    summary={'mode':'public_datasets_only','clips':len(rows),'finance_related_questions':12,'hindi_english_codeswitch':12,
             'audio_seconds':round(sum(r['duration_s'] for r in rows),3),'human_recording_required':False,'paid_api_calls':0,
             'evaluation_status':'prepared_not_run','source_references':'provisional; not human verified',
             'not_covered':['scripted finance transactions','matched negation/self-correction/identifier scenarios','Telugu-English conversational codeswitch','live telephone network']}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
