"""
Self-Evolution Engine: Autonomous Skill Synthesis, Post-Task Reflection,
and Bio-Inspired Sleep & Consolidation Phase.
"""

from __future__ import annotations
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import (
    DEFAULT_CONFIG,
    NexusConfig,
    SKILLS_STAGING_DIR,
    SKILLS_VERIFIED_DIR,
)
from core.llm_client import Tier1SubconsciousClient
from core.memory import BioCognitiveMemory
from core.sandbox import IsolatedSkillSandbox


SKILL_SYNTHESIS_SYSTEM_PROMPT = """Bạn là bộ phận Tổng hợp Kỹ năng (Procedural Skill Synthesizer) của hệ thống AI tự tiến hóa NEXUS-ZERO.
Nhiệm vụ của bạn là viết một module Python hoàn chỉnh, tự đóng gói, chỉ dùng thư viện chuẩn nằm trong danh sách cho phép:
(math, statistics, random, datetime, time, json, csv, re, collections, itertools, functools, hashlib, base64, urllib.parse, urllib.request, pathlib, typing, dataclasses, string, textwrap, decimal, fractions).

QUY TẮC BẮT BUỘC (NẾU VI PHẠM SẼ BỊ CỔNG AN TOÀN AST CHẶN):
1. KHÔNG dùng eval, exec, compile, __import__, os, subprocess, shutil, sys, open() ngoài thư mục hiện tại.
2. Module PHẢI khai báo biến hằng `SKILL_META` ở cấp cao nhất theo đúng cấu trúc:
SKILL_META = {
    "name": "ten_ky_nang_snake_case",
    "description": "Mô tả ngắn gọn kỹ năng làm gì",
    "keywords": ["từ khóa 1", "từ khóa 2", "keyword 3"],
    "parameters": {
        "query": "Chuỗi đầu vào hoặc biểu thức của người dùng"
    }
}
3. Module PHẢI có hàm `def run(query: str = "", **kwargs) -> dict:` nhận đầu vào (ưu tiên tự bóc tách số liệu/tham số từ chuỗi `query` của người dùng để Tầng 0 gọi trực tiếp với 0 token!) và trả về dict kết quả rõ ràng.
4. Module PHẢI có hàm `def self_test() -> bool:` tự kiểm thử ít nhất 2 trường hợp và trả về `True` nếu đúng hoàn toàn.
5. Chỉ trả về duy nhất khối code Python nằm trong cặp ```python ... ```.
"""


@dataclass
class SkillPromotionResult:
    promoted: bool
    skill_name: str
    file_path: str = ""
    message: str = ""
    test_output: Any = None


