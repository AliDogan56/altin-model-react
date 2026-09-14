"""LLM sağlayıcı ve rol ayarı: llm.toml (yol: LLM_CONFIG_PATH). Anahtarlar ortamdan (api_key_env)."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from ..config import settings

ROLES = ("technical_analyst", "calendar_news_scout", "macro_analyst", "chief_analyst", "anchor")
PROVIDER_KINDS = ("anthropic", "openai_compatible", "mock")


@dataclass
class ProviderConfig:
    name: str
    kind: str
    base_url: str = ""
    api_key_env: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "") if self.api_key_env else ""


@dataclass
class RoleConfig:
    name: str
    provider: str
    model: str
    max_tokens: int = 3000
    extra: dict = field(default_factory=dict)
    fallbacks: list = field(default_factory=list)   # sıralı: [{provider, model}, ...]

    def chain(self) -> list[tuple[str, str]]:
        chain = [(self.provider, self.model)]
        for item in self.fallbacks:
            chain.append((str(item.get("provider") or self.provider), str(item.get("model", ""))))
        return [(p, m) for p, m in chain if m]


@dataclass
class LlmSettings:
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    roles: dict[str, RoleConfig] = field(default_factory=dict)
    pause_seconds: int = 0
    source: str = ""

    def validate(self, mode: str = "full") -> list[str]:
        problems = []
        required = ROLES if mode == "full" else ("anchor",)
        for role_name in required:
            role = self.roles.get(role_name)
            if not role:
                problems.append(f"llm.roles.{role_name} tanımlı değil")
                continue
            if not role.model:
                problems.append(f"llm.roles.{role_name}.model boş")
            for provider_name, _ in role.chain():
                provider = self.providers.get(provider_name)
                if not provider:
                    problems.append(f"llm.roles.{role_name}: sağlayıcı '{provider_name}' llm.providers altında yok")
                    continue
                if provider.kind not in PROVIDER_KINDS:
                    problems.append(f"llm.providers.{provider.name}.kind geçersiz: {provider.kind}")
                if provider.kind == "openai_compatible" and not provider.base_url:
                    problems.append(f"llm.providers.{provider.name}.base_url boş")
                if provider.kind in ("anthropic", "openai_compatible") and provider.api_key_env and not provider.api_key:
                    problems.append(f"{provider.api_key_env} tanımlı değil (ortam ya da .env.secrets) — sağlayıcı {provider.name}, rol {role_name}")
                if provider.kind == "anthropic" and not provider.api_key_env:
                    problems.append(f"llm.providers.{provider.name}.api_key_env boş (Anthropic için zorunlu)")
        return problems

    def describe(self) -> dict:
        return {"source": self.source, "pause_seconds": self.pause_seconds,
                "roles": {name: [f"{p}/{m}" for p, m in role.chain()] for name, role in self.roles.items()}}


def load_llm_settings(path: str | Path | None = None) -> LlmSettings:
    config_path = Path(path or settings.llm_config_path)
    if not config_path.exists():
        raise RuntimeError(f"LLM ayar dosyası yok: {config_path}")
    with open(config_path, "rb") as handle:
        raw = tomllib.load(handle)
    llm = raw.get("llm", {})
    providers = {name: ProviderConfig(name=name, kind=str(v.get("kind", "")), base_url=str(v.get("base_url", "")), api_key_env=str(v.get("api_key_env", "")), extra=dict(v.get("extra", {})))
                 for name, v in llm.get("providers", {}).items()}
    roles = {name: RoleConfig(name=name, provider=str(v.get("provider", "")), model=str(v.get("model", "")), max_tokens=int(v.get("max_tokens", 3000)), extra=dict(v.get("extra", {})), fallbacks=list(v.get("fallbacks", [])))
             for name, v in llm.get("roles", {}).items()}
    return LlmSettings(providers, roles, settings.llm_pause_seconds, str(config_path))
