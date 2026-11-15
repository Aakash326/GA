import hashlib,json,os,sys,tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'scripts'))
import timbre_followup as t
import analyze_timbre_followup as a


class TimbreFollowupTests(unittest.TestCase):
    def test_live_setup_does_not_require_private_cost_file(self):
        import gnani_api as g
        with tempfile.TemporaryDirectory() as tmp,patch.object(t,'P',Path(tmp)),patch.object(t,'OUT',Path(tmp)/'results'),patch.dict(os.environ,{'GNANI_SPENT_TO_DATE_INR':'0'}),patch.object(g,'ATTEMPTS'),patch.object(g,'RAW'),patch.object(g,'TTS_AUDIO'),patch('requests.sessions.Session.request',side_effect=AssertionError('No request expected')):
            t.collect([])
    def test_planted_initial_tone_gap_and_sentence_pause_differ(self):
        rate=24000;tone=.15*np.sin(2*np.pi*800*np.arange(round(.08*rate))/rate)
        speech=.1*np.sin(2*np.pi*200*np.arange(rate)/rate)
        with tempfile.TemporaryDirectory() as tmp:
            positive=Path(tmp)/'positive.wav';negative=Path(tmp)/'negative.wav'
            sf.write(positive,np.concatenate([tone,np.zeros(round(.9*rate)),speech]),rate,subtype='PCM_16')
            sf.write(negative,np.concatenate([speech,np.zeros(round(.9*rate)),speech]),rate,subtype='PCM_16')
            pos,_=t.acoustic(positive);neg,_=t.acoustic(negative)
            self.assertTrue(all(v['early_gap_candidate'] for v in pos['views'].values()))
            self.assertTrue(all(not v['early_gap_candidate'] for v in neg['views'].values()))
            self.assertAlmostEqual(pos['views']['-45']['early_gap_s'],.9,places=2)
    def test_live_evidence_canonical_audio_preserves_decoded_samples(self):
        rows=a.read(P/'results/timbre_followup/audio_results.csv');self.assertGreaterEqual(len(rows),60)
        for r in rows:
            raw,sr=sf.read(P/r['raw_audio_path'],dtype='int16');fixed,fs=sf.read(P/r['audio_path'],dtype='int16')
            np.testing.assert_array_equal(raw,fixed);self.assertEqual(sr,fs)
            with wave.open(str(P/r['audio_path']),'rb') as w:self.assertEqual(w.getnframes(),len(fixed))
            self.assertEqual(hashlib.sha256((P/r['audio_path']).read_bytes()).hexdigest(),r['audio_sha256'])
    def test_judge_cache_has_real_audio_hashes_and_separate_provenance(self):
        files=list((P/'results/timbre_followup/judge').rglob('*.json'));self.assertTrue(files)
        for file in files:
            r=json.loads(file.read_text(encoding='utf8'))
            self.assertFalse(r['human_verified']);self.assertEqual(r['assessor'],'audio_model_provisional')
            self.assertEqual(r['input_sha256'],[hashlib.sha256((P/path).read_bytes()).hexdigest() for path in r['audio_paths']])
            if 'prompt' in r:
                fp=hashlib.sha256(json.dumps([r['model'],r['task'],r['input_sha256'],r['prompt']],ensure_ascii=False).encode()).hexdigest()
                self.assertEqual(r['fingerprint'],fp)
    def test_manifest_uses_documented_tags_and_keeps_failed_originals(self):
        rows=a.read(P/'data/timbre_followup_cases.csv')
        tags={r['tag'] for r in rows if r['section']=='tag' and r['language']=='en-IN' and r['model']=='timbre-v3.0'}
        self.assertEqual(tags,set(t.TAGS));self.assertEqual(len(tags),13)
        self.assertTrue(all(any(0x900<=ord(c)<=0x97f for c in r['input_text']) for r in rows if r['language']=='hi-IN'))
        self.assertTrue(any(r['case_id']=='NF-N-3-hi' for r in rows))
        self.assertEqual(len({r['case_id'] for r in rows}),len(rows))
    def test_replay_cannot_generate_or_judge_audio_and_reconciles_failures(self):
        with patch.object(t,'judge_request',side_effect=AssertionError('No live judge in replay')),patch('requests.sessions.Session.request',side_effect=AssertionError('No network in replay')):
            s=a.analyze(P)
        self.assertEqual(s['new_api_calls_in_replay'],0)
        self.assertEqual(sum(s['http_status_counts'].values()),s['http_requests'])
        self.assertEqual(s['http_status_counts'],{'200':72,'500':1,'400':1})
        self.assertEqual(len(s['transient_http_failures']),1)
        self.assertEqual(s['attempted_cases'],s['valid_audio_clips']+len(s['expected_rejections'])+len(s['unexpected_failures']))
        self.assertTrue(all(r['actual_http']==400 for r in s['expected_rejections']))
        self.assertTrue(all(r['actual_http']==200 and not r['ok'] for r in s['unexpected_failures']))
        for r in s['unexpected_failures']:
            record=t.chosen(a.read(P/'data/timbre_followup_cases.csv'))[r['case_id']]
            self.assertEqual((P/record['audio_path']).stat().st_size,44)
        self.assertEqual(len(s['rest_latency']),6);self.assertTrue(all(r['n']==3 for r in s['rest_latency']))
        self.assertEqual(len(s['fresh_streams']),6)


if __name__=='__main__':unittest.main()
