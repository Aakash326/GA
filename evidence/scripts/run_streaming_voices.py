"""Streaming start-up check across voices (paid; --live). T31 on all 13 Timbre v3.0 voices + 3 v2.5 English voices,
2 rounds, order shuffled per round (seeded). Skips saved runs. Run tags: stream_voice_<voice>_r<n>."""
import argparse, csv, random, sys
from pathlib import Path
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import gnani_api as g  # noqa: E402

V3 = ["Shivani", "Lakshmi", "Kalpana", "Chetana", "Vasudha", "Riyaa", "Tarika", "Avinash", "Shubham", "Prakash",
      "Devansh", "Yashraj", "Harshad"]
V25 = ["Kaveri", "Pranav", "Trupti"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--live", action="store_true"); args = ap.parse_args()
    text = {r["case_id"]: r["input_text"] for r in csv.DictReader(open(PROJECT / "data/tts_cases.csv", encoding="utf-8-sig"))}["T31"]
    jobs0 = [("timbre-v3.0", v) for v in V3] + [("timbre-v2.5", v) for v in V25]
    for rnd in (1, 2):
        jobs = list(jobs0); random.Random(777 + rnd).shuffle(jobs)
        for model, voice in jobs:
            tag = f"stream_voice_{voice.lower()}_r{rnd}"
            if g.stream_success("tts_stream","T31",tag,text,"en-IN",model=model,voice=voice):
                continue
            r = g.synthesize_stream("T31", text, "en-IN", run_tag=tag, voice=voice, model=model, live=args.live)
            if not r["ok"]:
                print(f"{model} {voice} r{rnd}: FAILED {r.get('http_status')} {r.get('error')}"); continue
            print(f"{model} {voice:8s} r{rnd}: first chunk {r['ttfa_ms']:.0f} ms ({r['first_chunk_audio_s']} s), "
                  f"stall-free {r['stall_free_start_ms']:.0f} ms, gaps {r['stalls']} ({r['stall_s']} s)")


if __name__ == "__main__":
    main()
