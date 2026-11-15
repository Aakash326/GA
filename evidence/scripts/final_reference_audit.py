"""Blind audio transcription then reference adjudication for the new 24 and original 35 disputed inputs.

Never shows Gnani hypotheses to the judge; never marks machine assessments human-verified.
"""
import argparse,csv,hashlib,json,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
import gemini_judge as judge
def read(name):
    with (P/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');args=ap.parse_args()
    out=P/'results/verification';judge.RAW=out/'final_reference_raw';jobs=[]
    for row in read('data/next/asr_dataset_replacement.csv'):jobs.append(('dataset_replacement',row))
    for row in read('data/next/asr_next_manifest.csv'):
        files=list((P/'results/next/judge/asr_verify').glob(row['clip_id']+'__*.json'))
        if len(files)!=1:raise ValueError('Original reference check missing/nonunique')
        if not json.loads(files[0].read_text(encoding='utf8'))['reply']['matches']:jobs.append(('original_dispute',row))
    assert len(jobs)==59
    def audit(job):
        cohort,r=job;cid=r['clip_id'];audio=P/r['input_path']
        digest=hashlib.sha256(audio.read_bytes()).hexdigest()
        if digest!=r['input_sha256']:raise ValueError('Input changed since manifest')
        blind=judge.transcribe_blind('final-'+cid,audio,r['language'],live=args.live)
        transcript=blind['reply'].get('transcript','')
        prompt=(f'Listen carefully to this original recording ({r["language"]}). You are adjudicating an ASR reference, '
                'not evaluating an ASR prediction. No system transcript is provided. '
                f'Dataset candidate: {r["reference_transcript"]}\nEarlier blind transcription: {transcript}\n'
                'Decide from the AUDIO whether the dataset candidate is faithful. Ignore punctuation, equivalent digit/number-word '
                'forms and equivalent native/Latin transliterations. Never ignore a different value, proper name, missing or extra spoken word. '
                'Return the dataset candidate unchanged when it is faithful. Otherwise supply an exact corrected transcript, including '
                'false starts and repetitions, native scripts for native words and Latin letters for English words. Use digits for quantities. '
                'Do not repair grammar or guess names. If any content remains uncertain, mark confidence medium/low and list uncertainty. '
                'A high-confidence correction must have no unresolved words. JSON only: '
                '{"dataset_matches":bool,"selected_reference":str,"confidence":"high"|"medium"|"low",'
                '"unclear":[str],"reason":str}.')
        result=judge._ask('reference_adjudication','final-'+cid,audio,prompt,args.live)
        reply=result['reply']
        if not isinstance(reply.get('dataset_matches'),bool) or reply.get('confidence') not in ['high','medium','low']:
            raise ValueError('Invalid reference verdict')
        chosen=r['reference_transcript'] if reply['dataset_matches'] else reply.get('selected_reference','')
        accepted=bool(isinstance(chosen,str) and chosen.strip() and reply['confidence']=='high' and not reply.get('unclear'))
        return dict(clip_id=cid,cohort=cohort,language=r['language'],input_sha256=digest,source_reference=r['reference_transcript'],
                    blind_transcript=transcript,resolved_reference=chosen if accepted else '',
                    proposed_reference=chosen,resolution_status=('llm_confirmed_dataset' if reply['dataset_matches'] else 'llm_corrected_reference') if accepted else 'unresolved',
                    confidence=reply['confidence'],unclear=json.dumps(reply.get('unclear',[]),ensure_ascii=False),
                    reason=reply.get('reason',''),assessor='audio_llm_provisional',human_verified=False,
                    model=result['model'],fingerprint=result['fingerprint'])
    rows=[];errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(audit,job):job for job in jobs}
        for future in as_completed(futures):
            try:rows.append(future.result())
            except Exception as e:errors.append({'clip_id':futures[future][1]['clip_id'],'error':str(e)[:300]})
            print(f'Reference audio audit {len(rows)}/{len(jobs)}; errors {len(errors)}',flush=True)
    rows.sort(key=lambda r:(r['cohort'],r['clip_id']))
    if rows:
        with (out/'final_reference_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={'expected':len(jobs),'assessed':len(rows),'resolved_provisionally':sum(r['resolution_status']!='unresolved' for r in rows),
             'unresolved':sum(r['resolution_status']=='unresolved' for r in rows),'errors':errors,
             'cohorts':{name:{'assessed':sum(r['cohort']==name for r in rows),'resolved':sum(r['cohort']==name and r['resolution_status']!='unresolved' for r in rows)} for name in ['dataset_replacement','original_dispute']},
             'human_verification':False,'independence_limit':'Same Gemini model family as earlier judge; provisional audio adjudication, not independent human truth.'}
    (out/'final_reference_audit_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
