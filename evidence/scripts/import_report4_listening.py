"""Validate exported independent listener scores; --apply merges actual marks only."""
import argparse,csv,shutil,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'scripts'))
from analyze_report4 import read,write
FIELDS=['naturalness','intelligibility','pronunciation','prosody','expressiveness']


def validate(rows,valid_ids):
    complete=[];seen=set()
    for row in rows:
        if not any(row.get(f,'').strip() for f in FIELDS):continue
        identity=(row.get('listener_id','').strip(),row.get('blind_id','').strip())
        if not all(identity) or identity[1] not in valid_ids or not row.get('language_qualification','').strip():raise ValueError('Listener ID, language qualification or blinded clip identity missing')
        if identity in seen:raise ValueError('Duplicate listener/clip in export')
        seen.add(identity)
        for field in FIELDS:
            value=row.get(field,'').strip()
            if value and (not value.isdigit() or not 1<=int(value)<=5):raise ValueError('Score outside 1–5')
        complete.append(row)
    return complete


def main():
    ap=argparse.ArgumentParser();ap.add_argument('exports',nargs='+',type=Path);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    out=P/'results/report4_quality';keys=read(out/'tts_listening_key.csv');valid={r['blind_id'] for r in keys}
    incoming=validate([r for path in args.exports for r in read(path)],valid)
    target=out/'tts_listening_scores.csv';existing=read(target);merged={(r['listener_id'],r['blind_id']):r for r in existing}
    for row in incoming:
        key=(row['listener_id'],row['blind_id']);old=merged.get(key)
        if old and any(old.get(f,'').strip() for f in FIELDS) and any(old.get(f,'').strip()!=row.get(f,'').strip() for f in FIELDS):raise ValueError('Conflicting existing marks; resolve explicitly before import')
        merged[key]=row
    if args.apply:
        backup=out/'import_backups'/'tts_listening_scores_before_import.csv';backup.parent.mkdir(exist_ok=True)
        if target.exists() and not backup.exists():shutil.copy2(target,backup)
        write(target,list(merged.values()))
        from analyze_report4_heldout import analyze
        analyze(P)
    print('Validated actual rated rows:',len(incoming),'Applied:',args.apply)


if __name__=='__main__':main()
