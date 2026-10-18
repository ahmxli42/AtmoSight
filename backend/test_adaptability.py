import json
import unittest
from fastapi.testclient import TestClient
from backend.app import app

class AdaptabilityTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(app)
    def analyze(self,csv,config):
        return self.client.post('/analyze',files={'file':('measurements.csv',csv)},data={'config':json.dumps(config)})
    def test_mapping_and_units_match_canonical(self):
        config={'mapping':{'PM2.5':'fine','PM10':'coarse','CO':'carbon'},'units':{'PM2.5':'mg/m3','PM10':'ug/m3','CO':'ug/m3'}}
        response=self.analyze('fine,coarse,carbon\n0.042,80,800\n',config)
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()['rows'][0]['result']
        canonical=self.client.post('/predict',json={'pm25':42,'pm10':80,'co':.8}).json()
        for label, probability in result['probabilities'].items():
            self.assertAlmostEqual(probability, canonical['probabilities'][label], places=12)
        self.assertEqual(result['original_values']['CO'],.8)
        self.assertEqual(response.json()['rows'][0]['original']['carbon'],'800')
    def test_target_mapping_and_duplicate_mapping_rejected(self):
        for config in [{'mapping':{'PM2.5':'AQI'}},{'mapping':{'PM2.5':'fine','PM10':'fine'}},{'mapping':{'CO':'CO2'}}]:
            self.assertEqual(self.analyze('AQI,fine,CO2\n100,42,400\n',config).status_code,422)
    def test_quality_only_unrelated_schema(self):
        response=self.analyze('temperature,humidity\n-5,60\n-5,60\n,70\n',{'quality_only':True,'interval':'hourly'})
        self.assertEqual(response.status_code,200,response.text)
        report=response.json()
        self.assertEqual(report['summary']['valid'],0)
        self.assertEqual(report['quality']['duplicate_rows'],1)
        self.assertEqual(report['quality']['columns'][0]['missing'],1)
        self.assertTrue(all(r['result'] is None for r in report['rows']))
    def test_configuration_selection_and_shap(self):
        for values,identifier in [({'pm25':42},'pm25'),({'pm25':42,'pm10':80},'pm_pair'),({'pm25':42,'pm10':80,'so2':12,'no2':20,'co':.8,'o3':35},'baseline')]:
            result=self.client.post('/predict',json=values).json()
            self.assertEqual(result['model_id'],identifier)
            self.assertAlmostEqual(result['explanation_base']+sum(f['impact'] for f in result['top_factors']),result['confidence'],places=5)
    def test_interval_and_ppm_guards(self):
        for config in [{'mapping':{'PM2.5':'fine'},'interval':'hourly'},{'mapping':{'PM2.5':'fine'},'units':{'PM2.5':'ppm'}}]:
            self.assertEqual(self.analyze('fine\n42\n',config).status_code,422)
    def test_aliases_and_reference_evaluation(self):
        csv='PM_25,PM_10,label\n42,80,Good\n'
        preview=self.client.post('/inspect',files={'file':('data.csv',csv)}).json()
        self.assertEqual(preview['suggestions']['PM2.5'],'PM_25')
        response=self.analyze(csv,{'mapping':preview['suggestions'],'label_column':'label'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['summary']['reference_rows'],1)
        self.assertEqual(sum(map(sum,response.json()['evaluation']['confusion_matrix'])),1)

    def test_temporal_diagnostics_preserve_station_boundaries(self):
        csv='Date,StationId,temperature\n2026-10-01,A,1\n2026-10-03,A,2\n2026-10-03,A,2\n2026-10-02,B,3\nbad,B,4\n'
        overview=self.client.post('/inspect',files={'file':('data.csv',csv)}).json()
        self.assertEqual(overview['temporal']['missing_station_days'],1)
        self.assertEqual(overview['temporal']['duplicate_station_days'],1)
        self.assertEqual(overview['temporal']['invalid_timestamps'],1)
        self.assertEqual(sum(b['count'] for b in overview['columns'][2]['histogram']),5)

    def test_malformed_configuration_rejected(self):
        self.assertEqual(self.analyze('fine\n42\n',{'mapping':['fine']}).status_code,422)

    def test_size_and_model_numeric_bounds(self):
        oversized='PM2.5\n'+'1'*50_000_000
        self.assertEqual(self.analyze(oversized,{}).status_code,413)
        response=self.analyze('PM2.5\n42\n1e308\n',{})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['summary']['valid'],1)
        self.assertEqual(response.json()['summary']['invalid'],1)

if __name__=='__main__': unittest.main()
