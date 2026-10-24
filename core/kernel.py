"""
NexusZeroKernel: The Tri-Tier Cognitive Orchestrator.
Routes tasks from Tier-0 (0-token Verified Skills & Local Memory) ->
Tier-1 (Budget-governed Gemini 3.5 Flash-Lite) ->
Tier-2 (Symbiotic Teacher Bridge with Gemini 4 Argon Ultra in Antigravity).
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bridge.teacher_protocol import SymbioticTeacherBridge
from config import (
    DB_PATH,
    DEFAULT_CONFIG,
    NexusConfig,
    TEACHER_INBOX_PATH,
    TEACHER_OUTBOX_PATH,
)
from core.budget import TokenBudgetGovernor
from core.evolution import SelfEvolutionEngine
from core.llm_client import Tier1SubconsciousClient
from core.memory import BioCognitiveMemory
from core.sandbox import IsolatedSkillSandbox


@dataclass
class CognitiveTurnResult:
    success: bool
    tier_used: str
    answer: str
    skill_used: str | None = None
    tokens_spent: int = 0
    latency_ms: float = 0.0
    teacher_request_id: str | None = None
    reflection: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class NexusZeroKernel:
    """
    The main cognitive brain of NEXUS-ZERO.
    Starts from zero skills and evolves its procedural & semantic memory over time.
    """

    def __init__(
        self,
        config: NexusConfig = DEFAULT_CONFIG,
        db_path: Path = DB_PATH,
        inbox_path: Path = TEACHER_INBOX_PATH,
        outbox_path: Path = TEACHER_OUTBOX_PATH,
    ):
        self.config = config
        self.config.ensure_directories()

        self.memory = BioCognitiveMemory(db_path=db_path, config=self.config)
        self.budget = TokenBudgetGovernor(db_path=db_path, config=self.config)
        self.sandbox = IsolatedSkillSandbox(config=self.config)
        self.llm = Tier1SubconsciousClient(budget=self.budget, config=self.config)
        self.evolution = SelfEvolutionEngine(
            memory=self.memory,
            sandbox=self.sandbox,
            llm_client=self.llm,
            config=self.config,
        )
        self.bridge = SymbioticTeacherBridge(
            memory=self.memory,
            evolution=self.evolution,
            inbox_path=inbox_path,
            outbox_path=outbox_path,
        )

    def handle_task(
        self,
        user_task: str,
        auto_forge_skill: bool = True,
    ) -> CognitiveTurnResult:
        """
        Execute the full Tri-Tier Cognitive Routing loop for a given task.
        """
        # Step 0: Automatically sync any new lessons waiting in Teacher Outbox
        sync_report = self.bridge.ingest_teacher_lessons()

        # =====================================================================
        # TIER 0: LOCAL REFLEX & PROCEDURAL SKILL EXECUTION (0 API TOKENS)
        # =====================================================================
        matched_skill = self.memory.match_procedural_skill(user_task)
        if matched_skill is not None:
            skill_path = Path(matched_skill.file_path)
            if skill_path.exists():
                exec_res = self.sandbox.execute_skill(
                    skill_path=skill_path,
                    kwargs={"query": user_task},
                )
                self.memory.update_skill_stats(
                    skill_name=matched_skill.skill_name,
                    success=exec_res.ok,
                    latency_ms=exec_res.latency_ms,
                )
                if exec_res.ok:
                    formatted_output = json.dumps(
                        exec_res.output, ensure_ascii=False, indent=2
                    )
                    reflection = self.evolution.reflect_and_update_graph(
                        task_input=user_task,
                        tier_used="tier0_skill",
                        output_summary=formatted_output,
                        success=True,
                        skill_used=matched_skill.skill_name,
                    )
                    self.memory.record_episode(
                        task_input=user_task,
                        tier_used="tier0_skill",
                        skill_used=matched_skill.skill_name,
                        output_summary=formatted_output,
                        success=True,
                        tokens_spent=0,
                        reflection=reflection,
                    )
                    return CognitiveTurnResult(
                        success=True,
                        tier_used="tier0_skill",
                        answer=formatted_output,
                        skill_used=matched_skill.skill_name,
                        tokens_spent=0,
                        latency_ms=exec_res.latency_ms,
                        reflection=reflection,
                        metadata={
                            "match_score": matched_skill.match_score,
                            "teacher_synced": sync_report["lessons_processed"],
                        },
                    )

        # Retrieve relevant Semantic Graph & Episodic Memory context (0 tokens)
        kg_context = self.memory.query_knowledge_context(user_task)
        past_episodes = self.memory.recall_similar_episodes(user_task, limit=3)

        # =====================================================================
        # TIER 1: SUBCONSCIOUS FLASH-LITE WORKER (STRICT TOKEN BUDGET)
        # =====================================================================
        total_tokens_this_turn = 0
        if self.llm.is_configured():
            # Try autonomous skill synthesis first if requested
            if auto_forge_skill:
                promo, synth_tokens, synth_err = (
                    self.evolution.attempt_tier1_skill_synthesis(user_task)
                )
                total_tokens_this_turn += synth_tokens
                if promo and promo.promoted:
                    exec_res = self.sandbox.execute_skill(
                        skill_path=Path(promo.file_path),
                        kwargs={"query": user_task},
                    )
                    self.memory.update_skill_stats(
                        skill_name=promo.skill_name,
                        success=exec_res.ok,
                        latency_ms=exec_res.latency_ms,
                    )
                    if exec_res.ok:
                        formatted_output = json.dumps(
                            exec_res.output, ensure_ascii=False, indent=2
                        )
                        reflection = self.evolution.reflect_and_update_graph(
                            task_input=user_task,
                            tier_used="tier1_forged_skill",
                            output_summary=formatted_output,
                            success=True,
                            skill_used=promo.skill_name,
                        )
                        self.memory.record_episode(
                            task_input=user_task,
                            tier_used="tier1_forged_skill",
                            skill_used=promo.skill_name,
                            output_summary=formatted_output,
                            success=True,
                            tokens_spent=total_tokens_this_turn,
                            reflection=reflection,
                        )
                        return CognitiveTurnResult(
                            success=True,
                            tier_used="tier1_forged_skill",
                            answer=formatted_output,
                            skill_used=promo.skill_name,
                            tokens_spent=total_tokens_this_turn,
                            latency_ms=exec_res.latency_ms,
                            reflection=reflection,
                            metadata={"promotion_message": promo.message},
                        )

            # Fallback to direct concise reasoning on Tier-1 Flash-Lite
            context_snippet = json.dumps(
                {
                    "known_heuristics": [
                        h["rule_text"] for h in kg_context.get("heuristics", [])[:3]
                    ],
                    "graph_nodes": [
                        {"id": n["node_id"], "summary": n["summary"]}
                        for n in kg_context.get("nodes", [])[:4]
                    ],
                },
                ensure_ascii=False,
            )
            direct_resp = self.llm.ask_subconscious(
                user_input=f"Ngữ cảnh bộ nhớ: {context_snippet}\n\nNhiệm vụ: {user_task}",
                system_instruction=(
                    "Bạn là nhân suy luận Tầng 1 của NEXUS-ZERO. "
                    "Trả lời ngắn gọn, chính xác, tiết kiệm token nhất có thể bằng tiếng Việt."
                ),
                purpose="tier1_direct_answer",
            )
            total_tokens_this_turn += direct_resp.tokens_used
            if direct_resp.ok and direct_resp.text.strip():
                reflection = self.evolution.reflect_and_update_graph(
                    task_input=user_task,
                    tier_used=f"tier1_llm ({direct_resp.model_used})",
                    output_summary=direct_resp.text,
                    success=True,
                )
                self.memory.record_episode(
                    task_input=user_task,
                    tier_used="tier1_llm",
                    output_summary=direct_resp.text,
                    success=True,
                    tokens_spent=total_tokens_this_turn,
                    reflection=reflection,
                )
                return CognitiveTurnResult(
                    success=True,
                    tier_used=f"tier1_llm ({direct_resp.model_used})",
                    answer=direct_resp.text,
                    tokens_spent=total_tokens_this_turn,
                    reflection=reflection,
                )
            escalation_reason = direct_resp.error
        else:
            escalation_reason = (
                "Chưa có Kỹ năng Tầng 0 phù hợp và Tầng 1 đang ở chế độ Offline (0-API-Key). "
                "Yêu cầu Giáo viên Gemini 4 Argon Ultra dạy Kỹ năng mới."
            )

        # =====================================================================
        # TIER 2: SYMBIOTIC ESCALATION TO GEMINI 4 ARGON ULTRA (ANTIGRAVITY)
        # =====================================================================
        req_id = self.bridge.enqueue_for_teacher(
            task_input=user_task,
            reason=escalation_reason,
            memory_context=kg_context,
        )
        msg = (
            f"[TẦNG 2 - CẦU NỐI GIÁO VIÊN] NEXUS-ZERO chưa có kỹ năng xử lý nhiệm vụ này ở Tầng 0.\n"
            f"- Lý do chuyển tiếp: {escalation_reason}\n"
            f"- Đã ghi hồ sơ yêu cầu học tập `{req_id}` vào `bridge/teacher_inbox.json`.\n"
            f"- Hãy bảo Gemini 4 Argon Ultra (trong Antigravity) dạy kỹ năng này, sau đó NEXUS-ZERO sẽ tự thực thi với 0 token!"
        )
        reflection = self.evolution.reflect_and_update_graph(
            task_input=user_task,
            tier_used="tier2_teacher_escalation",
            output_summary=msg,
            success=False,
        )
        self.memory.record_episode(
            task_input=user_task,
            tier_used="tier2_teacher_escalation",
            output_summary=msg,
            success=False,
            tokens_spent=total_tokens_this_turn,
            reflection=reflection,
        )
        return CognitiveTurnResult(
            success=False,
            tier_used="tier2_teacher_escalation",
            answer=msg,
            tokens_spent=total_tokens_this_turn,
            teacher_request_id=req_id,
            reflection=reflection,
            metadata={"past_episodes_checked": len(past_episodes)},
        )

    def get_full_status(self) -> dict[str, Any]:
        sync_info = self.bridge.ingest_teacher_lessons()
        return {
            "brain": self.memory.get_brain_stats(),
            "budget": self.budget.get_today_usage(),
            "tier1_api_configured": self.llm.is_configured(),
            "pending_teacher_requests": len(self.bridge.get_pending_requests()),
            "latest_teacher_sync": sync_info,
        }
