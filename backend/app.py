import csv
import io
import json
import math
import sys
import threading
from pathlib import Path
from functools import lru_cache
import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import FastAPI, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from backend.limits import MAX_UPLOAD_BYTES

FEATURES = ['PM2.5', 'PM10', 'SO2', 'NO2', 'CO', 'O3']
KEYS = ['pm25', 'pm10', 'so2', 'no2', 'co', 'o3']
MODEL_MAX=float(np.finfo(np.float32).max)
CEILINGS = [1000, 1200, 500, 500, 50, 300]
DISCLAIMER = 'Research decision support. Not an official government AQI advisory. Model probabilities are uncalibrated.'
BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
_load_lock = threading.Lock()

@lru_cache
def _load_engine():
    path = BASE / 'artifacts' / 'baseline.joblib'
    if not path.exists():
        raise HTTPException(503, 'No trained model is installed. Run python -m backend.train.')
    bundle = joblib.load(path)
    metadata = json.loads((BASE / 'artifacts' / 'metadata.json').read_text(encoding='utf-8'))
    station_path=BASE/'artifacts'/'baseline_station_evaluation.json'
    if station_path.exists(): metadata['station_holdout']=json.loads(station_path.read_text(encoding='utf-8'))
    return bundle['model'], bundle['anomaly'], shap.TreeExplainer(bundle['model']['classifier']), metadata

def engine():
    # Avoid loading the large forest/explainer twice on concurrent startup requests.
    with _load_lock:
        return _load_engine()

class Reading(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    pm25: float | None = Field(default=None, ge=0, le=MODEL_MAX)
    pm10: float | None = Field(default=None, ge=0, le=MODEL_MAX)
    so2: float | None = Field(default=None, ge=0, le=MODEL_MAX)
    no2: float | None = Field(default=None, ge=0, le=MODEL_MAX)
    co: float | None = Field(default=None, ge=0, le=MODEL_MAX)
    o3: float | None = Field(default=None, ge=0, le=MODEL_MAX)

class ImportSettings(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mapping: dict[str,str] | None = None
    units: dict[str,str] = Field(default_factory=dict)
    interval: Literal['daily','hourly','unknown'] = 'daily'
    quality_only: bool = False
    label_column: str = 'AQI_Bucket'

app = FastAPI(title='Atmosight', version='1.1.2')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173',
    'http://localhost:4173', 'http://127.0.0.1:4173', 'http://tauri.localhost', 'https://tauri.localhost', 'tauri://localhost'],
    allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])

@app.get('/health')
def health():
    return {'status': 'ready', 'model': engine()[3]['name']}

@app.get('/model')
def model_info():
    meta=dict(engine()[3])
    meta['sensor_models']=models()[1:]
    meta['limitations']=[l for l in meta['limitations'] if not l.startswith('Only the six-pollutant')]
    meta['limitations'].append('No temporal model. Sensor-specific variants have separate evaluation evidence; no automatic retraining or regional adaptation.')
    return meta

@lru_cache
def _variant(identifier):
    bundle = joblib.load(BASE/'artifacts'/f'{identifier}.joblib')
    meta = json.loads((BASE/'artifacts'/f'{identifier}.json').read_text(encoding='utf-8'))
    return bundle['model'], bundle['anomaly'], shap.TreeExplainer(bundle['model']['classifier']), meta

def select_engine(values):
    return _select_available(tuple(value is not None for value in values))

@lru_cache(maxsize=64)
def _select_available(mask):
    # Six sensors have only 64 availability patterns. Reuse routing decisions
    # instead of checking the filesystem and taking load locks for every CSV row.
    # Installed artifacts are immutable during a running backend session.
    available = {name for name,present in zip(FEATURES,mask) if present}
    if len(available)==6: return engine(), FEATURES, 'baseline'
    for identifier,names in [('pm_pair',['PM2.5','PM10']),('pm25',['PM2.5'])]:
        if set(names).issubset(available) and (BASE/'artifacts'/f'{identifier}.json').exists() and (BASE/'artifacts'/f'{identifier}.joblib').exists():
            with _load_lock: return _variant(identifier),names,identifier
    return engine(),FEATURES,'baseline'

@app.get('/models')
def models():
    baseline = dict(engine()[3],id='baseline')
    baseline['limitations']=[l for l in baseline['limitations'] if not l.startswith('Only the six-pollutant')]
    station_path=BASE/'artifacts'/'baseline_station_evaluation.json'
    if station_path.exists(): baseline['station_holdout']=json.loads(station_path.read_text(encoding='utf-8'))
    others = [json.loads(p.read_text(encoding='utf-8')) for p in (BASE/'artifacts').glob('pm*.json') if p.with_suffix('.joblib').exists()]
    return [baseline]+others

def prepare_predictions(readings):
    groups={}
    for index,reading in enumerate(readings):
        values=[getattr(reading,k) for k in KEYS]
        selected,names,identifier=select_engine(values)
        groups.setdefault(identifier,{'selected':selected,'names':names,'rows':[]})['rows'].append((index,dict(zip(FEATURES,values))))
    output=[None]*len(readings)
    for group in groups.values():
        model,anomaly,_,_=group['selected']; names=group['names']
        frame=pd.DataFrame([[values[n] for n in names] for _,values in group['rows']],columns=names).astype(float)
        probabilities=model.predict_proba(frame)
        scores=anomaly.decision_function(model['imputer'].transform(frame))
        for i,(index,_) in enumerate(group['rows']): output[index]=(probabilities[i],scores[i])
    return output

