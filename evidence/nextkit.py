"""Small helpers for gnani_next_stages.ipynb.

- Scoring is the same as gnani_evaluation.ipynb (sections 3-4): Levenshtein WER/CER, normalisation v2.
- Next-stage calls are logged to results/next/ (own attempts.jsonl, raw/, audio/), so the main benchmark is untouched.
- A paid call is sent only when GNANI_LIVE=1 and no saved success has the same request fingerprint.
"""
import json, os, re, threading, time, unicodedata
from pathlib import Path

import gnani_api as g
import gemini_judge as gj

NEXT = g.PROJECT / "results" / "next"
g.ATTEMPTS, g.RAW, g.TTS_AUDIO = NEXT / "attempts.jsonl", NEXT / "raw", NEXT / "audio"
gj.RAW = NEXT / "judge"
LIVE = os.getenv("GNANI_LIVE") == "1"

_lock, _log, _attempts = threading.RLock(), g._log, g.attempts       # N9 sends in parallel: one reader/writer at a time
def _locked(f):
    def run(*a, **kw):
        with _lock: return f(*a, **kw)
    return run
g._log, g.attempts = _locked(_log), _locked(_attempts)


# ---------------------------------------------------------------- scoring (copied from the main notebook)
def edit_counts(ref, hyp):
    n, m = len(ref), len(hyp)
    d = [[i + j if i * j == 0 else 0 for j in range(m + 1)] for i in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i-1][j] + 1, d[i][j-1] + 1, d[i-1][j-1] + (ref[i-1] != hyp[j-1]))
    return d[n][m]


def norm(text):
    t = unicodedata.normalize("NFC", text).casefold().replace("−", "-")
    t = "".join(str(unicodedata.digit(c)) if c.isdigit() and unicodedata.digit(c, None) is not None else c for c in t)
    out = []
    for i, c in enumerate(t):
        p, n = (t[i-1] if i else ""), (t[i+1] if i + 1 < len(t) else "")
        keep = c in "%₹" or unicodedata.category(c)[0] in "LNM" or c.isspace() \
            or (c in ".:" and p.isdigit() and n.isdigit()) or (c == "-" and n.isdigit() and not p.isalnum())
        out.append(c if keep else " ")
    return " ".join("".join(out).split())


def score(ref, hyp):
    r, h = norm(ref), norm(hyp)
    return {"ref_words": len(r.split()), "word_edits": edit_counts(r.split(), h.split()),
            "ref_chars": len(r), "char_edits": edit_counts(list(r), list(h))}


def wer_table(df, by=None):
    """Corpus WER/CER (edits summed over clips / reference length summed), optionally per group."""
    import pandas as pd
    s = pd.DataFrame([score(r, h if isinstance(h, str) else "") for r, h in zip(df["reference"], df["hypothesis"])],
                     index=df.index)
    keys = [df[c] for c in by] if isinstance(by, list) else df[by] if by else pd.Series("all", index=df.index)
    grp = s.groupby(keys)
    t = grp.sum()
    t.insert(0, "clips", grp.size())
    t["WER"], t["CER"] = (t.word_edits / t.ref_words).round(4), (t.char_edits / t.ref_chars).round(4)
    return t[["clips", "ref_words", "WER", "CER"]]


LATIN = re.compile(r"[a-z]")
latin_words = lambda text: sum(bool(LATIN.search(w)) for w in norm(text).split())


# ---------------------------------------------------------------- cached calls
def asr(cid, path, lang, tag="run1", **kw):
    """Prisma REST. kw: model, fmt, extra (e.g. {"keyterms": json}). Reused when the fingerprint matches."""
    _, _, _, fp = g.asr_request(path, lang, kw.get("fmt"), kw.get("model"), kw.get("extra"))
    hit = g.latest_success("asr", cid, tag, fingerprint=fp)
    if hit or not LIVE:
        return hit or {"ok": False, "error": "not run (live off)"}
    return g.transcribe(cid, path, lang, run_tag=tag, live=True, **kw)


