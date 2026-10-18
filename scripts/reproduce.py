"""Run unchanged study code in an isolated snapshot, preserving archived evidence."""
import argparse, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['cv','test','verify','report'],required=True)
    parser.add_argument('--check',action='store_true',help='check phase prerequisites without fitting forests or writing results')
    args=parser.parse_args()
    if args.check:
        import hashlib, json
        subprocess.run([sys.executable,'scripts/verify_data.py'],cwd=ROOT,check=True)
        subprocess.run([sys.executable,'scripts/verify_evidence.py'],cwd=ROOT,check=True)
        print('PASS: inputs/evidence intact; requested isolated phase:',args.phase)
        print('Remove --check to execute. Full study fits 160 forests; archived deployment guard is never bypassed.')
        return
    work=ROOT/'experiments/robustness/reruns/workspace'
    if not work.exists():
        work.mkdir(parents=True)
        tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
        for name in filter(None,tracked):
            if name.startswith('experiments/robustness/results/'): continue
            src=ROOT/name;dst=work/name
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        for src in (ROOT/'backend/artifacts').glob('*.joblib'):
            dst=work/'backend/artifacts'/src.name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    module='experiments.robustness.report' if args.phase=='report' else 'experiments.robustness.run'
    command=[sys.executable,'-m',module]
    if args.phase!='report':command+=['--phase',args.phase]
    subprocess.run(command,cwd=work,check=True)
if __name__=='__main__':main()
