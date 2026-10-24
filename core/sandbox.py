"""
AST Security Gate & Isolated Subprocess Sandbox.
Ensures that any Python Skill synthesized by the AI is statically verified,
cannot access secrets or dangerous system calls, and passes unit tests
inside an isolated workspace before promotion.
"""

from __future__ import annotations
import ast
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import DEFAULT_CONFIG, NexusConfig, SANDBOX_WORKSPACE


@dataclass
class SandboxResult:
    ok: bool
    output: Any
    error: str = ""
    latency_ms: float = 0.0
    skill_meta: dict[str, Any] | None = None


class ASTSecurityGate:
    """
    Static analyzer that inspects the Abstract Syntax Tree (AST) of AI-generated
    Python skill files before they are ever imported or executed.
    """

    def __init__(self, config: NexusConfig = DEFAULT_CONFIG):
        self.config = config
        self.allowed_roots = {m.strip().split(".")[0] for m in config.allowed_imports}

    def inspect_code(self, code: str) -> tuple[bool, list[str]]:
        violations: list[str] = []

        if len(code.encode("utf-8")) > self.config.max_skill_code_bytes:
            return False, ["Kích thước code vượt quá giới hạn an toàn (24KB)."]

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return False, [f"Lỗi cú pháp Python (SyntaxError): {exc}"]

        has_skill_meta = False
        has_run_fn = False
        has_self_test_fn = False

        for node in ast.walk(tree):
            # 1. Check imports against whitelist
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_mod = alias.name.split(".")[0]
                    if root_mod not in self.allowed_roots:
                        violations.append(
                            f"Import bị chặn bởi AST Gate: '{alias.name}' (không nằm trong danh sách trắng)."
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_mod = node.module.split(".")[0]
                    if root_mod not in self.allowed_roots:
                        violations.append(
                            f"ImportFrom bị chặn bởi AST Gate: '{node.module}'."
                        )

            # 2. Check forbidden built-in calls and dangerous attribute access
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    fn_name = node.func.id
                    if fn_name in self.config.forbidden_calls:
                        violations.append(f"Lời gọi hàm nguy hiểm bị cấm: '{fn_name}()'.")
                elif isinstance(node.func, ast.Attribute):
                    attr_name = node.func.attr
                    if attr_name in {
                        "system",
                        "popen",
                        "rmtree",
                        "remove",
                        "unlink",
                        "rmdir",
                        "kill",
                        "spawnl",
                        "spawnv",
                        "execv",
                        "execve",
                        "fork",
                    }:
                        violations.append(
                            f"Phương thức hệ thống nguy hiểm bị cấm: '.{attr_name}()'."
                        )

            # 3. Prevent dunder introspection escapes (__subclasses__, __globals__, etc.)
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr not in {
                    "__name__",
                    "__doc__",
                    "__init__",
                }:
                    violations.append(
                        f"Truy cập thuộc tính dunder bị cấm: '{node.attr}'."
                    )

            # 4. Verify Skill Contract declarations
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "SKILL_META":
                        has_skill_meta = True
            elif isinstance(node, ast.FunctionDef):
                if node.name == "run":
                    has_run_fn = True
                elif node.name == "self_test":
                    has_self_test_fn = True

        if not has_skill_meta:
            violations.append("Thiếu biến hằng 'SKILL_META' định nghĩa thông tin kỹ năng.")
        if not has_run_fn:
            violations.append("Thiếu hàm chuẩn 'def run(**kwargs):' để thực thi kỹ năng.")
        if not has_self_test_fn:
            violations.append("Thiếu hàm tự kiểm thử 'def self_test():'.")

        return len(violations) == 0, violations


class IsolatedSkillSandbox:
    """
    Executes verified or staged Python skills inside a separate OS subprocess
    with stripped environment variables (no API keys exposed), locked working
    directory, and hard execution timeout.
    """

    def __init__(self, config: NexusConfig = DEFAULT_CONFIG):
        self.config = config
        self.gate = ASTSecurityGate(config)
        self.config.ensure_directories()

    @staticmethod
    def _build_safe_env() -> dict[str, str]:
        """Strip sensitive API keys and credentials from child process environment."""
        safe_keys = {
            "SYSTEMROOT",
            "PATH",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "HOMEDRIVE",
            "HOMEPATH",
            "PYTHONIOENCODING",
        }
        env = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return env

    def validate_and_test_skill_file(self, skill_path: Path) -> SandboxResult:
        """
        Run AST Security Gate + execute `self_test()` inside isolated subprocess.
        Returns metadata if and only if both static & dynamic checks pass.
        """
        code = skill_path.read_text(encoding="utf-8")
        ok, violations = self.gate.inspect_code(code)
        if not ok:
            return SandboxResult(
                ok=False,
                output=None,
                error="Vi phạm cổng an toàn AST:\n- " + "\n- ".join(violations),
            )

        runner_code = (
            "import importlib.util, json, sys\n"
            f"spec = importlib.util.spec_from_file_location('skill_mod', {repr(str(skill_path))})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "meta = getattr(mod, 'SKILL_META', {})\n"
            "test_res = mod.self_test()\n"
            "print(json.dumps({'ok': bool(test_res), 'meta': meta, 'test_result': test_res}, ensure_ascii=False))\n"
        )

        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-X", "utf8", "-c", runner_code],
                cwd=str(SANDBOX_WORKSPACE),
                env=self._build_safe_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.config.sandbox_timeout_seconds,
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
        except subprocess.TimeoutExpired:
            return SandboxResult(
                ok=False,
                output=None,
                error=f"Quá thời gian chạy thử nghiệm ({self.config.sandbox_timeout_seconds}s timeout).",
            )

        if proc.returncode != 0:
            return SandboxResult(
                ok=False,
                output=None,
                error=f"Lỗi khi chạy self_test(): {proc.stderr.strip() or proc.stdout.strip()}",
                latency_ms=latency_ms,
            )

        try:
            last_line = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()][-1]
            payload = json.loads(last_line)
            if not payload.get("ok"):
                return SandboxResult(
                    ok=False,
                    output=payload.get("test_result"),
                    error="Hàm self_test() trả về False.",
                    latency_ms=latency_ms,
                )
            return SandboxResult(
                ok=True,
                output=payload.get("test_result"),
                skill_meta=payload.get("meta"),
                latency_ms=latency_ms,
            )
        except Exception as exc:
            return SandboxResult(
                ok=False,
                output=proc.stdout,
                error=f"Không đọc được kết quả JSON từ self_test(): {exc}",
                latency_ms=latency_ms,
            )

    def execute_skill(self, skill_path: Path, kwargs: dict[str, Any]) -> SandboxResult:
        """Execute `run(**kwargs)` of a verified skill in an isolated subprocess."""
        code = skill_path.read_text(encoding="utf-8")
        ok, violations = self.gate.inspect_code(code)
        if not ok:
            return SandboxResult(
                ok=False,
                output=None,
                error="Kỹ năng không vượt qua kiểm tra lại AST: " + "; ".join(violations),
            )

        kwargs_json = json.dumps(kwargs, ensure_ascii=False)
        runner_code = (
            "import importlib.util, json, sys\n"
            f"spec = importlib.util.spec_from_file_location('skill_mod', {repr(str(skill_path))})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            f"params = json.loads({repr(kwargs_json)})\n"
            "res = mod.run(**params)\n"
            "print(json.dumps({'ok': True, 'result': res}, ensure_ascii=False, default=str))\n"
        )

        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-X", "utf8", "-c", runner_code],
                cwd=str(SANDBOX_WORKSPACE),
                env=self._build_safe_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.config.sandbox_timeout_seconds,
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0
        except subprocess.TimeoutExpired:
            return SandboxResult(
                ok=False,
                output=None,
                error=f"Skill bị dừng do vượt quá {self.config.sandbox_timeout_seconds}s.",
            )

        if proc.returncode != 0:
            return SandboxResult(
                ok=False,
                output=None,
                error=proc.stderr.strip() or proc.stdout.strip(),
                latency_ms=latency_ms,
            )

        try:
            last_line = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()][-1]
            payload = json.loads(last_line)
            return SandboxResult(
                ok=True,
                output=payload.get("result"),
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            return SandboxResult(
                ok=False,
                output=proc.stdout,
                error=f"Lỗi phân tích kết quả trả về từ Skill: {exc}",
                latency_ms=round(latency_ms, 2),
            )
