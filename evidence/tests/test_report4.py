import csv,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));sys.path.insert(0,str(P/'scripts'))
from analyze_report4 import merge,attempt_ledger,counts,analyze
from analyze_report4_heldout import analyze as heldout_analyze,targets_in


class Report4Tests(unittest.TestCase):
    def test_controlled_30_and_earlier_60_are_different_sets(self):
        from reconcile_rest_sets import reconcile
        with tempfile.TemporaryDirectory() as tmp:
            s=reconcile(P,Path(tmp))
            self.assertEqual((s['controlled_measured_requests'],s['controlled_distinct_texts'],s['texts_per_length']),(30,3,1))
            self.assertEqual((s['controlled_excluded_warmups'],s['earlier_waveform_rest_files']),(2,60))
            self.assertEqual((s['earlier_timing_subset'],s['earlier_other_functionality_files']),(18,42))
            self.assertEqual(s['shared_case_ids_between_30_and_60'],0)
            self.assertFalse(s['pooled_into_controlled_timing'])

    @classmethod
    def setUpClass(cls):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No network in offline evidence replay')):
            cls.s=analyze(P);cls.h=heldout_analyze(P)
    def test_original_attempts_reconcile_including_sse_and_negative_case(self):
        r=self.s['http_cohorts']['timbre_followup']
        self.assertEqual((r['cases'],r['http_attempts'],r['valid_pcm_attempts']),(73,74,66))
        self.assertEqual(r['disjoint_attempt_outcomes'],{'valid_pcm':66,'empty_pcm':6,'http_error':2})
        self.assertEqual((r['retry_attempts'],r['explicit_recheck_cases']),(1,8))
        self.assertAlmostEqual(r['attempt_success_rate'],66/74);self.assertAlmostEqual(r['eventual_case_success_rate'],66/73)
        self.assertAlmostEqual(r['positive_case_success_rate'],66/72)
        with (P/'results/report4/tts_http_attempts.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        sse=[x for x in rows if x['transport']=='SSE'];self.assertEqual(len(sse),6)
        self.assertTrue(all(x['body_bytes']=='' and x['saved_audio_bytes'] for x in sse))
        self.assertEqual(len({r['attempt_id'] for r in rows}),len(rows))
    def test_positive_pcm_not_http_status_defines_success_and_retry_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'audio').mkdir()
            sf.write(root/'audio/empty.wav',np.zeros(0,dtype='int16'),8000,subtype='PCM_16')
            sf.write(root/'audio/speech.wav',np.ones(800,dtype='int16')*1000,8000,subtype='PCM_16')
            settings=dict(model='timbre-v3.0',voice='Tarika',language='en-IN',speed=1,endpoint='fixture',audio_config=dict(sample_rate=8000,encoding='linear_pcm',container='wav',num_channels=1,sample_width=2))
            shared=dict(kind='tts',case_id='fixture',settings=settings,input_text='hello',run_tag='fixture',latency_ms=100,ok=True)
            empty=attempt_ledger(root,[dict(shared,request_id='a',http_status=200,attempt=1,audio_path='audio/empty.wav',retry_inclusive_ms=100)],'fixture')
            self.assertEqual(empty[0]['attempt_outcome'],'empty_pcm');self.assertEqual(counts(empty)['valid_pcm_attempts'],0)
            retry=attempt_ledger(root,[dict(shared,request_id='a',http_status=500,attempt=1,retry_inclusive_ms=100),dict(shared,request_id='b',http_status=200,attempt=2,audio_path='audio/speech.wav',retry_inclusive_ms=1200)],'fixture')
            self.assertEqual(retry[1]['retry_of'],'a');self.assertEqual(retry[1]['retry_backoff_ms'],1000)
            self.assertEqual(retry[1]['final_case_outcome'],'recovered_on_retry')
    def test_validation_events_do_not_duplicate_requests(self):
        rows=merge([{'request_id':'x','ok':True,'http_status':200},{'request_id':'x','event':'audio_validated','ok':False}])
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]['ok']);self.assertEqual(rows[0]['http_status'],200)
    def test_controlled_repetitions_settings_hashes_and_per_trial_rtf(self):
        self.assertEqual(len(self.s['controlled_rest']),6)
        self.assertTrue(all(r['successful_trials']==5 and r['attempts']==5 for r in self.s['controlled_rest']))
        protocol=json.loads((P/'results/report4/protocol.json').read_text())
        self.assertEqual([p['input_chars'] for p in protocol['prompts']],[61,396,930])
        for p in protocol['prompts']:self.assertEqual(p['text_sha256'],hashlib.sha256(p['text'].encode()).hexdigest())
        with (P/'results/report4/rest_latency_trials.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),30)
        for r in rows:
            self.assertAlmostEqual(float(r['rtf_client']),float(r['request_total_ms'])/1000/float(r['duration_s']))
            self.assertEqual((r['sample_rate'],r['speed'],r['channels'],r['sample_width']),('24000','1.0','1','2'))
            self.assertEqual(hashlib.sha256(r['input_text'].encode()).hexdigest(),r['text_hash'])
    def test_warm_ws_excludes_cold_warmups_and_buffer_tradeoff(self):
        stream=self.s['streaming'];self.assertEqual((stream['streams'],stream['sensitivity_rows']),(32,576))
        self.assertEqual(stream['buffers_ms'],[0,50,100,200,500,1000])
        self.assertTrue(all(r['successful_trials']==5 for r in stream['warm_ws']))
        g=[r for r in stream['buffer_summary'] if r['cohort']=='report4_WS' and r['phase']=='warm_measured' and r['model']=='timbre-v3.0']
        self.assertEqual([r['streams_with_underflows'] for r in g if r['buffer_ms']==1000],[3])
        with (P/'results/report4/buffer_sensitivity.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        for r in rows:self.assertAlmostEqual(float(r['simulated_startup_ms'])-float(r['observed_ttfa_ms']),float(r['initial_buffer_ms']),delta=.1)
    def test_heldout_scores_and_scope_are_separate_and_no_human_marks_invented(self):
        self.assertEqual(self.h['asr_paired_clips'],15)
        self.assertEqual(self.h['asr']['baseline']['word_edits'],29);self.assertEqual(self.h['asr']['hinted']['word_edits'],28)
        self.assertEqual(self.h['paired_outcomes'],{'unchanged':14,'improved':1})
        self.assertEqual(self.h['target_term_coverage'],{'account':15})
        self.assertEqual((self.h['new_human_rating_rows'],self.h['rewrite_pairs_scored']),(0,0))
        self.assertEqual((self.h['quality_audio_available'],self.h['matched_neutral_prompt_pairs'],self.h['rewrite_audio_available']),(33,15,20))
        self.assertEqual(self.s['http_cohorts']['report4_quality']['disjoint_attempt_outcomes'],{'valid_pcm':53,'empty_pcm':1})
    def test_frozen_policy_precedes_asr_and_audio_never_overlaps_primary(self):
        policy=json.loads((P/'data/report4/frozen_policy.json').read_text());frozen=policy['frozen_at_utc'];digest=hashlib.sha256((P/'data/report4/frozen_policy.json').read_bytes()).hexdigest()
        attempts=[json.loads(x) for x in (P/'results/report4_quality/attempts.jsonl').read_text().splitlines()]
        self.assertTrue(all(r['started_at']>frozen for r in attempts if r['kind']=='asr'))
        with (P/'data/report4/asr_heldout_manifest.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        old=set()
        for name in ['data/asr_manifest.csv','data/next/asr_next_manifest.csv','data/next/asr_dataset_replacement.csv']:
            with (P/name).open(encoding='utf-8-sig') as f:old.update(r.get('input_sha256') for r in csv.DictReader(f))
        self.assertEqual(len({r['input_sha256'] for r in rows}),15)
        for r in rows:
            self.assertNotIn(r['input_sha256'],old);self.assertEqual(r['frozen_vocabulary_sha256'],digest)
            self.assertEqual(hashlib.sha256((P/r['input_path']).read_bytes()).hexdigest(),r['input_sha256'])
        self.assertEqual(targets_in('accountant bank account',['account','bank']),['account','bank'])


if __name__=='__main__':unittest.main()
