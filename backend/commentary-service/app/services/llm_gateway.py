"""Sağlayıcıdan bağımsız LLM katmanı. Her sağlayıcı `complete(system, user, schema, max_tokens, model, extra) -> (metin, kullanım)` verir.

- anthropic: Anthropic SDK (isteğe bağlı bağımlılık, tembel içe aktarım); şema verilirse output_config ile garantili JSON.
- openai_compatible: POST {base_url}/chat/completions (Groq, Gemini OpenAI ucu, OpenRouter, Mistral, Cerebras, yerel Ollama).
  Şema verilirse istemde JSON istenir, yanıt `parse_json` ile ayıklanır; ücretsiz katman 429/503'te bekleyip yeniden dener.
- mock: test için örnek çıktı.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import httpx

from .llm_config import LlmSettings, ProviderConfig, RoleConfig


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    finish_reason: str | None = None  # sağlayıcının bitiş nedeni (stop / length / ...)

    def as_dict(self) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "cache_read_tokens": self.cache_read_tokens}

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens,
                          self.cache_read_tokens + other.cache_read_tokens, other.finish_reason)


def parse_json(text: str) -> dict:
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.S)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start >= 0 and end > start:
            return json.loads(stripped[start:end + 1])
        raise


class Provider:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def complete(self, system: str, user: str, schema: dict | None, max_tokens: int, model: str, extra: dict | None = None) -> tuple[str, TokenUsage]:
        raise NotImplementedError


class AnthropicProvider(Provider):
    def complete(self, system, user, schema, max_tokens, model, extra=None):
        import anthropic  # isteğe bağlı bağımlılık: yalnız bu sağlayıcı kullanılırsa gerekir

        client = anthropic.Anthropic(api_key=self.config.api_key)
        kwargs = {"output_config": {"format": {"type": "json_schema", "schema": schema}}} if schema else {}
        response = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}], **kwargs,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"model reddetti: {getattr(response, 'stop_details', None)}")
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = response.usage
        return text, TokenUsage(usage.input_tokens, usage.output_tokens, getattr(usage, "cache_read_input_tokens", 0) or 0, response.stop_reason)


class OpenAICompatibleProvider(Provider):
    def complete(self, system, user, schema, max_tokens, model, extra=None):
        if schema:
            system += "\n\nYANIT BİÇİMİ: Yalnız geçerli JSON döndür, açıklama ve kod çiti ekleme. Şema:\n" + json.dumps(schema, ensure_ascii=False)
        body = {"model": model, "max_tokens": max_tokens, "temperature": 0.3,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        body.update(self.config.extra or {})
        body.update(extra or {})
        if schema:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        with httpx.Client(timeout=180) as client:
            response = None
            for attempt in range(4):  # ücretsiz katmanlar dakika/gün sınırında 429 döner: bekle, yeniden dene
                response = client.post(url, json=body, headers=headers)
                if response.status_code == 400 and schema and "response_format" in body:
                    body.pop("response_format")  # bazı uçlar json_object desteklemez
                    response = client.post(url, json=body, headers=headers)
                if response.status_code in (429, 503) and attempt < 3:
                    try:
                        wait = min(float(response.headers.get("retry-after", "0") or 0), 90)
                    except ValueError:
                        wait = 0
                    time.sleep(wait or (8 * (attempt + 1)))
                    continue
                break
            if response.status_code >= 400:
                raise RuntimeError(f"{self.config.name} {response.status_code}: {response.text[:300]}")
        payload = response.json()
        choice = payload["choices"][0]
        usage = payload.get("usage") or {}
        return (choice["message"].get("content") or ""), TokenUsage(int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0)), 0, choice.get("finish_reason"))


class MockProvider(Provider):
    def complete(self, system, user, schema, max_tokens, model, extra=None):
        if not schema:
            return "# Örnek not\n\nMock sağlayıcı çıktısı.", TokenUsage(len(system + user) // 4, 50, 0, "stop")
        out = {}
        for key, spec in schema.get("properties", {}).items():
            if spec.get("type") == "array":
                item = spec.get("items", {})
                if item.get("type") == "object":
                    ids = item.get("properties", {}).get("id", {}).get("enum") or ["a"]
                    out[key] = [{kk: (i if kk == "id" else f"örnek {kk} ({i})") for kk in item.get("properties", {})} for i in ids]
                else:
                    out[key] = ["örnek"]
            elif spec.get("type") == "object":
                out[key] = {kk: f"örnek {kk}" for kk in spec.get("properties", {})}
            elif spec.get("type") in ("number", "integer"):
                out[key] = 0
            else:
                out[key] = f"örnek {key}"
        return json.dumps(out, ensure_ascii=False), TokenUsage(len(system + user) // 4, 200, 0, "stop")


PROVIDER_CLASSES = {"anthropic": AnthropicProvider, "openai_compatible": OpenAICompatibleProvider, "mock": MockProvider}


def ask(llm: LlmSettings, role_name: str, system: str, user: str, schema: dict | None = None) -> tuple[str, TokenUsage, str]:
    """Rolün sağlayıcı zincirini sırayla dener; kısa/yarım yanıtı bir kez yineler, bozuk JSON'a bir onarım çağrısı yapar.
    Döndürür: (metin, kullanım, "sağlayıcı/model")."""
    role: RoleConfig = llm.roles[role_name]
    errors = []
    for provider_name, model in role.chain():
        provider = PROVIDER_CLASSES[llm.providers[provider_name].kind](llm.providers[provider_name])
        role_extra = role.extra if provider_name == role.provider else {}
        try:
            text, usage = provider.complete(system, user, schema, role.max_tokens, model, role_extra)
            break
        except Exception as error:  # noqa: BLE001
            errors.append(f"{provider_name}/{model}: {str(error)[:120]}")
    else:
        raise RuntimeError(f"{role_name}: bütün sağlayıcılar başarısız → " + " | ".join(errors))
    if not schema and (len(text.split()) < 80 or usage.finish_reason not in (None, "stop", "end_turn")):
        text2, usage2 = provider.complete(system, user, None, role.max_tokens, model, role_extra)  # ücretsiz katmanda yarım yanıt görülür
        if len(text2.split()) > len(text.split()):
            text = text2
        usage = usage + usage2
    if schema:
        try:
            parse_json(text)
        except (json.JSONDecodeError, ValueError):
            repair_system = ("Sana bozuk bir JSON metni verilecek. Yalnız geçerli, şemaya uyan JSON döndür; içeriği koru, kaçmış tırnak ve satır "
                             "sonlarını düzelt, açıklama ekleme. Şema: " + json.dumps(schema, ensure_ascii=False))
            text2, usage2 = provider.complete(repair_system, "Bozuk JSON:\n" + text[: role.max_tokens * 4], schema, role.max_tokens, model, role_extra)
            usage = usage + usage2
            parse_json(text2)  # hâlâ bozuksa hata yükselsin
            text = text2
    return text, usage, f"{provider_name}/{model}"
