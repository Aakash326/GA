"""Explicitly separate the 30 controlled timing runs from 60 earlier waveform files."""
import csv,json
from collections import Counter
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def read(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def reconcile(project=None,out=None):
    project=Path(project or P);out=Path(out or project/'results/submission');out.mkdir(parents=True,exist_ok=True)
    prior=read(project/'results/timbre_followup/audio_results.csv')
    rest=[r for r in prior if r['transport']=='REST'];sse=[r for r in prior if r['transport']=='SSE']
    trials=[r for r in read(project/'results/report4/rest_latency_trials.csv') if r['eligible_primary'].lower()=='true']
    ledger=read(project/'results/report4/tts_http_attempts.csv')
    warm=[r for r in ledger if r['cohort']=='report4_controlled' and r['phase']=='warmup_rest']
    assert len(rest)==60 and len(sse)==6 and len(trials)==30 and len(warm)==2
    assert len(set(r['text_hash'] for r in trials))==3
    assert all(len([r for r in trials if r['version']==m and r['length']==l])==5 for m in ['timbre-v3.0','timbre-v2.5'] for l in ['short','medium','long'])
    assert not ({r['case_id'] for r in rest}&{r['case_id'] for r in trials})
    sections=dict(Counter(r['section'] for r in rest));assert sections['rest_latency']==18
    rows=[]
    for r in rest:rows.append(dict(cohort='earlier_waveform_rest',case_id=r['case_id'],purpose='completed-file waveform check',section=r['section'],model=r['model'],input_text=r['input_text'],included_controlled_timing=False,audio_path=r['audio_path']))
    for r in sse:rows.append(dict(cohort='earlier_sse_audio',case_id=r['case_id'],purpose='streaming output; excluded from REST count',section=r['section'],model=r['model'],input_text=r['input_text'],included_controlled_timing=False,audio_path=r['audio_path']))
    for r in trials:rows.append(dict(cohort='controlled_measured_rest',case_id=r['case_id'],purpose='five-repeat latency/duration/RTF comparison',section=r['length'],model=r['version'],input_text=r['input_text'],included_controlled_timing=True,audio_path=r['audio_path']))
    for r in warm:rows.append(dict(cohort='controlled_rest_warmup',case_id=r['case_id'],purpose='excluded warm-up',section='short',model=r['version'],input_text=r['input_text'],included_controlled_timing=False,audio_path=r['body_path']))
    with (out/'rest_cohort_membership.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=dict(controlled_models=2,controlled_distinct_texts=3,texts_per_length=1,successful_repeats_per_model_text=5,
        controlled_measured_requests=30,controlled_excluded_warmups=2,controlled_rest_requests_total=32,
        earlier_waveform_rest_files=60,earlier_waveform_sections=sections,earlier_timing_subset=18,earlier_other_functionality_files=42,
        earlier_sse_files=6,shared_case_ids_between_30_and_60=0,pooled_into_controlled_timing=False,
        explanation='30 = 2 models × 3 distinct texts (one per length) × 5 successful repeats. Two warm-ups excluded. The earlier 60-file REST waveform set comprises 18 earlier timing runs (three repeats/model/length) + 42 functionality/configuration outputs. Earlier files are not pooled into the controlled medians.')
    (out/'rest_count_reconciliation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return summary
if __name__=='__main__':print(json.dumps(reconcile(),ensure_ascii=False,indent=2))
