"""Merge data/listening/tts_listening_filled.csv into results/listening_ratings.csv.

The listener's own mark is kept in `target_result`. `adjudicated_result` is the value used for the strict score:
  - equal to the listener's mark when one was given;
  - for an unmarked target, read from the listener's comment ONLY where the comment states the outcome
    (ADJUDICATIONS below, each with its reason); otherwise `unmarked` (not scored);
  - DISPUTES flag marks that conflict with the targets frozen before generation; they are reported, not overridden.
Re-running replaces this listener's previous TTS rows (earlier T01/T35 spot checks are kept).
"""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SRC = PROJECT / "data" / "listening" / "tts_listening_filled.csv"
OUT = PROJECT / "results" / "listening_ratings.csv"
LISTENER = "R1"  # same project owner who did the earlier checks; the export left the ID blank

ADJUDICATIONS = {  # (case, target) -> (result, reason)
    ("T41", "qty"): ("ambiguous", "listener comment: 'the 15 and 50 were not so clear'"),
    ("T41", "rejected"): ("ambiguous", "listener comment: 'the 15 and 50 were not so clear'"),
    ("T49", "id"): ("correct", "listener comment: read 'double zero double zero 42', all digits kept; listener judged correct"),
}
DISPUTES = {
    ("T60", "amount"): "marked wrong because the amount was spoken in Hindi; frozen targets accept Hindi number words, "
                       "so this is wrong only if the value itself was wrong. Re-listen needed.",
}
COLS = ["case_id", "listener_id", "listener_languages", "target_id", "target_critical", "target_result",
        "adjudicated_result", "adjudication_note", "naturalness_1to5", "prosody_1to5", "content_complete",
        "meaning_preserved", "artifact_flags", "comment", "blind_transcription", "blind_before_reveal",
        "cannot_judge", "rated_at", "source"]


def main() -> None:
    with SRC.open(encoding="utf-8-sig", newline="") as fh:
        marks = list(csv.DictReader(fh))
    kept = []
    if OUT.exists():
        with OUT.open(encoding="utf-8-sig", newline="") as fh:
            kept = [r for r in csv.DictReader(fh) if r.get("source", "") != "tts_listening_page"]
    rows = []
    for r in kept:
        r.setdefault("adjudicated_result", "correct" if r.get("target_correct") == "true" else "")
        r.setdefault("target_result", "correct" if r.get("target_correct") == "true" else "")
        r.setdefault("source", "chat spot check")
        rows.append({c: r.get(c, "") for c in COLS})
    for m in marks:
        key = (m["case_id"], m["target_id"])
        result = m["target_result"].strip()
        adj, note = (result or "unmarked"), ""
        if not result and key in ADJUDICATIONS:
            adj, note = ADJUDICATIONS[key]
        if key in DISPUTES:
            note = (note + " " if note else "") + "DISPUTED: " + DISPUTES[key]
        rows.append({**{c: m.get(c, "") for c in COLS}, "listener_id": m["listener_id"] or LISTENER,
                     "target_result": result, "adjudicated_result": adj, "adjudication_note": note,
                     "source": "tts_listening_page"})
    with OUT.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    page = [r for r in rows if r["source"] == "tts_listening_page"]
    tally = {}
    for r in page:
        tally[r["adjudicated_result"]] = tally.get(r["adjudicated_result"], 0) + 1
    print(f"{len(rows)} rows written ({len(page)} from the page); adjudicated: {tally}")


if __name__ == "__main__":
    main()
