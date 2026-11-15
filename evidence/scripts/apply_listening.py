"""Merge data/listening/asr_reference_check_filled.csv into data/asr_manifest.csv.

Rules (frozen before any model output was seen):
- verify + match     -> human_reference_verified=true, dataset text kept
- verify + mismatch  -> reference replaced by the listener's heard transcript, verified=true
- verify + skip      -> verified=false, reference_origin notes the listener could not judge
- verify + unmarked  -> dataset text kept, verified=false, origin records the spot-check pass rate
- transcribe + ok    -> reference = heard transcript, verified=true, language from the listener
- nospeech + silent  -> verified=true; nospeech + speech -> excluded (not a valid no-speech control)
Model output never feeds into references.
"""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT / "data" / "asr_manifest.csv"
FILLED = PROJECT / "data" / "listening" / "asr_reference_check_filled.csv"
LANG = {"English": "en-IN", "Hindi": "hi-IN", "Hinglish (code-mixed)": "hi-IN,en-IN", "Telugu": "te-IN",
        "Telugu-English mix": "te-IN,en-IN"}


def main() -> None:
    with MANIFEST.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)
    with FILLED.open(encoding="utf-8-sig", newline="") as fh:
        marks = {r["clip_id"]: r for r in csv.DictReader(fh)}

    verify = [m for m in marks.values() if m["kind"] == "verify"]
    judged = [m for m in verify if m["status"] in ("match", "mismatch")]
    matched = sum(m["status"] == "match" for m in judged)
    spot = f"{matched}/{len(judged)} listened dataset clips matched"

    for r in rows:
        m = marks.get(r["clip_id"])
        if not m:
            continue
        st, heard = m["status"], m["heard_transcript"].strip()
        who = m["listener_id"] or "R1"
        if m["kind"] == "verify":
            if st == "match":
                r.update(human_reference_verified="true", reference_origin=f"dataset text, confirmed by listener {who}")
            elif st == "mismatch" and heard:
                r.update(reference_transcript=heard, human_reference_verified="true",
                         reference_origin=f"corrected by listener {who} (dataset text differed)")
            elif st == "skip":
                r.update(human_reference_verified="false",
                         reference_origin=f"dataset text; listener {who} could not judge ({spot})")
            else:
                r.update(human_reference_verified="false", reference_origin=f"dataset text, not individually checked ({spot})")
        elif m["kind"] == "transcribe" and st == "ok" and heard:
            r.update(reference_transcript=heard, human_reference_verified="true",
                     reference_origin=f"transcribed by listener {who}", language=LANG.get(m["language_heard"], r["language"]),
                     tags=r["tags"] + (";code_switch" if "mix" in m["language_heard"].lower() else ""))
        elif m["kind"] == "transcribe" and st == "problem":
            r.update(selected="false", exclusion_reason=f"listener {who}: unusable audio. {m['listener_note']}".strip())
        elif m["kind"] == "nospeech" and st == "silent":
            r.update(human_reference_verified="true", reference_origin=f"no speech confirmed by listener {who}")
        elif m["kind"] == "nospeech" and st == "speech":
            r.update(selected="false", exclusion_reason=f"listener {who} heard speech; invalid no-speech control")
        if m["listener_note"]:
            r["notes"] = (r["notes"] + f" Listener: {m['listener_note']}").strip()

    # Derived clips reuse the source clip's words, so they inherit its verification.
    by_id = {r["clip_id"]: r for r in rows}
    for r in rows:
        origin = r["reference_origin"]
        if origin.startswith("inherited from ") or " (source " in origin:
            src_id = origin.split("inherited from ")[-1].split()[0] if origin.startswith("inherited") else \
                origin.split(" (source ")[-1].rstrip(")")
            src = by_id.get(src_id)
            if src:
                r.update(reference_transcript=src["reference_transcript"],
                         human_reference_verified=src["human_reference_verified"],
                         reference_origin=f"inherited from {src_id} (source {src_id})")

    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        key = (r["category"], r["human_reference_verified"])
        counts[key] = counts.get(key, 0) + 1
    print(spot)
    for k in sorted(counts):
        print(f"  {k[0]:16s} verified={k[1]:5s} {counts[k]}")


if __name__ == "__main__":
    main()
