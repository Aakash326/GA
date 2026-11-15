"""Provisional audio verification. No Gnani synthesis/transcription calls. Human status is never changed."""
import argparse, csv, hashlib, json, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
import gemini_judge as judge

def read(path):
    with (P/path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');args=ap.parse_args()
    out=P/'results/verification';out.mkdir(exist_ok=True);judge.RAW=out/'raw'
    jobs=[]
    for manifest,audio,cohort in [('data/tts_cases.csv','results/tts_audio','baseline'),
                                 ('data/next/tts_next_cases.csv','results/next/audio','next')]:
        for r in read(manifest):jobs.append((cohort,r,P/audio/(r['case_id']+'.wav')))
    def audit(job):
        cohort,r,audio=job;targets=json.loads(r['expected_targets_json']);variants=json.loads(r['accepted_variants_json'])
        prompt=('Assess this audio as a strict speech evaluator. This is provisional automated assessment, not human verification. '
                'First write exactly what is audible, including signs, every digit, negations and uncertain words. '
                'Then compare each target below to the SOUND. Never infer a missing minus, zero, NOT, or digit from the supplied text. '
                'For teen/ty ambiguity mark ambiguous rather than guessing. A changed value, lost zero/sign or missing word is wrong. '
                'Also flag wording or target specifications that a native listener should review. '
                f'Language: {r["language"]}. Input text: {r["input_text"]}. Targets: {json.dumps(targets,ensure_ascii=False)}. '
                f'Accepted/rejected readings: {json.dumps(variants,ensure_ascii=False)}. '
                'JSON only: {"heard":str,"target_spec_issues":[str],"targets":[{"id":str,"result":"correct"|"wrong"|"ambiguous","heard":str}]}')
        rep=judge._ask('strict_audio_audit',cohort+'-'+r['case_id'],audio,prompt,args.live)
        reply=rep['reply'];expected={t['id'] for t in targets};got=[t['id'] for t in reply.get('targets',[])]
        if len(got)!=len(expected) or set(got)!=expected:raise ValueError('Target coverage mismatch '+r['case_id'])
        if any(t['result'] not in ['correct','wrong','ambiguous'] for t in reply['targets']):raise ValueError('Invalid verdict')
        return [dict(cohort=cohort,case_id=r['case_id'],target_id=t['id'],language=r['language'],result=t['result'],
                     heard=t.get('heard',''),assessor='audio_llm_provisional',model=rep['model'],human_verified=False,
                     input_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),fingerprint=rep['fingerprint'],
                     target_spec_issues=json.dumps(reply.get('target_spec_issues',[]),ensure_ascii=False)) for t in reply['targets']]
    rows=[];errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(audit,job):job for job in jobs}
        for future in as_completed(futures):
            job=futures[future]
            try:rows.extend(future.result())
            except Exception as e:errors.append({'case_id':job[1]['case_id'],'error':str(e)[:300]})
            print(f'Audio audit {len(rows)} targets; {len(errors)} errors',flush=True)
    rows.sort(key=lambda r:(r['cohort'],r['case_id'],r['target_id']))
    if rows:
        with (out/'tts_llm_verification.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # Reuse the existing blind audio transcriptions for disputed SVQ references; never silently replace truth.
    asr=[]
    for r in read('data/next/asr_next_manifest.csv'):
        files=list((P/'results/next/judge/asr_blind').glob(r['clip_id']+'__*.json'))
        if not files:continue
        cached=json.loads(files[0].read_text(encoding='utf8'));proposal=cached['reply'].get('transcript','')
        asr.append(dict(clip_id=r['clip_id'],reference_dataset=r['reference_transcript'],llm_proposed_reference=proposal,
                        reference_status='llm_provisional_human_pending',model=cached['model'],human_verified=False))
    if asr:
        with (out/'asr_llm_reference_review.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(asr[0]));w.writeheader();w.writerows(asr)
    counts={}
    for r in rows:
        key=r['cohort']+':'+r['result'];counts[key]=counts.get(key,0)+1
    summary={'status':'complete' if not errors and len({(r['cohort'],r['case_id']) for r in rows})==len(jobs) else 'incomplete',
             'model':judge.MODEL,'tts_prompts_expected':len(jobs),'tts_targets_assessed':len(rows),'verdict_counts':counts,
             'asr_cached_audio_transcriptions_reviewed':len(asr),'human_verification':'pending',
             'limitations':'Same model family as earlier judge; second automated pass, not independent human validation.',
             'errors':errors,'gnani_calls':0}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary),flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
