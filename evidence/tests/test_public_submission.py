import json
from pathlib import Path
import sys
import tempfile
import unittest

P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'scripts'))
from public_submission import asr_public,tts_human,naturalness_human,audio_quality
from validate_playback import schedule,validate


class PublicSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows,cls.summary,cls.overlap=asr_public()
    def test_all_reported_audio_is_public_and_available(self):
        self.assertEqual(len(self.rows),370)
        self.assertTrue(all(not r['clip_id'].startswith('CALL-') for r in self.rows))
        self.assertTrue(all(r['input_integrity']=='sha256_verified' for r in self.rows))
    def test_source_reference_headlines(self):
        self.assertEqual((self.summary['baseline']['word_edits'],self.summary['baseline']['reference_words']),(309,1630))
        self.assertAlmostEqual(self.summary['baseline']['wer'],309/1630)
        self.assertEqual(self.summary['baseline']['speech_clips'],221)
        self.assertEqual(self.summary['baseline']['no_speech_controls'],5)
        self.assertEqual(self.summary['baseline']['no_speech_false_transcriptions'],0)
    def test_human_only_tts_headlines_and_complete_pairs(self):
        rows,summary,pairs=tts_human()
        self.assertEqual(len(rows),110);self.assertTrue(all(r['assessor']=='human' for r in rows))
        self.assertEqual([(r['correct_targets'],r['human_scored_targets']) for r in summary],[(57,62),(35,48)])
        self.assertEqual(len(pairs),9);self.assertEqual(sum(r['outcome']=='fixed' for r in pairs),8)
    def test_quality_ratings_deduplicate_target_rows(self):
        rows,s=naturalness_human()
        self.assertEqual(len(rows),4);self.assertEqual(s['source_target_rows'],7)
        self.assertEqual(s['listeners'],1);self.assertEqual(s['naturalness_mean'],4.5);self.assertEqual(s['prosody_mean'],5)
    def test_audio_duration_uses_actual_pcm_not_placeholder_headers(self):
        import csv
        with tempfile.TemporaryDirectory() as d:
            s=audio_quality(Path(d))
            self.assertEqual(s['decoded_nonempty'],164)
            self.assertEqual(s['clips_with_placeholder_header_lengths'],164)
            with (Path(d)/'tts_audio_quality.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
            for r in rows:
                self.assertLess(float(r['decoded_duration_s']),120)
                self.assertLessEqual(int(r['decoded_frames'])*2,(P/r['audio_path']).stat().st_size)


class IndependentPlaybackTests(unittest.TestCase):
    def test_tolerance_changes_reporting_not_actual_playout(self):
        a=schedule([0,112,250],[100,100,100],1000,tolerance_ms=1)
        b=schedule([0,112,250],[100,100,100],1000,tolerance_ms=20)
        self.assertEqual(a['starts'],b['starts']);self.assertEqual(a['all_gaps'],b['all_gaps'])
        self.assertEqual((len(a['gaps']),len(b['gaps'])),(2,1))
    def test_fixed_prebuffer_can_remove_a_planted_short_underrun(self):
        self.assertEqual(len(schedule([100,312],[200,100],1000)['gaps']),1)
        self.assertEqual(schedule([100,312],[200,100],1000,start=150)['gaps'],[])
    def test_planted_gap_and_exact_delayed_start(self):
        immediate=schedule([100,400],[100,100],1000)
        self.assertEqual(immediate['gaps'],[(200,200)]);self.assertEqual(immediate['earliest_start'],300)
        self.assertEqual(schedule([100,400],[100,100],1000,start=300)['gaps'],[])
        self.assertTrue(schedule([100,400],[100,100],1000,start=298)['gaps'])
    def test_continuous_control(self):
        self.assertEqual(schedule([100,150,220],[100,100,100],1000)['gaps'],[])
    def test_invalid_timelines_fail(self):
        for arrivals,lengths in [([],[]),([2,1],[1,1]),([1],[0]),([1,2],[1])]:
            with self.assertRaises(ValueError):schedule(arrivals,lengths,1000)
    def test_all_saved_streams_and_pcm_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            s=validate(Path(d))
            self.assertEqual((s['streams'],s['byte_duration_checks_passed']),(14,14))
            self.assertEqual((s['v3_with_stalls'],s['v25_with_stalls']),(12,0))
            self.assertTrue(s['all_delayed_streams_without_stalls'])
            self.assertEqual(len(list(Path(d).glob('*.wav'))),28)
            self.assertLess(s['max_absolute_rounding_correction_ms'],1.2)
            sensitivity=s['buffer_sensitivity']
            self.assertEqual(sensitivity['conditions'],168)
            self.assertTrue(sensitivity['v3_underflow_in_all_conditions'])
            self.assertTrue(sensitivity['v25_no_underflows_in_all_conditions'])


class MeasurementTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from reconcile_measurements import reconcile
        rows,_,_=asr_public()
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        cls.metrics=reconcile(rows,Path(cls.tmp.name))
    def test_pcm_rtf_and_baseline_timers_reconcile(self):
        m=self.metrics
        self.assertEqual((m['asr_rest_speech_n'],m['tts_rest_prompts']),(221,98))
        self.assertEqual(m['asr_rest_latency_ms_median'],192.1)
        self.assertEqual(m['tts_rest_latency_ms_median'],1492.25)
        self.assertAlmostEqual(m['tts_rest_rtf_median'],.3722769982993197)
    def test_connection_runs_and_paired_stream_cohort(self):
        m=self.metrics
        self.assertTrue(all(r['runs']==5 for r in m['connections'].values()))
        self.assertEqual(m['connections']['v2.5|WebSocket|cold']['smooth_total_ms'],549.5)
        self.assertEqual(m['connections']['v2.5|WebSocket|warm']['smooth_total_ms'],178.5)
        self.assertEqual(m['asr_stream_clips'],18)
        self.assertAlmostEqual(m['asr_final_after_audio_ms_median'],262.6)
        self.assertEqual(round(m['asr_final_after_audio_ms_median']),263)


if __name__=='__main__':unittest.main()
