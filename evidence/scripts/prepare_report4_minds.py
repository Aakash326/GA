"""Prepare only 15 unused public banking utterances; keep the frozen vocabulary."""
import hashlib,io,json,random,re,sys
from pathlib import Path
import requests,soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'scripts'))
from prepare_report4 import D,freeze
from analyze_report4 import read,write,dump


def prepare():
    policy=freeze();manifest=D/'asr_heldout_manifest.csv'
    if manifest.exists():return read(manifest)
    session=requests.Session()
    info=session.get('https://huggingface.co/api/datasets/PolyAI/minds14',timeout=30);info.raise_for_status();revision=info.json()['sha']
    terms=policy['keyterms'];pattern=re.compile(r'\b(?:'+'|'.join(re.escape(t) for t in terms)+r')\b',re.I)
    candidates=[]
    for offset in [0,100,200]:
        result=session.get('https://datasets-server.huggingface.co/rows',params=dict(dataset='PolyAI/minds14',config='en-US',split='train',offset=offset,length=100),timeout=45)
        result.raise_for_status()
        for item in result.json()['rows']:
            r=item['row'];text=r['transcription']
            if pattern.search(text) and 4<=len(text.split())<=36:candidates.append(dict(index=item['row_idx'],path=r['path'],text=text,audio=r['audio']))
        if len(candidates)>=30:break
    random.Random(4104).shuffle(candidates);selected=[];texts=set()
    for row in candidates:
        norm=' '.join(row['text'].casefold().split())
        if norm in texts:continue
        texts.add(norm);selected.append(row)
        if len(selected)==15:break
    if len(selected)!=15:raise ValueError('Insufficient banking references under frozen vocabulary')
    frozen=[{k:v for k,v in r.items() if k!='audio'} for r in selected]
    path=D/'asr_selection.json'
    if path.exists() and json.loads(path.read_text())!=frozen:raise ValueError('Selection changed')
    dump(path,frozen)
    dump(D/'asr_source_notice.json',dict(dataset='PolyAI/minds14',revision=revision,source_url='https://huggingface.co/datasets/PolyAI/minds14',license='CC-BY-4.0',
         source_locale='en-US',api_language_hint='en-IN',speaker_identity='Not provided; distinct speakers cannot be established',
         reason='The existing SVQ inventory had fewer than 15 unused clean domain utterances under the frozen vocabulary. Vocabulary unchanged; no new predictions seen before selection.',
         scope='15 targeted public banking-intent recordings, no private calls; separate held-out cohort.'))
    rows=[]
    for i,row in enumerate(selected,1):
        audio=row['audio'];url=audio[0]['src'] if isinstance(audio,list) else audio['src']
        response=session.get(url,timeout=45);response.raise_for_status()
        x,rate=sf.read(io.BytesIO(response.content),dtype='int16',always_2d=True)
        if len(x)/rate>30:raise ValueError('Held-out clip exceeds REST 30-second limit')
        if x.shape[1]!=1:raise ValueError('Unexpected multi-channel source')
        dest=D/'audio'/f'R4-ASR-{i:02d}.wav';dest.parent.mkdir(exist_ok=True)
        sf.write(dest,x,rate,subtype='PCM_16')
        rows.append(dict(clip_id=f'R4-ASR-{i:02d}',input_path=dest.relative_to(P).as_posix(),input_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
                         language='en-IN',source_locale='en-US',duration_s=len(x)/rate,sample_rate_hz=rate,
                         source_dataset='PolyAI/minds14',source_revision=revision,source_ref=row['path'],source_row_index=row['index'],
                         speaker_id='not supplied',reference_transcript=row['text'],reference_basis='original dataset transcription; not independently human verified',license='CC-BY-4.0',
                         target_terms_json=json.dumps(sorted(set(m.group(0).casefold() for m in pattern.finditer(row['text'])))),
                         frozen_vocabulary_sha256=hashlib.sha256((D/'frozen_policy.json').read_bytes()).hexdigest(),status='prepared_not_run'))
        print('Public banking audio prepared',i,'/ 15',flush=True)
    old_hashes={r.get('input_sha256') for name in ['data/asr_manifest.csv','data/next/asr_next_manifest.csv','data/next/asr_dataset_replacement.csv'] for r in read(P/name)}
    if any(r['input_sha256'] in old_hashes for r in rows):raise ValueError('Held-out audio overlap')
    write(manifest,rows);return rows


if __name__=='__main__':prepare()
