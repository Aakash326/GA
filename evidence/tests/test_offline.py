"""Offline checks for the evaluation helpers (no network, no API keys used).

Run:  .venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""
import json
import os
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
os.environ["GNANI_LIVE"] = "0"
import gnani_api as g  # noqa: E402


class LiveGuard(unittest.TestCase):
    def test_no_request_without_live(self):
        with self.assertRaises(g.LiveModeOff):
            g.synthesize("X", "Yes.", "en-IN")
        with self.assertRaises(g.LiveModeOff):
            g.transcribe("X", "data/audio/NS-01.wav", "en-IN")


class Fingerprints(unittest.TestCase):
    def test_tts_fingerprint_changes_with_text_voice_and_model(self):
        _, _, a = g.tts_request("Your balance is 5.", "en-IN", "Tarika", "timbre-v3.0")
        _, _, b = g.tts_request("Your balance is 50.", "en-IN", "Tarika", "timbre-v3.0")
        _, _, c = g.tts_request("Your balance is 5.", "en-IN", "Kaveri", "timbre-v2.5")
        _, _, a2 = g.tts_request("Your balance is 5.", "en-IN", "Tarika", "timbre-v3.0")
        self.assertEqual(a, a2)
        self.assertEqual(len({a, b, c}), 3)

    def test_asr_fingerprint_changes_with_audio_and_settings(self):
        _, _, _, a = g.asr_request("data/audio/CL-EN-01.wav", "en-IN")
        _, _, _, b = g.asr_request("data/audio/CL-EN-02.wav", "en-IN")
        _, _, _, c = g.asr_request("data/audio/CL-EN-01.wav", "en-IN", fmt="verbatim")
        self.assertEqual(len({a, b, c}), 3)

    def test_latest_success_refuses_stale_cache(self):
        with tempfile.TemporaryDirectory() as d:
            old = g.ATTEMPTS
            g.ATTEMPTS = Path(d) / "attempts.jsonl"
            try:
                rows = [{"kind": "tts", "case_id": "T1", "run_tag": "run1", "ok": True, "fingerprint": "aaa", "settings": {"v": 1}},
                        {"kind": "tts", "case_id": "T2", "run_tag": "run1", "ok": True, "settings": {"v": 1}}]  # legacy
                g.ATTEMPTS.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
                self.assertIsNotNone(g.latest_success("tts", "T1", fingerprint="aaa"))
                self.assertIsNone(g.latest_success("tts", "T1", fingerprint="bbb"))            # changed input -> resend
                self.assertIsNotNone(g.latest_success("tts", "T1"))                            # replay ignores fingerprints
                self.assertIsNone(g.latest_success("tts", "T2", fingerprint="x", legacy_settings={"v": 1}))
                self.assertIsNone(g.latest_success("tts", "T2", fingerprint="x", legacy_settings={"v": 2}))
            finally:
                g.ATTEMPTS = old


class Streaming(unittest.TestCase):
    def test_stall_simulation_and_stall_free_start(self):
        chunks = [{"t_s": 0.632, "dur_s": 0.08}, {"t_s": 1.607, "dur_s": 0.029}, {"t_s": 1.607, "dur_s": 0.085}]
        r = g.playback_stalls(chunks)
        self.assertEqual(r["stalls"], 1)
        self.assertAlmostEqual(r["stall_free_start_ms"], 1527.0, places=1)
        self.assertEqual(g.playback_stalls([{"t_s": 0.5, "dur_s": 2.0}, {"t_s": 1.0, "dur_s": 2.0}])["stalls"], 0)


class NumberChecks(unittest.TestCase):
    """Mirror of the notebook's signed/ordered number check (review fix 7)."""
    @staticmethod
    def snum(t):
        t = t.replace("−", "-")
        return re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?", t)

    def test_sign_order_and_extras_detected(self):
        self.assertNotEqual(self.snum("the change was -2.5%"), self.snum("the change was 2.5%"))
        self.assertNotEqual(self.snum("buy 15 not 50"), self.snum("buy 50 not 15"))
        self.assertEqual(Counter(self.snum("buy 15 not 50")), Counter(self.snum("buy 50 not 15")))  # digit-token recall misses it
        self.assertNotEqual(self.snum("reference 004291"), self.snum("reference 4291"))
        self.assertEqual(self.snum("ref 004291"), self.snum("ref 004291"))


class ReportInputs(unittest.TestCase):
    def test_summary_metrics_present_and_consistent(self):
        s = json.loads((PROJECT / "results/submission/summary.json").read_text(encoding="utf-8"))
        self.assertEqual([(r['correct_targets'],r['human_scored_targets']) for r in s['tts_human']],[(57,62),(35,48)])
        self.assertGreater(s['asr']['baseline']['raw_wer'],s['asr']['baseline']['wer'])
        t=s['latency']
        self.assertAlmostEqual(t['tts_rest_latency_ms_median'],1492.25)
        self.assertGreater(t['connections']['v2.5|WebSocket|cold']['smooth_total_ms'],t['connections']['v2.5|WebSocket|warm']['smooth_total_ms'])


if __name__ == "__main__":
    unittest.main()
