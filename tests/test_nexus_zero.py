"""
Automated Verification Suite for Project NEXUS-ZERO.
Tests:
1. AST Security Gate (blocks dangerous imports, eval/exec, dunder escapes).
2. Token Budget Governor (daily limit enforcement & 0-token SQLite prompt cache).
3. Tier-0 Procedural Skill Matching & Subprocess Execution.
4. Ebbinghaus Memory Decay & Knowledge Graph Reinforcement.
"""

from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import NexusConfig, SKILLS_VERIFIED_DIR
from core.budget import BudgetExhaustedError, TokenBudgetGovernor
from core.kernel import NexusZeroKernel
from core.sandbox import ASTSecurityGate


def test_ast_security_gate() -> None:
    gate = ASTSecurityGate()

    # 1. Malicious skill attempting subprocess, eval, open, and getattr
    malicious_code = """
import subprocess
SKILL_META = {"name": "hack", "description": "bad", "keywords": ["hack"], "parameters": {}}
def run(**kwargs):
    eval("1+1")
    open("secret.txt")
    getattr(object, "__subclasses__")
    return subprocess.check_output("whoami")
def self_test():
    return True
"""
    ok, violations = gate.inspect_code(malicious_code)
    assert not ok, "AST Gate must block subprocess, eval(), open(), and getattr()"
    assert any("subprocess" in v for v in violations)
    assert any("eval" in v for v in violations)
    assert any("open" in v for v in violations)
    assert any("getattr" in v for v in violations)

    # 2. Malicious dunder escape attempt
    dunder_escape = """
import math
SKILL_META = {"name": "escape", "description": "bad", "keywords": ["escape"], "parameters": {}}
def run(**kwargs):
    return ().__class__.__base__.__subclasses__()
def self_test():
    return True
"""
    ok2, violations2 = gate.inspect_code(dunder_escape)
    assert not ok2, "AST Gate must block dunder attribute escapes"
    print("[PASS] AST Security Gate blocks forbidden imports, eval(), open(), getattr(), and dunder escapes.")


def test_budget_governor_and_cache(tmp_path: Path) -> None:
    cfg = NexusConfig(daily_token_limit=1000, max_calls_per_minute=3)
    db_file = tmp_path / "test_budget.db"
    gov = TokenBudgetGovernor(db_path=db_file, config=cfg)

    gov.verify_can_spend(400)
    gov.record_spend("gemini-3.5-flash-lite", "test_call_1", 600)

    # Exceeding daily limit (600 + 500 > 1000) must raise BudgetExhaustedError
    try:
        gov.verify_can_spend(500)
        raise AssertionError("Should have raised BudgetExhaustedError")
    except BudgetExhaustedError:
        pass

    # Verify Semantic Prompt Cache (0 tokens on repeat query)
    gov.save_cache("gemini-3.5-flash-lite", "sys", "Hello World", "Xin chào!", 50)
    cached = gov.check_cache("gemini-3.5-flash-lite", "sys", "   hello   world ")
    assert cached == "Xin chào!"
    print("[PASS] Token Budget Governor enforces hard token caps and 0-token cache.")


def test_isolated_kernel_tier0_and_decay(tmp_path: Path) -> None:
    db_file = tmp_path / "test_nexus.db"
    inbox_file = tmp_path / "teacher_inbox.json"
    outbox_file = tmp_path / "teacher_outbox.json"

    kernel = NexusZeroKernel(
        db_path=db_file,
        inbox_path=inbox_file,
        outbox_path=outbox_file,
    )

    # Register existing verified skills into the isolated test DB
    for skill_file in SKILLS_VERIFIED_DIR.glob("*.py"):
        kernel.evolution.forge_and_verify_skill(
            raw_code=skill_file.read_text(encoding="utf-8"),
            suggested_name=skill_file.stem,
            source_label="test_suite",
        )

    # 1. Multi-keyword statistical task
    res = kernel.handle_task(
        "Phân tích thống kê và tìm outlier cho dãy số [5, 7, 8, 9, 10, 12, 99]"
    )
    assert res.success is True
    assert res.tier_used == "tier0_skill"
    assert res.skill_used == "statistical_analyzer"
    assert res.tokens_spent == 0

    # 2. Single-keyword query ("sha256")
    res_hash = kernel.handle_task("Tính sha256 cho chuỗi NEXUS-ZERO")
    assert res_hash.success is True
    assert res_hash.tier_used == "tier0_skill"
    assert res_hash.skill_used == "text_entropy_hash"
    assert res_hash.tokens_spent == 0

    # 3. Verify Ebbinghaus decay protects procedural skills & prunes weak transient nodes
    kernel.memory.upsert_knowledge_node(
        node_id="concept:temp_weak",
        label="temp_weak",
        category="task_concept",
        confidence=0.5,
    )
    with kernel.memory._connect() as conn:
        conn.execute(
            "UPDATE kg_nodes SET strength = 0.12, access_count = 2 WHERE node_id = 'concept:temp_weak'"
        )
    decay_report = kernel.memory.apply_ebbinghaus_decay()
    assert decay_report["pruned_nodes"] >= 1
    print(
        f"[PASS] Isolated Kernel solved multi/single-keyword tasks at Tier-0 ({res.latency_ms:.1f}ms, 0 tokens) & pruned weak nodes."
    )


if __name__ == "__main__":
    import tempfile

    test_ast_security_gate()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_budget_governor_and_cache(tmp_path)
        test_isolated_kernel_tier0_and_decay(tmp_path)
    print("\nALL NEXUS-ZERO VERIFICATION TESTS PASSED!")
