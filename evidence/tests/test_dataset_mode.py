import csv,hashlib,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]
class DatasetMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (P/'data/next/asr_dataset_replacement.csv').open(encoding='utf-8-sig',newline='') as f:cls.rows=list(csv.DictReader(f))
    def test_24_actual_audio_files_and_hashes(self):
        self.assertEqual(len(self.rows),24)
        self.assertEqual(len({r['input_sha256'] for r in self.rows}),24)
        for r in self.rows:self.assertEqual(hashlib.sha256((P/r['input_path']).read_bytes()).hexdigest(),r['input_sha256'])
    def test_source_and_coverage_labels_preserved(self):
        finance=[r for r in self.rows if r['category']=='finance_related_questions']
        mixed=[r for r in self.rows if r['category']=='technical_hindi_english_codeswitch']
        self.assertEqual(len(finance),12);self.assertEqual(len(mixed),12)
        self.assertEqual({r['language'] for r in finance},{'en-IN','hi-IN','te-IN'})
        self.assertTrue(all('CC-BY-SA-4.0' in r['license_or_consent'] for r in mixed))
        self.assertTrue(all(r['human_reference_verified']=='false' and r['status']=='prepared_not_run' for r in self.rows))
    def test_no_microphone_capture_in_public_review_pages(self):
        for name in ['data/listening/tts_quality_study.html','results/playback_validation/index.html']:
            page=(P/name).read_text(encoding='utf8')
            self.assertNotIn('getUserMedia',page);self.assertNotIn('data-start',page)
        with (P/'data/listening/tts_quality_study_manifest.csv').open(encoding='utf-8-sig',newline='') as f:study=list(csv.DictReader(f))
        self.assertEqual(len(study),12)
        self.assertTrue(all((P/r['audio_path']).is_file() for r in study))
if __name__=='__main__':unittest.main()
