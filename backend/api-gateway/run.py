import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

aliases = {"local": "localhost", "dev": "development", "prod": "production"}
requested = sys.argv[1] if len(sys.argv) > 1 else "localhost"
profile = aliases.get(requested, requested)
if profile not in {"localhost", "development", "production"}:
    raise SystemExit("Profil localhost, development veya production olmalıdır")
load_dotenv(Path(__file__).with_name(f".env.{profile}"), override=True)
os.environ["APP_ENV"] = profile

if __name__ == "__main__":
    debugger_attached = sys.gettrace() is not None
    debug_mode = debugger_attached or os.getenv("DEBUG_MODE", "false").lower() in {"1", "true", "yes", "on"}
    uvicorn.run("app.main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")),
                reload=False, log_level="debug" if debug_mode else "info")
