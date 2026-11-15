"""Prepare review pages, import owner decisions, and reconcile dashboard evidence. No paid API calls."""
import argparse, csv, hashlib, json, math, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
import soundfile as sf

P=Path(__file__).resolve().parents[1]
def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,rows,fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(rows[0]);tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    tmp.replace(path)
def now():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def yes(value):return str(value).lower()=='true'
def merge(existing,rows,key):
    result={r[key]:r for r in existing}
    result.update({r[key]:r for r in rows});return list(result.values())
def inside(root,name):
    path=(Path(root)/name).resolve()
    if not path.is_relative_to(Path(root).resolve()):raise ValueError('File must be within the selected audio directory')
    return path

def prepare():
    folder=P/'data/listening';folder.mkdir(exist_ok=True)
    manifests=read(P/'data/next/asr_next_manifest.csv');disputed=[]
    final_path=P/'results/verification/final_reference_audit.csv'
    final={r['clip_id']:r for r in read(final_path)} if final_path.exists() else {}
    for r in manifests:
        hits=list((P/'results/next/judge/asr_verify').glob(r['clip_id']+'__*.json'))
        if len(hits)!=1:raise ValueError('Reference cache is missing or non-unique: '+r['clip_id'])
        verdict=json.loads(hits[0].read_text(encoding='utf8'))['reply']
        if verdict.get('matches'):continue
        blind=list((P/'results/next/judge/asr_blind').glob(r['clip_id']+'__*.json'))
        proposal=json.loads(blind[0].read_text(encoding='utf8'))['reply'].get('transcript','') if len(blind)==1 else ''
        if r['clip_id'] in final and final[r['clip_id']]['resolved_reference']:
            proposal=final[r['clip_id']]['resolved_reference']
        disputed.append({**r,'proposal':proposal,'differences':verdict.get('differences',[]),
                         'src':'../../'+r['input_path']})
    if len(disputed)!=35:raise ValueError(f'Expected 35 original disputes, got {len(disputed)}')
    replacement=P/'data/next/asr_dataset_replacement.csv'
    datasets=read(replacement) if replacement.exists() else []
    result_file=P/'results/next/dataset_replacement_verified_results.csv'
    if datasets and result_file.exists():
        checked={r['clip_id']:r for r in read(result_file)}
        for row in datasets:
            if row['clip_id'] in checked:
                row['status']='API '+checked[row['clip_id']]['status']+'; reference '+checked[row['clip_id']]['reference_status']
    queue=[] if datasets else read(P/'data/next/asr_recording_queue.csv')
    scenarios=[
        dict(scenario_id='CALL01',instruction='English FAQ and normal goodbye; verify both call legs and response timing.',kind='normal'),
        dict(scenario_id='CALL02',instruction='Hindi then English; change language mid-call. Verify transcript and spoken response.',kind='code_switch'),
        dict(scenario_id='CALL03',instruction='Ask for a long explanation, then interrupt after about one second: "Stop, I meant tomorrow". Old speech must stop and the corrected reply must not contain old audio.',kind='barge_in'),
        dict(scenario_id='CALL04',instruction='Interrupt twice rapidly, then say a clear new request. Check for stuck TTS, stale words and overlapping responses.',kind='double_barge_in'),
        dict(scenario_id='CALL05',instruction='Say a fictional amount, ID and correction (fifteen, not fifty). Verify the exact values on both legs.',kind='critical_values'),
        dict(scenario_id='CALL06',instruction='Wait silently, speak again, then hang up during a response. Check reconnect and socket cleanup.',kind='lifecycle')]
    template=(P/'scripts/remaining_workflow.html').read_text(encoding='utf8')
    data={'recordings':queue,'datasets':datasets,'references':disputed,'calls':scenarios}
    html=template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
    (folder/'remaining_verifications.html').write_text(html,encoding='utf8')
    write(P/'data/next/disputed_asr_review_template.csv',[
        dict(clip_id=r['clip_id'],audio_sha256=r['input_sha256'],listener_id='',reviewer_language_confirmed='false',
             decision='',reference='',comment='') for r in disputed])
    write(P/'data/next/recording_import_template.csv',[
        dict(queue_id=r['clip_id'],speaker_id='',audio_filename='',consent_confirmed='false',
             reference_verified='false',reference='',expected_entities_json='{}') for r in queue],fields=['queue_id','speaker_id','audio_filename','consent_confirmed','reference_verified','reference','expected_entities_json'])
    write(P/'data/next/call_scenarios.csv',scenarios)
    print(json.dumps({'dataset_replacement_clips':len(datasets),'recording_scripts':len(queue),'disputed_references':len(disputed),'call_scenarios':len(scenarios),
                     'page':'data/listening/remaining_verifications.html'}))
    status()