def predict(reading: Reading, explain=True, prepared=None, adaptive=False):
    values = [getattr(reading, key) for key in KEYS]
    if all(v is None for v in values):
        raise ValueError('Provide at least one pollutant measurement.')
    selected,names,identifier = select_engine(values) if adaptive else (engine(),FEATURES,'baseline')
    model, anomaly, explainer, metadata = selected
    by_name = dict(zip(FEATURES,values))
    # Batch predictions already include probability and anomaly scores. Avoid
    # constructing/imputing a separate DataFrame for every output row.
    if prepared is None or explain:
        frame = pd.DataFrame([[np.nan if by_name[n] is None else by_name[n] for n in names]], columns=names)
        transformed = model['imputer'].transform(frame)
    probabilities = prepared[0] if prepared is not None else model.predict_proba(frame)[0]
    index = int(np.argmax(probabilities))
    warnings = [f'{name} is missing; training median used.' for name, value in zip(FEATURES, values) if value is None]
    if identifier!='baseline':
        warnings = [f'{name} is unavailable and is not required by the selected model.' for name,value in zip(FEATURES,values) if value is None]
        if available_unused := [n for n,v in zip(FEATURES,values) if v is not None and n not in names]:
            warnings.append('Selected model does not use: '+', '.join(available_unused))
        warnings.append('Sensor-specific research model: inspect its evaluation evidence before interpreting results.')
    warnings += [f'{name} exceeds the screening ceiling ({ceiling}); verify the measurement.'
                 for name, value, ceiling in zip(FEATURES, values, CEILINGS) if value is not None and value > ceiling]
    if values[0] is not None and values[1] is not None and values[0] > values[1]:
        warnings.append('PM2.5 exceeds PM10; check units and sensor consistency.')
    score = float(prepared[1] if prepared is not None else anomaly.decision_function(transformed)[0])
    unusual = score < 0
    if unusual:
        warnings.append('Isolation Forest flags this reading as statistically unusual.')
    factors = []
    base = None
    if explain:
        contributions = explainer.shap_values(transformed, check_additivity=False)
        vector = contributions[0, :, index] if isinstance(contributions, np.ndarray) else contributions[index][0]
        factors = sorted([{'pollutant': name, 'impact': float(value)}
                         for name, value in zip(names, vector)], key=lambda f: abs(f['impact']), reverse=True)
        base = float(np.asarray(explainer.expected_value)[index])
    return {'predicted_category': str(model.classes_[index]), 'confidence': float(probabilities[index]),
            'probabilities': dict(zip(model.classes_.tolist(), probabilities.tolist())),
            'top_factors': factors, 'explanation_base': base, 'is_unusual_reading': unusual,
            'anomaly_score': score,
            'completeness': sum(v is not None for v in values) / 6,
            'warnings': warnings, 'original_values': dict(zip(FEATURES, values)), 'disclaimer': DISCLAIMER,
            'model_artifact_sha256':metadata.get('artifact_sha256'),'model_id':identifier,'model_name':metadata['name'],'model_features':names,
            'model_evaluation':{'accuracy':metadata['accuracy'],'macro_f1':metadata['macro_f1'],
                'station_holdout':{k:metadata['station_holdout'][k] for k in ['accuracy','macro_f1','test_rows']} if metadata.get('station_holdout') else None},
            'model_completeness':sum(by_name[n] is not None for n in names)/len(names)}

@app.post('/predict')
def classify(reading: Reading):
    try:
        return predict(reading,adaptive=True)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

@app.post('/inspect')
async def inspect_dataset(file: UploadFile):
    from backend.import_analysis import inspect
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content)>MAX_UPLOAD_BYTES: raise HTTPException(413,'CSV exceeds the 50 MB limit.')
        return await run_in_threadpool(inspect, content)
    except (UnicodeDecodeError,csv.Error,ValueError) as error:
        raise HTTPException(422,str(error)) from error

@app.post('/analyze')
async def analyze(file: UploadFile, config: str = Form('{}')):
    from backend.import_analysis import analyze as analyze_import
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content)>MAX_UPLOAD_BYTES: raise HTTPException(413,'CSV exceeds the 50 MB limit.')
    try:
        settings=json.loads(config)
        if not isinstance(settings,dict): raise ValueError('Import configuration must be an object.')
        settings=ImportSettings.model_validate(settings).model_dump()
        def work():
            report = analyze_import(content,settings,predict,Reading,models() if not settings.get('quality_only') else [],prepare_predictions)
            # The report already contains JSON-compatible values. Serialize once
            # in the worker, rather than walking every row again on the event loop.
            # This keeps health/model requests responsive during large exports.
            return JSONResponse(report)
        return await run_in_threadpool(work)
    except (UnicodeDecodeError,csv.Error,ValueError,TypeError) as error:
        raise HTTPException(422,str(error)) from error

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    import uvicorn
    import os
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('ATMOSIGHT_PORT','8000')))
