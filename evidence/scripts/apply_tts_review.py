"""Apply data/listening/tts_targets_review_filled.csv to data/tts_cases.csv.

approved -> prompt_status=ready; flagged -> prompt_status=needs_change (note appended);
unreviewed -> unchanged. Only `ready` prompts may be synthesised.
"""
import csv
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CASES = PROJECT / "data" / "tts_cases.csv"
REVIEW = PROJECT / "data" / "listening" / "tts_targets_review_filled.csv"


def main() -> None:
    with CASES.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields, rows = reader.fieldnames, list(reader)
    with REVIEW.open(encoding="utf-8-sig", newline="") as fh:
        review = {r["case_id"]: r for r in csv.DictReader(fh)}
    for r in rows:
        v = review.get(r["case_id"])
        if not v or not v["decision"]:
            continue
        if v["decision"] == "ok":
            r["prompt_status"] = "ready"
        elif v["decision"] == "flag":
            r["prompt_status"] = "needs_change"
            r["notes"] = (r["notes"] + f" Review: {v['note']}").strip()
    with CASES.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["prompt_status"]] = counts.get(r["prompt_status"], 0) + 1
    print(counts)
    for r in rows:
        if r["prompt_status"] == "needs_change":
            print(" ", r["case_id"], "->", r["notes"].split("Review:")[-1].strip())


if __name__ == "__main__":
    main()
