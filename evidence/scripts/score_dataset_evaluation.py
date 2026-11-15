"""Offline scoring of the replacement set against source and adjudicated references, with exclusions explicit."""
import hashlib,json,os,sys
from pathlib import Path
import pandas as pd
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));os.environ['GNANI_LIVE']='0'
import nextkit as k
def summarize(df):
    usable=df[df.reference_usable & df.status.eq('success')]
    return {'clips':len(df),'successful_calls':int(df.status.eq('success').sum()),'scored':len(usable),
            'reference_unresolved':int((~df.reference_usable).sum()),
            'wer':float(usable.word_edits.sum()/usable.ref_words.sum()) if len(usable) else None,
            'cer':float(usable.char_edits.sum()/usable.ref_chars.sum()) if len(usable) else None}
def main():
    source=pd.read_csv(P/'results/next/dataset_replacement_results.csv',keep_default_na=False)
    manifest=pd.read_csv(P/'data/next/asr_dataset_replacement.csv',keep_default_na=False).set_index('clip_id')
    audit=pd.read_csv(P/'results/verification/final_reference_audit.csv',keep_default_na=False).query("cohort == 'dataset_replacement'").set_index('clip_id')
    if len(audit)!=24 or set(audit.index)!=set(source.clip_id):raise ValueError('Incomplete/mismatched replacement reference audit')
    rows=[]
    for r in source.itertuples():
        a=audit.loc[r.clip_id];m=manifest.loc[r.clip_id]
        if hashlib.sha256((P/m.input_path).read_bytes()).hexdigest()!=a.input_sha256:raise ValueError('Audit/input hash mismatch')
        usable=a.resolution_status!='unresolved' and bool(a.resolved_reference)
        row=dict(clip_id=r.clip_id,category=r.category,language=r.language,status=r.status,
                 source_reference=r.reference,resolved_reference=a.resolved_reference,hypothesis=r.hypothesis,
                 reference_usable=usable,reference_status=a.resolution_status,reference_confidence=a.confidence,
                 reference_assessor='audio_llm_provisional',human_verified=False)
        if usable and r.status=='success':row.update(k.score(a.resolved_reference,r.hypothesis))
        rows.append(row)
    df=pd.DataFrame(rows);df.to_csv(P/'results/next/dataset_replacement_verified_results.csv',index=False,encoding='utf-8-sig')
    raw=k.wer_table(source[source.status.eq('success')]).iloc[0]
    summary={**summarize(df),'by_category':{name:summarize(group) for name,group in df.groupby('category')},
             'source_reference_wer':float(raw.WER),'source_reference_cer':float(raw.CER),
             'reference_assessment':'Audio-LLM adjudicated independently of Gnani hypotheses; provisional, not human truth',
             'dataset_scope':'12 finance-related questions; 12 technical Hindi-English tutorial utterances',
             'evaluation_status':'completed_with_reference_limits' if (~df.reference_usable).any() else 'completed_provisional_reference_scoring'}
    (P/'results/next/dataset_replacement_verified_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    # Owner blanks stay human-pending; existing machine marks can still be displayed without re-calling the judge.
    pending=P/'results/verification/n1_pending_targets.csv'
    if pending.exists():
        left=pd.read_csv(pending,keep_default_na=False)
        machine=pd.read_csv(P/'results/verification/tts_llm_verification.csv',keep_default_na=False)
        left.merge(machine[['case_id','target_id','result','heard','model','fingerprint']],on=['case_id','target_id'],validate='one_to_one').to_csv(P/'results/verification/tts_pending_machine_evidence.csv',index=False,encoding='utf-8-sig')
    attempts=[json.loads(l) for l in (P/'results/next/attempts.jsonl').read_text(encoding='utf8').splitlines()]
    new=[r for r in attempts if r.get('run_tag')=='public_dataset_v1']
    seconds=sum(r.get('billing_units') or 0 for r in new)
    estimate=round(seconds*.03/3.6,4)
    prior_path=P/'results/reconciliation/user_reported_spend.json'
    if prior_path.exists():
        prior=json.loads(prior_path.read_text())
        cost={'starting_spend_inr':prior['amount_inr'],'starting_spend_source':'user reported, not dashboard independently verified',
              'new_asr_attempts':len(new),'new_asr_audio_seconds':seconds,'new_asr_estimate_inr':estimate,
              'estimated_gnani_cumulative_inr':round(prior['amount_inr']+estimate,4),
              'budget_ceiling_inr':500,'gemini':'separate token-based billing; see saved usage; not included in Gnani estimate',
              'dashboard_reconciliation':'post-run reading pending'}
        (P/'results/reconciliation/current_cost_summary.json').write_text(json.dumps(cost,indent=2)+'\n')
        print(json.dumps({'evaluation':summary,'cost':cost}))
    else:
        print(json.dumps({'evaluation':summary}))
if __name__=='__main__':main()
