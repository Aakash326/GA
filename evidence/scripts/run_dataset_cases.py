"""Replay or explicitly run the 24 public replacement clips. References stay provisional."""
import argparse,hashlib,json,os,sys
from pathlib import Path
import pandas as pd
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');args=ap.parse_args()
    os.environ['GNANI_LIVE']='1' if args.live else '0'
    import nextkit as k
    manifest=pd.read_csv(P/'data/next/asr_dataset_replacement.csv',keep_default_na=False);rows=[]
    for r in manifest.itertuples():
        if hashlib.sha256((P/r.input_path).read_bytes()).hexdigest()!=r.input_sha256:raise ValueError('Dataset audio hash changed')
        res=k.asr(r.clip_id,r.input_path,r.language,tag='public_dataset_v1')
        row=dict(clip_id=r.clip_id,category=r.category,language=r.language,source_dataset=r.source_dataset,
                 reference=r.reference_transcript,hypothesis=res.get('transcript',''),reference_status=r.reference_status,
                 status='success' if res.get('ok') else 'not_run_or_failed')
        if res.get('ok'):row.update(k.score(row['reference'],row['hypothesis']),latency_ms=res.get('latency_ms'))
        rows.append(row)
    out=P/'results/next';out.mkdir(exist_ok=True)
    df=pd.DataFrame(rows);df.to_csv(out/'dataset_replacement_results.csv',index=False,encoding='utf-8-sig')
    ok=df[df.status.eq('success')]
    summary={'prepared':len(df),'successful':len(ok),'pending_or_failed':len(df)-len(ok),'reference_assessment':'dataset references, provisional; not human verified',
             'scope':'finance-related read questions and technical Hindi-English code-switching; not transaction commands'}
    if len(ok):
        summary.update(wer=float(ok.word_edits.sum()/ok.ref_words.sum()),cer=float(ok.char_edits.sum()/ok.ref_chars.sum()))
        k.wer_table(ok,'category').to_csv(out/'dataset_replacement_by_category.csv')
    (out/'dataset_replacement_run_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary))
if __name__=='__main__':main()
