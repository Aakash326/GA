"""Build an interview submission; private administration files remain in the working project."""
import argparse,csv,hashlib,json,re,shutil,zipfile
from pathlib import Path
from submission_privacy import excluded,csv_payload,private_json,private_row,secrets_from_env,check_secrets
P=Path(__file__).resolve().parents[1]
SKIP={'.venv','.git','__pycache__','cache','before_expansion','before_followup_fixes'}
ROOT_DOCS={'README.md','DATASETS.md','TESTING_STAGES.md','METHODS.md','IMPROVEMENTS.md','VERIFICATION.md','TIMBRE_FOLLOWUP.md','REPORT4_IMPLEMENTATION.md'}
INTERNAL={'budget_reservations.json','remaining_status.json','workflow_implementation.json',
          'dataset_replacement_validation.json','dataset_only_policy.json','cost_coverage.json'}
def selected(path):
    rel=path.relative_to(P);parts=rel.parts
    if any(x in SKIP for x in parts) or path.name in INTERNAL:return False
    if excluded(rel.as_posix()):return False
    if rel.as_posix() in ['tests/test_restricted_exploration.py','results/summary_metrics.json','results/next/summary_next.json','results/expanded_dataset_summary.json']:return False
    if path.name.startswith('call_') and path.suffix=='.csv':return False
    if parts[:2]==('results','reconciliation'):return False
    if parts[:2]==('results','reproduced'):return False
    if parts[:2]==('results','charts'):return False
    if path.name in ['gnani_evaluation.ipynb','gnani_next_stages.ipynb']:return False
    if path.name in ['.env','submission_manifest.json']:return False
    if path.suffix in ['.pyc','.bin','.log','.pid','.lock','.docx']:return False
    if path.suffix=='.json':
        try:
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            if isinstance(data,dict) and private_row(data):return False
        except (ValueError,UnicodeError):pass
    if path.suffix=='.md':
        if len(parts)==1:return path.name in ROOT_DOCS
        if parts[0]=='results':return False
    return True
def redact_json(data):
    if isinstance(data,dict):return {k:redact_json(v) for k,v in data.items() if k not in ['cost','current_cost','cost_inr','starting_spend_inr','estimated_gnani_cumulative_inr','budget_ceiling_inr']}
    if isinstance(data,list):return [redact_json(x) for x in data]
    return data
def notebook(data):
    cells=[{'cell_type':'markdown','metadata':{},'source':['Supporting exploratory analysis. The submission report uses the public-dataset ASR and human-reviewed TTS profile in run_evaluation.py; see README.md. These notebook outputs are cleared in the release.']}]
    for cell in data['cells']:
        source=''.join(cell.get('source',[]))
        if cell['cell_type']=='markdown':
            lines=[line for line in source.splitlines(keepends=True) if not re.search(r'budget|owner.reported|starting.spend|spent.so.far',line,re.I)]
            source=''.join(lines).replace('project owner','project reviewer')
            source=re.sub(r'audio[- ]LLM', 'automated audio assessment', source, flags=re.I)
            source=re.sub(r'\bLLM\b', 'automated assessment', source)
            if not source.strip():continue
            cell['source']=source.splitlines(keepends=True)
        if cell['cell_type']=='code':
            cell['outputs']=[];cell['execution_count']=None
        for output in cell.get('outputs',[]):
            if output.get('output_type')!='stream':continue
            text=output.get('text',[]);text=''.join(text) if isinstance(text,list) else text
            clean=[]
            for line in text.splitlines(keepends=True):
                if line.lstrip().startswith('{'):
                    try:
                        value=json.loads(line)
                        if isinstance(value,dict):line=json.dumps(redact_json(value),ensure_ascii=False)+'\n'
                    except json.JSONDecodeError:pass
                if re.search(r'owner.reported|starting.spend|cumulative.*spend|budget ceiling',line,re.I):continue
                clean.append(line.replace('project owner','project reviewer'))
            output['text']=clean
        cells.append(cell)
    data['cells']=cells;return data
def payload(path):
    raw=path.read_bytes();rel=path.relative_to(P).as_posix()
    if path.suffix=='.csv':return csv_payload(raw,rel,PRIVATE_COUNTS)
    if path.suffix=='.jsonl':
        rows=[private_json(json.loads(line)) for line in raw.decode('utf8').splitlines() if line.strip()]
        return ('\n'.join(json.dumps(row,ensure_ascii=False) for row in rows if row is not None)+'\n').encode('utf8')
    if path.suffix=='.ipynb':
        if path.name=='gnani_submission.ipynb':return raw
        return (json.dumps(notebook(json.loads(raw.decode('utf8'))),ensure_ascii=False,indent=1)+'\n').encode('utf8')
    if rel=='results/next/summary_next.json':return (json.dumps(redact_json(json.loads(raw.decode('utf8'))),ensure_ascii=False,indent=1)+'\n').encode('utf8')
    if rel=='results/verification/n1_review_import.json':
        data=json.loads(raw.decode('utf8'));data['listener_identity']='Human reviewer; listener ID and language metadata were not supplied in the export.'
        return (json.dumps(data,indent=2)+'\n').encode('utf8')
    if path.suffix=='.json':
        try:
            original=json.loads(raw.decode('utf-8-sig'));clean=private_json(original)
            if clean==original:return raw  # Preserve hashes of public frozen protocols and raw API results.
            return (json.dumps(clean,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        except (ValueError,UnicodeError):return raw  # HTTP error bodies can be plain text despite the saved suffix.
    return raw
def main():
    global PRIVATE_COUNTS
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=P.parent/'gnani_evaluation_submission.zip');args=ap.parse_args()
    with (P/'results/asr_results_labelled.csv').open(encoding='utf-8-sig',newline='') as f:PRIVATE_COUNTS={r['clip_id']:r for r in csv.DictReader(f) if r['clip_id'].startswith('CALL-')}
    private_hashes=set()
    for row in PRIVATE_COUNTS.values():
        path=P/row['input_path']
        if path.is_file():private_hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
    files=[f for f in P.rglob('*') if f.is_file() and selected(f) and not (f.suffix in ['.wav','.flac','.mp3'] and hashlib.sha256(f.read_bytes()).hexdigest() in private_hashes)]
    secrets=secrets_from_env(P);hashes={}
    for f in files:
        data=payload(f);name=f.relative_to(P).as_posix()
        if f.suffix not in ['.wav','.flac','.mp3','.png','.pdf']:check_secrets(data,name,secrets)
        hashes[name]=hashlib.sha256(data).hexdigest()
    manifest=P/'submission_manifest.json';manifest.write_text(json.dumps(hashes,indent=2)+'\n')
    output=args.output.resolve();tmp=output.with_suffix('.zip.tmp')
    if output.exists():
        backup=output.with_name('gnani_evaluation_submission_before_timbre_followup.zip')
        if not backup.exists():shutil.copy2(output,backup)
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for f in files:z.writestr('gnani_evaluation/'+f.relative_to(P).as_posix(),payload(f))
        z.write(manifest,'gnani_evaluation/submission_manifest.json')
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP CRC failed')
        for name,digest in hashes.items():
            if hashlib.sha256(z.read('gnani_evaluation/'+name)).hexdigest()!=digest:raise RuntimeError('Hash mismatch: '+name)
        assert not any('/reconciliation/' in name or '/before_followup_fixes/' in name for name in z.namelist())
        assert not any('/results/next/call/' in name or re.search(r'/CALL-\d{2}([_/.]|$)',name) for name in z.namelist())
    tmp.replace(output);print('Verified interview submission:',output,'files:',len(files)+1,flush=True)
if __name__=='__main__':main()
