"""Thin HTTP layer for Gnani Prisma (STT) and Timbre (TTS).

Only request/response handling lives here; scoring and analysis stay in the notebook.

Guarantees:
- No request is sent unless live mode is on (GNANI_LIVE=1 in the environment, or live=True).
- Every attempt is appended to results/attempts.jsonl and its raw body saved under results/raw/
  BEFORE anything else looks at it. Successful TTS audio is saved to results/tts_audio/.
- The API key is read from .env and never written to disk or printed.
- Replay helpers return the latest saved successful result, so analysis can rerun with no API calls.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from budget_guard import reserve as reserve_budget
import numpy as np
import requests
import soundfile as sf
from dotenv import load_dotenv

PROJECT = Path(__file__).resolve().parent
RESULTS = PROJECT / "results"
RAW = RESULTS / "raw"
TTS_AUDIO = RESULTS / "tts_audio"
ATTEMPTS = RESULTS / "attempts.jsonl"

load_dotenv(PROJECT / ".env")

ASR_ENDPOINT = os.getenv("GNANI_ASR_ENDPOINT") or "https://api.vachana.ai/stt/v3"
ASR_MODEL = os.getenv("GNANI_ASR_MODEL") or "prisma-v3.0"
ASR_FORMAT = os.getenv("GNANI_ASR_FORMAT") or "transcribe"
TTS_ENDPOINT = os.getenv("GNANI_TTS_ENDPOINT") or "https://api.vachana.ai/api/v1/tts/inference"
TTS_MODEL = os.getenv("GNANI_TTS_MODEL") or "timbre-v3.0"
TTS_VOICE = os.getenv("GNANI_TTS_VOICE") or "Tarika"
TTS_SAMPLE_RATE = int(os.getenv("GNANI_TTS_SAMPLE_RATE") or 24000)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BACKOFF_S = (1.0, 2.0, 4.0, 8.0)

_session = requests.Session()  # reused connection; logged per attempt


class LiveModeOff(RuntimeError):
    pass


def _key() -> str:
    key = os.getenv("GNANI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GNANI_API_KEY is empty in .env")
    return key


def _require_live(live: bool | None) -> None:
    on = live if live is not None else os.getenv("GNANI_LIVE") == "1"
    if not on:
        raise LiveModeOff("Live mode is off: no request sent. Set GNANI_LIVE=1 or pass live=True to spend credits.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def fingerprint(settings: dict, content: bytes | str = b"") -> str:
    """Identity of a request: effective settings + input content. Cached results are reused only on an exact match."""
    h = hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    h.update(content.encode("utf-8") if isinstance(content, str) else content)
    return h.hexdigest()[:24]


def asr_request(audio_path, language_code: str, fmt: str | None = None, model: str | None = None,
                extra: dict | None = None):
    """(absolute audio path, form data, settings, fingerprint) for one Prisma REST request."""
    path = PROJECT / audio_path
    data = {"model": model or ASR_MODEL, "language_code": language_code, "format": fmt or ASR_FORMAT}
    data.update(extra or {})
    settings = {"endpoint": ASR_ENDPOINT, **data}
    return path, data, settings, fingerprint(settings, path.read_bytes())


def tts_request(text: str, language: str, voice: str | None = None, model: str | None = None, speed: float = 1.0,
                sample_rate: int | None = None, container: str = "wav", endpoint: str | None = None):
    """(payload, settings, fingerprint) for one Timbre request (REST, SSE or WebSocket share the payload shape)."""
    payload = {"text": text, "voice": voice or TTS_VOICE, "model": model or TTS_MODEL, "language": language,
               "speed": speed, "audio_config": {"sample_rate": sample_rate or TTS_SAMPLE_RATE, "num_channels": 1,
                                                "sample_width": 2, "encoding": "linear_pcm", "container": container}}
    settings = {"endpoint": endpoint or TTS_ENDPOINT, **{k: v for k, v in payload.items() if k != "text"}}
    return payload, settings, fingerprint(settings, text)


def _log(record: dict) -> None:
    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    with ATTEMPTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def _error_summary(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    if isinstance(body.get("error"), dict):
        return f"{body['error'].get('type')}: {body['error'].get('message')}"
    if isinstance(body.get("detail"), dict):
        return f"{body['detail'].get('error_code')}: {body['detail'].get('message')}"
    return json.dumps(body, ensure_ascii=False)[:300]


def _post_with_retries(kind: str, case_id: str, run_tag: str, settings: dict, send, fingerprint_: str | None = None, billing_units: float | None = None) -> dict:
    """send(request_id) -> requests.Response. Returns the final attempt record (with 'response')."""
    case_dir = RAW / kind / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    retry_start = time.perf_counter()
    record: dict = {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request_id = f"{case_id}-{run_tag}-a{attempt}-{uuid.uuid4().hex[:8]}"
        started_at = _now()
        t0 = time.perf_counter()
        resp, exc = None, None
        try:
            resp = send(request_id)
            _ = resp.content  # body fully received before the clock stops
        except requests.RequestException as e:
            exc = e
        t1 = time.perf_counter()
        record = {
            "kind": kind, "case_id": case_id, "run_tag": run_tag, "attempt": attempt,
            "request_id": request_id, "started_at": started_at, "latency_ms": round((t1 - t0) * 1000, 1),
            "retry_inclusive_ms": round((t1 - retry_start) * 1000, 1), "settings": settings,
            "http_status": resp.status_code if resp is not None else None,
            "content_type": resp.headers.get("content-type") if resp is not None else None,
            "connection_reused": attempt > 1 or _session_used_before(),
            "fingerprint": fingerprint_, "validation_required": kind == "tts", "billing_units": billing_units,
        }
        stem = request_id
        if exc is not None:
            record.update(ok=False, error=f"{type(exc).__name__}: {exc}"[:300])
        elif resp.status_code == 200:
            record["ok"] = True
        else:
            record.update(ok=False, error=_error_summary(resp))
        if resp is not None:
            if kind == "asr" or resp.status_code != 200:
                body_path = case_dir / f"{stem}.json"
                body_path.write_bytes(resp.content)
            else:
                body_path = case_dir / f"{stem}.bin"
                body_path.write_bytes(resp.content)
            record["raw_path"] = body_path.relative_to(PROJECT).as_posix()
        record["response"] = resp
        _log({k: v for k, v in record.items() if k != "response"})
        status = record["http_status"]
        if record["ok"] or (status is not None and status not in RETRYABLE_STATUS):
            break
        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_S[attempt - 1])
    _mark_session_used()
    return record


_SESSION_USED = False


def _session_used_before() -> bool:
    return _SESSION_USED


def _mark_session_used() -> None:
    global _SESSION_USED
    _SESSION_USED = True


# ------------------------------------------------------------------ ASR
def transcribe(case_id: str, audio_path: str | Path, language_code: str, *, run_tag: str = "run1",
               fmt: str | None = None, model: str | None = None, extra: dict | None = None,
               live: bool | None = None, timeout_s: float = 60.0) -> dict:
    """One Prisma REST transcription with retries. Returns a flat result dict (no response object)."""
    _require_live(live)
    audio_path, data, settings, fp = asr_request(audio_path, language_code, fmt, model, extra)

    def send(request_id):
        with audio_path.open("rb") as fh:
            return _session.post(ASR_ENDPOINT, headers={"X-API-Key-ID": _key(), "X-API-Request-ID": request_id},
                                 data=data, files={"audio_file": (audio_path.name, fh, "audio/wav")},
                                 timeout=(10, timeout_s))

    reserve_budget(PROJECT, "asr", sf.info(audio_path).duration, MAX_ATTEMPTS)
    rec = _post_with_retries("asr", case_id, run_tag, settings, send, fp, sf.info(audio_path).duration)
    resp = rec.pop("response")
    out = {k: v for k, v in rec.items()}
    if rec["ok"]:
        body = resp.json()
        out.update(transcript=body.get("transcript", ""), model_returned=body.get("model"),
                   detected_language_code=body.get("detected_language_code"), truncated=bool(body.get("truncated")),
                   server_processing_s=body.get("processing_time"), server_end_to_end_s=body.get("end_to_end_latency"),
                   api_request_id=body.get("request_id"))
    return out


# ------------------------------------------------------------------ TTS
def synthesize(case_id: str, text: str, language: str, *, run_tag: str = "run1", voice: str | None = None,
               model: str | None = None, speed: float = 1.0, sample_rate: int | None = None,
               live: bool | None = None, timeout_s: float = 120.0) -> dict:
    """One Timbre REST synthesis. Valid audio is decoded, measured and saved to results/tts_audio/."""
    _require_live(live)
    payload, settings, fp = tts_request(text, language, voice, model, speed, sample_rate)

    def send(request_id):
        return _session.post(TTS_ENDPOINT, headers={"X-API-Key-ID": _key(), "X-API-Request-ID": request_id},
                             json=payload, timeout=(10, timeout_s))

    reserve_budget(PROJECT, "tts", len(text), MAX_ATTEMPTS)
    rec = _post_with_retries("tts", case_id, run_tag, settings, send, fp, len(text))
    resp = rec.pop("response")
    out = {k: v for k, v in rec.items()}
    out.update(input_text=text, text_characters=len(text), text_words=len(text.split()))
    if rec["ok"]:
        try:
            samples, sr = sf.read(io.BytesIO(resp.content), dtype="float32", always_2d=True)
        except Exception as e:  # undecodable body is a failure, not a result
            out.update(ok=False, error=f"decode failed: {e}"[:300])
            _log({**{k: v for k, v in out.items()}, "event": "decode_failure"})
            return out
        duration = len(samples) / sr if sr else 0.0
        TTS_AUDIO.mkdir(parents=True, exist_ok=True)
        audio_path = TTS_AUDIO / f"{rec['request_id']}.wav"
        audio_path.write_bytes(resp.content)
        peak = float(abs(samples).max()) if len(samples) else 0.0
        out.update(audio_path=audio_path.relative_to(PROJECT).as_posix(), sample_rate_hz=sr,
                   audio_duration_s=round(duration, 3), peak=round(peak, 4),
                   rtf=round(out["latency_ms"] / 1000 / duration, 4) if duration > 0 else None)
        if duration <= 0 or peak < 1e-3:
            out.update(ok=False, error="empty or silent audio")
        _log({**out, "event": "audio_validated"})
    return out


# ------------------------------------------------------------------ TTS streaming (SSE)
TTS_SSE_ENDPOINT = os.getenv("GNANI_TTS_SSE_ENDPOINT") or "https://api.vachana.ai/api/v1/tts/sse"


def playback_stalls(chunks: list[dict]) -> dict:
    """Simulate playback starting when the first audio arrives: count gaps where the next chunk is late."""
    stalls, stall_s, play_end = 0, 0.0, None
    for c in chunks:
        if play_end is None:
            play_end = c["t_s"] + c["dur_s"]
            continue
        if c["t_s"] > play_end + 1e-3:
            stalls += 1
            stall_s += c["t_s"] - play_end
            play_end = c["t_s"]
        play_end += c["dur_s"]
    # Earliest playback start that never runs out of audio: every chunk must arrive before its play position.
    offset, start = 0.0, 0.0
    for c in chunks:
        start = max(start, c["t_s"] - offset)
        offset += c["dur_s"]
    return {"stalls": stalls, "stall_s": round(stall_s, 3),
            "stall_free_start_ms": round(start * 1000, 1) if chunks else None}


def synthesize_stream(case_id: str, text: str, language: str, *, run_tag: str = "run1", voice: str | None = None,
                      model: str | None = None, speed: float = 1.0, sample_rate: int | None = None,
                      live: bool | None = None, timeout_s: float = 120.0) -> dict:
    """One Timbre SSE request. Raw 16-bit PCM chunks, so each chunk is playable on arrival.

    Times are client-side seconds from dispatch: headers, first `start` event, first audio chunk (TTFA),
    and the `complete` event. Chunk arrival times and durations are saved for stall analysis.
    One attempt only: a stream that fails part-way is a failure, not something to retry silently."""
    _require_live(live)
    sr = sample_rate or TTS_SAMPLE_RATE
    payload = {"text": text, "voice": voice or TTS_VOICE, "model": model or TTS_MODEL, "language": language,
               "speed": speed, "audio_config": {"sample_rate": sr, "num_channels": 1, "sample_width": 2,
                                                "encoding": "linear_pcm", "container": "raw"}}
    reserve_budget(PROJECT, "tts", len(text))
    request_id = f"{case_id}-{run_tag}-sse-{uuid.uuid4().hex[:8]}"
    rec = {"kind": "tts_stream", "case_id": case_id, "run_tag": run_tag, "attempt": 1, "request_id": request_id,
           "started_at": _now(), "settings": {"endpoint": TTS_SSE_ENDPOINT, **{k: v for k, v in payload.items() if k != "text"}},
           "connection_reused": _session_used_before(), "input_text": text, "text_characters": len(text)}
    rec["fingerprint"] = fingerprint(rec["settings"], text)
    chunks, pcm, events, error = [], bytearray(), [], None
    t0 = time.perf_counter()
    t_headers = t_start = t_first = t_complete = None
    try:
        with _session.post(TTS_SSE_ENDPOINT, headers={"X-API-Key-ID": _key(), "X-API-Request-ID": request_id,
                                                      "Accept": "text/event-stream"},
                           json=payload, stream=True, timeout=(10, timeout_s)) as resp:
            t_headers = time.perf_counter() - t0
            rec["http_status"] = resp.status_code
            if resp.status_code != 200:
                error = _error_summary(resp)
            else:
                event, data_lines = None, []
                for line in resp.iter_lines(decode_unicode=True):
                    if line is None:
                        continue
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())
                    elif line == "" and (event or data_lines):
                        now = time.perf_counter() - t0
                        data = json.loads("".join(data_lines)) if data_lines else {}
                        events.append({"event": event, "t_s": round(now, 4)})
                        if event == "start" and t_start is None:
                            t_start = now
                        elif event == "chunk" and data.get("audio"):
                            raw = base64.b64decode(data["audio"])
                            pcm.extend(raw)
                            if t_first is None:
                                t_first = now
                            chunks.append({"index": data.get("chunk_index"), "t_s": round(now, 4), "bytes": len(raw),
                                           "dur_s": round(len(raw) / 2 / sr, 4)})
                        elif event == "complete":
                            t_complete = now
                        elif event == "error":
                            error = json.dumps(data, ensure_ascii=False)[:300]
                        event, data_lines = None, []
    except requests.RequestException as e:
        error = f"{type(e).__name__}: {e}"[:300]
    t_end = time.perf_counter() - t0
    _mark_session_used()
    audio_s = len(pcm) / 2 / sr
    out_dir = RAW / "tts_stream" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    timeline = out_dir / f"{request_id}.json"
    timeline.write_text(json.dumps({"events": events, "chunks": chunks}, indent=1), encoding="utf-8")
    rec.update(ok=error is None and t_complete is not None and audio_s > 0, error=error,
               headers_ms=None if t_headers is None else round(t_headers * 1000, 1),
               start_event_ms=None if t_start is None else round(t_start * 1000, 1),
               ttfa_ms=None if t_first is None else round(t_first * 1000, 1),
               complete_ms=None if t_complete is None else round(t_complete * 1000, 1),
               latency_ms=round(t_end * 1000, 1), chunks=len(chunks), audio_duration_s=round(audio_s, 3),
               first_chunk_audio_s=chunks[0]["dur_s"] if chunks else None,
               rtf=round(t_end / audio_s, 4) if audio_s else None, timeline_path=timeline.relative_to(PROJECT).as_posix(),
               **playback_stalls(chunks))
    if error is None and t_complete is None:
        rec["error"] = "stream ended without a complete event"
    if pcm:
        wav = TTS_AUDIO / "stream" / f"{request_id}.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        sf.write(wav, np.frombuffer(bytes(pcm), dtype="<i2"), sr, subtype="PCM_16")
        rec["audio_path"] = wav.relative_to(PROJECT).as_posix()
    _log(rec)
    return rec


# ------------------------------------------------------------------ TTS realtime (WebSocket)
TTS_WS_ENDPOINT = os.getenv("GNANI_TTS_WS_ENDPOINT") or "wss://api.vachana.ai/api/v1/tts"


class TTSWebSocket:
    """One WebSocket connection that can carry several sequential synthesis requests (cold first, then warm).

    with TTSWebSocket(live=True) as ws:
        first = ws.synthesize("T31", text, "en-IN", run_tag="ws_r1_cold")
        again = ws.synthesize("T31", text, "en-IN", run_tag="ws_r1_warm")
    """

    def __init__(self, live: bool | None = None, timeout_s: float = 60.0):
        _require_live(live)
        self.timeout_s = timeout_s
        self.ws = None
        self.connect_ms = None
        self.requests_sent = 0

    def __enter__(self):
        import websocket  # websocket-client
        t0 = time.perf_counter()
        self.ws = websocket.create_connection(TTS_WS_ENDPOINT, header=[f"X-API-Key-ID: {_key()}"], timeout=self.timeout_s)
        self.connect_ms = round((time.perf_counter() - t0) * 1000, 1)
        return self

    def __exit__(self, *exc):
        try:
            self.ws.close()
        except Exception:
            pass

    def synthesize(self, case_id: str, text: str, language: str, *, run_tag: str, voice: str | None = None,
                   model: str | None = None, speed: float = 1.0, sample_rate: int | None = None) -> dict:
        sr = sample_rate or TTS_SAMPLE_RATE
        payload = {"text": text, "voice": voice or TTS_VOICE, "model": model or TTS_MODEL, "language": language,
                   "speed": speed, "audio_config": {"sample_rate": sr, "num_channels": 1, "sample_width": 2,
                                                    "encoding": "linear_pcm", "container": "raw"}}
        reserve_budget(PROJECT, "tts", len(text))
        warm = self.requests_sent > 0
        rec = {"kind": "tts_ws", "case_id": case_id, "run_tag": run_tag, "attempt": 1, "started_at": _now(),
               "settings": {"endpoint": TTS_WS_ENDPOINT, **{k: v for k, v in payload.items() if k != "text"}},
               "connection": "warm (reused socket)" if warm else "cold (new socket)",
               "connect_ms": None if warm else self.connect_ms, "input_text": text, "text_characters": len(text)}
        request_id = f"{case_id}-{run_tag}-ws-{uuid.uuid4().hex[:8]}"
        rec.update(request_id=request_id, fingerprint=fingerprint(rec["settings"], text))
        chunks, pcm, events, error = [], bytearray(), [], None
        t_start = t_first = t_complete = None
        t0 = time.perf_counter()
        try:
            self.ws.send(json.dumps(payload))
            self.requests_sent += 1
            while True:
                msg = json.loads(self.ws.recv())
                now = time.perf_counter() - t0
                typ = msg.get("type")
                events.append({"event": typ, "t_s": round(now, 4)})
                if typ == "start" and t_start is None:
                    t_start = now
                    rec["server_request_id"] = msg.get("request_id")
                elif typ == "audio" and (msg.get("data") or {}).get("audio"):
                    raw = base64.b64decode(msg["data"]["audio"])
                    pcm.extend(raw)
                    if t_first is None:
                        t_first = now
                    chunks.append({"index": msg["data"].get("chunk_index"), "t_s": round(now, 4), "bytes": len(raw),
                                   "dur_s": round(len(raw) / 2 / sr, 4)})
                elif typ == "complete" and t_start is None and not chunks:
                    events[-1]["event"] = "stale_complete_ignored"   # leftover from the previous request on this socket
                    rec["stale_messages"] = rec.get("stale_messages", 0) + 1
                elif typ == "complete":
                    t_complete = now
                    break
                elif typ == "error":
                    error = (msg.get("message") or json.dumps(msg))[:300]
                    break
        except Exception as e:  # socket closed / timeout: a failure, recorded as such
            error = f"{type(e).__name__}: {e}"[:300]
        t_end = time.perf_counter() - t0
        audio_s = len(pcm) / 2 / sr
        out_dir = RAW / "tts_ws" / case_id
        out_dir.mkdir(parents=True, exist_ok=True)
        timeline = out_dir / f"{request_id}.json"
        timeline.write_text(json.dumps({"events": events, "chunks": chunks}, indent=1), encoding="utf-8")
        rec.update(ok=error is None and t_complete is not None and audio_s > 0, error=error,
                   start_event_ms=None if t_start is None else round(t_start * 1000, 1),
                   ttfa_ms=None if t_first is None else round(t_first * 1000, 1),
                   complete_ms=None if t_complete is None else round(t_complete * 1000, 1),
                   latency_ms=round(t_end * 1000, 1), chunks=len(chunks), audio_duration_s=round(audio_s, 3),
                   first_chunk_audio_s=chunks[0]["dur_s"] if chunks else None,
                   rtf=round(t_end / audio_s, 4) if audio_s else None,
                   timeline_path=timeline.relative_to(PROJECT).as_posix(), **playback_stalls(chunks))
        if pcm:
            wav = TTS_AUDIO / "ws" / f"{request_id}.wav"
            wav.parent.mkdir(parents=True, exist_ok=True)
            sf.write(wav, np.frombuffer(bytes(pcm), dtype="<i2"), sr, subtype="PCM_16")
            rec["audio_path"] = wav.relative_to(PROJECT).as_posix()
        _log(rec)
        return rec


# ------------------------------------------------------------------ replay
def attempts(kind: str | None = None) -> list[dict]:
    if not ATTEMPTS.exists():
        return []
    rows = [json.loads(line) for line in ATTEMPTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if kind is None or r["kind"] == kind]


def latest_success(kind: str, case_id: str, run_tag: str = "run1", fingerprint: str | None = None,
                   legacy_settings: dict | None = None) -> dict | None:
    """Latest successful saved attempt for a case, parsed from disk (no network).

    Replay/analysis calls pass no fingerprint and get the saved evidence. Callers deciding whether to SKIP a paid request
    pass the fingerprint of the request they would send: a saved result is reused only if it was made with exactly the
    same settings and input. Legacy records are available only for explicit historical replay without a fingerprint."""
    final = {}
    for i, r in enumerate(attempts(kind)):
        if r["case_id"] == case_id and r["run_tag"] == run_tag:
            final[r.get("request_id", f"legacy-{i}")] = r
    hits = [r for r in final.values() if r.get("ok") and
            (not r.get("validation_required") or r.get("event") == "audio_validated")]

    if fingerprint is not None:
        hits = [r for r in hits if r.get("fingerprint") == fingerprint
]
    if not hits:
        return None
    rec = dict(hits[-1])
    if kind == "asr":
        body = json.loads((PROJECT / rec["raw_path"]).read_text(encoding="utf-8"))
        rec.update(transcript=body.get("transcript", ""), model_returned=body.get("model"),
                   detected_language_code=body.get("detected_language_code"), truncated=bool(body.get("truncated")),
                   server_processing_s=body.get("processing_time"), server_end_to_end_s=body.get("end_to_end_latency"))
    return rec


def stream_success(kind, cid, tag, text, language, **settings):
    endpoint = TTS_WS_ENDPOINT if kind == "tts_ws" else TTS_SSE_ENDPOINT
    _, _, fp = tts_request(text, language, container="raw", endpoint=endpoint, **settings)
    return latest_success(kind, cid, tag, fingerprint=fp)
