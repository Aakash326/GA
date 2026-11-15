"""Apply the calibrated Gemini judge to everything humans have not scored (paid with --live; cached).

ASR
  unverified dataset references -> blind transcript + verification; match = "model-verified", else flagged for a human
  call clips (no reference)      -> blind transcript = DRAFT reference for a human to confirm
  unverified no-speech clips     -> blind transcript; empty = no speech confirmed by the judge
TTS
  every prompt in tts_cases.csv and tts_mitigation_cases.csv -> blind transcript + target verdicts
  (human marks still take precedence where they exist; see notebook)
Outputs: results/judge/asr_judge.csv, results/judge/tts_judge.csv
"""
import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import gemini_judge as j  # noqa: E402

OUT = PROJECT / "results" / "judge"


def read(path):
    with (PROJECT / path).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def asr(live, workers):
    man = read("data/asr_manifest.csv")
    todo = [r for r in man if r["selected"].lower() == "true" and r["human_reference_verified"].lower() != "true"]

    def run(r):
        lang = r["language"] or ("hi-IN,en-IN" if r["category"] == "real_telephony" else "")
        b = j.transcribe_blind(r["clip_id"], r["input_path"], lang, live=live)["reply"]
        blind = b.get("transcript", "") or ""
        row = {"clip_id": r["clip_id"], "category": r["category"], "language": r["language"], "reference": r["reference_transcript"],
               "judge_blind": blind, "judge_language": b.get("language", ""), "judge_no_speech": bool(b.get("no_speech")),
               "judge_unclear": json.dumps(b.get("unclear", []), ensure_ascii=False), "task": "", "judge_matches": "",
               "judge_confidence": "", "differences": "", "status": ""}
        if r["is_no_speech"].lower() == "true":
            ok = not blind.strip()
            row.update(task="no_speech_check", status="no speech confirmed by judge" if ok else "judge heard speech: human check")
        elif not r["reference_transcript"].strip():
            row.update(task="draft_reference", status="draft reference from judge: human to confirm")
        else:
            v = j.verify_reference(r["clip_id"], r["input_path"], lang, r["reference_transcript"], blind, live=live)["reply"]
            m = bool(v.get("matches"))
            row.update(task="verify_reference", judge_matches=m, judge_confidence=v.get("confidence", ""),
                       differences=json.dumps(v.get("differences", []), ensure_ascii=False),
                       status="model-verified" if m else "judge disagrees: human check")
        return row

    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(run, todo))
    write(OUT / "asr_judge.csv", rows)
    return rows


def tts(live, workers):
    cases = read("data/tts_cases.csv") + [r for r in read("data/tts_mitigation_cases.csv")]

    def run(c):
        cid = c["case_id"]
        audio = f"results/tts_audio/{cid}.wav"
        blind = j.tts_blind(cid, audio, c["language"], live=live)["reply"].get("heard", "")
        res = j.tts_judge(cid, audio, c["language"], c["input_text"], json.loads(c["expected_targets_json"] or "[]"),
                          json.loads(c["accepted_variants_json"] or "{}"), blind, live=live)["reply"]
        crit = {t["id"]: t["critical"] for t in json.loads(c["expected_targets_json"] or "[]")}
        out = []
        for t in res.get("targets", []):
            if t.get("id") not in crit:
                continue
            out.append({"case_id": cid, "category": c["category"], "language": c["language"], "target_id": t["id"],
                        "critical": crit[t["id"]], "judge_result": t.get("result"), "judge_heard": t.get("heard", ""),
                        "blind_heard": blind, "content_complete": res.get("content_complete"),
                        "naturalness_1to5": res.get("naturalness_1to5"), "prosody_1to5": res.get("prosody_1to5"),
                        "artifacts": json.dumps(res.get("artifacts", []), ensure_ascii=False), "comment": res.get("comment", "")})
        return out

    with ThreadPoolExecutor(workers) as ex:
        rows = [r for rs in ex.map(run, cases) for r in rs]
    write(OUT / "tts_judge.csv", rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    a = asr(args.live, args.workers)
    print("ASR:", {s: sum(r["status"] == s for r in a) for s in sorted({r["status"] for r in a})})
    t = tts(args.live, args.workers)
    res = {}
    for r in t:
        res[r["judge_result"]] = res.get(r["judge_result"], 0) + 1
    print("TTS targets:", len(t), res)


if __name__ == "__main__":
    main()
