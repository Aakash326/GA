import importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
import budget_guard as budget

P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('remaining',P/'scripts/remaining_workflow.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
spec=importlib.util.spec_from_file_location('call_evidence',P/'call_test/call_evidence.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.patch=patch.object(w,'P',self.root);self.patch.start()
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def test_recording_requires_consent_and_imports_verified_audio(self):
        w.write(self.root/'data/next/asr_recording_queue.csv',[dict(clip_id='D1',category='finance',language='en-IN')])
        audio=self.root/'downloads';audio.mkdir();sf.write(audio/'D1__s1.wav',np.ones(16000)*.1,16000)
        row=dict(queue_id='D1',speaker_id='s1',audio_filename='D1__s1.wav',consent_confirmed='false',
                 reference_verified='true',reference='Transfer fifteen rupees.',expected_entities_json='{"amount":"15"}')
        path=self.root/'import.csv';w.write(path,[row])
        with self.assertRaises(ValueError):w.import_recordings(path,audio,True)
        self.assertFalse((self.root/'data/next/asr_recorded_manifest.csv').exists())
        row['consent_confirmed']='true';w.write(path,[row]);w.import_recordings(path,audio,True)
        result=w.read(self.root/'data/next/asr_recorded_manifest.csv')
        self.assertEqual(result[0]['reference_status'],'human_verified')
        self.assertTrue((self.root/result[0]['input_path']).exists())
    def test_audio_path_cannot_escape(self):
        with self.assertRaises(ValueError):w.inside(self.root,'../outside.wav')
    def setup_reference(self):
        audio=self.root/'input.wav';audio.write_bytes(b'original')
        r=dict(clip_id='NX1',input_path='input.wav',input_sha256=w.sha(audio),reference_transcript='dataset')
        w.write(self.root/'data/next/asr_next_manifest.csv',[r]);w.write(self.root/'data/next/disputed_asr_review_template.csv',[dict(clip_id='NX1')])
        row=dict(clip_id='NX1',audio_sha256=r['input_sha256'],listener_id='R1',reviewer_language_confirmed='true',decision='corrected',reference='actual speech')
        path=self.root/'review.csv';w.write(path,[row]);return audio,path
    def test_reference_overlay_keeps_original_dataset_unchanged(self):
        audio,path=self.setup_reference();w.import_references(path,True)
        self.assertEqual(w.read(self.root/'data/next/asr_next_manifest.csv')[0]['reference_transcript'],'dataset')
        self.assertEqual(w.read(self.root/'results/verification/asr_human_reference_reviews.csv')[0]['reference'],'actual speech')
        audio.write_bytes(b'changed')
        with self.assertRaises(ValueError):w.import_references(path,True)
    def test_topups_and_partial_dashboard_period(self):
        row=dict(provider='Gnani',opening_balance_inr='100',current_balance_inr='90',credits_added_inr='20',
                 captured_at_utc='2026-11-14T10:00:00+00:00',covers_all_evaluation_usage='false',evidence_note='dashboard sample')
        path=self.root/'reading.csv';w.write(path,[row]);out=w.reconcile(path,True)
        self.assertEqual(out[0]['observed_spend_inr'],30)
        self.assertFalse((self.root/'results/reconciliation/gnani_latest.json').exists())
        row['covers_all_evaluation_usage']='true';w.write(path,[row]);w.reconcile(path,True)
        self.assertTrue((self.root/'results/reconciliation/gnani_latest.json').exists())
    def test_nan_dashboard_rejected(self):
        r=dict(provider='Gnani',opening_balance_inr='NaN',current_balance_inr='0',credits_added_inr='0')
        path=self.root/'bad.csv';w.write(path,[r])
        with self.assertRaises(ValueError):w.reconcile(path,True)
    def test_call_pass_requires_barge_in_observations(self):
        folder=self.root/'results/next/call/test';folder.mkdir(parents=True)
        (folder/'call_metadata.json').write_text(json.dumps(dict(call_id='x',scenario_id='CALL03',caller='phone')))
        row=dict(call_folder='test',scenario_id='CALL03',listener_id='R1',result='pass',old_audio_stopped='true',correct_new_reply='true',no_stale_audio='false')
        path=self.root/'call.csv';w.write(path,[row])
        with self.assertRaises(ValueError):w.import_call_reviews(path,True)
        row['no_stale_audio']='true';w.write(path,[row]);w.import_call_reviews(path,True)
        self.assertEqual(json.loads((folder/'human_call_review.json').read_text())['result'],'pass')
    def test_budget_shared_between_calls_and_rest(self):
        with patch.dict(os.environ,{'GNANI_SPENT_TO_DATE_INR':'480'}):
            budget.reserve_fixed(self.root,15)
            with self.assertRaises(RuntimeError):budget.reserve_fixed(self.root,6,kind='tts')
    def test_barge_in_server_timing_is_logged(self):
        tracker=e.TurnEvidence(self.root);tracker.record('bot_started',0);tracker.record('user_started',1)
        tracker.record('interruption',1.1);tracker.record('bot_stopped',1.3)
        rows=[json.loads(x) for x in (self.root/'events.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['server_stop_after_barge_in_ms'],300)
        self.assertIn('barge_in_started',[r['event'] for r in rows])

if __name__=='__main__':unittest.main()
