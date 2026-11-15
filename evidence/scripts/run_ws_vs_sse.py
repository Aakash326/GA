"""SSE vs WebSocket streaming, same time window (paid; --live). Blocks are shuffled within each round (seeded).

T31 (short), 5 rounds, for v3.0 Tarika and v2.5 Kaveri:
  sse            one SSE request
  ws cold+warm   open a socket, send T31, send T31 again on the same socket, close
T23 (~20 s audio), 3 rounds, v3.0 Tarika: one SSE request and one WebSocket (cold) request.
Run tags: cmp_<transport>_<voice>_<case>_r<n>[_cold|_warm]. Saved successful runs are skipped.
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


def saved(tag, cid, text, model, voice, kind):
    return g.stream_success(kind,cid,tag,text,"en-IN",model=model,voice=voice)


def show(r):
    if not r["ok"]:
        return f"FAILED {r.get('error')}"
    return (f"first {r['ttfa_ms']:.0f} ms, smooth {r['stall_free_start_ms']:.0f} ms, complete {r['complete_ms']:.0f} ms, "
            f"pauses {r['stalls']} ({r['stall_s']} s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    text = {r["case_id"]: r["input_text"] for r in csv.DictReader(open(PROJECT / "data/tts_cases.csv", encoding="utf-8-sig"))}
    for rnd in range(1, 6):
        blocks = [("sse", "tarika", "T31"), ("ws", "tarika", "T31"), ("sse", "kaveri", "T31"), ("ws", "kaveri", "T31")]
        if rnd <= 3:
            blocks += [("sse", "tarika", "T23"), ("ws1", "tarika", "T23")]
        random.Random(4242 + rnd).shuffle(blocks)
        for transport, v, cid in blocks:
            model, voice = VOICES[v]
            base = f"cmp_{transport.rstrip('1')}_{v}_{cid}_r{rnd}"
            if transport == "sse":
                if saved(base,cid,text[cid],model,voice,"tts_stream"):
                    continue
                r = g.synthesize_stream(cid, text[cid], "en-IN", run_tag=base, voice=voice, model=model, live=args.live)
                print(f"r{rnd} SSE {voice:7s} {cid}: {show(r)}")
            else:
                tags = [base + "_cold"] + ([base + "_warm"] if transport == "ws" else [])
                if all(saved(t,cid,text[cid],model,voice,"tts_ws") for t in tags):
                    continue
                with g.TTSWebSocket(live=args.live) as ws:
                    for t in tags:
                        r = ws.synthesize(cid, text[cid], "en-IN", run_tag=t, voice=voice, model=model)
                        print(f"r{rnd} WS  {voice:7s} {cid} {t.rsplit('_', 1)[1]}: {show(r)}")


if __name__ == "__main__":
    main()
