#!/usr/bin/env python3
"""Read-only production audit snapshot. Never calls training or prediction routes."""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base",default="https://onsaltinanaliz.com")
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    result={"captured_at":datetime.now(timezone.utc).isoformat(),"base":args.base,"read_only":True,"responses":{}}
    for path in ("/model-service/health","/model-service/v1/learning/metrics","/model-service/v1/learning/job","/model-service/v1/features/latest"):
        try:
            with urlopen(args.base.rstrip("/")+path,timeout=30) as response:
                result["responses"][path]={"status":response.status,"body":json.load(response)}
        except Exception as error:
            result["responses"][path]={"error":type(error).__name__+": "+str(error)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({path:item.get("status",item.get("error")) for path,item in result["responses"].items()}))
