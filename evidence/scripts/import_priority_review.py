"""Validate an owner N1 export. Preserve blank/unknown/non-blind metadata without inventing judgments."""
import argparse,csv,hashlib,json,shutil
from collections import Counter
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('csv');ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    source=Path(args.csv);rows=read(source)
    expected=read(P/'results/verification/human_review_queue_priority50.csv')
    expected_keys={(r['case_id'],r['target_id']) for r in expected}
    keys=[(r['case_id'],r['target_id']) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=expected_keys:raise ValueError('Export must contain each selected target exactly once')
    if any(r['target_result'] not in ['','correct','wrong','ambiguous'] for r in rows):raise ValueError('Invalid target result')
    usable=[r for r in rows if r['target_result'] and r.get('cannot_judge','').lower()!='true']
    accepted={(r['case_id'],r['target_id']) for r in usable}
    clips={r['case_id'] for r in rows}
    complete=sum(all((r['case_id'],r['target_id']) in accepted for r in rows if r['case_id']==cid) for cid in clips)
    summary={'source_file':source.name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
       'listener_identity':'project owner confirmed completion in conversation; exported listener ID/languages left blank',
       'selected_clips':len(clips),'fully_marked_clips':complete,'selected_targets':len(rows),'human_marked_targets':len(usable),
       'pending_targets':len(rows)-len(usable),'human_results':dict(Counter(r['target_result'] for r in usable)),
       'blind_first_marked_targets':sum(r.get('blind_before_reveal','').lower()=='true' for r in usable),
       'subjective_ratings_complete':all(r.get('naturalness_1to5') and r.get('prosody_1to5') for r in usable),
       'status':'complete' if len(usable)==len(rows) else 'partial_human_review',
       'selection':'targeted priority sample; not a representative population accuracy estimate'}
    if args.apply:
        folder=P/'results/verification';folder.mkdir(exist_ok=True)
        archive=folder/'owner_exports';archive.mkdir(exist_ok=True)
        archived=archive/f'n1_{summary["source_sha256"][:16]}.csv'
        if not archived.exists():shutil.copy2(source,archived)
        dest=P/'data/listening/n1_tts_filled.csv'
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()!=summary['source_sha256']:
            backup=archive/f'n1_previous_{hashlib.sha256(dest.read_bytes()).hexdigest()[:16]}.csv'
            if not backup.exists():shutil.copy2(dest,backup)
        if source.resolve()!=dest.resolve():shutil.copy2(source,dest)
        (folder/'n1_review_import.json').write_text(json.dumps(summary,indent=2)+'\n')
        pending=[r for r in rows if (r['case_id'],r['target_id']) not in accepted]
        with (folder/'n1_pending_targets.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(pending)
    print(json.dumps(summary))
if __name__=='__main__':main()
