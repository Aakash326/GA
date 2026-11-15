"""Check the delivered repository and published numbers after offline replay.

From GA_Submission: python assets/verify_repository.py
Replay first with: python evidence/run_evaluation.py --mode replay --part all --reports
"""
import argparse,csv,hashlib,json,re,subprocess,sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote,urlsplit
from pypdf import PdfReader

parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
P=args.root.resolve();E=P/'evidence'
required=['README.md','DATASETS.md','METHODS.md','TESTING_STAGES.md','IMPROVEMENTS.md','VERIFICATION.md','TIMBRE_FOLLOWUP.md','REPORT4_IMPLEMENTATION.md','STREAMING_TRACE_PROVENANCE.md']
assert all((E/n).is_file() for n in required)
assert (E/'run_evaluation.py').is_file() and (E/'requirements-lock.txt').is_file()
docs=[P/'README.md',P/'HTML_PLAN.md']+sorted(E.glob('*.md'));links=0
for f in docs:
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',f.read_text(encoding='utf8')):
        parsed=urlsplit(target.strip('<>'))
        if parsed.scheme or not parsed.path:continue
        path=(f.parent/unquote(parsed.path)).resolve()
        assert path.is_relative_to(P), 'Documentation link escapes release: '+target
        if path!=P/'assets/repository_verification.json':assert path.exists(), 'Missing documentation target: '+target
        links+=1
s=json.loads((E/'results/submission/summary.json').read_text(encoding='utf8'))
assert s['headline_reconciliation']=='passed' and s['new_api_calls']==0
assert all(abs(s['asr'][k]['wer']-v)<1e-12 for k,v in {'baseline':309/1630,'followup':186/881,'public24':48/249}.items())
assert [(r['human_scored_targets'],r['correct_targets']) for r in s['tts_human']]==[(62,57),(48,35)]
expected={'timbre-v3.0':{'short':3436.5,'medium':6504.2,'long':11747.1},'timbre-v2.5':{'short':766.6,'medium':1183.2,'long':2563.6}}
assert all(abs(r['request_total_ms_median']-expected[r['model']][r['length']])<.11 for r in s['report4']['controlled_rest'])
assert s['report4']['streaming']['streams']==32 and s['report4']['streaming']['sensitivity_rows']==576
held=s['report4_heldout'];assert held['new_human_rating_rows']==0 and held['rewrite_pairs_scored']==0
traces=list(csv.DictReader((E/'results/report4/stream_trials.csv').open(encoding='utf-8-sig',newline='')))
counts=Counter((r['cohort'],r['phase']) for r in traces)
assert counts=={('original_N8','saved_trace'):14,('fresh_SSE','saved_trace'):6,('report4_WS','warm_measured'):10,('report4_WS','cold_warmup'):2}
assert len({r['request_id'] for r in traces})==32
for r in traces:
    for pk,hk in [('audio_path','audio_sha256'),('timeline_path','timeline_sha256')]:
        path=(E/r[pk]).resolve();assert path.is_relative_to(E)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==r[hk]
assert all(len(PdfReader(path).pages)==2 for path in [P/'report.pdf',E/'report.pdf',E/'next_stages_report.pdf'])
assert 'replay passed' in (P/'assets/replay_output.txt').read_text(encoding='utf8')
assert re.search(r'Ran 74 tests in .*\n\s*OK',(P/'assets/regression_test_output.txt').read_text(encoding='utf8'))
pip=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
assert pip.returncode==0,pip.stdout+pip.stderr
result=dict(status='passed',python=sys.version.split()[0],replay_command='python run_evaluation.py --mode replay --part all --reports',
            replay_working_directory='evidence',replay_log='assets/replay_output.txt',headline_results_reproduced=True,
            markdown_files_checked=len(docs),local_markdown_links_checked=links,broken_local_links=0,
            required_repository_files_exist=True,implementation_tests=74,two_page_pdfs=3,
            trace_provenance={f'{k[0]}/{k[1]}':v for k,v in counts.items()},
            trace_source_hashes_verified=64,streaming_traces=32,buffer_conditions=576,
            excluded_warm_ttfa_ids=[r['case_id'] for r in traces if r['phase']=='cold_warmup'],
            new_human_listening_marks=0,heldout_tts_rewrite_pairs_scored=0,
            unfinished_human_studies_labeled_future_validation=True,pip_check=pip.stdout.strip(),new_api_calls=0)
(P/'assets/repository_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps(result,indent=2))
