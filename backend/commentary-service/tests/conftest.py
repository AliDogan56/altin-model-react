"""Testler gerçek veri dizinine dokunmaz: DATA_DIR geçici dizine, üretim kapalı, mock LLM."""
import os
import pathlib
import tempfile

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="commentary-test-"))
os.environ.setdefault("APP_ENV", "localhost")
os.environ["DATA_DIR"] = str(_TMP)
os.environ["DATABASE_PATH"] = str(_TMP / "test.sqlite3")
os.environ["AUTO_GENERATE"] = "false"
os.environ["AUTO_NARRATE"] = "false"   # ağ yok; anlatım testleri synthesize_pcm'yi sahteler
os.environ["LLM_PAUSE_SECONDS"] = "0"
os.environ["COMMENTARY_ADMIN_TOKEN"] = "test-admin-token"
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "latest"
