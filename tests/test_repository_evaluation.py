import json
from pathlib import Path
import unittest

from scripts.demo_repository_review import fixed_metrics


class FixedEvaluationTests(unittest.TestCase):
    def cases(self):
        fixtures = json.loads((Path(__file__).parent / 'fixtures/expected_defects.json').read_text())
        return [{'function': name, 'expected': expected,
                 'correct_defect_found': expected['expected_defect'] is not None,
                 'false_positive': name in ('sensorConnected', 'readSensor')}
                for name, expected in fixtures.items()]

    def test_auxiliary_helper_retained_but_excluded_from_fixed_metrics(self):
        cases = self.cases()
        result = fixed_metrics(cases)
        self.assertEqual(len(cases), 31)
        self.assertEqual((result['true_positives'], result['false_positives']), (20, 1))
        self.assertEqual(result['safe_functions'], 10)
        self.assertEqual(result['safe_false_positive_rate'], 0.1)
        self.assertEqual(result['safe_false_positives'], ['readSensor'])
        self.assertEqual(result['auxiliary_safe_false_positives'], ['sensorConnected'])
        self.assertFalse(next(c for c in cases if c['function'] == 'sensorConnected')['included_in_fixed_evaluation'])

    def test_missing_fixed_case_rejected(self):
        with self.assertRaisesRegex(ValueError, '20 defective and 10 safe'):
            fixed_metrics([c for c in self.cases() if c['function'] != 'readSensor'])