def tts(cid, text, lang, tag="run1", **kw):
    payload, settings, fp = g.tts_request(text, lang, kw.get("voice"), kw.get("model"), kw.get("speed", 1.0), kw.get("sample_rate"))
    hit = g.latest_success("tts", cid, tag, fingerprint=fp)
    if hit:
        hit.setdefault("audio_path", f"results/next/audio/{cid}.wav" if tag == "run1" else f"results/next/audio/{cid}__{tag}.wav")
    if hit or not LIVE:
        return hit or {"ok": False, "error": "not run (live off)"}
    return g.synthesize(cid, text, lang, run_tag=tag, live=True, **kw)


def stt_stream(cid, path, lang, tag="ws", **headers):
    """Prisma realtime WebSocket at real-time pace: 1,024-byte frames every 512/rate s, then 1.5 s of silence.

    Returns transcripts with arrival time and end-of-audio-to-final latency. Saved and reused like REST."""
    import soundfile as sf, websocket
    samples, rate = sf.read(g.PROJECT / path, dtype="int16")
    pcm = samples.tobytes()
    hdr = {"model": "prisma-v3.0", "language_code": lang, "format": "transcribe", "x-sample-rate": str(rate), **headers}
    fp = g.fingerprint({"endpoint": "stt/v3/stream", **hdr}, pcm)
    out_file = NEXT / "raw" / "stt_stream" / cid / f"{tag}__{fp}.json"
    hit = [r for r in g.attempts("stt_stream") if r["case_id"] == cid and r["run_tag"] == tag and r.get("fingerprint") == fp and r.get("ok")]
    if hit or not LIVE:
        return json.loads((g.PROJECT / hit[-1].get("raw_path", NEXT / "raw" / "stt_stream" / cid / f"{tag}.json")).read_text(encoding="utf-8")) if hit else {"ok": False, "error": "not run (live off)"}
    frame, step = 1024, 512 / rate
    pcm += bytes(frame - len(pcm) % frame) + bytes(int(1.5 / step) * frame)
    speech_end = len(pcm) / 2 / rate - 1.5
    t0 = time.perf_counter()
    ws = websocket.create_connection("wss://api.vachana.ai/stt/v3/stream", timeout=20,
                                     header=[f"x-api-key-id: {g._key()}", *[f"{k}: {v}" for k, v in hdr.items()]])
    connect_ms, msgs = (time.perf_counter() - t0) * 1000, []
    ws.settimeout(0.001)
    t0 = time.perf_counter()
    for i in range(0, len(pcm), frame):
        try: ws.send_binary(pcm[i:i + frame])
        except Exception: break                                               # server closed (error message kept)
        while time.perf_counter() - t0 < (i // frame + 1) * step:          # keep real-time cadence, read as we go
            try: msgs.append({**json.loads(ws.recv()), "t_s": time.perf_counter() - t0})
            except Exception: time.sleep(0.002)
    ws.settimeout(4)                                                          # drain: stop after 4 s of quiet
    while True:
        try: msgs.append({**json.loads(ws.recv()), "t_s": time.perf_counter() - t0})
        except Exception: break
    ws.close()
    finals = [m for m in msgs if m.get("type") == "transcript"]
    rec = {"ok": bool(finals), "kind": "stt_stream", "case_id": cid, "run_tag": tag, "fingerprint": fp,
           "connect_ms": round(connect_ms, 1), "speech_end_s": round(speech_end, 3),
           "transcript": " ".join(m.get("text", "") for m in finals),
           "first_final_s": round(finals[0]["t_s"], 3) if finals else None,
           "last_final_after_speech_ms": round((finals[-1]["t_s"] - speech_end) * 1000, 1) if finals else None,
           "server_latency_ms": [m.get("latency") for m in finals], "segments": len(finals),
           "errors": [m.get("message") for m in msgs if m.get("type") == "error"], "messages": msgs}
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    rec["raw_path"] = out_file.relative_to(g.PROJECT).as_posix()
    g._log({k: v for k, v in rec.items() if k != "messages"} | {"started_at": g._now()})
    return rec
