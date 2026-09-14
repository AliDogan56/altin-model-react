"""LLM ayarını ve anahtarları doğrular; isteğe bağlı olarak her rolün zincirindeki ilk sağlayıcıya küçük bir istek atar.

  .venv/bin/python scripts/check_llm.py            # yalnız doğrulama (ağ yok)
  .venv/bin/python scripts/check_llm.py --ping     # her rol için kısa bir çağrı (ücretsiz katman kotasını harcar)
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env.localhost", override=False)
load_dotenv(ROOT / ".env.secrets", override=False)
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.services.llm_config import load_llm_settings  # noqa: E402


def main() -> int:
    llm = load_llm_settings()
    problems = llm.validate(settings.pipeline_mode)
    print(f"ayar: {llm.source}  mod: {settings.pipeline_mode}")
    for role, chain in llm.describe()["roles"].items():
        print(f"  {role:22s} {' → '.join(chain)}")
    if problems:
        print("SORUN:\n  - " + "\n  - ".join(problems))
        return 1
    print("doğrulama: tamam")
    if "--ping" in sys.argv:
        from app.services.llm_gateway import ask
        for role in llm.roles:
            try:
                text, usage, model = ask(llm, role, "Kısa yanıt ver.", "Tek kelimeyle 'tamam' yaz.")
                print(f"  {role:22s} {model}: {text.strip()[:40]!r} {usage.as_dict()}")
            except Exception as error:  # noqa: BLE001
                print(f"  {role:22s} HATA {str(error)[:160]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
