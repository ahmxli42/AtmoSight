"""Wait for the active CV phase, then execute final testing and reporting."""
import subprocess
import sys
import time
from .core import HERE, ROOT

def main():
    cv=HERE/'results/cv'
    while len(list(cv.glob('*.json')))<40:
        time.sleep(30)
    for args in [
        ['-m','experiments.robustness.run','--phase','test'],
        ['-m','experiments.robustness.run','--phase','verify'],
        ['-m','experiments.robustness.report']]:
        print('Executing:',sys.executable,*args,flush=True)
        subprocess.run([sys.executable,*args],cwd=ROOT,check=True)

if __name__=='__main__': main()
