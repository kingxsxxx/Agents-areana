from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from ..config import settings
from ..utils.logger import logger


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _safe_json_loads(text: str) -> Optional[dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


@dataclass
class BaseAdapter:
    provider: str
    model: str
    api_key: str
    base_url: str
    timeout: int = settings.AI_REQUEST_TIMEOUT
    max_retries: int = settings.AI_MAX_RETRIES

    def __post_init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self) -> None:
        await self.client.aclose()

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(f"{self.provider} API key is empty")

    @staticmethod
    def _build_prompt(
        agent_config: dict[str, Any],
        context: Optional[dict[str, Any]],
        max_words: int,
    ) -> tuple[str, str]:
        ctx = context or {}
        phase = str(ctx.get("phase", "") or "")
        topic = str(ctx.get("topic", "") or "")
        instruction = str(ctx.get("instruction", "") or "")
        reference = str(ctx.get("reference", "") or "")
        constraints = ctx.get("constraints", [])
        constraints_text = (
            "\n".join(f"- {c}" for c in constraints if c)
            if isinstance(constraints, list)
            else ""
        )
        is_opening = any(k in phase for k in ["开场", "立论", "opening"])
        is_cross = "盘问" in phase or "cross" in phase.lower()
        is_free = "自由" in phase or "free" in phase.lower()
        is_summary = "总结" in phase or "summary" in phase.lower()
        is_judge = "评委" in phase or "judge" in phase.lower()
        phase_style = (
            "开局允许一句礼貌，其余内容直接论证。"
            if is_opening
            else "禁止寒暄和敬语，直接进入冲突点与证据点。"
        )
        if is_cross:
            phase_style = "盘问阶段：问题或回答必须可追问、可核查，不能空泛。"
        elif is_free:
            phase_style = "自由辩论：短句、高密度、可更强势；仅攻击观点，不攻击人格。"
        elif is_summary:
            phase_style = "总结阶段：回扣全场核心分歧，给出明确胜负依据。"
        elif is_judge:
            phase_style = "评委点评：客观简洁，给依据、优缺点、改进建议。"

        system_prompt = (
            agent_config.get("system_prompt")
            or f"You are {agent_config.get('name', 'Agent')} in a formal debate."
        )
        context_text = json.dumps(ctx, ensure_ascii=False)
        user_prompt = (
            "请生成一段中文辩论发言（只输出正文，不要标题或括号说明）。\n"
            f"目标字数上限: {max_words}\n"
            f"辩题: {topic}\n"
            f"环节: {phase}\n"
            f"立场: {agent_config.get('side', 'neutral')}\n"
            f"风格要求: {phase_style}\n"
            "硬性约束:\n"
            "- 禁止套话和空话（如“我们认为”“感谢对方”“我们接受质询”）。\n"
            "- 全文至少包含1个可核验信息点（数据、机制、案例、事实链）。\n"
            "- 必须回应争议点，不要只重复己方立场。\n"
            "- 允许类比、反问、非常规切入，避免固定模板结构。\n"
            "- 允许锋利和攻击性，但仅针对论证与证据，不做人身攻击。\n"
            f"{constraints_text}\n"
            f"附加指令: {instruction}\n"
            f"对方最近发言参考: {reference}\n"
            f"Context JSON: {context_text}\n"
            "Return plain text only."
        )
        return system_prompt, user_prompt

    async def generate_speech(
        self,
        agent_config: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        max_words: int = 300,
        **kwargs: Any,
    ) -> str:
        raise NotImplementedError

    async def generate_score(self, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        prompt = (
            "Score this debate and return strict JSON with keys "
            "pro_score, con_score, comments.\n"
            f"Input: {json.dumps(payload, ensure_ascii=False)}"
        )
        text = await self.generate_speech(
            {"name": "Judge", "side": "neutral", "system_prompt": "You are a neutral debate judge."},
            {"task": "score"},
            max_words=200,
            user_override=prompt,
            **kwargs,
        )
        parsed = _safe_json_loads(text or "")
        if not parsed:
            return {"pro_score": 75, "con_score": 75, "comments": text[:400] if text else "Auto score fallback"}
        return {
            "pro_score": int(parsed.get("pro_score", 75)),
            "con_score": int(parsed.get("con_score", 75)),
            "comments": str(parsed.get("comments", "")),
        }


class OpenAICompatibleAdapter(BaseAdapter):
    async def generate_speech(
        self,
        agent_config: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        max_words: int = 300,
        **kwargs: Any,
    ) -> str:
        self._require_key()
        system_prompt, user_prompt = self._build_prompt(agent_config, context, max_words)
        user_prompt = kwargs.get("user_override") or user_prompt
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(kwargs.get("temperature", 0.7)),
            "max_tokens": int(kwargs.get("max_tokens", max(128, min(2048, max_words * 3)))),
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await self.client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                if isinstance(content, list):
                    return " ".join(str(item.get("text", "")) for item in content if isinstance(item, dict)).strip()
                return str(content).strip()
            except Exception as exc:
                last_error = exc
                logger.warning(f"{self.provider} request failed (attempt {attempt}/{self.max_retries}): {exc}")
        raise RuntimeError(f"{self.provider} generation failed: {last_error}")


class DashScopeQwenAdapter(BaseAdapter):
    async def generate_speech(
        self,
        agent_config: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        max_words: int = 300,
        **kwargs: Any,
    ) -> str:
        self._require_key()
        system_prompt, user_prompt = self._build_prompt(agent_config, context, max_words)
        user_prompt = kwargs.get("user_override") or user_prompt
        url = f"{self.base_url.rstrip('/')}/services/aigc/text-generation/generation"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            },
            "parameters": {
                "temperature": float(kwargs.get("temperature", 0.7)),
                "max_tokens": int(kwargs.get("max_tokens", max(128, min(2048, max_words * 3)))),
            },
            "result_format": "message",
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await self.client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                output = data.get("output", {})
                if "text" in output:
                    return str(output["text"]).strip()
                choices = output.get("choices", [])
                if choices:
                    return str(choices[0].get("message", {}).get("content", "")).strip()
                raise RuntimeError(f"Unexpected Qwen response: {data}")
            except Exception as exc:
                last_error = exc
                logger.warning(f"{self.provider} request failed (attempt {attempt}/{self.max_retries}): {exc}")
        raise RuntimeError(f"{self.provider} generation failed: {last_error}")


