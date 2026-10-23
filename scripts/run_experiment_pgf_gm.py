#!/usr/bin/env python3
"""Experiment 2: geometric-mean gravity+basement-depth paired flanks."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'vendor'), str(ROOT/'src')]
from gems57 import evaluate_holdout, spatial, emit
from gems57.grid import load_grid
from gems87.features import load_band, bounded_control
from gems87.features_pgf import pgf
from gems87.experiment import canary, crop_slices
FULL_BUDGET=37_654; CAND='pgf_gm_dots'; CONTROLS=('magnetic_hgm_control','topographic_slope_control'); SURFACE='pgf_gm_continuous'
def main():
    grid=load_grid(ROOT/'data/raw'); fp,cat=grid.footprint,grid.catalogue
    g13,_=pgf(load_band(ROOT,13),fp); g15,_=pgf(load_band(ROOT,15),fp)
    gm=np.sqrt(np.maximum(g13['pgf'],0)*np.maximum(g15['pgf'],0)).astype(np.float32); gm[~fp]=0
    features={'pgf_gm':gm,'pgf_gm_d2':np.sqrt(g13['pgf_d2_abs']*g15['pgf_d2_abs']).astype(np.float32),
      'magnetic_hgm_control':bounded_control(load_band(ROOT,3),fp),
      'topographic_slope_control':bounded_control(load_band(ROOT,19),fp)}
    names=[CAND,*CONTROLS,SURFACE]; terms={n:None for n in names}; folds_out=[]
    for fold in spatial.folds(cat,fp,buffer_px=80):
        f=int(fold['fold']); sl=crop_slices(fold['region'])
        local={k:fold[k][sl] for k in ('region','truth','visible')}; valid=fp[sl]
        active=valid&local['region']&~local['visible']
        canaries={n:canary(v[sl],local['truth'],active,seed=87200+f) for n,v in features.items()}
        if not all(c['passed'] for c in canaries.values()):
            out=dict(status='blocked-by-leakage-canary',canaries=canaries,failed_fold=f)
            (ROOT/'evidence/holdout_pgf_gm.json').write_text(json.dumps(out,indent=2)+'\n'); print(out); return 2
        budget=int(round(FULL_BUDGET*int((valid&local['region']).sum())/int(fp.sum()))); metrics={}
        for arm in names:
            src='pgf_gm' if arm in (CAND,SURFACE) else arm; values=features[src][sl]
            if arm==SURFACE: pred=np.where(active,values,0).astype(np.float32)
            else:
                ranking,_=emit.emit_decimated(values,active,tile_px=3); pred=emit.emit_prefix(ranking,budget).astype(np.float32)
            result,block=evaluate_holdout.evaluate(pred,local,valid,block_side=200,origin=(sl[0].start,sl[1].start),global_shape=fp.shape)
            terms[arm]=block if terms[arm] is None else terms[arm]+block; metrics[arm]=result
            print(f'fold {f} {arm}: HOLDOUT-DTI={result["dti"]:.6f}',flush=True)
        folds_out.append(dict(fold=f,split=fold['receipt'],canaries=canaries,area_allocated_budget=budget,metrics=metrics))
    summary=evaluate_holdout.pooled_summary(terms,draws=2000,seed=87222,candidate=CAND)
    best=max(CONTROLS,key=lambda n:summary['scores'][n]['dti'])
    beats=all(summary['paired_differences'][n]['ci95'][0]>0 for n in CONTROLS)
    out=dict(evidence_class='HOLDOUT-DTI',evaluator_version=evaluate_holdout.VERSION,status='evaluated',
      full_grid_budget=FULL_BUDGET,withheld_positive_pixels=int(sum(f['split']['truth_px'] for f in folds_out)),
      folds=folds_out,pooled=summary,best_comparable_control=best,paired_lower_ci_beats_all_comparable_controls=bool(beats))
    (ROOT/'evidence/holdout_pgf_gm.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:summary['scores'][k] for k in names},indent=2)); print('paired:',json.dumps(summary['paired_differences'],indent=2)); print('BEATS_ALL',beats)
    return 0
if __name__=='__main__': raise SystemExit(main())
