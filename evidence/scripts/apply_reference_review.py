"""Apply data/listening/reference_review_filled.csv (listener decisions on judge-disputed items) to the ASR manifest.

call ok        -> reference = listener-confirmed text, verified, language from listener
call unusable  -> excluded (selected=false) with reason
flagged dataset/judge/edit -> chosen text becomes the reference for the source clip AND its derived copies, verified
flagged skip   -> unchanged (stays unverified; reported as judge-disputed)
nospeech silent/speech -> verified / excluded
Model output (Prisma) is never used. Gemini text only enters a reference after a listener chose it.
"""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
MAN = PROJECT / "data" / "asr_manifest.csv"
SRC = PROJECT / "data" / "listening" / "reference_review_filled.csv"
LANG = {"English": "en-IN", "Hindi": "hi-IN", "Hinglish (code-mixed)": "hi-IN,en-IN", "Telugu": "te-IN"}


def main():
    with MAN.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)
    by_id = {r["clip_id"]: r for r in rows}
    with SRC.open(encoding="utf-8-sig", newline="") as fh:
        decisions = list(csv.DictReader(fh))
    n = {}
    for d in decisions:
        ch, text = d["choice"], d["text"].strip()
        who = d.get("decision_source") or "listener R1"
        if not ch:
            continue
        n[f"{d['kind']}:{ch}"] = n.get(f"{d['kind']}:{ch}", 0) + 1
        if d["kind"] == "call":
            r = by_id[d["clip_id"]]
            if ch == "ok" and text:
                r.update(reference_transcript=text, human_reference_verified="true",
                         reference_origin=f"Gemini blind draft, confirmed by {who}",
                         language=LANG.get(d["language_heard"], r["language"]))
                if "Hinglish" in d["language_heard"] and "code_switch" not in r["tags"]:
                    r["tags"] += ";code_switch"
            elif ch == "unusable":
                r.update(selected="false", exclusion_reason=f"{who}: unusable audio")
        elif d["kind"] == "flagged":
            if ch == "skip":
                continue
            new = {"dataset": d["dataset_reference"], "judge": d["judge_text"], "edit": text}[ch]
            origin = {"dataset": f"dataset text, upheld by {who} after a judge dispute",
                      "judge": f"corrected: Gemini transcript chosen over the dataset text by {who}",
                      "edit": f"corrected by {who} (own transcript)"}[ch]
            for cid in d["applies_to"].split(";"):
                if cid in by_id:
                    r = by_id[cid]
                    r.update(reference_transcript=new, human_reference_verified="true",
                             reference_origin=origin if cid == d["clip_id"] else f"inherited from {d['clip_id']} ({origin})")
        elif d["kind"] == "nospeech":
            r = by_id[d["clip_id"]]
            if ch == "silent":
                r.update(human_reference_verified="true", reference_origin=f"no speech confirmed by {who}")
            else:
                r.update(selected="false", exclusion_reason=f"{who}: speech audible; invalid no-speech control")
    with MAN.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print("applied:", n)


if __name__ == "__main__":
    main()
