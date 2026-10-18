"""Regression checks for large CSVs and bounded prediction chunks."""
import json
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app import app, prepare_predictions
from backend.import_analysis import parse
from backend.limits import MAX_ROWS, PREDICTION_CHUNK_ROWS

class LargeImportTests(unittest.TestCase):
    def test_file_over_old_size_limit_retains_every_row(self):
        content='temperature,notes\n'+('20,'+'x'*900+'\n')*6000
        self.assertGreater(len(content),5_000_000)
        with TestClient(app) as client:
            inspection=client.post('/inspect',files={'file':('large.csv',content)})
            self.assertEqual(inspection.status_code,200,inspection.text)
            self.assertEqual(inspection.json()['total'],6000)
            response=client.post('/analyze',files={'file':('large.csv',content)},data={'config':json.dumps({'quality_only':True})})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(len(data['rows']),6000)
        self.assertEqual(data['quality']['duplicate_rows'],5999)
        self.assertEqual(data['rows'][-1]['original']['notes'],'x'*900)

    def test_chunk_boundaries_keep_predictions_and_errors_in_order(self):
        content='PM2.5,PM10,id\n' + ''.join(
            f'{-1 if i==1000 else 42},{80 if i%2 else ""},{i}\n' for i in range(2501))
        with patch('backend.app.prepare_predictions',wraps=prepare_predictions) as chunks:
            with TestClient(app) as client:
                response=client.post('/analyze',files={'file':('many.csv',content)})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['summary']['valid'],2500)
        self.assertEqual(data['summary']['invalid'],1)
        self.assertEqual([r['original']['id'] for r in data['rows']],[str(i) for i in range(2501)])
        self.assertIsNotNone(data['rows'][1000]['error'])
        self.assertEqual(data['rows'][0]['result']['model_id'],'pm25')
        self.assertEqual(data['rows'][1]['result']['model_id'],'pm_pair')
        self.assertEqual(data['rows'][-1]['result']['model_id'],'pm25')
        # flush clears its input list, so call_args cannot measure sizes later.
        self.assertEqual(chunks.call_count,3)

    def test_row_boundary_and_chunk_configuration(self):
        headers,rows=parse(('temperature\n'+'20\n'*MAX_ROWS).encode())
        self.assertEqual(len(rows),MAX_ROWS)
        with self.assertRaisesRegex(ValueError,'250,000'):
            parse(('temperature\n'+'20\n'*(MAX_ROWS+1)).encode())
        self.assertEqual(PREDICTION_CHUNK_ROWS,1000)

if __name__=='__main__': unittest.main()
