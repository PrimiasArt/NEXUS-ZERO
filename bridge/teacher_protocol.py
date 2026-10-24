"""
Symbiotic Teacher Bridge (`teacher_inbox.json` <-> `teacher_outbox.json`).
Allows NEXUS-ZERO to escalate hard problems, failed skill syntheses, or zero-budget
tasks directly to Gemini 4 Argon Ultra + 40+ MCP tools inside Antigravity,
and ingest Teacher-synthesized Skills, Knowledge Graph nodes, and Core Heuristics.
"""

from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from typing import Any

from config import TEACHER_INBOX_PATH, TEACHER_OUTBOX_PATH
from core.evolution import SelfEvolutionEngine
from core.memory import BioCognitiveMemory


class SymbioticTeacherBridge:
    """
    Manages asynchronous and interactive knowledge transfer between the local
    NEXUS-ZERO brain and the Supreme Teacher (Gemini 4 Argon Ultra in Antigravity).
    """

    def __init__(
        self,
        memory: BioCognitiveMemory,
        evolution: SelfEvolutionEngine,
        inbox_path: Path = TEACHER_INBOX_PATH,
        outbox_path: Path = TEACHER_OUTBOX_PATH,
    ):
        self.memory = memory
        self.evolution = evolution
        self.inbox_path = inbox_path
        self.outbox_path = outbox_path
        self._ensure_files()

    def _ensure_files(self) -> None:
        self.inbox_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.inbox_path.exists():
            self.inbox_path.write_text(
                json.dumps(
                    {
                        "description": "Hàng đợi câu hỏi từ NEXUS-ZERO gửi lên Giáo viên Gemini 4 Argon Ultra (Antigravity).",
                        "pending_requests": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if not self.outbox_path.exists():
            self.outbox_path.write_text(
                json.dumps(
                    {
                        "description": "Bài giảng, Đồ thị tri thức và Kỹ năng Python mới từ Giáo viên Argon Ultra truyền xuống NEXUS-ZERO.",
                        "pending_lessons": [],
                        "history_applied": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def enqueue_for_teacher(
        self,
        task_input: str,
        reason: str,
        memory_context: dict[str, Any],
    ) -> str:
        """
        Write a structured escalation request to `bridge/teacher_inbox.json`
        when Tier-0 has no matching skill and Tier-1 is out of budget or fails.
        """
        self._ensure_files()
        data = json.loads(self.inbox_path.read_text(encoding="utf-8"))
        req_id = "req_" + uuid.uuid4().hex[:8]
        entry = {
            "request_id": req_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "task_input": task_input,
            "escalation_reason": reason,
            "known_skills": [s.skill_name for s in self.memory.list_skills()],
            "relevant_graph_nodes": [
                n["node_id"] for n in memory_context.get("nodes", [])[:5]
            ],
            "status": "waiting_for_argon_ultra",
        }
        data.setdefault("pending_requests", []).append(entry)
        self.inbox_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return req_id

    def get_pending_requests(self) -> list[dict[str, Any]]:
        self._ensure_files()
        data = json.loads(self.inbox_path.read_text(encoding="utf-8"))
        return [
            r
            for r in data.get("pending_requests", [])
            if r.get("status") == "waiting_for_argon_ultra"
        ]

    def ingest_teacher_lessons(self) -> dict[str, Any]:
        """
        Reads `bridge/teacher_outbox.json`, validates & promotes any new Python
        skills via AST Security Gate + Sandbox, imports Knowledge Graph nodes/edges
        and Core Heuristics, and marks requests as resolved.
        """
        self._ensure_files()
        outbox = json.loads(self.outbox_path.read_text(encoding="utf-8"))
        pending_lessons = outbox.get("pending_lessons", [])
        if not pending_lessons:
            return {
                "lessons_processed": 0,
                "skills_promoted": [],
                "skills_rejected": [],
                "nodes_added": 0,
                "heuristics_added": 0,
            }

        skills_promoted: list[str] = []
        skills_rejected: list[dict[str, str]] = []
        nodes_added = 0
        heuristics_added = 0
        resolved_req_ids: set[str] = set()

        for lesson in pending_lessons:
            req_id = lesson.get("request_id")
            if req_id:
                resolved_req_ids.add(req_id)

            # 1. Ingest Knowledge Graph Nodes
            for node in lesson.get("knowledge_nodes", []):
                self.memory.upsert_knowledge_node(
                    node_id=node["node_id"],
                    label=node.get("label", node["node_id"]),
                    category=node.get("category", "teacher_concept"),
                    summary=node.get("summary", ""),
                    confidence=float(node.get("confidence", 0.95)),
                    strength_boost=0.8,
                )
                nodes_added += 1

            # 2. Ingest Knowledge Graph Edges
            for edge in lesson.get("knowledge_edges", []):
                self.memory.upsert_knowledge_edge(
                    source_id=edge["source_id"],
                    relation=edge["relation"],
                    target_id=edge["target_id"],
                    weight=float(edge.get("weight", 1.5)),
                    evidence=edge.get("evidence", "Taught by Gemini 4 Argon Ultra"),
                )

            # 3. Ingest Core Heuristics
            for rule in lesson.get("heuristics", []):
                self.memory.add_core_heuristic(
                    domain=rule.get("domain", "general"),
                    rule_text=rule["rule_text"],
                    confidence=float(rule.get("confidence", 0.95)),
                )
                heuristics_added += 1

            # 4. Forge & Verify Teacher-Provided Python Skills
            for skill_spec in lesson.get("skills", []):
                promo = self.evolution.forge_and_verify_skill(
                    raw_code=skill_spec["code"],
                    suggested_name=skill_spec.get("name", "teacher_skill"),
                    source_label="teacher:gemini_4_argon_ultra",
                )
                if promo.promoted:
                    skills_promoted.append(promo.skill_name)
                else:
                    skills_rejected.append(
                        {"name": promo.skill_name, "error": promo.message}
                    )

            lesson["applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            outbox.setdefault("history_applied", []).append(lesson)

        outbox["pending_lessons"] = []
        self.outbox_path.write_text(
            json.dumps(outbox, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Mark corresponding inbox requests as resolved
        if resolved_req_ids:
            inbox = json.loads(self.inbox_path.read_text(encoding="utf-8"))
            for req in inbox.get("pending_requests", []):
                if req.get("request_id") in resolved_req_ids:
                    req["status"] = "resolved_by_argon_ultra"
            self.inbox_path.write_text(
                json.dumps(inbox, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        return {
            "lessons_processed": len(pending_lessons),
            "skills_promoted": skills_promoted,
            "skills_rejected": skills_rejected,
            "nodes_added": nodes_added,
            "heuristics_added": heuristics_added,
        }
