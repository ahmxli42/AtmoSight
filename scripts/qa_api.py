"""Real HTTP uploads against a running Atmosight backend; preserves CSVs/models."""
import os
import argparse
import json
import time
from collections import Counter
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8003')
parser.add_argument('--output', default='api-results.json')
parser.add_argument('--large-only', action='store_true')
args = parser.parse_args()
records=[]
dataset_root=Path(os.environ.get('ATMOSIGHT_DATASET_DIR', ROOT/'Dataset'))
out=ROOT/'docs'/'qa-2026-10-17'/args.output
out.parent.mkdir(parents=True,exist_ok=True)
def record(name, start, **details):
    records.append(dict(name=name, seconds=round(time.perf_counter()-start,3), **details))
    out.write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps(records[-1]),flush=True)

with httpx.Client(base_url=args.url,timeout=600,trust_env=False) as client:
    if not args.large_only:
        start=time.perf_counter()
        models=client.get('/models'); models.raise_for_status()
        assert {m['id'] for m in models.json()}=={'baseline','pm_pair','pm25'}
        record('model registry',start)
        for values,model in [({'pm25':42},'pm25'),({'pm25':42,'pm10':80},'pm_pair'),({'pm25':42,'pm10':80,'so2':12,'no2':20,'co':.8,'o3':35},'baseline'),({'no2':20},'baseline')]:
            start=time.perf_counter();r=client.post('/predict',json=values);r.raise_for_status();v=r.json()
            assert v['model_id']==model
            assert abs(sum(v['probabilities'].values())-1)<1e-9
            assert abs(v['explanation_base']+sum(f['impact'] for f in v['top_factors'])-v['confidence'])<1e-5
            record('prediction '+model,start,inputs=values,category=v['predicted_category'])
        for name,content in [('duplicate','PM2.5,PM2.5\n1,2\n'),('empty','PM2.5\n'),('unclosed quote','PM2.5\n"42\n'),('invalid utf8',b'PM2.5\n\xff')]:
            start=time.perf_counter();r=client.post('/inspect',files={'file':('invalid.csv',content)})
            assert r.status_code==422,(name,r.status_code)
            record('reject '+name,start,status=r.status_code)
        for name in ['stations.csv','city_day.csv','station_day_cleaned.csv']:
            start=time.perf_counter()
            with (dataset_root/name).open('rb') as f:r=client.post('/analyze',files={'file':(name,f,'text/csv')})
            r.raise_for_status();data=r.json();summary=data['summary'];assert len(data['rows'])==summary['total']
            assert summary['valid']+summary['invalid']==summary['total'] or data['compatibility']['quality_only']
            record('upload '+name,start,summary=summary,quality_only=data['compatibility']['quality_only'],response_bytes=len(r.content))
        start=time.perf_counter()
        with (dataset_root/'city_hour.csv').open('rb') as f:r=client.post('/inspect',files={'file':('city_hour.csv',f)})
        assert r.status_code==413
        record('oversize real file',start,status=r.status_code)
    name='station_day.csv';start=time.perf_counter()
    with (dataset_root/name).open('rb') as f:r=client.post('/analyze',files={'file':(name,f,'text/csv')})
    r.raise_for_status();data=r.json();summary=data['summary']
    assert summary['total']==108035 and len(data['rows'])==108035
    assert summary['valid']+summary['invalid']==summary['total']
    assert [row['row'] for row in data['rows']]==list(range(2,108037))
    record('upload '+name,start,summary=summary,response_bytes=len(r.content),models=dict(Counter(row['result']['model_id'] for row in data['rows'] if row['result'])))
