import csv
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'scripts'))
from submission_privacy import csv_payload,excluded,private_json,check_secrets


class ReleasePrivacyTests(unittest.TestCase):
    def test_public_json_preserves_frozen_and_response_byte_hashes(self):
        import package_submission as pack
        raw=b'{\r\n  "policy": ["account", "bank"],\r\n  "version": 1\r\n}\r\n'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'frozen_policy.json';path.write_bytes(raw)
            with patch.object(pack,'P',root):self.assertEqual(pack.payload(path),raw)
    def test_mixed_private_json_still_redacts_before_publication(self):
        import json
        import package_submission as pack
        raw=b'{"rows":[{"case_id":"CL-EN-01","text":"public"},{"case_id":"CALL-01","text":"private"}]}'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'mixed.json';path.write_bytes(raw)
            with patch.object(pack,'P',root):clean=pack.payload(path)
            self.assertEqual(json.loads(clean),{'rows':[{'case_id':'CL-EN-01','text':'public'}]})
            self.assertNotIn(b'private',clean)
    def test_private_csv_records_are_omitted_entirely(self):
        raw=b'clip_id,reference_transcript,hypothesis_raw,word_edits,ref_word_count,human_reference_verified\nCALL-01,private sentence,private name,2,8,true\n'
        data=csv_payload(raw,'results/asr_results.csv',{'CALL-01':{'nospace_char_edits':'3','nospace_ref_chars':'40'}})
        self.assertEqual(list(csv.DictReader(io.StringIO(data.decode('utf-8-sig')))),[])
        self.assertNotIn(b'CALL-01',data);self.assertNotIn(b'private sentence',data)
    def test_public_csv_unchanged(self):
        raw=b'clip_id,reference_transcript\nCL-EN-01,public sentence\n'
        self.assertEqual(csv_payload(raw,'data/asr_manifest.csv',{}),raw)
    def test_raw_private_assets_excluded(self):
        for name in ['data/audio/CALL-01.wav','results/raw/asr/CALL-01/request.json','results/judge/raw/asr_blind/CALL-01__fingerprint.json','results/next/call/session/turn.wav','results/verification/owner_exports/file.csv']:
            self.assertTrue(excluded(name),name)
        self.assertFalse(excluded('data/audio/CL-EN-01.wav'))
    def test_private_log_drops_transcript(self):
        row=private_json({'case_id':'CALL-01','transcript':'private text','http_status':200,'kind':'asr'})
        self.assertIsNone(row)
    def test_private_call_audio_path_caches_are_omitted(self):
        self.assertIsNone(private_json({'id':'session-turn-1','audio':'results/next/call/session/caller1.wav','reply':{'transcript':'private'}}))
    def test_known_secret_blocks_release_without_printing_value(self):
        value=b'fixture-sensitive-value'
        with self.assertRaisesRegex(ValueError,'artifact.json'):
            check_secrets(value,'artifact.json',[value])
        check_secrets(b'no credentials','public.csv',[value])
    def test_plaintext_api_error_with_json_suffix_is_preserved(self):
        import package_submission as pack
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'response.json';path.write_bytes(b'upstream temporarily unavailable')
            with patch.object(pack,'P',root):
                self.assertEqual(pack.payload(path),b'upstream temporarily unavailable')


if __name__=='__main__':unittest.main()
