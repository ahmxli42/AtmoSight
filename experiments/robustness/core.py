"""Pure experiment helpers. Never writes to deployed artifacts."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from backend.train import ROOT, FEATURES, CATEGORIES
from backend.train_sensor_models import pipeline

HERE=Path(__file__).resolve().parent
PROTOCOL=json.loads((HERE/'protocol.json').read_text())
GAS=np.array([2,3,4,5])

def digest_array(x):
    x=np.asarray(x,dtype=np.float64).copy()
    x[np.isnan(x)]=np.nan
    return hashlib.sha256(x.tobytes()).hexdigest()

def load_data():
    data=pd.read_csv(ROOT/'Dataset/station_day.csv')
    counts={'raw':len(data)}
    data=data.dropna(subset=['AQI_Bucket']);counts['after_nonmissing_target']=len(data)
    data=data.drop_duplicates(['StationId','Date']);counts['after_station_date_deduplication']=len(data)
    data=data[data.AQI_Bucket.isin(CATEGORIES)].copy();counts['after_recognized_categories']=len(data)
    data[FEATURES]=data[FEATURES].apply(pd.to_numeric,errors='coerce')
    counts['after_numeric_coercion']=len(data)
    data=data.loc[~(data[FEATURES]<0).any(axis=1)].copy()
    counts['after_negative_filter']=len(data)
    data['source_csv_row']=data.index+2
    data=data.reset_index(drop=True)
    counts['naturally_all_missing']=int(data[FEATURES].isna().all(axis=1).sum())
    if np.isinf(data[FEATURES].to_numpy(dtype=float)).any():
        raise ValueError('Infinite source values require an explicit protocol amendment.')
    return data,counts

def split_indices(data):
    train,test=train_test_split(np.arange(len(data)),test_size=.2,stratify=data.AQI_Bucket,random_state=42)
    gt,ge=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(data,groups=data.StationId.fillna('Unknown')))
    assert not set(train)&set(test) and not set(gt)&set(ge)
    assert not set(data.iloc[gt].StationId)&set(data.iloc[ge].StationId)
    return {'random':(train,test),'station':(gt,ge)}

def degrade(x,condition,seed):
    """Noise -> random mask -> gas removal -> observed-value rescue."""
    x=np.asarray(x,dtype=float)
    if x.ndim!=2 or x.shape[1]!=6: raise ValueError('Exactly six pollutant features required.')
    cfg=PROTOCOL[condition];rng=np.random.default_rng(seed)
    observed=np.isfinite(x)
    noisy=np.maximum(0,x*(1+rng.normal(0,cfg['sigma'],x.shape)))
    out=noisy.copy()
    mask=rng.random(x.shape)<cfg['mask_probability']
    out[mask & observed]=np.nan
    selected=rng.choice(len(x),size=int(len(x)*cfg['gas_absence_fraction']),replace=False)
    out[np.ix_(selected,GAS)]=np.nan
    rescue=np.flatnonzero(observed.any(axis=1)&np.isnan(out).all(axis=1))
    restored_gases=0
    for row in rescue:
        possible=np.flatnonzero(observed[row,:2])
        if not len(possible):
            possible=np.flatnonzero(observed[row]);restored_gases+=1
        col=rng.choice(possible);out[row,col]=noisy[row,col]
    assert not np.any(observed.any(axis=1)&np.isnan(out).all(axis=1))
    stats={'rows':len(x),'initial_missing_fraction':float(np.isnan(x).mean()),
        'random_mask_observed_fraction':float((mask&observed).sum()/observed.sum()) if observed.sum() else None,
        'gas_rows_selected':len(selected),'gas_selection_fraction':len(selected)/len(x) if len(x) else 0,
        'final_missing_fraction':float(np.isnan(out).mean()),
        'final_all_gases_missing_fraction':float(np.isnan(out[:,GAS]).all(axis=1).mean()),
        'naturally_all_missing':int((~observed.any(axis=1)).sum()),
        'rescued_rows':len(rescue),'rescued_with_gas':restored_gases}
    return out,stats,rescue

def fit_imputer(clean_train):
    return SimpleImputer(strategy='median',keep_empty_features=True).fit(clean_train)

def transform(x,imputer,flags):
    values=imputer.transform(x)
    return np.column_stack([values,np.isnan(x).astype(float)]) if flags else values

def classifier(seed):
    # Reuse the deployed baseline configuration without training or saving it.
    return clone(pipeline(limited=False)['classifier']).set_params(random_state=seed)

def train_pair(clean,y,mode,seed):
    """Return A/B rows and labels, with unchanged class counts between arms."""
    rng=np.random.default_rng(seed)
    if mode=='augment':
        moderate,ms,_=degrade(clean,'moderate',seed+101)
        severe,ss,_=degrade(clean,'severe',seed+202)
        return np.tile(clean,(3,1)),np.vstack([clean,moderate,severe]),np.tile(y,3),{'moderate':ms,'severe':ss,'clean_rows':len(clean)}
    order=rng.permutation(len(clean));n_m=len(clean)//4;n_s=len(clean)//2-n_m
    b=clean.copy()
    m,ms,_=degrade(clean[order[:n_m]],'moderate',seed+101)
    s,ss,_=degrade(clean[order[n_m:n_m+n_s]],'severe',seed+202)
    b[order[:n_m]]=m;b[order[n_m:n_m+n_s]]=s
    return clean.copy(),b,y.copy(),{'moderate':ms,'severe':ss,'clean_rows':len(clean)-n_m-n_s}

def evaluation_sets(clean,seed):
    conditions={'clean':clean.copy()};stats={};rescues={}
    for i,name in enumerate(['moderate','severe']):
        conditions[name],stats[name],rescues[name]=degrade(clean,name,seed+1001+i*1000)
    return conditions,stats,rescues

def paired_matrices(conditions,imputer,flags):
    # The same object is passed to each arm; read-only arrays catch mutations.
    result={k:transform(v,imputer,flags) for k,v in conditions.items()}
    for matrix in result.values():matrix.flags.writeable=False
    return result

def metrics(y,pred):
    ranks={c:i for i,c in enumerate(CATEGORIES)}
    scores={'accuracy':float(accuracy_score(y,pred)),
        'macro_f1':float(f1_score(y,pred,labels=CATEGORIES,average='macro',zero_division=0)),
        'within_one':float(np.mean([abs(ranks[a]-ranks[b])<=1 for a,b in zip(y,pred)]))}
    scores.update({f'f1_{c}':float(v) for c,v in zip(CATEGORIES,f1_score(y,pred,labels=CATEGORIES,average=None,zero_division=0))})
    return scores

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def protected_files():
    paths=list((ROOT/'backend/artifacts').glob('*'))+list((ROOT/'backend').glob('*.py'))
    paths+=list((ROOT/'Design/src').rglob('*'))+list((ROOT/'scripts').glob('*'))
    paths += [ROOT/'.gitignore',ROOT/'Dataset/station_day.csv',ROOT/'Design/package.json',ROOT/'Design/package-lock.json',ROOT/'Design/src-tauri/Cargo.toml',ROOT/'Design/src-tauri/Cargo.lock',ROOT/'Design/src-tauri/tauri.conf.json']
    paths+=list((ROOT/'Design/src-tauri/src').rglob('*'))
    return {str(p.relative_to(ROOT)).replace('\\','/'):file_hash(p) for p in paths if p.is_file()}
