"""Score imported finance/code-switching recordings. Live calls require --live and a reconciled budget."""
import argparse, json, os, sys
from pathlib import Path
import pandas as pd
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');args=ap.parse_args()
    os.environ['GNANI_LIVE']='1' if args.live else '0'
    import nextkit as k
    path=P/'data/next/asr_recorded_manifest.csv'
    if not path.exists():print('No verified recordings imported yet. No requests sent.');return
    manifest=pd.read_csv(path,keep_default_na=False);results=[]
    for r in manifest.itertuples():
        if str(r.human_reference_verified).lower()!='true' or str(r.consent_confirmed).lower()!='true':
            raise ValueError('Recording lacks transcript verification/consent')
        if __import__('hashlib').sha256((P/r.input_path).read_bytes()).hexdigest()!=r.input_sha256:raise ValueError('Recording hash changed')
        res=k.asr(r.clip_id,r.input_path,r.language,tag='recorded_v1')
        row=dict(clip_id=r.clip_id,queue_id=r.queue_id,speaker_id=r.speaker_id,category=r.category,language=r.language,
                 reference=r.reference_transcript,hypothesis=res.get('transcript',''),status='success' if res.get('ok') else 'not_run_or_failed',
                 expected_entities_json=r.expected_entities_json,slot_semantics='human_review_pending')
        if res.get('ok'):row.update(k.score(row['reference'],row['hypothesis']),latency_ms=res.get('latency_ms'))
        results.append(row)
    df=pd.DataFrame(results);out=P/'results/next';out.mkdir(exist_ok=True)
    df.to_csv(out/'recorded_asr_results.csv',index=False,encoding='utf-8-sig')
    ok=df[df.status.eq('success')]
    summary={'prepared':len(df),'successful':len(ok),'pending_or_failed':len(df)-len(ok),'human_slot_verification':'pending'}
    if len(ok):
        summary.update(wer=float(ok.word_edits.sum()/ok.ref_words.sum()),cer=float(ok.char_edits.sum()/ok.ref_chars.sum()))
        k.wer_table(ok,'category').to_csv(out/'recorded_asr_by_category.csv')
    (out/'recorded_asr_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary))
if __name__=='__main__':main()
