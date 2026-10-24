"""
Bio-Inspired 3-Tier Memory Engine (SQLite WAL + FTS5 + Knowledge Graph).
Designed for ultra-low RAM/CPU footprint while providing persistent,
self-reinforcing cognitive memory across sessions.
"""

from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from config import DB_PATH, DEFAULT_CONFIG, NexusConfig


def _sanitize_fts_query(text: str) -> str:
    """Convert arbitrary user input (Vietnamese/English) into safe FTS5 OR tokens."""
    tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    filtered = [t for t in tokens if len(t) >= 2][:12]
    if not filtered:
        return ""
    return " OR ".join(f'"{t}"' for t in filtered)


def _tokenize_keywords(text: str) -> set[str]:
    """Extract normalized unicode word tokens for fast local Jaccard/overlap scoring."""
    return {t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if len(t) >= 2}


@dataclass
class SkillRecord:
    skill_name: str
    description: str
    trigger_keywords: list[str]
    parameters_schema: dict[str, Any]
    file_path: str
    code_hash: str
    success_count: int
    fail_count: int
    avg_latency_ms: float
    match_score: float = 0.0


class BioCognitiveMemory:
    """
    Persistent 3-compartment brain:
    1. Episodic Memory: Past experiences, execution traces, reflections.
    2. Semantic Memory: Weighted Knowledge Graph (Nodes & Edges) + Core Heuristics.
    3. Procedural Memory: Indexed Python Skills Vault for 0-token Tier-0 execution.
    """

    def __init__(self, db_path: Path = DB_PATH, config: NexusConfig = DEFAULT_CONFIG):
        self.db_path = db_path
        self.config = config
        self.config.ensure_directories()
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                -- 1. EPISODIC MEMORY
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_input TEXT NOT NULL,
                    tier_used TEXT NOT NULL,
                    skill_used TEXT,
                    output_summary TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 1,
                    tokens_spent INTEGER NOT NULL DEFAULT 0,
                    reflection TEXT DEFAULT '',
                    created_at REAL NOT NULL
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
                    task_input,
                    output_summary,
                    reflection,
                    content='episodes',
                    content_rowid='id'
                );

                -- 2. SEMANTIC KNOWLEDGE GRAPH & HEURISTICS
                CREATE TABLE IF NOT EXISTS kg_nodes (
                    node_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'concept',
                    summary TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.8,
                    strength REAL NOT NULL DEFAULT 1.0,
                    access_count INTEGER NOT NULL DEFAULT 1,
                    last_accessed REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kg_edges (
                    edge_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    evidence TEXT DEFAULT '',
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES kg_nodes(node_id) ON DELETE CASCADE,
                    FOREIGN KEY (target_id) REFERENCES kg_nodes(node_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS core_heuristics (
                    rule_id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.9,
                    strength REAL NOT NULL DEFAULT 1.0,
                    times_applied INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                );

                -- 3. PROCEDURAL MEMORY (VERIFIED SKILLS REGISTRY)
                CREATE TABLE IF NOT EXISTS skills_registry (
                    skill_name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    trigger_keywords_json TEXT NOT NULL,
                    parameters_schema_json TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    code_hash TEXT NOT NULL,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    avg_latency_ms REAL NOT NULL DEFAULT 0.0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )

    # =========================================================================
    # COMPARTMENT 1: EPISODIC MEMORY
    # =========================================================================
    def record_episode(
        self,
        task_input: str,
        tier_used: str,
        output_summary: str,
        success: bool = True,
        skill_used: str | None = None,
        tokens_spent: int = 0,
        reflection: str = "",
    ) -> int:
        now = time.time()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO episodes (
                    task_input, tier_used, skill_used, output_summary,
                    success, tokens_spent, reflection, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_input,
                    tier_used,
                    skill_used,
                    output_summary[:2000],
                    1 if success else 0,
                    tokens_spent,
                    reflection[:1000],
                    now,
                ),
            )
            rowid = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO episodes_fts(rowid, task_input, output_summary, reflection)
                VALUES (?, ?, ?, ?)
                """,
                (rowid, task_input, output_summary[:2000], reflection[:1000]),
            )
            return rowid

    def recall_similar_episodes(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        fts_query = _sanitize_fts_query(query)
        with self._connect() as conn:
            if fts_query:
                rows = conn.execute(
                    """
                    SELECT e.*, bm25(episodes_fts) AS rank_score
                    FROM episodes_fts
                    JOIN episodes e ON e.id = episodes_fts.rowid
                    WHERE episodes_fts MATCH ?
                    ORDER BY rank_score ASC, e.created_at DESC
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
                if rows:
                    return [dict(r) for r in rows]

            rows = conn.execute(
                "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # =========================================================================
    # COMPARTMENT 2: SEMANTIC KNOWLEDGE GRAPH & HEURISTICS
    # =========================================================================
    def upsert_knowledge_node(
        self,
        node_id: str,
        label: str,
        category: str = "concept",
        summary: str = "",
        confidence: float = 0.85,
        strength_boost: float = 0.25,
    ) -> None:
        now = time.time()
        norm_id = re.sub(r"\s+", "_", node_id.strip().lower())
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT strength, access_count, summary FROM kg_nodes WHERE node_id = ?",
                (norm_id,),
            ).fetchone()
            if existing:
                new_strength = min(5.0, float(existing["strength"]) + strength_boost)
                new_count = int(existing["access_count"]) + 1
                merged_summary = summary if summary else existing["summary"]
                conn.execute(
                    """
                    UPDATE kg_nodes
                    SET label = ?, category = ?, summary = ?, confidence = MAX(confidence, ?),
                        strength = ?, access_count = ?, last_accessed = ?
                    WHERE node_id = ?
                    """,
                    (
                        label,
                        category,
                        merged_summary,
                        confidence,
                        new_strength,
                        new_count,
                        now,
                        norm_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO kg_nodes (
                        node_id, label, category, summary, confidence,
                        strength, access_count, last_accessed
                    ) VALUES (?, ?, ?, ?, ?, 1.0, 1, ?)
                    """,
                    (norm_id, label, category, summary, confidence, now),
                )

    def upsert_knowledge_edge(
        self,
        source_id: str,
        relation: str,
        target_id: str,
        weight: float = 1.0,
        evidence: str = "",
    ) -> None:
        now = time.time()
        src = re.sub(r"\s+", "_", source_id.strip().lower())
        tgt = re.sub(r"\s+", "_", target_id.strip().lower())
        rel = re.sub(r"\s+", "_", relation.strip().lower())
        edge_id = f"{src}__{rel}__{tgt}"

        # Ensure endpoints exist
        self.upsert_knowledge_node(src, source_id, strength_boost=0.05)
        self.upsert_knowledge_node(tgt, target_id, strength_boost=0.05)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO kg_edges (edge_id, source_id, relation, target_id, weight, evidence, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(edge_id) DO UPDATE SET
                    weight = MIN(5.0, kg_edges.weight + 0.2),
                    evidence = CASE WHEN excluded.evidence != '' THEN excluded.evidence ELSE kg_edges.evidence END,
                    updated_at = excluded.updated_at
                """,
                (edge_id, src, rel, tgt, weight, evidence, now),
            )

    def add_core_heuristic(
        self, domain: str, rule_text: str, confidence: float = 0.9
    ) -> str:
        rule_id = "rule_" + hashlib.sha1(rule_text.encode("utf-8")).hexdigest()[:10]
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO core_heuristics (rule_id, domain, rule_text, confidence, strength, times_applied, created_at)
                VALUES (?, ?, ?, ?, 1.0, 0, ?)
                ON CONFLICT(rule_id) DO UPDATE SET
                    confidence = MAX(core_heuristics.confidence, excluded.confidence),
                    strength = MIN(5.0, core_heuristics.strength + 0.3)
                """,
                (rule_id, domain.lower(), rule_text, confidence, now),
            )
        return rule_id

    def query_knowledge_context(self, query: str, limit: int = 8) -> dict[str, Any]:
        tokens = list(_tokenize_keywords(query))
        with self._connect() as conn:
            nodes = conn.execute(
                "SELECT * FROM kg_nodes ORDER BY strength DESC, last_accessed DESC LIMIT 50"
            ).fetchall()

            matched_nodes = []
            for n in nodes:
                node_tokens = _tokenize_keywords(
                    f"{n['node_id']} {n['label']} {n['summary']}"
                )
                overlap = len(node_tokens.intersection(tokens))
                if overlap > 0 or len(matched_nodes) < 3:
                    matched_nodes.append((overlap * float(n["strength"]), dict(n)))

            matched_nodes.sort(key=lambda x: x[0], reverse=True)
            top_nodes = [item[1] for item in matched_nodes[:limit]]
            node_ids = [n["node_id"] for n in top_nodes]

            edges = []
            if node_ids:
                placeholders = ",".join("?" for _ in node_ids)
                edge_rows = conn.execute(
                    f"""
                    SELECT * FROM kg_edges
                    WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders})
                    ORDER BY weight DESC LIMIT 15
                    """,
                    node_ids + node_ids,
                ).fetchall()
                edges = [dict(e) for e in edge_rows]

            heuristics = [
                dict(h)
                for h in conn.execute(
                    "SELECT * FROM core_heuristics ORDER BY strength DESC, confidence DESC LIMIT 6"
                ).fetchall()
            ]
            return {
                "nodes": top_nodes,
                "edges": edges,
                "heuristics": heuristics,
            }

    # =========================================================================
    # COMPARTMENT 3: PROCEDURAL MEMORY (SKILLS VAULT)
    # =========================================================================
    def register_verified_skill(
        self,
        skill_name: str,
        description: str,
        trigger_keywords: list[str],
        parameters_schema: dict[str, Any],
        file_path: str,
        code_hash: str,
    ) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO skills_registry (
                    skill_name, description, trigger_keywords_json,
                    parameters_schema_json, file_path, code_hash,
                    success_count, fail_count, avg_latency_ms, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0.0, ?, ?)
                ON CONFLICT(skill_name) DO UPDATE SET
                    description = excluded.description,
                    trigger_keywords_json = excluded.trigger_keywords_json,
                    parameters_schema_json = excluded.parameters_schema_json,
                    file_path = excluded.file_path,
                    code_hash = excluded.code_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    skill_name,
                    description,
                    json.dumps(trigger_keywords, ensure_ascii=False),
                    json.dumps(parameters_schema, ensure_ascii=False),
                    file_path,
                    code_hash,
                    now,
                    now,
                ),
            )

    def update_skill_stats(
        self, skill_name: str, success: bool, latency_ms: float
    ) -> None:
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT success_count, fail_count, avg_latency_ms FROM skills_registry WHERE skill_name = ?",
                (skill_name,),
            ).fetchone()
            if not row:
                return
            succ = int(row["success_count"]) + (1 if success else 0)
            fail = int(row["fail_count"]) + (0 if success else 1)
            total = succ + fail
            avg_lat = ((float(row["avg_latency_ms"]) * (total - 1)) + latency_ms) / max(1, total)
            conn.execute(
                """
                UPDATE skills_registry
                SET success_count = ?, fail_count = ?, avg_latency_ms = ?, updated_at = ?
                WHERE skill_name = ?
                """,
                (succ, fail, avg_lat, now, skill_name),
            )

    def match_procedural_skill(self, task_query: str) -> SkillRecord | None:
        """
        Tier-0 Reflex Matcher: scores all verified skills against the user task
        using keyword overlap + description token similarity + reliability bonus.
        Costs 0 API tokens and runs in < 2ms.
        """
        query_tokens = _tokenize_keywords(task_query)
        if not query_tokens:
            return None

        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM skills_registry").fetchall()

        best_skill: SkillRecord | None = None
        best_score = 0.0

        for row in rows:
            keywords: list[str] = json.loads(row["trigger_keywords_json"])
            kw_tokens = _tokenize_keywords(" ".join(keywords))
            desc_tokens = _tokenize_keywords(
                f"{row['skill_name'].replace('_', ' ')} {row['description']}"
            )

            # Calculate phrase & token matches
            exact_phrase_hits = sum(
                1 for kw in keywords if kw.lower() in task_query.lower()
            )
            matched_kw_tokens = len(query_tokens.intersection(kw_tokens))
            kw_overlap = matched_kw_tokens / max(
                1, min(len(query_tokens), len(kw_tokens) or 1)
            )
            desc_overlap = len(query_tokens.intersection(desc_tokens)) / max(
                1, len(query_tokens)
            )

            succ = int(row["success_count"])
            fail = int(row["fail_count"])
            reliability = (succ + 1) / (succ + fail + 1)

            phrase_score = min(1.0, exact_phrase_hits * 0.65)
            kw_score = min(1.0, kw_overlap + (0.15 * matched_kw_tokens))

            score = (
                (0.50 * phrase_score)
                + (0.35 * kw_score)
                + (0.15 * desc_overlap)
            ) * reliability

            if score > best_score:
                best_score = score
                best_skill = SkillRecord(
                    skill_name=row["skill_name"],
                    description=row["description"],
                    trigger_keywords=keywords,
                    parameters_schema=json.loads(row["parameters_schema_json"]),
                    file_path=row["file_path"],
                    code_hash=row["code_hash"],
                    success_count=succ,
                    fail_count=fail,
                    avg_latency_ms=float(row["avg_latency_ms"]),
                    match_score=round(score, 4),
                )

        if best_skill and best_skill.match_score >= self.config.tier0_skill_match_threshold:
            return best_skill
        return None

    def list_skills(self) -> list[SkillRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM skills_registry ORDER BY success_count DESC, updated_at DESC"
            ).fetchall()
        return [
            SkillRecord(
                skill_name=r["skill_name"],
                description=r["description"],
                trigger_keywords=json.loads(r["trigger_keywords_json"]),
                parameters_schema=json.loads(r["parameters_schema_json"]),
                file_path=r["file_path"],
                code_hash=r["code_hash"],
                success_count=int(r["success_count"]),
                fail_count=int(r["fail_count"]),
                avg_latency_ms=float(r["avg_latency_ms"]),
            )
            for r in rows
        ]

    # =========================================================================
    # BIO-INSPIRED CONSOLIDATION & FORGETTING CURVE (SLEEP PHASE)
    # =========================================================================
    def apply_ebbinghaus_decay(self) -> dict[str, int]:
        """
        Decay unused memories using an access-reinforced Ebbinghaus curve
        and prune transient nodes below the minimum strength threshold.
        """
        decay = self.config.ebbinghaus_decay_factor
        base_loss = max(0.0, 1.0 - decay)
        min_strength = self.config.min_node_strength_threshold
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE kg_nodes
                SET strength = strength * (1.0 - (? / MAX(1, access_count)))
                WHERE category != 'procedural_skill'
                """,
                (base_loss,),
            )
            pruned_cur = conn.execute(
                """
                DELETE FROM kg_nodes
                WHERE strength < ? AND category != 'procedural_skill'
                """,
                (min_strength,),
            )
            pruned_count = pruned_cur.rowcount
            remaining = conn.execute("SELECT COUNT(*) AS c FROM kg_nodes").fetchone()["c"]
        return {"pruned_nodes": pruned_count, "remaining_nodes": remaining}

    def get_brain_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            ep_total = conn.execute("SELECT COUNT(*) AS c FROM episodes").fetchone()["c"]
            ep_tier0 = conn.execute(
                "SELECT COUNT(*) AS c FROM episodes WHERE tier_used = 'tier0_skill'"
            ).fetchone()["c"]
            kg_nodes = conn.execute("SELECT COUNT(*) AS c FROM kg_nodes").fetchone()["c"]
            kg_edges = conn.execute("SELECT COUNT(*) AS c FROM kg_edges").fetchone()["c"]
            heuristics = conn.execute(
                "SELECT COUNT(*) AS c FROM core_heuristics"
            ).fetchone()["c"]
            skills = conn.execute(
                "SELECT COUNT(*) AS c FROM skills_registry"
            ).fetchone()["c"]

        return {
            "episodes_total": ep_total,
            "tier0_zero_token_hits": ep_tier0,
            "knowledge_nodes": kg_nodes,
            "knowledge_edges": kg_edges,
            "core_heuristics": heuristics,
            "verified_skills": skills,
        }
