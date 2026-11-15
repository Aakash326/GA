"""Add Tamil, Kannada and Marathi coverage (ASR clips + TTS prompts). No Gnani API calls.

Appends to data/asr_manifest.csv and data/tts_cases.csv; existing rows and review fields are untouched.
Idempotent: rows that already exist are not duplicated, downloaded audio is cached.

ASR, per language (selected with a fixed seed before any model output exists):
  8 clean (distinct speakers where possible), 3 clean containing digits, and 1 each recorded in
  background speech, media noise and traffic noise -> 14 clips x 3 languages = 42.
TTS, per language: the same six messages (plain, amount, date, ID, English-mixed, negation) -> 18 prompts.
"""
import csv
import hashlib
import io
import json
import random
import re
import sys
from pathlib import Path

import fsspec
import pandas as pd
import pyarrow.parquet as pq

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
import prepare_asr_data as prep  # noqa: E402

SEED = 20261115
LOCALES = {"ta_in": ("TA", "ta-IN"), "kn_in": ("KN", "kn-IN"), "mr_in": ("MR", "mr-IN")}
INDEX = PROJECT / "data" / "sources" / "svq_index_ta_kn_mr.csv"
LATIN = re.compile(r"[A-Za-z]")
DIGIT = re.compile(r"\d")


def read(path):
    with (PROJECT / path).open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return reader.fieldnames, list(reader)