def import_recordings(csv_path,audio_dir,apply=False):
    specs={r['clip_id']:r for r in read(P/'data/next/asr_recording_queue.csv')}
    rows=[];copies=[]
    for r in read(csv_path):
        if not r.get('audio_filename'):continue
        if r['queue_id'] not in specs:raise ValueError('Unknown recording script')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',r['speaker_id']):raise ValueError('Speaker ID must use letters, digits, underscore or hyphen')
        if not yes(r['consent_confirmed']) or not yes(r['reference_verified']) or not r['reference'].strip():
            raise ValueError('Confirm consent and the actual spoken reference before import')
        entities=json.loads(r.get('expected_entities_json') or '{}')
        if not isinstance(entities,dict):raise ValueError('Expected entities must be a JSON object')
        source=inside(audio_dir,r['audio_filename']);audio,rate=sf.read(source,always_2d=True)
        if rate!=16000 or audio.shape[1]!=1 or not 0.25<=len(audio)/rate<=60:
            raise ValueError('Recordings must be 16 kHz mono, 0.25–60 seconds: '+source.name)
        if abs(audio).max()<0.001:raise ValueError('Silent recording: '+source.name)
        cid='REC-'+r['queue_id']+'__'+r['speaker_id'];dest=P/'data/next/recordings'/f'{cid}.wav'
        digest=sha(source)
        if dest.exists() and sha(dest)!=digest:raise ValueError('Audio ID already exists with different content: '+cid)
        spec=specs[r['queue_id']]
        rows.append(dict(clip_id=cid,queue_id=r['queue_id'],selected='true',category=spec['category'],language=spec['language'],
            speaker_id=r['speaker_id'],duration_s=round(len(audio)/rate,3),sample_rate_hz=rate,input_path=dest.relative_to(P).as_posix(),
            input_sha256=digest,reference_transcript=r['reference'].strip(),reference_status='human_verified',
            human_reference_verified='true',consent_confirmed='true',expected_entities_json=json.dumps(entities,ensure_ascii=False),
            source_dataset='consented_owner_recording',license_or_consent='owner-recorded explicit consent',imported_at=now()))
        copies.append((source,dest))
    if len({r['clip_id'] for r in rows})!=len(rows):raise ValueError('Duplicate recording IDs in export')
    if apply and rows:
        for source,dest in copies:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest) if source.resolve()!=dest.resolve() else None
        path=P/'data/next/asr_recorded_manifest.csv'
        write(path,merge(read(path) if path.exists() else [],rows,'clip_id'))
    print(json.dumps({'valid_recordings':len(rows),'applied':apply}))
    return rows

