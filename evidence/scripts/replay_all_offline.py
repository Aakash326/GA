"""Compatibility entry point: replay the released public ASR/TTS benchmark and reports."""
import os
from pathlib import Path
import subprocess
import sys
P=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    subprocess.run([sys.executable,str(P/'run_evaluation.py'),'--mode','replay','--part','all','--reports'],cwd=P,env={**os.environ,'GNANI_LIVE':'0'},check=True)
