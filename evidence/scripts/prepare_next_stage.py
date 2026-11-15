"""Prepare the NEXT-STAGE data set (no Gnani or Gemini calls; only free public downloads).

Kept apart from the measured benchmark in data/next/ so the completed report stays reproducible.

  data/next/asr_next_manifest.csv   120 new Google SVQ clips (20 per language), new speakers/sentences first
  data/next/tts_next_cases.csv       66 targeted TTS prompts (close numbers, signs, leading zeros, times, native-language
                                     numbers), each in a raw form and a rewritten form to test the preprocessing rule
  data/next/asr_recording_queue.csv  24 scripted utterances (finance, code-switching, corrections) for consented recording
All references/targets are drafts: status columns say what review is required before scoring.
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

NEXT = PROJECT / "data" / "next"
AUDIO = NEXT / "audio"
SEED = 20261114
LANG = {"en_in": "en-IN", "hi_in": "hi-IN", "te_in": "te-IN", "ta_in": "ta-IN", "kn_in": "kn-IN", "mr_in": "mr-IN"}
PLAN = [("clean", False, "CL", 8), ("clean", True, "NUM", 4), ("background_speech", False, "BG", 3),
        ("media_noise", False, "MEDIA", 3), ("traffic_noise", False, "TRAFFIC", 2)]
LATIN, DIGIT = re.compile(r"[A-Za-z]"), re.compile(r"\d")


def row_group_bounds(name):
    with fsspec.open(prep.SVQ_BASE + name, "rb", block_size=2**20) as fh:
        md = pq.ParquetFile(fh).metadata
    out, start = [], 0
    for i in range(md.num_row_groups):
        n = md.row_group(i).num_rows
        out.append((i, start, start + n))
        start += n
    return out


def select_asr():
    man = pd.read_csv(PROJECT / "data/asr_manifest.csv", encoding="utf-8-sig", dtype=str).fillna("")
    used_ids = set(man["source_ref"].str.split("#").str[-1])
    used_text = set(man["reference_transcript"].str.strip())
    used_spk = man["speaker_id"].value_counts().to_dict()
    idx = pd.concat([pd.read_csv(PROJECT / "data/sources/svq_index_in.csv"),
                     pd.read_csv(PROJECT / "data/sources/svq_index_ta_kn_mr.csv")], ignore_index=True)
    idx = idx[~idx.utt_id.isin(used_ids) & ~idx.text.str.strip().isin(used_text)]
    rng = random.Random(SEED)
    picks = []
    for loc, lang in LANG.items():
        chosen_spk = {}
        for env, digits, tag, n in PLAN:
            pool = idx[(idx.locale == loc) & (idx.environment == env)]
            pool = pool[pool.text.str.contains(DIGIT)] if digits else pool[~pool.text.str.contains(DIGIT)]
            if loc != "en_in":
                pool = pool[~pool.text.str.contains(LATIN)]
            if pool.empty:
                continue
            # one row group per file keeps the download small; pick the group with the most unused speakers
            name = pool.file.iloc[0]
            bounds = row_group_bounds(name)
            def group_of(r): return next(g for g, lo, hi in bounds if lo <= r < hi)
            pool = pool.assign(rg=pool.row.map(group_of))
            best = max(pool.rg.unique(), key=lambda g: (pool[pool.rg == g].speaker_id.map(lambda s: s not in used_spk).sum(),
                                                         pool[pool.rg == g].speaker_id.nunique()))
            pool = pool[pool.rg == best]
            # fewest previous uses first (new speakers first), one clip per speaker per pass, seeded order
            spk = sorted(pool.speaker_id.unique(), key=lambda s: (used_spk.get(s, 0) + chosen_spk.get(s, 0), s))
            rng.shuffle(spk)
            spk.sort(key=lambda s: used_spk.get(s, 0) + chosen_spk.get(s, 0))
            got, taken = [], set()
            while len(got) < n and len(taken) < len(pool):
                for s in spk:
                    rows = pool[(pool.speaker_id == s) & ~pool.utt_id.isin(taken)].sort_values("utt_id")
                    if len(rows) and len(got) < n:
                        r = rows.iloc[rng.randrange(len(rows))]
                        got.append(r); taken.add(r.utt_id); chosen_spk[s] = chosen_spk.get(s, 0) + 1
                if not any(len(pool[(pool.speaker_id == s) & ~pool.utt_id.isin(taken)]) for s in spk):
                    break
            for i, r in enumerate(got, 1):
                picks.append((f"NX-{lang[:2].upper()}-{tag}-{i:02d}", lang, tag, r))
    return picks


def build_asr():
    picks = select_asr()
    blobs = prep.fetch_svq_audio([r for *_, r in picks])
    AUDIO.mkdir(parents=True, exist_ok=True)
    rows = []
    used_spk = set(pd.read_csv(PROJECT / "data/asr_manifest.csv", encoding="utf-8-sig", dtype=str)["speaker_id"].dropna())
    for cid, lang, tag, r in picks:
        dest = AUDIO / f"{cid}.wav"
        if not dest.exists():
            prep.write_wav(dest, prep.load_mono(io.BytesIO(blobs[r.utt_id])), prep.TARGET_SR)
        info = prep.sf.info(dest)
        rows.append({"clip_id": cid, "selected": "true", "stage": "next", "category": {"CL": "clean", "NUM": "numbers"}.get(tag, "real_noise"),
                     "environment": r.environment, "language": lang, "speaker_id": r.speaker_id,
                     "new_speaker": str(r.speaker_id not in used_spk).lower(), "duration_s": round(info.duration, 3),
                     "sample_rate_hz": info.samplerate, "input_path": dest.relative_to(PROJECT).as_posix(),
                     "source_dataset": "google/svq 1.0.0", "source_ref": f"{r.file}#{r.utt_id}",
                     "reference_transcript": r.text, "reference_status": "dataset text - needs listener or calibrated judge",
                     "license_or_consent": prep.SVQ_LICENSE, "input_sha256": prep.sha256(dest)})
    write(NEXT / "asr_next_manifest.csv", rows)
    return rows


# ---------------------------------------------------------------- TTS
WORDS = {13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
         30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"}


def close(q, rej):
    return [{"id": "qty", "written": str(q), "must_hear": f"{WORDS.get(q, q)} (the requested quantity)", "critical": True},
            {"id": "rejected", "written": str(rej), "must_hear": f"{WORDS.get(rej, rej)} (the rejected quantity)", "critical": True},
            {"id": "not", "written": "not", "must_hear": "negation audible", "critical": True}], \
           {"qty": {"accept": [WORDS.get(q, str(q))], "reject": [WORDS.get(rej, str(rej)), "unclear teen/ty"]},
            "rejected": {"accept": [WORDS.get(rej, str(rej))], "reject": [WORDS.get(q, str(q)), "unclear teen/ty"]},
            "not": {"accept": ["not / its equivalent"], "reject": ["omitted"]}}


def signed(value_spoken):
    return [{"id": "sign", "written": "-", "must_hear": "a negative value (minus / negative)", "critical": True},
            {"id": "value", "written": value_spoken, "must_hear": value_spoken, "critical": True}], \
           {"sign": {"accept": ["minus", "negative", "native-language minus"], "reject": ["sign omitted", "dash read as a pause"]},
            "value": {"accept": [value_spoken], "reject": ["any other value"]}}


def ident(digits):
    return [{"id": "digits", "written": digits, "must_hear": " ".join(digits) + " (every digit, leading zeros kept)", "critical": True}], \
           {"digits": {"accept": ["each digit in order", "double/triple grouping"], "reject": ["read as a number", "leading zeros lost"]}}


def timet(hhmm):
    return [{"id": "time", "written": hhmm, "must_hear": f"{hhmm} with minutes intact", "critical": True}], \
           {"time": {"accept": ["hour + 'oh/zero' + minutes", "minutes past the hour"], "reject": ["'nine five' style", "wrong hour/minutes"]}}


def tts_prompts():
    P = []  # (case, lang, category, text, (targets, variants), pair_id, form)
    for a, b in [(13, 30), (14, 40), (15, 50), (16, 60), (17, 70), (18, 80), (19, 90)]:
        tv = close(a, b)
        P += [("en-IN", "close_numbers", f"Please send {a} units, not {b}.", tv, f"en-close-{a}", "raw"),
              ("en-IN", "close_numbers", f"Please send {WORDS[a]} units, not {WORDS[b]}.", tv, f"en-close-{a}", "rewritten")]
    P += [("en-IN", "signed", "The change was −1.5%.", signed("one point five percent"), "en-sign-pct", "raw"),
          ("en-IN", "signed", "The change was -1.5%.", signed("one point five percent"), "en-sign-pct", "ascii_minus"),
          ("en-IN", "signed", "The change was minus 1.5 percent.", signed("one point five percent"), "en-sign-pct", "rewritten"),
          ("en-IN", "signed", "Your balance is −₹3,200.", signed("three thousand two hundred rupees"), "en-sign-inr", "raw"),
          ("en-IN", "signed", "Your balance is -₹3,200.", signed("three thousand two hundred rupees"), "en-sign-inr", "ascii_minus"),
          ("en-IN", "signed", "Your balance is minus three thousand two hundred rupees.", signed("three thousand two hundred rupees"), "en-sign-inr", "rewritten"),
          ("en-IN", "identifiers", "The code is 00700.", ident("00700"), "en-id-00700", "raw"),
          ("en-IN", "identifiers", "The code is 0 0 7 0 0.", ident("00700"), "en-id-00700", "rewritten"),
          ("en-IN", "identifiers", "The PIN ends in 0091.", ident("0091"), "en-id-0091", "raw"),
          ("en-IN", "identifiers", "The PIN ends in zero zero nine one.", ident("0091"), "en-id-0091", "rewritten"),
          ("en-IN", "identifiers", "Your ID is 000123.", ident("000123"), "en-id-000123", "raw"),
          ("en-IN", "identifiers", "Your ID is zero zero zero one two three.", ident("000123"), "en-id-000123", "rewritten"),
          ("en-IN", "times", "The call is at 9:05 AM.", timet("9:05"), "en-time-905", "raw"),
          ("en-IN", "times", "The call is at nine oh five A M.", timet("9:05"), "en-time-905", "rewritten"),
          ("en-IN", "times", "Cut-off time is 3:30 PM.", timet("3:30"), "en-time-330", "raw"),
          ("en-IN", "times", "Cut-off time is three thirty P M.", timet("3:30"), "en-time-330", "rewritten")]
    native = {
        "hi-IN": [("close", "मात्रा 15 है, 50 नहीं।", "मात्रा पंद्रह है, पचास नहीं।"),
                  ("signed", "बदलाव −1.5% रहा।", "बदलाव माइनस एक दशमलव पाँच प्रतिशत रहा।"),
                  ("ident", "आपका कोड 0070 है।", "आपका कोड शून्य शून्य सात शून्य है।"),
                  ("time", "कॉल सुबह 9:05 बजे है।", "कॉल सुबह नौ बजकर पाँच मिनट पर है।")],
        "te-IN": [("close", "పరిమాణం 15, 50 కాదు.", "పరిమాణం పదిహేను, యాభై కాదు."),
                  ("signed", "మార్పు −1.5% ఉంది.", "మార్పు మైనస్ ఒకటి పాయింట్ ఐదు శాతం ఉంది."),
                  ("ident", "మీ కోడ్ 0070.", "మీ కోడ్ సున్నా సున్నా ఏడు సున్నా.")],
        "ta-IN": [("close", "அளவு 15, 50 அல்ல.", "அளவு பதினைந்து, ஐம்பது அல்ல."),
                  ("signed", "மாற்றம் −1.5%.", "மாற்றம் மைனஸ் ஒன்று புள்ளி ஐந்து சதவீதம்."),
                  ("ident", "உங்கள் குறியீடு 0070.", "உங்கள் குறியீடு பூஜ்யம் பூஜ்யம் ஏழு பூஜ்யம்.")],
        "kn-IN": [("close", "ಪ್ರಮಾಣ 15, 50 ಅಲ್ಲ.", "ಪ್ರಮಾಣ ಹದಿನೈದು, ಐವತ್ತು ಅಲ್ಲ."),
                  ("signed", "ಬದಲಾವಣೆ −1.5%.", "ಬದಲಾವಣೆ ಮೈನಸ್ ಒಂದು ಪಾಯಿಂಟ್ ಐದು ಶೇಕಡಾ."),
                  ("ident", "ನಿಮ್ಮ ಕೋಡ್ 0070.", "ನಿಮ್ಮ ಕೋಡ್ ಸೊನ್ನೆ ಸೊನ್ನೆ ಏಳು ಸೊನ್ನೆ.")],
        "mr-IN": [("close", "प्रमाण 15 आहे, 50 नाही.", "प्रमाण पंधरा आहे, पन्नास नाही."),
                  ("signed", "बदल −1.5% आहे.", "बदल उणे एक पूर्णांक पाच टक्के आहे."),
                  ("ident", "तुमचा कोड 0070 आहे.", "तुमचा कोड शून्य शून्य सात शून्य आहे.")],
    }
    kind = {"close": ("close_numbers", lambda: close(15, 50)), "signed": ("signed", lambda: signed("one point five percent")),
            "ident": ("identifiers", lambda: ident("0070")), "time": ("times", lambda: timet("9:05"))}
    for lang, items in native.items():
        for k, raw, rew in items:
            cat, tv = kind[k]
            P += [(lang, cat, raw, tv(), f"{lang[:2]}-{k}", "raw"), (lang, cat, rew, tv(), f"{lang[:2]}-{k}", "rewritten")]
    P += [("auto", "code_switching", "आपका balance −₹3,200 है।", signed("three thousand two hundred rupees"), "mix-sign", "raw"),
          ("auto", "code_switching", "आपका balance minus ₹3,200 है।", signed("three thousand two hundred rupees"), "mix-sign", "rewritten"),
          ("auto", "code_switching", "Order quantity 15 है, 50 नहीं।", close(15, 50), "mix-close", "raw"),
          ("auto", "code_switching", "Order quantity fifteen है, fifty नहीं।", close(15, 50), "mix-close", "rewritten")]
    rows = []
    for i, (lang, cat, text, (tg, var), pair, form) in enumerate(P, 1):
        rows.append({"case_id": f"NT{i:03d}", "selected": "true", "stage": "next", "category": cat, "language": lang,
                     "input_text": text, "pair_id": pair, "input_form": form, "model": "timbre-v3.0", "voice": "Tarika",
                     "speed": "1.0", "audio_format": "wav", "sample_rate_hz": "24000",
                     "expected_targets_json": json.dumps(tg, ensure_ascii=False),
                     "accepted_variants_json": json.dumps(var, ensure_ascii=False),
                     "prompt_status": "draft_needs_review",
                     "notes": "AI-drafted text and targets; native-language prompts need a competent speaker to approve "
                              "wording and accepted readings before generation."})
    write(NEXT / "tts_next_cases.csv", rows)
    return rows


# ---------------------------------------------------------------- recording queue
QUEUE_NEW = [
    ("FIN-01", "en-IN", "finance_action", "Sell twenty-five shares of Infosys at market price.", '{"action":"SELL","qty":"25","entity":"Infosys"}'),
    ("FIN-02", "hi-IN,en-IN", "code_switching", "मेरा SIP amount दो हज़ार से बढ़ाकर पाँच हज़ार कर दो।", '{"action":"INCREASE_SIP","from":"2000","to":"5000"}'),
    ("FIN-03", "en-IN", "identifier", "My account number ends with zero zero four seven.", '{"id_suffix":"0047"}'),
    ("FIN-04", "en-IN", "self_correction", "Buy thirty, no sorry, thirteen shares.", '{"action":"BUY","final_qty":"13","rejected_qty":"30"}'),
    ("FIN-05", "hi-IN,en-IN", "negation", "मुझे Reliance के पाँच सौ shares बेचने हैं, खरीदने नहीं।", '{"action":"SELL","qty":"500","entity":"Reliance","rejected":"BUY"}'),
    ("FIN-06", "te-IN,en-IN", "code_switching", "నా SIP ఈ నెల debit అయిందా?", '{"intent":"SIP_DEBIT_STATUS"}'),
    ("FIN-07", "en-IN", "amount", "Transfer one lakh fifty thousand rupees to my savings account.", '{"amount_inr":"150000"}'),
    ("FIN-08", "en-IN", "identifier", "My PAN is A B C D E one two three four F.", '{"pan":"ABCDE1234F","fictional":true}'),
    ("FIN-09", "en-IN", "negation", "Cancel the stop-loss order, don't modify it.", '{"action":"CANCEL","rejected":"MODIFY"}'),
    ("FIN-10", "en-IN", "domain_terms", "What is today's gold price per ten grams on MCX?", '{"entity":"gold","unit":"10g","exchange":"MCX"}'),
    ("FIN-11", "hi-IN,en-IN", "negation", "कल का order cancel करना है, आज का नहीं।", '{"action":"CANCEL","date":"tomorrow","rejected":"today"}'),
    ("FIN-12", "en-IN", "amount", "Set a price alert at two thousand four hundred and fifty rupees.", '{"alert_inr":"2450"}'),
]


def build_queue():
    with (PROJECT / "data/asr_priority_recordings.csv").open(encoding="utf-8-sig", newline="") as fh:
        old = list(csv.DictReader(fh))
    rows = [{"clip_id": r["clip_id"], "language": r["language"] or ("hi-IN,en-IN" if r["category"] == "code_switching" else "en-IN"),
             "category": r["category"], "script_to_read": r["source_or_prompt"].strip("“”\""), "expected_entities_json": r["expected_entities_json"],
             "speaker_requirement": "native/bilingual speaker of the listed language(s); natural delivery, no accent imitation",
             "consent": "written consent required before upload to any vendor", "status": "needs_recording", "notes": r["notes"]}
            for r in old]
    rows += [{"clip_id": c, "language": l, "category": k, "script_to_read": s, "expected_entities_json": e,
              "speaker_requirement": "native/bilingual speaker of the listed language(s); natural delivery, no accent imitation",
              "consent": "written consent required before upload to any vendor", "status": "needs_recording",
              "notes": "Fictional values only. Record 2 speakers each if possible; transcribe what was actually said."}
             for c, l, k, s, e in QUEUE_NEW]
    write(NEXT / "asr_recording_queue.csv", rows)
    return rows


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    t = tts_prompts()
    q = build_queue()
    a = build_asr()
    langs = {}
    for r in a:
        langs[r["language"]] = langs.get(r["language"], 0) + 1
    print(f"TTS next prompts: {len(t)} | recording queue: {len(q)} | ASR next clips: {len(a)} {langs}; "
          f"new speakers in {sum(r['new_speaker'] == 'true' for r in a)} clips")
