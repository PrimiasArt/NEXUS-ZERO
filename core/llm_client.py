"""
Tier-1 Subconscious Worker Client using the official `google-genai` SDK
(`client.interactions.create` with `gemini-3.5-flash-lite` and `gemini-3.8-flash`).
Strictly governed by `TokenBudgetGovernor` and Semantic Cache.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any

from config import DEFAULT_CONFIG, NexusConfig
from core.budget import BudgetExhaustedError, TokenBudgetGovernor


@dataclass
class LLMResponse:
    ok: bool
    text: str
    tokens_used: int = 0
    from_cache: bool = False
    model_used: str = ""
    error: str = ""


class Tier1SubconsciousClient:
    """
    Lightweight, budget-constrained wrapper around the Gemini Interactions API.
    Defaults to `gemini-3.5-flash-lite` for maximum token economy.
    """

    def __init__(
        self,
        budget: TokenBudgetGovernor,
        config: NexusConfig = DEFAULT_CONFIG,
    ):
        self.budget = budget
        self.config = config
        self._client: Any = None

    def is_configured(self) -> bool:
        return bool(os.getenv("GEMINI_API_KEY"))

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Chưa thiết lập biến môi trường GEMINI_API_KEY cho Tầng 1 (Flash-Lite)."
            )
        from google import genai

        self._client = genai.Client(api_key=api_key)
        return self._client

    def ask_subconscious(
        self,
        user_input: str,
        system_instruction: str,
        purpose: str = "subconscious_reasoning",
        use_reasoning_tier: bool = False,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        model = (
            self.config.tier1_reasoning_model
            if use_reasoning_tier
            else self.config.tier1_fast_model
        )

        # 1. Check 0-token local SQLite Prompt Cache first
        cached = self.budget.check_cache(model, system_instruction, user_input)
        if cached is not None:
            return LLMResponse(
                ok=True,
                text=cached,
                tokens_used=0,
                from_cache=True,
                model_used=f"{model} (cached)",
            )

        # 2. Check API Key availability
        if not self.is_configured():
            return LLMResponse(
                ok=False,
                text="",
                model_used=model,
                error="GEMINI_API_KEY chưa được cấu hình. Tự động chuyển sang Cầu nối Giáo viên (Gemini 4 Argon Ultra).",
            )

        # 3. Check Token Budget Governor before making network call
        estimated_in = max(50, (len(system_instruction) + len(user_input)) // 4)
        out_cap = max_output_tokens or self.config.max_output_tokens_per_call
        try:
            self.budget.verify_can_spend(estimated_tokens=estimated_in + (out_cap // 2))
        except BudgetExhaustedError as exc:
            return LLMResponse(
                ok=False,
                text="",
                model_used=model,
                error=str(exc),
            )

        # 4. Call Gemini Interactions API (`client.interactions.create`)
        try:
            client = self._get_client()
            interaction = client.interactions.create(
                model=model,
                system_instruction=system_instruction,
                input=user_input,
                generation_config={
                    "max_output_tokens": out_cap,
                },
            )
            output_text = interaction.output_text or ""
            total_tokens = estimated_in + max(20, len(output_text) // 4)
            if getattr(interaction, "usage", None) and getattr(
                interaction.usage, "total_tokens", None
            ):
                total_tokens = int(interaction.usage.total_tokens)

            # Record token spend & cache result
            self.budget.record_spend(model=model, purpose=purpose, total_tokens=total_tokens)
            if output_text.strip():
                self.budget.save_cache(
                    model=model,
                    system_instruction=system_instruction,
                    user_input=user_input,
                    response_text=output_text,
                    tokens_estimate=total_tokens,
                )

            return LLMResponse(
                ok=True,
                text=output_text,
                tokens_used=total_tokens,
                from_cache=False,
                model_used=model,
            )
        except Exception as exc:
            return LLMResponse(
                ok=False,
                text="",
                model_used=model,
                error=f"Lỗi gọi Gemini API ({model}): {exc}",
            )
