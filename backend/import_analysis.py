"""Flexible import: explicit mapping, conservative units and useful quality-only analysis."""
import csv
import io
import json
import math
import re
from collections import Counter
from datetime import datetime
from bisect import bisect_right
import numpy as np
from sklearn.metrics import accuracy_score,f1_score,confusion_matrix
from backend.limits import MAX_UPLOAD_BYTES, MAX_ROWS, PREDICTION_CHUNK_ROWS

FEATURES=['PM2.5','PM10','SO2','NO2','CO','O3']
KEYS=['pm25','pm10','so2','no2','co','o3']
CATEGORIES=['Good','Satisfactory','Moderate','Poor','Very Poor','Severe']
ALIASES={'PM2.5':['pm25','pm2p5','particulatematter25'], 'PM10':['pm10','particulatematter10'],
    'SO2':['so2','sulfurdioxide','sulphurdioxide'],'NO2':['no2','nitrogendioxide'],
    'CO':['co','carbonmonoxide'],'O3':['o3','ozone']}
def normalize(text): return re.sub(r'[^a-z0-9]','',text.lower())
def forbidden(text): return normalize(text).startswith(('aqi','co2','carbondioxide','airqualityindex')) or normalize(text) in ['label','target','category']
def missing(value): return value is None or str(value).strip().lower() in ['','na','nan','null','n/a']

def parse(content):
    if len(content)>MAX_UPLOAD_BYTES: raise ValueError('CSV exceeds the 50 MB limit.')
    reader=csv.DictReader(io.StringIO(content.decode('utf-8-sig')), strict=True)
    headers=reader.fieldnames or []
    if not headers or any(not h.strip() for h in headers): raise ValueError('CSV needs nonempty column headers.')
    if len(set(headers))!=len(headers): raise ValueError('Duplicate CSV headers are not supported.')
    rows=[]
    for row in reader:
        rows.append(row)
        if len(rows)>MAX_ROWS: raise ValueError(f'CSV is limited to {MAX_ROWS:,} observations per analysis.')
    if not rows: raise ValueError('CSV contains no observations.')
    return headers,rows

def inspect(content, parsed=None):
    headers,rows=parsed if parsed is not None else parse(content)
    suggestions={}
    for feature,aliases in ALIASES.items():
        matches=[h for h in headers if normalize(h) in aliases or h==feature]
        suggestions[feature]=matches[0] if len(matches)==1 else ''
    columns=[]
    for header in headers:
        values=[r.get(header) for r in rows]
        numbers=[]
        for value in values:
            if missing(value): continue
            try:
                number=float(value)
                if math.isfinite(number): numbers.append(number)
            except (ValueError,TypeError): pass
        average=sum(n/len(numbers) for n in numbers) if numbers else None
        histogram=[]
        if numbers:
            lo,hi=min(numbers),max(numbers)
            edges=[lo*(1-i/10)+hi*(i/10) for i in range(11)] if lo!=hi else [lo,hi]
            counts=[0]*(len(edges)-1)
            for n in numbers: counts[min(len(counts)-1,max(0,bisect_right(edges,n)-1))]+=1
            histogram=[{'lower':edges[i],'upper':edges[i+1],'count':count} for i,count in enumerate(counts)]
        columns.append({'name':header,'missing':sum(missing(v) for v in values),
            'numeric':len(numbers),'negative':sum(n<0 for n in numbers),
            'min':min(numbers) if numbers else None,'max':max(numbers) if numbers else None,
            'mean':average if average is not None and math.isfinite(average) else None,'histogram':histogram})
    duplicates=sum(c-1 for c in Counter(tuple(r.get(h) for h in headers) for r in rows).values())
    date_header=next((h for h in headers if normalize(h) in ['date','datetime','timestamp']),None)
    station_header=next((h for h in headers if normalize(h) in ['stationid','siteid','stationcode']),None)
    temporal=None
    if date_header:
        dates=[]; invalid=0; absent=0; groups={}; missing_station=0
        for row in rows:
            text=row.get(date_header)
            if missing(text): absent+=1;continue
            try:
                day=datetime.fromisoformat(text.strip().replace('Z','+00:00')).date()
                dates.append(day)
                station=row.get(station_header) if station_header else None
                if station_header and missing(station): missing_station+=1
                elif station_header: groups.setdefault(station,[]).append(day)
            except ValueError: invalid+=1
        gaps=0;duplicate_pairs=0
        for days in groups.values():
            ordered=sorted(set(days));duplicate_pairs+=len(days)-len(ordered)
            gaps+=sum(max(0,(b-a).days-1) for a,b in zip(ordered,ordered[1:]))
        temporal={'date_column':date_header,'station_column':station_header,'invalid_timestamps':invalid,
            'missing_timestamps':absent,'missing_station_ids':missing_station,
            'start':min(dates).isoformat() if dates else None,'end':max(dates).isoformat() if dates else None,
            'missing_station_days':gaps if station_header else None,'duplicate_station_days':duplicate_pairs if station_header else None,
            'method':'ISO 8601 calendar dates, without timezone conversion. Gaps inside each observed station range only; no fabricated observations or automatic aggregation.'}
    return {'headers':headers,'preview':rows[:5],'suggestions':suggestions,'total':len(rows),
        'columns':columns,'duplicate_rows':duplicates,
        'temporal':temporal,
        'reference_suggestion':next((h for h in headers if normalize(h)=='aqibucket'),'')}