def import_references(csv_path,apply=False):
    manifest={r['clip_id']:r for r in read(P/'data/next/asr_next_manifest.csv')}
    allowed={r['clip_id'] for r in read(P/'data/next/disputed_asr_review_template.csv')};rows=[]
    for r in read(csv_path):
        if not r.get('decision') or r['decision']=='pending':continue
        cid=r['clip_id']
        if cid not in allowed:raise ValueError('Not an original disputed reference: '+cid)
        if not r.get('listener_id','').strip() or not yes(r.get('reviewer_language_confirmed')):raise ValueError('Listener and language confirmation required')
        if r['audio_sha256']!=manifest[cid]['input_sha256'] or sha(P/manifest[cid]['input_path'])!=r['audio_sha256']:
            raise ValueError('Audio changed since review: '+cid)
        if r['decision'] not in ['accept_dataset','accept_proposal','corrected','unintelligible']:raise ValueError('Invalid reference decision')
        ref=manifest[cid]['reference_transcript'] if r['decision']=='accept_dataset' else r.get('reference','').strip()
        if r['decision']!='unintelligible' and not ref:raise ValueError('A spoken reference is required')
        rows.append(dict(clip_id=cid,listener_id=r['listener_id'].strip(),decision=r['decision'],reference=ref,
             human_reference_verified=str(r['decision']!='unintelligible').lower(),audio_sha256=r['audio_sha256'],
             comment=r.get('comment',''),blind_transcription=r.get('blind_transcription',''),reviewed_at=now()))
    if len({r['clip_id'] for r in rows})!=len(rows):raise ValueError('Duplicate decisions')
    if apply and rows:
        path=P/'results/verification/asr_human_reference_reviews.csv'
        write(path,merge(read(path) if path.exists() else [],rows,'clip_id'))
    print(json.dumps({'valid_reference_decisions':len(rows),'applied':apply}));return rows

def reconcile(csv_path,apply=False):
    rows=read(csv_path);out=[]
    for r in rows:
        opening,current,added=[float(r[k]) for k in ['opening_balance_inr','current_balance_inr','credits_added_inr']]
        if any(not math.isfinite(x) or x<0 for x in [opening,current,added]):raise ValueError('Balances must be finite and non-negative')
        captured=datetime.fromisoformat(r['captured_at_utc'].replace('Z','+00:00'))
        if captured.tzinfo is None:raise ValueError('Snapshot needs a timezone')
        if not r.get('evidence_note','').strip():raise ValueError('Enter the dashboard period/account or screenshot reference')
        spent=round(opening+added-current,4)
        if spent<0:raise ValueError('Negative charges: verify opening balance and credit additions')
        if r['provider'] not in ['Gnani','Gemini','Exotel']:raise ValueError('Unknown provider')
        out.append({**r,'observed_spend_inr':spent,'captured_at_utc':captured.isoformat()})
    if apply:
        folder=P/'results/reconciliation';folder.mkdir(parents=True,exist_ok=True)
        for r in out:
            name=r['provider'].lower();path=folder/(name+'_snapshots.csv')
            old=read(path) if path.exists() else [];old.append(r);write(path,old)
            # This period must begin before the first evaluation call; the user explicitly confirms that scope.
            if name=='gnani' and yes(r.get('covers_all_evaluation_usage')):
                (folder/'gnani_latest.json').write_text(json.dumps(r,indent=2))
    print(json.dumps({'snapshots':out,'applied':apply}));return out

def import_call_reviews(csv_path,apply=False):
    output=[];destinations=[]
    for r in read(csv_path):
        if r.get('result') not in ['pass','fail','cannot_judge']:continue
        folder=inside(P/'results/next/call',r['call_folder'])
        meta=json.loads((folder/'call_metadata.json').read_text())
        if r['scenario_id']!=meta['scenario_id']:raise ValueError('Review scenario does not match call metadata')
        if not r.get('listener_id','').strip():raise ValueError('Listener ID required')
        if r['scenario_id'] in ['CALL03','CALL04'] and r['result']=='pass':
            if not all(yes(r[k]) for k in ['old_audio_stopped','correct_new_reply','no_stale_audio']):
                raise ValueError('A passing barge-in review requires all three observations')
        if r.get('response_heard_ms'):
            ms=float(r['response_heard_ms'])
            if not math.isfinite(ms) or ms<0:raise ValueError('Invalid caller-observed latency')
        reviewed={**r,'reviewed_at':now(),'caller':meta['caller']}
        destinations.append(folder/'human_call_review.json');output.append(reviewed)
    if apply:
        for path,reviewed in zip(destinations,output):path.write_text(json.dumps(reviewed,indent=2))
    print(json.dumps({'valid_call_reviews':len(output),'applied':apply}));return output

