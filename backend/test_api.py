"""Checks inference integrity and CSV validation using the actual trained artifact."""
import unittest
from fastapi.testclient import TestClient
from backend.app import app

class InferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.values = {'pm25': 42, 'pm10': 80, 'so2': 12, 'no2': 20, 'co': .8, 'o3': 35}

    def test_shap_reconstructs_probability(self):
        response = self.client.post('/predict', json=self.values)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertAlmostEqual(sum(result['probabilities'].values()), 1)
        self.assertAlmostEqual(result['explanation_base'] + sum(f['impact'] for f in result['top_factors']), result['confidence'], places=5)
        self.assertEqual(result['completeness'], 1)

    def test_invalid_and_leaked_inputs_rejected(self):
        for values in [{}, {'pm25': -1}, {'pm25': 10, 'AQI': 20}]:
            self.assertEqual(self.client.post('/predict', json=values).status_code, 422)

    def test_partial_input_preserved(self):
        result = self.client.post('/predict', json={'pm25': 42}).json()
        self.assertAlmostEqual(result['completeness'], 1/6)
        self.assertIsNone(result['original_values']['PM10'])
        self.assertEqual(result['model_id'],'pm25')
        self.assertEqual(result['model_completeness'],1)

    def test_batch_matches_single_and_keeps_invalid_rows(self):
        csv = 'PM2.5,PM10,SO2,NO2,CO,O3,AQI,AQI_Bucket\n42,80,12,20,0.8,35,999,Good\n-1,80,12,20,0.8,35,5,Good\n42,,,,,,777,Good\n'
        response = self.client.post('/analyze', files={'file': ('data.csv', csv, 'text/csv')})
        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        self.assertEqual(report['summary']['valid'], 2)
        self.assertEqual(report['summary']['invalid'], 1)
        single = self.client.post('/predict', json=self.values).json()
        for label, probability in single['probabilities'].items():
            self.assertAlmostEqual(report['rows'][0]['result']['probabilities'][label], probability, places=12)
        self.assertEqual(report['rows'][0]['original']['AQI'], '999')
        self.assertEqual(report['rows'][2]['result']['original_values']['PM10'], None)

    def test_csv_schema_and_limits(self):
        for csv in ['PM2.5,PM2.5\n1,2\n', 'PM2.5\n']:
            self.assertEqual(self.client.post('/analyze', files={'file': ('data.csv', csv)}).status_code, 422)

    def test_unclosed_csv_quote_is_rejected_without_merging_rows(self):
        for endpoint in ['/inspect', '/analyze']:
            response = self.client.post(endpoint, files={'file': ('broken.csv', 'PM2.5,PM10\n"42,80\n55,100\n')})
            self.assertEqual(response.status_code, 422, response.text)

    def test_every_sensor_availability_pattern_uses_expected_route(self):
        from itertools import product
        from backend.app import select_engine
        for mask in product([False, True], repeat=6):
            values = [42 if present else None for present in mask]
            expected = 'baseline' if all(mask) else 'pm_pair' if mask[0] and mask[1] else 'pm25' if mask[0] else 'baseline'
            self.assertEqual(select_engine(values)[2], expected)

if __name__ == '__main__':
    unittest.main()