def analyze(content,config,predict,Reading,models,prepare):
    headers,source=parse(content)
    overview=inspect(content, (headers,source))
    mapping=config.get('mapping')
    if mapping is None: mapping={f:f if f in headers else '' for f in FEATURES}
    if any(f not in FEATURES for f in mapping): raise ValueError('Unknown model feature in mapping.')
    used=[h for h in mapping.values() if h]
    if len(set(used))!=len(used): raise ValueError('A source column cannot map to more than one pollutant.')
    for f,h in mapping.items():
        if h and (h not in headers or forbidden(h)): raise ValueError(f'Invalid or forbidden source mapping for {f}: {h}')
    units=config.get('units',{})
    if any(f not in FEATURES for f in units): raise ValueError('Unknown feature in units configuration.')
    quality_only=config.get('quality_only',False) or not used
    if config.get('interval','daily')!='daily' and not config.get('quality_only') and used: raise ValueError('Classification currently requires daily observations. Aggregate hourly data independently or choose quality-only analysis.')
    factors={}
    for f in FEATURES:
        if not mapping.get(f): continue
        unit=units.get(f,'mg/m3' if f=='CO' else 'ug/m3')
        if unit not in ['ug/m3','mg/m3']:
            if quality_only:
                factors[f]=1
                continue
            raise ValueError(f'Unsupported unit for {f}; ppm conversion requires additional physical information.')
        factors[f]=(1 if unit==('mg/m3' if f=='CO' else 'ug/m3') else .001 if f=='CO' else 1000)
    report=[]
    readings=[]
    indexes=[]
    def flush():
        prepared=prepare(readings)
        for i,(index,reading) in enumerate(zip(indexes,readings)):
            report[index]['result']=predict(reading,explain=False,adaptive=True,prepared=prepared[i])
        readings.clear()
        indexes.clear()
    for number,row in enumerate(source,2):
        try:
            if None in row: raise ValueError('Row has more values than headers.')
            values={}
            for key,f in zip(KEYS,FEATURES):
                raw=row.get(mapping.get(f,''))
                value=None if missing(raw) else float(raw)
                if value is not None:
                    if not math.isfinite(value) or value<0: raise ValueError(f'{f} must be finite and nonnegative.')
                    value*=factors.get(f,1)
                    if not math.isfinite(value): raise ValueError(f'{f} overflows after unit conversion.')
                values[key]=value
            if not quality_only:
                if all(v is None for v in values.values()): raise ValueError('Provide at least one pollutant measurement.')
                readings.append(Reading(**values)); indexes.append(len(report))
            report.append({'row':number,'original':row,'result':None,'error':None,'normalized':None if quality_only else dict(zip(FEATURES,values.values()))})
        except (ValueError,TypeError) as error:
            report.append({'row':number,'original':row,'result':None,'error':str(error)})
        if len(readings)>=PREDICTION_CHUNK_ROWS: flush()
    if readings: flush()
    valid=[r for r in report if r['result']]
    label=config.get('label_column','AQI_Bucket')
    refs=[r for r in valid if r['original'].get(label) in CATEGORIES]
    metrics=None
    if refs:
        actual=[r['original'][label] for r in refs]; predicted=[r['result']['predicted_category'] for r in refs]
        metrics={'accuracy':accuracy_score(actual,predicted),'macro_f1':f1_score(actual,predicted,labels=CATEGORIES,average='macro',zero_division=0),
            'confusion_matrix':confusion_matrix(actual,predicted,labels=CATEGORIES).tolist(),'categories':CATEGORIES,
            'caveat':'Uploaded-label agreement; independence, regional transfer and label quality are not established. Macro F1 includes all six categories, including absent-class zeros.'}
    mapped=[f for f in FEATURES if mapping.get(f)]
    eligible=[{'id':m['id'],'name':m['name'],'accuracy':m['accuracy'],'macro_f1':m['macro_f1']} for m in models if set(m['features']).issubset(mapped)]
    return {'rows':report,'summary':{'total':len(report),'valid':len(valid),'invalid':sum(r['error'] is not None for r in report),
        'unusual':sum(r['result']['is_unusual_reading'] for r in valid),'with_warnings':sum(bool(r['result']['warnings']) for r in valid),
        'reference_rows':len(refs),'reference_agreement':metrics['accuracy'] if metrics else None},
        'quality':overview,'evaluation':metrics,'compatibility':{'mapped':mapped,'eligible':eligible,
            'quality_only':quality_only,'mapping':mapping,'units':units,
            'policy':'Per-row selection: complete six inputs, then PM pair, then PM2.5; otherwise explicit baseline imputation fallback.'},
        'disclaimer':'Research decision support. Uncalibrated probabilities. Unit conversion does not establish sensor or regional compatibility.'}
