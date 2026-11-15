"""Calibrate the Gemini judge before trusting it (paid Gemini calls with --live; cached).

ASR reference checking
  positives: every listener-verified speech reference (should be judged a match)
  negatives (planted, seed 20261114): for verified clips,
    swap   - the reference of a different clip in the same language (should be rejected)
    subtle - the true reference with ONE token changed: a digit changed when the text has digits, otherwise one word
             replaced by a word from another reference of the same language (should be rejected; this is the
             1499 -> 1999 kind of error)
TTS target judging
  every target the human listener scored (adjudicated correct / wrong / ambiguous) is re-judged blind-first;
  agreement, Cohen's kappa and the confusion table are reported.
Outputs: results/judge/calibration_asr.csv, results/judge/calibration_tts.csv, results/judge/calibration_summary.json
"""
import argparse
import csv
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import gemini_judge as j  # noqa: E402

OUT = PROJECT / "results" / "judge"
SEED = 20261114


def read(path):
    with (PROJECT / path).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def plant(ref, others, rng):
    digits = list(re.finditer(r"\d", ref))
    if digits:
        m = rng.choice(digits)
        new = str((int(m.group()) + rng.randint(1, 8)) % 10)
        return ref[:m.start()] + new + ref[m.end():], f"digit {m.group()}->{new}"
    words = ref.split()
    pool = [w for o in others for w in o.split() if len(w) > 3 and w not in words]
    i = max(range(len(words)), key=lambda k: (len(words[k]), -k))  # change the longest word (a content word)
    repl = rng.choice(pool)
    words[i] = repl
    return " ".join(words), f"word -> {repl}"


def kappa(pairs):
    labels = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == l for a, _ in pairs) / n) * (sum(b == l for _, b in pairs) / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def asr_calibration(live, workers):
    man = read("data/asr_manifest.csv")
    ver = [r for r in man if r["human_reference_verified"].lower() == "true" and r["is_no_speech"].lower() != "true"
           and r["reference_transcript"].strip()]
    by_lang = {}
    for r in man:
        if r["reference_transcript"].strip() and r["is_no_speech"].lower() != "true":
            by_lang.setdefault(r["language"], []).append(r)
    rng = random.Random(SEED)
    base = [r for r in ver if r["source_id"] == r["clip_id"]] or ver
    items = [(r["clip_id"], r, r["reference_transcript"], "positive", "") for r in ver]
    for r in rng.sample(base, min(10, len(base))):
        other = rng.choice([o for o in by_lang[r["language"]] if o["reference_transcript"] != r["reference_transcript"]])
        items.append((f"NEG-SWAP-{r['clip_id']}", r, other["reference_transcript"], "negative_swap", f"text of {other['clip_id']}"))
    for r in base:
        others = [o["reference_transcript"] for o in by_lang[r["language"]] if o["clip_id"] != r["clip_id"]]
        planted, how = plant(r["reference_transcript"], others, rng)
        items.append((f"NEG-SUBTLE-{r['clip_id']}", r, planted, "negative_subtle", how))

    def run(item):
        iid, r, ref, kind, how = item
        blind = j.transcribe_blind(r["clip_id"], r["input_path"], r["language"], live=live)["reply"].get("transcript", "")
        v = j.verify_reference(iid, r["input_path"], r["language"], ref, blind, live=live)["reply"]
        return {"item": iid, "clip_id": r["clip_id"], "language": r["language"], "kind": kind, "planted": how,
                "reference_given": ref, "blind_transcript": blind, "judge_matches": bool(v.get("matches")),
                "judge_confidence": v.get("confidence"), "differences": json.dumps(v.get("differences", []), ensure_ascii=False),
                "judge_correct": bool(v.get("matches")) == (kind == "positive")}

    with ThreadPoolExecutor(workers) as ex:
        rows = list(ex.map(run, items))
    write(OUT / "calibration_asr.csv", rows)
    summary = {}
    for kind in ("positive", "negative_swap", "negative_subtle"):
        rs = [r for r in rows if r["kind"] == kind]
        summary[kind] = {"n": len(rs), "judge_correct": sum(r["judge_correct"] for r in rs),
                         "rate": round(sum(r["judge_correct"] for r in rs) / len(rs), 3) if rs else None}
    return summary


def tts_calibration(live, workers):
    human = [r for r in read("results/listening_ratings.csv") if r["adjudicated_result"] in ("correct", "wrong", "ambiguous")]
    mit_h = [r for r in read("results/tts_mitigation_ratings.csv") if r["adjudicated_result"] in ("correct", "wrong", "ambiguous")]
    cases = {r["case_id"]: r for r in read("data/tts_cases.csv")}
    cases.update({r["case_id"]: r for r in read("data/tts_mitigation_cases.csv")})
    wanted = {}
    for r in human + mit_h:
        wanted.setdefault(r["case_id"], {})[r["target_id"]] = r["adjudicated_result"]

    def run(cid):
        c = cases[cid]
        audio = f"results/tts_audio/{cid}.wav"
        blind = j.tts_blind(cid, audio, c["language"], live=live)["reply"].get("heard", "")
        res = j.tts_judge(cid, audio, c["language"], c["input_text"], json.loads(c["expected_targets_json"]),
                          json.loads(c["accepted_variants_json"]), blind, live=live)["reply"]
        got = {t["id"]: t for t in res.get("targets", [])}
        return [{"case_id": cid, "target_id": tid, "human": h, "judge": got.get(tid, {}).get("result", "missing"),
                 "judge_heard": got.get(tid, {}).get("heard", ""), "blind_heard": blind,
                 "agree": got.get(tid, {}).get("result") == h} for tid, h in wanted[cid].items()]

    with ThreadPoolExecutor(workers) as ex:
        rows = [r for rs in ex.map(run, sorted(wanted)) for r in rs]
    write(OUT / "calibration_tts.csv", rows)
    pairs = [(r["human"], r["judge"]) for r in rows]
    conf = {}
    for h, g in pairs:
        conf.setdefault(h, {}).setdefault(g, 0)
        conf[h][g] += 1
    strict = [(h == "correct", g == "correct") for h, g in pairs]
    return {"targets": len(rows), "exact_agreement": round(sum(a == b for a, b in pairs) / len(pairs), 3),
            "kappa_3class": round(kappa(pairs), 3),
            "agreement_correct_vs_not": round(sum(a == b for a, b in strict) / len(strict), 3),
            "kappa_correct_vs_not": round(kappa([(str(a), str(b)) for a, b in strict]), 3), "confusion_human_to_judge": conf}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    summary = {"model": j.MODEL, "asr": asr_calibration(args.live, args.workers), "tts": tts_calibration(args.live, args.workers)}
    (OUT / "calibration_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
