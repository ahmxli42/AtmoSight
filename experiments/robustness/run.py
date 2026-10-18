"""Resumable prespecified CV and paired tests. No deployment writes."""
import argparse
import gc
import json
import platform
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import confusion_matrix
from .core import *

OUT=HERE/'results'
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2),encoding='utf-8');temp.replace(path)

def initialize():
    OUT.mkdir(parents=True,exist_ok=True)
    data,counts=load_data();splits=split_indices(data)
    code={name:file_hash(HERE/name) for name in ['core.py','run.py','protocol.json']}
    path=OUT/'manifest.json'
    if path.exists():
        manifest=json.loads(path.read_text())
        if manifest['code_hashes']!=code:raise RuntimeError('Experiment code or protocol changed; do not mix runs.')
        if manifest['protected_hashes']!=protected_files():raise RuntimeError('Protected deployed inputs changed.')
        return data,splits
    manifest={'started_utc':datetime.now(timezone.utc).isoformat(),'protocol':PROTOCOL,
        'code_hashes':code,'protected_hashes':protected_files(),'filter_counts':counts,
        'class_distribution':{c:int((data.AQI_Bucket==c).sum()) for c in CATEGORIES},
        'libraries':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__},
        'classifier_parameters':classifier(42).get_params(),'features':FEATURES,'categories':CATEGORIES,
        'splits':{}}
    for name,(train,test) in splits.items():
        record={'train_rows':len(train),'test_rows':len(test),
            'train_source_csv_rows':data.iloc[train].source_csv_row.tolist(),
            'test_source_csv_rows':data.iloc[test].source_csv_row.tolist(),
            'train_class_counts':data.iloc[train].AQI_Bucket.value_counts().to_dict(),
            'test_class_counts':data.iloc[test].AQI_Bucket.value_counts().to_dict(),
            'train_all_missing':int(data.iloc[train][FEATURES].isna().all(axis=1).sum()),
            'test_all_missing':int(data.iloc[test][FEATURES].isna().all(axis=1).sum())}
        if name=='station':
            record.update(train_stations=sorted(data.iloc[train].StationId.unique()),test_stations=sorted(data.iloc[test].StationId.unique()))
            existing=json.loads((ROOT/'backend/artifacts/baseline_station_evaluation.json').read_text())
            assert record['train_stations']==existing['training_station_ids']
            assert record['test_stations']==existing['test_station_ids']
        manifest['splits'][name]=record
    manifest['prespecified_document_sha256']=file_hash(ROOT/'docs/ROBUSTNESS_EXPERIMENT.md')
    (OUT/'prespecified_document.md').write_text((ROOT/'docs/ROBUSTNESS_EXPERIMENT.md').read_text(encoding='utf-8'),encoding='utf-8')
    save(path,manifest)
    return data,splits

def run_pair(phase,protocol,unit,variant,xtrain,ytrain,xeval,yeval,seed,train_ids,eval_ids,conditions,stats,rescues):
    path=OUT/phase/f'{protocol}_{unit}_{variant}.json'
    if path.exists():return
    started=time.perf_counter()
    flags=variant.endswith('_flags');mode='augment' if variant.startswith('augment') else 'replace'
    imputer=fit_imputer(xtrain)
    a,b,labels,training_stats=train_pair(xtrain,ytrain,mode,seed)
    shared=paired_matrices(conditions,imputer,flags)
    before={k:digest_array(v) for k,v in shared.items()}
    record={'phase':phase,'protocol':protocol,'unit':unit,'variant':variant,'seed':seed,
        'features':FEATURES+([f'{f}_missing' for f in FEATURES] if flags else []),
        'train_original_rows':len(xtrain),'train_rows_per_arm':len(labels),'eval_rows':len(yeval),
        'train_indices_sha256':digest_array(train_ids),'eval_indices_sha256':digest_array(eval_ids),
        'imputation_medians':imputer.statistics_.tolist(),'evaluation_hashes':before,
        'raw_evaluation_hashes':{k:digest_array(v) for k,v in conditions.items()},
        'training_degradation':training_stats,'evaluation_degradation':stats,'models':{}}
    for arm,training in [('A',a),('B',b)]:
        stamp=time.perf_counter();model=classifier(seed)
        model.fit(transform(training,imputer,flags),labels)
        result={}
        for condition,matrix in shared.items():
            prediction=model.predict(matrix)
            result[condition]=metrics(yeval,prediction)
            if condition=='severe':
                result[condition]['confusion_matrix']=confusion_matrix(yeval,prediction,labels=CATEGORIES).tolist()
                rescued=np.zeros(len(yeval),dtype=bool);rescued[rescues['severe']]=True
                result[condition]['repair_diagnostic']={}
                for name,mask in [('rescued',rescued),('not_rescued',~rescued),('naturally_all_missing',np.isnan(xeval).all(axis=1))]:
                    result[condition]['repair_diagnostic'][name]={'rows':int(mask.sum()),'metrics':metrics(yeval[mask],prediction[mask]) if mask.any() else None}
        record['models'][arm]={'results':result,'seconds':time.perf_counter()-stamp}
        print(f'{phase} {protocol} {unit} {variant} {arm} fitted/evaluated ({time.perf_counter()-stamp:.1f}s)',flush=True)
        del model;gc.collect()
    assert before=={k:digest_array(v) for k,v in shared.items()}
    record['paired_input_verified']=True;record['seconds']=time.perf_counter()-started
    save(path,record)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['cv','test','verify'],required=True);args=parser.parse_args()
    data,splits=initialize()
    if args.phase=='verify':
        save(OUT/'preservation_check.json',{'verified_utc':datetime.now(timezone.utc).isoformat(),'unchanged':True,'files':len(protected_files())});print('All protected files unchanged.');return
    if args.phase=='test':
        expected=[OUT/'cv'/f'{p}_fold{f}_{v}.json' for p in splits for f in range(1,6) for v in PROTOCOL['variants']]
        if not all(p.exists() for p in expected):raise RuntimeError('Complete all prespecified CV runs before final testing.')
    x=data[FEATURES].to_numpy(dtype=float);y=data.AQI_Bucket.to_numpy()
    for protocol,(train,test) in splits.items():
        if args.phase=='cv':
            cv=StratifiedKFold(n_splits=5,shuffle=True,random_state=42)
            units=[(f'fold{fold}',train[a],train[b],42+fold*10000) for fold,(a,b) in enumerate(cv.split(train,y[train]),1)]
        else:units=[(f'seed{seed}',train,test,seed) for seed in PROTOCOL['test_seeds']]
        for unit,tr,ev,seed in units:
            assert not set(tr)&set(ev)
            conditions,stats,rescues=evaluation_sets(x[ev],seed)
            for variant in PROTOCOL['variants']:
                run_pair(args.phase,protocol,unit,variant,x[tr],y[tr],x[ev],y[ev],seed,tr,ev,conditions,stats,rescues)
    print(args.phase+' complete',flush=True)

if __name__=='__main__':main()
