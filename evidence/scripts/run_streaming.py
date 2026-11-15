"""Timbre SSE streaming timing test (paid; requires --live).

Design (fixed before running): rounds interleave prompts and voices so time-of-day load affects both voices alike.
  T31 (61 chars, ~3.5 s audio): 5 rounds x {v3.0 Tarika, v2.5 Kaveri}
  T23 (396 chars, ~23 s audio): 3 rounds x {v3.0 Tarika, v2.5 Kaveri}
  T25 (930 chars, ~53 s audio): 1 round x {v3.0 Tarika}
Order within a round is shuffled with a fixed seed. Already-saved successful runs are skipped.
"""
import argparse
import csv
import random
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import gnani_api as g  # noqa: E402

VOICES = {"tarika": ("timbre-v3.0", "Tarika"), "kaveri": ("timbre-v2.5", "Kaveri")}
PLAN = [("T31", ["tarika", "kaveri"], 5), ("T23", ["tarika", "kaveri"], 3), ("T25", ["tarika"], 1)]


def done(case_id, tag, text, model, voice):
    return g.stream_success("tts_stream",case_id,tag,text,"en-IN",model=model,voice=voice)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    with (PROJECT / "data" / "tts_cases.csv").open(encoding="utf-8-sig", newline="") as fh:
        text = {r["case_id"]: r["input_text"] for r in csv.DictReader(fh)}
    rounds = max(n for _, _, n in PLAN)
    for rnd in range(1, rounds + 1):
        jobs = [(cid, v) for cid, voices, n in PLAN if rnd <= n for v in voices]
        random.Random(20261113 + rnd).shuffle(jobs)
        for cid, v in jobs:
            tag = f"stream_{v}_r{rnd}"
            model, voice = VOICES[v]
            if done(cid, tag, text[cid], model, voice):
                print(f"{cid} {tag}: already saved"); continue
            model, voice = VOICES[v]
            r = g.synthesize_stream(cid, text[cid], "en-IN", run_tag=tag, voice=voice, model=model, live=args.live)
            if not r["ok"]:
                print(f"{cid} {tag}: FAILED {r.get('http_status')} {r.get('error')}"); continue
            print(f"{cid} {tag}: TTFA {r['ttfa_ms']:.0f} ms, stall-free start {r['stall_free_start_ms']:.0f} ms, "
                  f"complete {r['complete_ms']:.0f} ms, {r['audio_duration_s']} s audio, {r['chunks']} chunks, "
                  f"stalls {r['stalls']} ({r['stall_s']} s)")


if __name__ == "__main__":
    main()
