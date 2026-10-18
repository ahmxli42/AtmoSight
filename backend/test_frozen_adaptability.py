"""Run against a separately started frozen backend on port 8002."""
import json
import httpx

def main():
    with httpx.Client(base_url='http://127.0.0.1:8002',timeout=60) as client:
        response=client.get('/models'); response.raise_for_status()
        assert {m['id'] for m in response.json()}=={'baseline','pm25','pm_pair'}
        for values,identifier in [({'pm25':42},'pm25'),({'pm25':42,'pm10':80},'pm_pair'),
            ({'pm25':42,'pm10':80,'so2':12,'no2':20,'co':.8,'o3':35},'baseline')]:
            response=client.post('/predict',json=values);response.raise_for_status();result=response.json()
            assert result['model_id']==identifier
            assert abs(result['explanation_base']+sum(f['impact'] for f in result['top_factors'])-result['confidence'])<1e-5
            assert len(result['model_artifact_sha256'])==64
        config={'mapping':{'PM2.5':'fine','PM10':'coarse','CO':'carbon'},'units':{'PM2.5':'mg/m3','CO':'ug/m3'}}
        response=client.post('/analyze',files={'file':('mapped.csv','fine,coarse,carbon\n0.042,80,800\n')},data={'config':json.dumps(config)})
        response.raise_for_status();report=response.json()
        assert report['rows'][0]['result']['model_id']=='pm_pair'
        assert report['rows'][0]['normalized']['CO']==.8
        assert report['rows'][0]['original']['carbon']=='800'
        response=client.post('/analyze',files={'file':('quality.csv','temperature,humidity\n-5,60\n-5,60\n')},data={'config':json.dumps({'quality_only':True,'interval':'hourly'})})
        response.raise_for_status();report=response.json()
        assert report['summary']['valid']==0 and report['quality']['duplicate_rows']==1
        print('Frozen backend passed: model registry, all three routes, SHAP reconstruction, artifact provenance, unit mapping, original preservation, and quality-only analysis.')

if __name__=='__main__': main()
