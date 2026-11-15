"""Run a checkpointed batch of Gnani calls for chosen case IDs.

    .venv\\Scripts\\python.exe scripts\\run_batch.py --asr CL-EN-02 CL-HI-01 --tts T01 T35 --live

- Skips a case only if a saved success has the same request fingerprint (settings + audio bytes / text);
  pre-fingerprint records are reused only if their settings match exactly (no double charging, no stale reuse).
- ASR: only `selected` rows; language hint from the manifest (`indic-auto` when blank).
- TTS: only prompts with prompt_status=ready; settings from the CSV row.
- Every attempt is saved by gnani_api before anything is printed.
- Model transcripts are shown only for clips whose reference is already verified, so a later
  listener checking an unverified reference is not influenced by the model's output.
"""
import argparse
import csv
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import gnani_api as g  # noqa: E402


def load(path):
    with (PROJECT / path).open(encoding="utf-8-sig", newline="") as fh:
        return {r.get("clip_id") or r.get("case_id"): r for r in csv.DictReader(fh)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asr", nargs="*", default=[])
    ap.add_argument("--tts", nargs="*", default=[])
    ap.add_argument("--run-tag", default="run1")
    ap.add_argument("--live", action="store_true", help="required to spend credits")
    ap.add_argument("--tts-file", default="data/tts_cases.csv", help="e.g. data/tts_mitigation_cases.csv")
    args = ap.parse_args()
    asr_rows, tts_rows = load("data/asr_manifest.csv"), load(args.tts_file)

    totals = {"asr_seconds": 0.0, "tts_chars": 0, "sent": 0, "skipped": 0, "failed": 0}
    for cid in args.asr:
        r = asr_rows[cid]
        if r["selected"].lower() != "true":
            print(f"ASR {cid}: not selected, skipped"); continue
        lang = r["language"] or "indic-auto"
        _, _, settings, fp = g.asr_request(r["input_path"], lang, fmt=r.get("output_mode") or None, model=r.get("model") or None)
        if g.latest_success("asr", cid, args.run_tag, fingerprint=fp, legacy_settings=settings):
            print(f"ASR {cid}: already done with identical settings/input, reused"); totals["skipped"] += 1; continue
        res = g.transcribe(cid, r["input_path"], lang, run_tag=args.run_tag, fmt=r.get("output_mode") or None, model=r.get("model") or None, live=args.live)
        totals["sent"] += 1; totals["asr_seconds"] += float(r["duration_s"])
        if not res["ok"]:
            totals["failed"] += 1
            print(f"ASR {cid}: FAILED {res['http_status']} {res.get('error')}"); continue
        verified = r["human_reference_verified"].lower() == "true"
        shown = res["transcript"] if (verified or r["is_no_speech"].lower() == "true") else "<hidden until reference verified>"
        same = "exact match" if verified and res["transcript"].strip() == r["reference_transcript"].strip() else ""
        print(f"ASR {cid} [{r['category']}, {lang}, {r['duration_s']} s] {res['latency_ms']:.0f} ms "
              f"lang={res.get('detected_language_code')} | {shown} {same}")
        if verified and not same:
            print(f"      reference: {r['reference_transcript']}")

    for cid in args.tts:
        r = tts_rows[cid]
        if r["prompt_status"] != "ready":
            print(f"TTS {cid}: status {r['prompt_status']}, skipped"); continue
        _, settings, fp = g.tts_request(r["input_text"], r["language"], r["voice"], r["model"], float(r["speed"]),
                                        int(r["sample_rate_hz"]))
        if g.latest_success("tts", cid, args.run_tag, fingerprint=fp, legacy_settings=settings):
            print(f"TTS {cid}: already done with identical settings/text, reused"); totals["skipped"] += 1; continue
        res = g.synthesize(cid, r["input_text"], r["language"], run_tag=args.run_tag, voice=r["voice"], model=r["model"],
                           speed=float(r["speed"]), sample_rate=int(r["sample_rate_hz"]), live=args.live)
        totals["sent"] += 1; totals["tts_chars"] += len(r["input_text"])
        if not res["ok"]:
            totals["failed"] += 1
            print(f"TTS {cid}: FAILED {res.get('http_status')} {res.get('error')}"); continue
        print(f"TTS {cid} [{r['category']}, {r['language']}, {len(r['input_text'])} chars] {res['latency_ms']:.0f} ms, "
              f"{res['audio_duration_s']} s audio, RTF {res['rtf']} -> {res['audio_path']}")

    est = totals["asr_seconds"] * 0.03 / 3.6 + totals["tts_chars"] * 0.11 / 61
    print(f"\nsent {totals['sent']}, reused {totals['skipped']}, failed {totals['failed']}; "
          f"{totals['asr_seconds']:.1f} s ASR audio, {totals['tts_chars']} TTS chars; pilot-rate estimate ₹{est:.2f}")


if __name__ == "__main__":
    main()
