import unittest
import numpy as np
from .core import *

class RobustnessTests(unittest.TestCase):
    def test_operators_are_pure_nonnegative_and_retain_observation(self):
        x=np.random.default_rng(1).uniform(1,100,(10000,6));x[0]=np.nan;x[1,:2]=np.nan;before=x.copy()
        for condition in ['moderate','severe']:
            out,stats,rescue=degrade(x,condition,42)
            np.testing.assert_array_equal(x,before)
            self.assertTrue(np.isnan(out[0]).all())
            self.assertTrue(np.isfinite(out[1:]).any(axis=1).all())
            self.assertTrue((out[np.isfinite(out)]>=0).all())
            self.assertLess(abs(stats['random_mask_observed_fraction']-PROTOCOL[condition]['mask_probability']),.015)
            self.assertEqual(stats['gas_rows_selected'],int(len(x)*PROTOCOL[condition]['gas_absence_fraction']))
            self.assertTrue(np.isnan(out[np.isnan(x)]).all())
            p=PROTOCOL[condition]['mask_probability'];g=PROTOCOL[condition]['gas_absence_fraction']
            # Complete rows: joint gas loss adds four missing cells, then the
            # all-erased safeguard restores one cell with the shown probability.
            expected=p+(1-p)*g*4/6-((1-g)*p**6+g*p**2)/6
            self.assertLess(abs(stats['final_missing_fraction']-expected),.015)
        gas_only=np.full((1000,6),np.nan);gas_only[:,4]=1
        out,stats,_=degrade(gas_only,'severe',42)
        self.assertTrue(np.isfinite(out[:,4]).all())
        self.assertGreater(stats['rescued_with_gas'],0)
    def test_training_medians_ignore_extreme_validation_values(self):
        clean=np.array([[1]*6,[3]*6,[np.nan]*6]);imputer=fit_imputer(clean)
        np.testing.assert_equal(imputer.statistics_,np.full(6,2))
        transform(np.array([[1e12]*6,[np.nan]*6]),imputer,True)
        np.testing.assert_equal(imputer.statistics_,np.full(6,2))
        values=transform(np.array([[np.nan,1,2,3,4,5]]),imputer,True)
        np.testing.assert_equal(values[0,6:],[1,0,0,0,0,0])
    def test_paired_eval_matrices_identical_and_readonly(self):
        x=np.arange(600,dtype=float).reshape(-1,6)
        conditions,_,_=evaluation_sets(x,42);imputer=fit_imputer(x)
        shared=paired_matrices(conditions,imputer,True)
        used=[]
        for arm in ['A','B']:used.append({k:(id(v),digest_array(v)) for k,v in shared.items()})
        self.assertEqual(used[0],used[1])
        self.assertFalse(shared['severe'].flags.writeable)
        again,_,_=evaluation_sets(x,42)
        np.testing.assert_equal(conditions['severe'],again['severe'])
    def test_construction_keeps_labels_and_equal_rows(self):
        x=np.ones((101,6));y=np.array(['Good']*101)
        for mode,mult in [('replace',1),('augment',3)]:
            a,b,labels,stats=train_pair(x,y,mode,42)
            self.assertEqual(a.shape,b.shape);self.assertEqual(len(a),101*mult)
            np.testing.assert_equal(labels,np.tile(y,mult))
            self.assertTrue(np.isfinite(b).any(axis=1).all())
    def test_exact_existing_filter_and_nonoverlapping_splits(self):
        data,counts=load_data();self.assertEqual(len(data),87025)
        self.assertEqual(counts['naturally_all_missing'],272)
        self.assertEqual(FEATURES,['PM2.5','PM10','SO2','NO2','CO','O3'])
        self.assertFalse(set(FEATURES)&{'AQI','AQI_Bucket','StationId','Date'})
        for name,(train,test) in split_indices(data).items():
            self.assertFalse(set(train)&set(test))
            self.assertEqual(len(train)+len(test),len(data))
            if name=='station':self.assertFalse(set(data.iloc[train].StationId)&set(data.iloc[test].StationId))
    def test_baseline_hyperparameters_reused(self):
        params=classifier(44).get_params()
        self.assertEqual(params['n_estimators'],200);self.assertIsNone(params['max_depth'])
        self.assertEqual(params['min_samples_leaf'],1);self.assertEqual(params['class_weight'],'balanced')
    def test_decision_rule_requires_both_conditions(self):
        from .report import decision_rule
        self.assertTrue(decision_rule([.02]*5,[-.01]*5))
        self.assertFalse(decision_rule([.02]*5,[-.011]*5))
        self.assertFalse(decision_rule([0]*5,[0]*5))
        self.assertFalse(decision_rule([-.02,0,.01,.02,.03],[0]*5))

if __name__=='__main__':unittest.main()