class GeminiAdapter(BaseAdapter):
    async def generate_speech(
        self,
        agent_config: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        max_words: int = 300,
        **kwargs: Any,
    ) -> str:
        self._require_key()
        system_prompt, user_prompt = self._build_prompt(agent_config, context, max_words)
        user_prompt = kwargs.get("user_override") or user_prompt
        url = f"{self.base_url.rstrip('/')}/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": float(kwargs.get("temperature", 0.7)),
                "maxOutputTokens": int(kwargs.get("max_tokens", max(128, min(2048, max_words * 3)))),
            },
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = await self.client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError(f"Gemini empty candidates: {data}")
                parts = candidates[0].get("content", {}).get("parts", [])
                text = " ".join(str(p.get("text", "")) for p in parts if isinstance(p, dict)).strip()
                if not text:
                    raise RuntimeError(f"Gemini empty text: {data}")
                return text
            except Exception as exc:
                last_error = exc
                logger.warning(f"{self.provider} request failed (attempt {attempt}/{self.max_retries}): {exc}")
        raise RuntimeError(f"{self.provider} generation failed: {last_error}")


class AIAdapterFactory:
    _adapters: dict[str, BaseAdapter] = {}
    _aliases: dict[str, str] = {}

    @classmethod
    async def initialize(cls, config: dict[str, dict[str, Any]]) -> None:
        await cls.close_all()
        config = config or {}

        provider_defaults = {
            "deepseek": settings.DEEPSEEK_API_BASE,
            "gpt-4": settings.OPENAI_API_BASE,
            "openai": settings.OPENAI_API_BASE,
            "qwen": settings.QWEN_API_BASE,
            "kimi": settings.KIMI_API_BASE,
            "doubao": settings.DOUBAO_API_BASE,
            "gemini": settings.GEMINI_API_BASE,
            "glm": settings.GLM_API_BASE,
        }

        for key, item in config.items():
            provider_key = (key or "").strip().lower()
            model = str(item.get("model") or provider_key).strip()
            api_key = str(item.get("api_key") or "")
            base_url = str(item.get("base_url") or provider_defaults.get(provider_key, "")).strip()

            if provider_key == "gemini":
                adapter: BaseAdapter = GeminiAdapter(provider_key, model, api_key, base_url)
            elif (
                provider_key == "qwen"
                and "dashscope.aliyuncs.com" in base_url
                and "compatible-mode" not in base_url
            ):
                adapter = DashScopeQwenAdapter(provider_key, model, api_key, base_url)
            else:
                adapter = OpenAICompatibleAdapter(provider_key, model, api_key, base_url)

            cls._adapters[provider_key] = adapter
            cls._aliases[_normalize_name(provider_key)] = provider_key
            cls._aliases[_normalize_name(model)] = provider_key

        logger.info(f"Initialized adapters: {list(cls._adapters.keys())}")

    @classmethod
    async def get_adapter(cls, model_name: Optional[str]) -> BaseAdapter:
        if not cls._adapters:
            await cls.initialize({})

        if not model_name:
            if cls._adapters:
                return next(iter(cls._adapters.values()))
            raise RuntimeError("No adapters configured")

        normalized = _normalize_name(model_name)
        key = cls._aliases.get(normalized)
        if key and key in cls._adapters:
            return cls._adapters[key]

        if normalized in cls._adapters:
            return cls._adapters[normalized]

        # Partial match fallback.
        for provider_key, adapter in cls._adapters.items():
            if normalized in _normalize_name(provider_key) or normalized in _normalize_name(adapter.model):
                return adapter

        if cls._adapters:
            return next(iter(cls._adapters.values()))
        raise RuntimeError("No adapters configured")

    @classmethod
    def list_available_models(cls) -> list[str]:
        return [adapter.model for adapter in cls._adapters.values()]

    @classmethod
    async def close_all(cls) -> None:
        for adapter in cls._adapters.values():
            try:
                await adapter.close()
            except Exception:
                pass
        cls._adapters.clear()
        cls._aliases.clear()


async def initialize_adapters(config: dict[str, dict[str, Any]]) -> None:
    await AIAdapterFactory.initialize(config)