def write(path, fields, rows):
    tmp = PROJECT / (path + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(PROJECT / path)


def build_index() -> pd.DataFrame:
    if INDEX.exists():
        return pd.read_csv(INDEX)
    frames = []
    for loc in LOCALES:
        for env in ("clean", "background_speech", "media_noise", "traffic_noise"):
            name = f"utts_{loc}_{env}.parquet"
            with fsspec.open(prep.SVQ_BASE + name, "rb", block_size=2**20) as fh:
                t = pq.ParquetFile(fh).read(columns=["utt_id", "locale", "speaker_id", "speaker_age",
                                                      "speaker_gender", "environment", "text"])
            d = t.to_pandas()
            d["file"], d["row"] = name, range(len(d))
            frames.append(d)
            print(f"  indexed {name}: {len(d)} rows, {d.speaker_id.nunique()} speakers")
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(INDEX, index=False, encoding="utf-8")
    return df


def select(df: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    rng = random.Random(SEED)
    picks = []
    for loc, (short, _) in LOCALES.items():
        used = set()
        base = df[(df.locale == loc) & ~df.text.str.contains(LATIN)]
        plan = [("CL", base[(base.environment == "clean") & ~base.text.str.contains(DIGIT)], 8, "clean"),
                ("NUM", base[(base.environment == "clean") & base.text.str.contains(DIGIT)], 3, "numbers"),
                ("BG", base[(base.environment == "background_speech") & ~base.text.str.contains(DIGIT)], 1, "real_noise"),
                ("MEDIA", base[(base.environment == "media_noise") & ~base.text.str.contains(DIGIT)], 1, "real_noise"),
                ("TRAFFIC", base[(base.environment == "traffic_noise") & ~base.text.str.contains(DIGIT)], 1, "real_noise")]
        for tag, pool, n, category in plan:
            for i, r in enumerate(prep.pick_distinct_speakers(pool, n, rng, used), 1):
                cat = f"clean_{short.lower()}" if category == "clean" else category
                picks.append((f"LANG-{short}-{tag}-{i:02d}", cat, r))
    return picks


def asr(fields, rows):
    have = {r["clip_id"] for r in rows}
    df = build_index()
    picks = select(df)
    todo = [p for p in picks if p[0] not in have]
    if not todo:
        print("ASR: nothing to add")
        return rows
    blobs = prep.fetch_svq_audio([r for _, _, r in todo])
    for cid, category, r in todo:
        dest = prep.AUDIO / f"{cid}.wav"
        if not dest.exists():
            prep.write_wav(dest, prep.load_mono(io.BytesIO(blobs[r.utt_id])), prep.TARGET_SR)
        short, lang = LOCALES[r.locale]
        env = r.environment
        row = {f: "" for f in fields}
        info = prep.sf.info(dest)
        row.update(clip_id=cid, selected="true", category=category,
                   tags=f"added_language;{short.lower()};{env}" + (";numbers" if category == "numbers" else ""),
                   source_id=cid, speaker_id=r.speaker_id, language=lang, model="prisma-v3.0", output_mode="transcribe",
                   sample_rate_hz=info.samplerate, duration_s=round(info.duration, 3), input_path=f"data/audio/{cid}.wav",
                   source_dataset="google/svq 1.0.0", source_ref=f"{r.file}#{r.utt_id}", source_or_prompt=r.text,
                   reference_transcript=r.text,
                   reference_origin="dataset text, not individually checked (no listener for this language yet)",
                   human_reference_verified="false", is_no_speech="false", license_or_consent=prep.SVQ_LICENSE,
                   input_sha256=prep.sha256(dest), notes=f"{env}; {r.speaker_gender}, age {r.speaker_age}. Added for language coverage.",
                   evaluation_group=r.speaker_id)
        row["evaluation_split"] = "holdout" if int(hashlib.sha256(r.speaker_id.encode()).hexdigest()[:8], 16) % 5 == 0 else "exploration"
        rows.append(row)
    print(f"ASR: added {len(todo)} clips")
    return rows


# ---------------------------------------------------------------- TTS
MESSAGES = {  # (case suffix, category, text by language)
    "plain": ("additional_controls", {
        "ta-IN": "உங்கள் கோரிக்கை பெறப்பட்டது. நாளை உங்களைத் தொடர்பு கொள்வோம்.",
        "kn-IN": "ನಿಮ್ಮ ವಿನಂತಿಯನ್ನು ಸ್ವೀಕರಿಸಲಾಗಿದೆ. ನಾಳೆ ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸುತ್ತೇವೆ.",
        "mr-IN": "तुमची विनंती मिळाली आहे. आम्ही उद्या तुमच्याशी संपर्क साधू."}),
    "amount": ("numeric", {
        "ta-IN": "உங்கள் இருப்பு ₹1,25,450.",
        "kn-IN": "ನಿಮ್ಮ ಬ್ಯಾಲೆನ್ಸ್ ₹1,25,450 ಆಗಿದೆ.",
        "mr-IN": "तुमची शिल्लक ₹1,25,450 आहे."}),
    "date": ("numeric", {
        "ta-IN": "உங்கள் கட்டணத்தை நவம்பர் 23 அன்று செலுத்த வேண்டும்.",
        "kn-IN": "ನಿಮ್ಮ ಪಾವತಿ ನವೆಂಬರ್ 23 ರಂದು ಬಾಕಿ ಇದೆ.",
        "mr-IN": "तुमचे पेमेंट 23 नोव्हेंबरला देय आहे."}),
    "id": ("identifiers", {
        "ta-IN": "உங்கள் குறிப்பு எண் 004291.",
        "kn-IN": "ನಿಮ್ಮ ಉಲ್ಲೇಖ ಸಂಖ್ಯೆ 004291.",
        "mr-IN": "तुमचा संदर्भ क्रमांक 004291 आहे."}),
    "mixed": ("code_switching", {
        "ta-IN": "உங்கள் KYC pending ஆக உள்ளது, இன்றே complete செய்யுங்கள்.",
        "kn-IN": "ನಿಮ್ಮ KYC pending ಆಗಿದೆ, ಇವತ್ತೇ complete ಮಾಡಿ.",
        "mr-IN": "तुमचे KYC pending आहे, कृपया आज complete करा."}),
    "negation": ("prosody", {
        "ta-IN": "உங்கள் OTP-ஐ யாருடனும் பகிர வேண்டாம்.",
        "kn-IN": "ನಿಮ್ಮ OTP ಅನ್ನು ಯಾರೊಂದಿಗೂ ಹಂಚಿಕೊಳ್ಳಬೇಡಿ.",
        "mr-IN": "तुमचा OTP कोणालाही सांगू नका."}),
}
NEG_WORD = {"ta-IN": ("வேண்டாம்", "vendaam"), "kn-IN": ("ಹಂಚಿಕೊಳ್ಳಬೇಡಿ", "hanchikollabedi"), "mr-IN": ("नका", "naka")}
LANG_NAME = {"ta-IN": "Tamil", "kn-IN": "Kannada", "mr-IN": "Marathi"}


def targets_for(kind, lang):
    name = LANG_NAME[lang]
    t = lambda tid, written, must, accept, reject, critical=True: (
        {"id": tid, "written": written, "must_hear": must, "critical": critical}, {"accept": accept, "reject": reject})
    if kind == "plain":
        return [t("content", "full sentence pair", f"complete, intelligible {name}; nothing skipped",
                  [f"every word present with natural {name} pronunciation"], ["word omitted", "read with Hindi/English phonology"])]
    if kind == "amount":
        return [t("amount", "₹1,25,450", "one lakh twenty-five thousand four hundred fifty rupees",
                  [f"the same amount in {name} number words", "the same amount in English number words"],
                  ["digit-by-digit reading", "any other value", "currency word missing"])]
    if kind == "date":
        return [t("date", "23 November", "twenty-third (of) November",
                  [f"23 in {name} or English number words with November", "twenty-third November"],
                  ["any other day", "thirty-two", "month missing"])]
    if kind == "id":
        return [t("id", "004291", "zero zero four two nine one",
                  [f"each digit in {name}", "each digit in English", "double zero four two nine one"],
                  ["four thousand two hundred ninety-one", "leading zeros lost", "any digit changed"])]
    if kind == "mixed":
        return [t("kyc", "KYC", "K-Y-C letters", ["K Y C"], ["kick", "skipped"]),
                t("english", "pending ... complete", "English words clear inside the sentence", ["pending", "complete"], ["skipped", "garbled"])]
    if kind == "negation":
        word, roman = NEG_WORD[lang]
        return [t("negation", word, f"the negative ending '{roman}' clearly audible (do NOT share)", [roman], ["omitted", "positive form"]),
                t("otp", "OTP", "O-T-P letters", ["O T P"], ["opt", "O P"])]
    raise ValueError(kind)


def tts(fields, rows):
    have = {r["case_id"] for r in rows}
    next_num = max(int(r["case_id"][1:]) for r in rows) + 1
    existing = {(r["language"], r["input_text"]) for r in rows}
    added = 0
    for lang in ("ta-IN", "kn-IN", "mr-IN"):
        for kind, (category, texts) in MESSAGES.items():
            text = texts[lang]
            if (lang, text) in existing:
                continue
            cid = f"T{next_num}"
            next_num += 1
            pairs = targets_for(kind, lang)
            row = {f: "" for f in fields}
            row.update(case_id=cid, selected="true", category=category, input_text=text, prompt_status="ready",
                       target_word_count=str(len(text.split())), language=lang, model="timbre-v3.0", voice="Tarika",
                       speed="1.0", audio_format="wav", sample_rate_hz="24000",
                       expected_targets_json=json.dumps([p[0] for p in pairs], ensure_ascii=False),
                       accepted_variants_json=json.dumps({p[0]["id"]: p[1] for p in pairs}, ensure_ascii=False),
                       notes=(f"Added language coverage ({LANG_NAME[lang]}, message '{kind}'). Text and targets drafted and "
                              "reviewed by an AI assistant; needs a competent listener of this language."))
            rows.append(row)
            added += 1
    print(f"TTS: added {added} prompts" + (f" (T{next_num - added}-T{next_num - 1})" if added else ""))
    return rows


def main():
    f, rows = read("data/asr_manifest.csv")
    write("data/asr_manifest.csv", f, asr(f, rows))
    f, rows = read("data/tts_cases.csv")
    write("data/tts_cases.csv", f, tts(f, rows))


if __name__ == "__main__":
    main()
