#!/usr/bin/env python3
"""Run offline evaluation without network, production writes or model promotion."""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.evaluation import run

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset",type=Path,default=ROOT/"data/xauusd_training_5y.csv")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--experiments",nargs="*")
    args=parser.parse_args()
    run(args.dataset,args.output,args.experiments)
