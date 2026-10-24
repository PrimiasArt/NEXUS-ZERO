"""
Project NEXUS-ZERO: Central Configuration & Constraints
Self-Evolving Cognitive Architecture from Scratch.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(r"F:\Project\NEXUS-ZERO")
DATA_DIR = BASE_DIR / "data"
SANDBOX_WORKSPACE = DATA_DIR / "sandbox_workspace"
DB_PATH = DATA_DIR / "nexus_memory.db"

SKILLS_VAULT_DIR = BASE_DIR / "skills_vault"
SKILLS_STAGING_DIR = SKILLS_VAULT_DIR / "staging"
SKILLS_VERIFIED_DIR = SKILLS_VAULT_DIR / "verified"

BRIDGE_DIR = BASE_DIR / "bridge"
TEACHER_INBOX_PATH = BRIDGE_DIR / "teacher_inbox.json"
TEACHER_OUTBOX_PATH = BRIDGE_DIR / "teacher_outbox.json"


@dataclass
class NexusConfig:
    """Central configuration enforcing budget, hardware, and safety constraints."""

    # --- Model Tiers (Strict adherence to current Gemini API models) ---
    tier1_fast_model: str = "gemini-3.5-flash-lite"
    tier1_reasoning_model: str = "gemini-3.8-flash"
    teacher_model_name: str = "gemini-4-argon"

    # --- Constraint 1: Strict API Token Budget Governor ---
    daily_token_limit: int = int(os.getenv("NEXUS_DAILY_TOKEN_LIMIT", "40000"))
    max_calls_per_minute: int = int(os.getenv("NEXUS_MAX_RPM", "8"))
    max_output_tokens_per_call: int = 1024
    enable_semantic_cache: bool = True

    # --- Constraint 2: Low-Hardware Local Footprint ---
    # Uses SQLite WAL + FTS5 BM25 instead of heavy RAM/VRAM embedding servers
    max_episodic_context_items: int = 5
    max_graph_context_nodes: int = 10
    tier0_skill_match_threshold: float = 0.45

    # --- Constraint 3: AST Security Gate & Isolated Execution Sandbox ---
    sandbox_timeout_seconds: int = 8
    max_skill_code_bytes: int = 24_576  # 24 KB max per generated skill
    allowed_imports: set[str] = field(
        default_factory=lambda: {
            "math",
            "statistics",
            "random",
            "datetime",
            "time",
            "json",
            "csv",
            "re",
            "collections",
            "itertools",
            "functools",
            "hashlib",
            "base64",
            "urllib.parse",
            "urllib.request",
            "pathlib",
            "typing",
            "dataclasses",
            "string",
            "textwrap",
            "decimal",
            "fractions",
        }
    )
    forbidden_calls: set[str] = field(
        default_factory=lambda: {
            "eval",
            "exec",
            "compile",
            "__import__",
            "globals",
            "locals",
            "vars",
            "dir",
            "getattr",
            "delattr",
            "setattr",
            "open",
            "input",
            "breakpoint",
        }
    )

    # --- Constraint 4: Bio-Inspired Memory Consolidation & Decay ---
    ebbinghaus_decay_factor: float = 0.92  # Applied during Sleep cycle
    min_node_strength_threshold: float = 0.15

    def ensure_directories(self) -> None:
        """Create all required runtime directories if they do not exist."""
        for directory in (
            DATA_DIR,
            SANDBOX_WORKSPACE,
            SKILLS_STAGING_DIR,
            SKILLS_VERIFIED_DIR,
            BRIDGE_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)


DEFAULT_CONFIG = NexusConfig()
