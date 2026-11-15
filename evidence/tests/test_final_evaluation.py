import csv,hashlib,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def read(name):
    with (P/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
class FinalEvaluation(unittest.TestCase):
    def test_all_24_calls_succeeded_and_references_are_machine_labelled(self):
        rows=read('results/next/dataset_replacement_verified_results.csv')
        self.assertEqual(len(rows),24);self.assertEqual(len({r['clip_id'] for r in rows}),24)
        self.assertTrue(all(r['status']=='success' and r['reference_usable']=='True' for r in rows))
        self.assertTrue(all(r['human_verified']=='False' and r['reference_assessor']=='audio_llm_provisional' for r in rows))
    def test_reference_audit_uses_unchanged_input_audio(self):
        manifest={r['clip_id']:r for name in ['data/next/asr_next_manifest.csv','data/next/asr_dataset_replacement.csv'] for r in read(name)}
        rows=read('results/verification/final_reference_audit.csv');self.assertEqual(len(rows),59)
        self.assertEqual(sum(r['cohort']=='original_dispute' for r in rows),35)
        for r in rows:
            self.assertEqual(r['input_sha256'],hashlib.sha256((P/manifest[r['clip_id']]['input_path']).read_bytes()).hexdigest())
            self.assertEqual(r['human_verified'],'False')
    def test_report_summary_uses_weighted_word_counts(self):
        rows=read('results/next/dataset_replacement_verified_results.csv')
        expected=sum(float(r['word_edits']) for r in rows)/sum(float(r['ref_words']) for r in rows)
        summary=json.loads((P/'results/next/dataset_replacement_verified_summary.json').read_text())
        self.assertAlmostEqual(summary['wer'],expected)
        self.assertEqual(sum(r['scored'] for r in summary['by_category'].values()),24)
    def test_owner_tts_blanks_remain_pending(self):
        summary=json.loads((P/'results/verification/n1_review_import.json').read_text())
        self.assertEqual(summary['human_marked_targets'],74);self.assertEqual(summary['pending_targets'],15)
        self.assertEqual(len(read('results/verification/tts_pending_machine_evidence.csv')),15)
if __name__=='__main__':unittest.main()
