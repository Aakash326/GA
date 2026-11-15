import csv
import json
from pathlib import Path
import sys
import unittest

P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
from evaluation_metrics import normalize, score, corpus
import run_evaluation as runner


class CustomMetricTests(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(score('same words','same words')['wer'],0)
        self.assertEqual(score('same words','same words')['cer'],0)
    def test_substitution(self):
        r=score('buy fifteen shares','buy fifty shares')
        self.assertEqual((r['substitutions'],r['deletions'],r['insertions']),(1,0,0))
        self.assertAlmostEqual(r['wer'],1/3)
    def test_insertion(self):
        self.assertEqual(score('check balance','please check balance')['insertions'],1)
    def test_deletion(self):
        self.assertEqual(score('my balance is ten','my balance ten')['deletions'],1)
    def test_empty_reference(self):
        for hyp in ['', 'invented words']:
            r=score('',hyp);self.assertIsNone(r['wer']);self.assertIsNone(r['cer'])
            self.assertEqual(r['false_transcription'],bool(hyp))
        self.assertEqual(score('','invented words')['no_speech_inserted_words'],2)
    def test_empty_hypothesis(self):
        self.assertEqual(score('two words','')['wer'],1)
    def test_unicode_digits_and_signs(self):
        self.assertEqual(normalize('ವರ್ಷ ೨೦೧೭; −2.5%'),'ವರ್ಷ 2017 -2.5%')
        self.assertEqual(score('ವರ್ಷ ೨೦೧೭','ವರ್ಷ 2017')['wer'],0)
        self.assertNotEqual(normalize('-2.5%'),normalize('2.5%'))
    def test_unicode_composition_and_case(self):
        self.assertEqual(normalize('E\u0301'),normalize('é'))
    def test_punctuation_and_number_formatting(self):
        self.assertEqual(normalize('Hello, world! 9:05 AM.'),'hello world 9:05 am')
        self.assertEqual(normalize('ID 0070'),'id 0070')
    def test_mixed_scripts_not_exempted(self):
        self.assertGreater(score('चित्रम फिल्म','चित्रम film')['wer'],0)
    def test_whitespace_and_cer(self):
        self.assertEqual(normalize(' a\t b\n'),'a b')
        self.assertAlmostEqual(score('a b','ab')['cer'],1/3)
        self.assertEqual(score('a b','ab')['nospace_char_edits'],0)
    def test_corpus_weighting_and_no_speech_exclusion(self):
        rows=[score('a','b'),score('one two three four five six seven eight nine','one two three four five six seven eight nine'),score('','hallucination')]
        self.assertAlmostEqual(corpus(rows)['wer'],.1)
        self.assertEqual(corpus(rows)['speech_clips'],2)
    def test_more_than_one_hundred_percent_is_valid(self):
        self.assertEqual(score('a','b c d')['wer'],3)


if __name__=='__main__':unittest.main()