def call_report():
    rows=[]
    for f in sorted((P/'results/next/call').glob('*/call_metadata.json')):
        meta=json.loads(f.read_text());events=f.parent/'events.jsonl'
        ev=[json.loads(l) for l in events.read_text().splitlines()] if events.exists() else []
        usage=f.parent/'usage.jsonl';units=[json.loads(l) for l in usage.read_text().splitlines()] if usage.exists() else []
        reviews=f.parent/'human_call_review.json';review=json.loads(reviews.read_text()) if reviews.exists() else {}
        rows.append(dict(call_id=meta['call_id'],scenario_id=meta.get('scenario_id',''),caller=meta['caller'],
            interruptions=sum(e['event']=='interruption' for e in ev),tts_cancelled=sum(e['event']=='tts_cancelled' for e in ev),
            asr_seconds=sum(e.get('seconds',0) for e in units if e['kind']=='asr'),
            tts_characters=sum(e.get('characters',0) for e in units if e['kind']=='tts'),
            human_result=review.get('result','pending'),folder=f.parent.relative_to(P).as_posix()))
    if rows:write(P/'results/verification/live_call_evidence.csv',rows)
    print(json.dumps({'instrumented_calls':len(rows),'human_verified':sum(r['human_result'] in ['pass','fail'] for r in rows)}))
    return rows

def status():
    recorded=P/'data/next/asr_recorded_manifest.csv';reviews=P/'results/verification/asr_human_reference_reviews.csv'
    rr=read(recorded) if recorded.exists() else [];ar=read(reviews) if reviews.exists() else []
    snapshot=P/'results/reconciliation/gnani_latest.json'
    replacement=P/'data/next/asr_dataset_replacement.csv'
    dataset_rows=read(replacement) if replacement.exists() else []
    value={'recording_scripts':0 if dataset_rows else 24,'dataset_replacement_clips':len(dataset_rows),'custom_recording_required':not bool(dataset_rows),'dataset_evaluation_summary_available':(P/'results/next/dataset_replacement_verified_summary.json').exists(),'recordings_imported':len(rr),'scripts_recorded':len({r['queue_id'] for r in rr}),
           'original_asr_disputes':35,'human_reference_decisions':len(ar),
           'human_approved_references':sum(yes(r['human_reference_verified']) for r in ar),
           'gnani_dashboard_reconciled':snapshot.exists(),
           'recording_and_review_tools':'implemented','real_call_completion':'outside dataset-only scope; optional' if dataset_rows else 'requires real call evidence'}
    audit=P/'results/verification/final_reference_audit_summary.json'
    if audit.exists():
        reviewed=json.loads(audit.read_text())
        value['asr_disputes_llm_adjudicated']=reviewed['cohorts']['original_dispute']['resolved']
        value['reference_assessment']='provisional audio-LLM; human decisions tracked separately'
    run=P/'results/next/dataset_replacement_verified_summary.json'
    if run.exists():value['dataset_evaluation']=json.loads(run.read_text())['evaluation_status']
    n1=P/'results/verification/n1_review_import.json'
    if n1.exists():
        review=json.loads(n1.read_text())
        value['tts_priority_review']={k:review[k] for k in ['status','selected_clips','fully_marked_clips','human_marked_targets','pending_targets']}
    dest=P/'results/verification/remaining_status.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(value,indent=2))
    print(json.dumps(value));return value

def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare');sub.add_parser('status');sub.add_parser('call-report')
    for cmd in ['import-recordings','import-references','import-call-reviews','reconcile']:
        x=sub.add_parser(cmd);x.add_argument('csv');x.add_argument('--apply',action='store_true')
        if cmd=='import-recordings':x.add_argument('--audio-dir',required=True)
    args=ap.parse_args()
    if args.command=='prepare':prepare()
    elif args.command=='status':status()
    elif args.command=='call-report':call_report()
    elif args.command=='import-recordings':import_recordings(args.csv,args.audio_dir,args.apply);status()
    elif args.command=='import-references':import_references(args.csv,args.apply);status()
    elif args.command=='import-call-reviews':import_call_reviews(args.csv,args.apply);call_report();status()
    elif args.command=='reconcile':reconcile(args.csv,args.apply);status()
if __name__=='__main__':main()
