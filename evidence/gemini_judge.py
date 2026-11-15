"""Gemini as an independent listening assistant (judge). Never used as the system under test.

Rules
- Blind first: every clip is transcribed WITHOUT the expected text; comparison happens in a second call that sees the
  blind transcript, the expected text and the audio again.
- Every response is cached under results/judge/raw/<task>/<id>.json and reused (no repeated charges).
- Judge output is evidence to triage human listening, not ground truth. Calibration (scripts/judge_calibrate.py)
  measures agreement with human marks and with planted errors before any judge result is used.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT = Path(__file__).resolve().parent
RAW = PROJECT / "results" / "judge" / "raw"
load_dotenv(PROJECT / ".env")
MODEL = os.getenv("GEMINI_JUDGE_MODEL") or "gemini-3.8-flash"
LANG_NAMES = {"en-IN": "Indian English", "hi-IN": "Hindi", "te-IN": "Telugu", "ta-IN": "Tamil", "kn-IN": "Kannada",
              "mr-IN": "Marathi", "hi-IN,en-IN": "Hindi-English (Hinglish)", "auto": "the language(s) heard",
              "hi-en": "Hindi-English (Hinglish)", "": "the language(s) heard"}

_client = None


def client():
    global _client
    if _client is None:
        from google import genai
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is empty in .env")
        _client = genai.Client(api_key=key)
    return _client


def _ask(task: str, item_id: str, audio_path: Path, prompt: str, live: bool) -> dict:
    """One cached Gemini call with audio + text, JSON reply. Returns the parsed reply plus metadata.

    The cache is keyed by a fingerprint of model + prompt (which embeds targets/reference) + audio bytes, so changing
    any of them is a miss. Pre-fingerprint cache files are reused only when GEMINI_TRUST_LEGACY_CACHE=1."""
    import hashlib
    path = Path(audio_path)
    path = path if path.is_absolute() else PROJECT / path
    audio = path.read_bytes()
    fp = hashlib.sha256(MODEL.encode() + b"\0" + prompt.encode("utf-8") + b"\0" + audio).hexdigest()[:24]
    safe = re.sub(r'[^A-Za-z0-9_.-]', '_', item_id)
    cache, legacy = RAW / task / f"{safe}__{fp[:12]}.json", RAW / task / f"{safe}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    if legacy.exists():
        old = json.loads(legacy.read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp or (old.get("fingerprint") is None and os.getenv("GEMINI_TRUST_LEGACY_CACHE") == "1"):
            return old
    if not live:
        raise RuntimeError(f"not cached (or cache fingerprint differs) and live=False: {task}/{item_id}")
    from google.genai import types
    resp, data, last_err, t0 = None, None, None, time.perf_counter()
    for attempt in range(1, 5):  # retry only the API call and JSON parsing
        t0 = time.perf_counter()
        try:
            resp = client().models.generate_content(
                model=MODEL,
                contents=[types.Part.from_bytes(data=audio, mime_type="audio/wav"), prompt],
                config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"))
            data = json.loads(resp.text or "")
            break
        except Exception as e:  # rate limits / transient errors / malformed JSON
            last_err = e
            time.sleep(2 * attempt)
    if data is None:
        raise RuntimeError(f"{task}/{item_id} failed after retries: {last_err}")
    usage = getattr(resp, "usage_metadata", None)
    out = {"task": task, "id": item_id, "model": MODEL, "fingerprint": fp, "audio": path.relative_to(PROJECT).as_posix(),
           "latency_ms": round((time.perf_counter() - t0) * 1000), "reply": data,
           "tokens": {"prompt": getattr(usage, "prompt_token_count", None),
                      "output": getattr(usage, "candidates_token_count", None)} if usage else None}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# ------------------------------------------------------------------ ASR side
def transcribe_blind(item_id: str, audio_path, language: str, live: bool = False) -> dict:
    lang = LANG_NAMES.get(language, language)
    prompt = (f"You are a careful human transcriber. Transcribe exactly what is spoken in this audio ({lang}). "
              "Write every word that is actually said, including false starts and repetitions; do not correct grammar "
              "or guess unclear words. Write Hindi and Marathi in Devanagari, Telugu, Tamil and Kannada in their own "
              "scripts, and English words in Latin letters. Write numbers as digits. If no speech is audible, return an "
              'empty transcript. Reply with JSON only: {"transcript": str, "language": str, '
              '"no_speech": bool, "unclear": [str]} where "unclear" lists words you could not hear confidently.')
    return _ask("asr_blind", item_id, audio_path, prompt, live)


def verify_reference(item_id: str, audio_path, language: str, reference: str, blind: str, live: bool = False) -> dict:
    lang = LANG_NAMES.get(language, language)
    prompt = (f"You are checking a reference transcript for a speech-recognition test ({lang}). Listen to the audio "
              f"again carefully.\nReference transcript: {reference}\nYour earlier blind transcript: {blind}\n"
              "Decide whether the reference matches the spoken words exactly. IGNORE differences in punctuation, "
              "capitalisation, word spacing or word-joining (e.g. compound words split differently), whether an English "
              "loanword is written in Latin or native script, and digits versus number words for the same number. "
              "Do NOT ignore any different, missing or extra word, or any different number or digit. "
              'Reply with JSON only: {"matches": bool, "differences": [{"reference": str, "heard": str}], '
              '"confidence": "high"|"medium"|"low"}.')
    return _ask("asr_verify", item_id, audio_path, prompt, live)


# ------------------------------------------------------------------ TTS side
def tts_blind(item_id: str, audio_path, language: str, live: bool = False) -> dict:
    lang = LANG_NAMES.get(language, language)
    prompt = (f"This is synthetic speech ({lang}). Write down exactly what you hear, word for word, as a listener "
              "would. Write numbers the way they are SPOKEN (e.g. 'one lakh twenty five thousand', 'zero zero four two', "
              "'minus two point five percent'), spell out letter-by-letter acronyms with spaces (e.g. 'K Y C'), and keep "
              "native scripts for Indian-language words. If a word is unclear, write your best guess in [brackets]. "
              'Reply with JSON only: {"heard": str, "unclear": [str]}.')
    return _ask("tts_blind", item_id, audio_path, prompt, live)


def tts_judge(item_id: str, audio_path, language: str, text: str, targets: list, variants: dict, blind: str,
              live: bool = False) -> dict:
    lang = LANG_NAMES.get(language, language)
    spec = [{"id": t["id"], "written": t["written"], "must_hear": t["must_hear"],
             "accept": variants.get(t["id"], {}).get("accept", []), "not_correct": variants.get(t["id"], {}).get("reject", [])}
            for t in targets]
    prompt = (f"You are a strict listening judge for a text-to-speech test ({lang}). Listen to the audio again.\n"
              f"Text sent to the TTS system: {text}\nYour earlier blind transcription: {blind}\n"
              f"Targets to check (decided before the audio existed): {json.dumps(spec, ensure_ascii=False)}\n"
              "For each target, decide from what is AUDIBLE only: 'correct' if what is spoken matches an accepted reading "
              "or is unambiguously equivalent; 'wrong' if it matches a not-correct reading or a different value/word is "
              "spoken; 'ambiguous' if you cannot tell clearly. A missing sign, a missing 'not', lost leading zeros or a "
              "different number is 'wrong'. Also rate naturalness 1-5 (1 robotic, 3 understandable but synthetic, "
              "5 natural and fluent) and prosody 1-5, and say whether any words are missing, added or repeated. "
              'Reply with JSON only: {"targets": [{"id": str, "result": "correct"|"wrong"|"ambiguous", "heard": str}], '
              '"content_complete": bool, "naturalness_1to5": int, "prosody_1to5": int, "artifacts": [str], "comment": str}.')
    return _ask("tts_judge", item_id, audio_path, prompt, live)
