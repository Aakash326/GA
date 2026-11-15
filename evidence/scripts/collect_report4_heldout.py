"""Bounded optional Report-4 follow-ups; new human ratings remain uncollected."""
import argparse,hashlib,json,os,random,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'scripts'))
from analyze_report4 import read,logs,merge,dump
D=P/'data/report4';O=P/'results/report4_quality'


def run():
    import gnani_api as g
    g.ATTEMPTS=O/'attempts.jsonl';g.RAW=O/'raw';g.TTS_AUDIO=O/'audio'
    prior=P/'results/reconciliation/user_reported_spend.json'
    if not os.getenv('GNANI_SPENT_TO_DATE_INR') and prior.exists():os.environ['GNANI_SPENT_TO_DATE_INR']=str(json.loads(prior.read_text())['amount_inr'])
    frozen=D/'frozen_policy.json';policy=json.loads(frozen.read_text(encoding='utf8'));policy_hash=hashlib.sha256(frozen.read_bytes()).hexdigest()
    def cached(cid):return [r for r in merge(logs(O/'attempts.jsonl')) if r['case_id']==cid]
    asr=read(D/'asr_heldout_manifest.csv');random.Random(4104).shuffle(asr)
    for i,row in enumerate(asr):
        if row['frozen_vocabulary_sha256']!=policy_hash:raise ValueError('Frozen vocabulary mismatch')
        if hashlib.sha256((P/row['input_path']).read_bytes()).hexdigest()!=row['input_sha256']:raise ValueError('Changed held-out audio')
        order=['baseline','hinted'] if i%2 else ['hinted','baseline']
        for condition in order:
            cid=row['clip_id']+'-'+condition
            if cached(cid):continue
            result=g.transcribe(cid,row['input_path'],'en-IN',run_tag='report4_heldout',model='prisma-v3.0',fmt='transcribe',
                                extra={'keyterms':json.dumps(policy['keyterms'])} if condition=='hinted' else None,live=True)
            print('Held-out ASR',cid,result.get('http_status'),result.get('ok'),flush=True);time.sleep(.2)
    tts=read(D/'tts_rewrite_manifest.csv')+read(D/'tts_quality_manifest.csv');random.Random(4104).shuffle(tts)
    for row in tts:
        if cached(row['case_id']):continue
        if hashlib.sha256(row['text'].encode()).hexdigest()!=row['text_sha256']:raise ValueError('Frozen prompt mismatch')
        result=g.synthesize(row['case_id'],row['text'],row['language'],run_tag='report4_quality',model=row['model'],voice=row['voice'],speed=1.,sample_rate=24000,live=True)
        print('Prepared listening audio',row['case_id'],result.get('http_status'),result.get('ok'),flush=True);time.sleep(.2)
    dump(O/'collection_scope.json',dict(asr_clips=len(asr),asr_conditions=['baseline','hinted'],tts_cases=len(tts),
         naturalness_human_ratings_collected=0,critical_target_human_ratings_collected=0,policy_sha256=policy_hash,
         limitations='Source transcripts are dataset labels; new TTS quality and rewrite outcomes remain unscored until independent human review.'))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true')
    if not ap.parse_args().live:raise SystemExit('No calls sent; use --live for the bounded frozen manifests')
    run()
