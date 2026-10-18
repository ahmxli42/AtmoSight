"""Evaluate sensor configurations on identical random and station-held-out splits."""
import json
import hashlib
from datetime import datetime, timezone
import joblib
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from backend.train import ROOT, ARTIFACTS, FEATURES, CATEGORIES

def pipeline(limited=True):
    return Pipeline([('imputer', SimpleImputer(strategy='median')),
        ('classifier', RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42, n_jobs=-1,
            max_depth=12 if limited else None,min_samples_leaf=5 if limited else 1))])

def main():
    data = pd.read_csv(ROOT / 'Dataset/station_day.csv').dropna(subset=['AQI_Bucket']).drop_duplicates(['StationId','Date'])
    data = data[data.AQI_Bucket.isin(CATEGORIES)].copy()
    data[FEATURES] = data[FEATURES].apply(pd.to_numeric, errors='coerce')
    data = data.loc[~(data[FEATURES] < 0).any(axis=1)].reset_index(drop=True)
    train, test = train_test_split(data.index, test_size=.2, stratify=data.AQI_Bucket, random_state=42)
    group_train, group_test = next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(data, groups=data.StationId.fillna('Unknown')))
    results = []
    for identifier, features in [('pm25', ['PM2.5']), ('pm_pair', ['PM2.5','PM10'])]:
        model = pipeline().fit(data.loc[train,features], data.loc[train,'AQI_Bucket'])
        pred = model.predict(data.loc[test,features])
        station_model = pipeline().fit(data.loc[group_train,features],data.loc[group_train,'AQI_Bucket'])
        station_pred = station_model.predict(data.loc[group_test,features])
        anomaly = IsolationForest(n_estimators=200,contamination=.05,random_state=42,n_jobs=-1).fit(model['imputer'].transform(data.loc[train,features]))
        path = ARTIFACTS / f'{identifier}.joblib'
        joblib.dump({'model':model,'anomaly':anomaly},path,compress=3)
        meta = {'scikit_learn_version':sklearn.__version__,'id':identifier,'name':'PM2.5-only Random Forest' if identifier=='pm25' else 'PM2.5 + PM10 Random Forest',
            'features':features,'categories':CATEGORIES,'accuracy':accuracy_score(data.loc[test,'AQI_Bucket'],pred),
            'macro_f1':f1_score(data.loc[test,'AQI_Bucket'],pred,average='macro'),
            'classification_report':classification_report(data.loc[test,'AQI_Bucket'],pred,output_dict=True),
            'confusion_matrix':confusion_matrix(data.loc[test,'AQI_Bucket'],pred,labels=CATEGORIES).tolist(),
            'station_holdout':{'accuracy':accuracy_score(data.loc[group_test,'AQI_Bucket'],station_pred),
                'macro_f1':f1_score(data.loc[group_test,'AQI_Bucket'],station_pred,average='macro'),
                'test_rows':len(group_test),'training_stations':data.loc[group_train,'StationId'].nunique(),
                'test_stations':data.loc[group_test,'StationId'].nunique(),
                'training_station_ids':sorted(data.loc[group_train,'StationId'].dropna().unique().tolist()),
                'test_station_ids':sorted(data.loc[group_test,'StationId'].dropna().unique().tolist())},
            'train_rows':len(train),'test_rows':len(test),'observations':len(data),'seed':42,'estimators':200,
            'max_depth':12,'min_samples_leaf':5,
            'imputation':dict(zip(features,model['imputer'].statistics_.tolist())), 'calibrated':False,
            'artifact_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'dataset_sha256':hashlib.sha256((ROOT/'Dataset/station_day.csv').read_bytes()).hexdigest(),
            'evaluated_at_utc':datetime.now(timezone.utc).isoformat(),
            'limitations':['Random-split artifact; station-held-out score uses a separate training-only pipeline.',
                'No Pakistan-specific, temporal or real-sensor validation. Probability is uncalibrated.',
                'Reduced sensor configurations can have substantially weaker class discrimination.']}
        (ARTIFACTS/f'{identifier}.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
        results.append(meta)
        print(identifier,meta['accuracy'],meta['macro_f1'],meta['station_holdout'],flush=True)
    (ARTIFACTS/'sensor_evaluation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

if __name__=='__main__': main()