class SelfEvolutionEngine:
    """
    Drives continual learning from zero:
    - Forges, validates, and promotes new Python skills into `skills_vault/verified/`.
    - Extracts knowledge entities/edges from task episodes.
    - Runs the Sleep & Consolidation phase (Ebbinghaus decay + heuristic distillation).
    """

    def __init__(
        self,
        memory: BioCognitiveMemory,
        sandbox: IsolatedSkillSandbox,
        llm_client: Tier1SubconsciousClient,
        config: NexusConfig = DEFAULT_CONFIG,
    ):
        self.memory = memory
        self.sandbox = sandbox
        self.llm = llm_client
        self.config = config
        self.config.ensure_directories()

    @staticmethod
    def extract_python_code(raw_text: str) -> str:
        match = re.search(r"```(?:python)?\s*(.*?)```", raw_text, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
        return raw_text.strip()

    def forge_and_verify_skill(
        self,
        raw_code: str,
        suggested_name: str = "custom_skill",
        source_label: str = "self_evolution",
    ) -> SkillPromotionResult:
        """
        Stages candidate Python skill code, inspects it via ASTSecurityGate,
        executes `self_test()` inside IsolatedSkillSandbox, and promotes to
        `skills_vault/verified/` upon passing all checks.
        """
        clean_code = self.extract_python_code(raw_code)
        safe_filename = re.sub(r"[^a-zA-Z0-9_]", "_", suggested_name.lower()).strip("_")
        if not safe_filename.startswith("skill_"):
            safe_filename = f"skill_{safe_filename}"

        staging_path = SKILLS_STAGING_DIR / f"{safe_filename}.py"
        staging_path.write_text(clean_code, encoding="utf-8")

        # Validate with AST Gate + Subprocess self_test()
        validation = self.sandbox.validate_and_test_skill_file(staging_path)
        if not validation.ok or not validation.skill_meta:
            return SkillPromotionResult(
                promoted=False,
                skill_name=safe_filename,
                file_path=str(staging_path),
                message=validation.error,
                test_output=validation.output,
            )

        meta = validation.skill_meta
        official_name = re.sub(
            r"[^a-zA-Z0-9_]", "_", str(meta.get("name", safe_filename)).lower()
        )
        verified_path = SKILLS_VERIFIED_DIR / f"{official_name}.py"
        shutil.copy2(staging_path, verified_path)

        code_hash = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()[:16]
        description = str(meta.get("description", "Kỹ năng tự tổng hợp"))
        keywords = [str(k) for k in meta.get("keywords", [official_name])]
        parameters = dict(meta.get("parameters", {"query": "Input string"}))

        # Register into Procedural Memory (Tier-0 Vault)
        self.memory.register_verified_skill(
            skill_name=official_name,
            description=description,
            trigger_keywords=keywords,
            parameters_schema=parameters,
            file_path=str(verified_path),
            code_hash=code_hash,
        )

        # Connect into Semantic Knowledge Graph
        self.memory.upsert_knowledge_node(
            node_id=f"skill:{official_name}",
            label=official_name,
            category="procedural_skill",
            summary=description,
            confidence=0.95,
            strength_boost=0.5,
        )
        self.memory.upsert_knowledge_edge(
            source_id=f"skill:{official_name}",
            relation="synthesized_by",
            target_id=source_label,
            weight=1.2,
            evidence=f"Passed AST Gate & self_test ({validation.latency_ms:.1f}ms)",
        )

        return SkillPromotionResult(
            promoted=True,
            skill_name=official_name,
            file_path=str(verified_path),
            message=(
                f"Đã kiểm duyệt AST & self_test() thành công ({validation.latency_ms:.1f}ms). "
                f"Thăng cấp lên '{verified_path.name}'."
            ),
            test_output=validation.output,
        )

    def attempt_tier1_skill_synthesis(
        self, task_description: str
    ) -> tuple[SkillPromotionResult | None, int, str]:
        """
        Ask Tier-1 (`gemini-3.5-flash-lite`) to forge a generalizable Python skill
        for a novel analytical/computational task so future similar tasks cost 0 tokens.
        """
        prompt = (
            f"Yêu cầu của người dùng: {task_description}\n\n"
            "Hãy thiết kế một kỹ năng Python tổng quát (nhận `query: str` và tự bóc tách số liệu/dữ liệu bằng regex hoặc parser trong hàm `run(query: str = '', **kwargs)`) "
            "để không chỉ giải quyết câu hỏi này mà còn giải được mọi câu hỏi tương tự trong tương lai ở Tầng 0."
        )
        resp = self.llm.ask_subconscious(
            user_input=prompt,
            system_instruction=SKILL_SYNTHESIS_SYSTEM_PROMPT,
            purpose="tier1_skill_synthesis",
            use_reasoning_tier=False,
            max_output_tokens=1024,
        )
        if not resp.ok:
            return None, 0, resp.error

        promo = self.forge_and_verify_skill(
            raw_code=resp.text,
            suggested_name="auto_synthesized",
            source_label=resp.model_used,
        )
        return promo, resp.tokens_used, ""

    def reflect_and_update_graph(
        self,
        task_input: str,
        tier_used: str,
        output_summary: str,
        success: bool,
        skill_used: str | None = None,
    ) -> str:
        """
        Lightweight local reflection (0 API tokens): extracts key concepts and links
        the episode outcome into the Semantic Knowledge Graph.
        """
        words = [
            w.lower()
            for w in re.findall(r"\w+", task_input, flags=re.UNICODE)
            if len(w) >= 4
        ]
        unique_concepts = list(dict.fromkeys(words))[:4]
        for concept in unique_concepts:
            self.memory.upsert_knowledge_node(
                node_id=f"concept:{concept}",
                label=concept,
                category="task_concept",
                summary=f"Xuất hiện trong nhiệm vụ: {task_input[:80]}",
                confidence=0.8 if success else 0.5,
                strength_boost=0.15 if success else 0.05,
            )
            if skill_used:
                self.memory.upsert_knowledge_edge(
                    source_id=f"skill:{skill_used}",
                    relation="solves_concept" if success else "failed_on_concept",
                    target_id=f"concept:{concept}",
                    weight=1.0 if success else 0.3,
                    evidence=output_summary[:120],
                )

        if success and skill_used:
            return f"Kỹ năng '{skill_used}' xử lý thành công ở {tier_used}; đã củng cố liên kết đồ thị tri thức."
        if not success:
            return f"Nhiệm vụ chưa hoàn tất ở {tier_used}; cần bổ sung kỹ năng mới hoặc nhờ Giáo viên Argon Ultra hướng dẫn."
        return f"Đã ghi nhận trải nghiệm mới qua {tier_used}."

    def run_sleep_cycle(self) -> dict[str, Any]:
        """
        Bio-Inspired Sleep & Consolidation Cycle:
        1. Applies Ebbinghaus exponential decay to unused knowledge graph nodes.
        2. Analyzes recent episodes to synthesize local meta-heuristics.
        3. Reports memory optimization statistics.
        """
        decay_stats = self.memory.apply_ebbinghaus_decay()
        recent_episodes = self.memory.recall_similar_episodes("", limit=15)

        total_eps = len(recent_episodes)
        tier0_hits = sum(
            1 for ep in recent_episodes if ep.get("tier_used") == "tier0_skill"
        )
        failures = [ep for ep in recent_episodes if not ep.get("success")]

        new_rules_added = 0
        if total_eps > 0:
            autonomy_ratio = (tier0_hits / total_eps) * 100.0
            rule_text = (
                f"Tỷ lệ tự chủ Tầng 0 (0-token) hiện đạt {autonomy_ratio:.1f}% trên {total_eps} nhiệm vụ gần nhất. "
                "Ưu tiên đóng gói các phép tính, phân tích chuỗi và xử lý dữ liệu lặp lại thành Verified Skill."
            )
            self.memory.add_core_heuristic(
                domain="meta_cognition",
                rule_text=rule_text,
                confidence=0.92,
            )
            new_rules_added += 1

        if failures:
            fail_topics = "; ".join(ep["task_input"][:50] for ep in failures[:3])
            self.memory.add_core_heuristic(
                domain="failure_prevention",
                rule_text=f"Cần rèn thêm kỹ năng chuyên biệt cho các dạng bài từng thất bại: {fail_topics}",
                confidence=0.95,
            )
            new_rules_added += 1

        return {
            "pruned_weak_nodes": decay_stats["pruned_nodes"],
            "active_knowledge_nodes": decay_stats["remaining_nodes"],
            "recent_episodes_consolidated": total_eps,
            "new_core_heuristics_distilled": new_rules_added,
        }
