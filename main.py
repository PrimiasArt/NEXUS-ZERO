"""
NEXUS-ZERO CLI & Interactive Cognitive Dashboard.
Usage:
  python main.py status
  python main.py ask "<câu hỏi hoặc nhiệm vụ>"
  python main.py sync-teacher
  python main.py sleep
  python main.py skills
  python main.py graph
"""

from __future__ import annotations
import argparse
import json
import sys

from core.kernel import NexusZeroKernel


def _ensure_utf8_console() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def print_banner() -> None:
    print("=" * 72)
    print(" 🧠 NEXUS-ZERO | HỆ THỐNG NHẬN THỨC TỰ TIẾN HÓA TỪ CON SỐ 0")
    print("    Tầng 0: Local Reflex & Verified Skills (0 Token, AST Sandbox)")
    print("    Tầng 1: Gemini 3.5 Flash-Lite (Strict Token Budget Governor)")
    print("    Tầng 2: Symbiotic Teacher Bridge (Gemini 4 Argon Ultra + MCP)")
    print("=" * 72)


def cmd_status(kernel: NexusZeroKernel) -> None:
    print_banner()
    status = kernel.get_full_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))


def cmd_ask(kernel: NexusZeroKernel, task: str) -> None:
    print_banner()
    print(f"🎯 Nhiệm vụ đầu vào: {task}\n" + "-" * 72)
    res = kernel.handle_task(task)
    print(f"⚡ Tầng xử lý     : {res.tier_used}")
    print(f"🛠️  Kỹ năng sử dụng : {res.skill_used or '(Chưa có)'}")
    print(f"🪙 Token tiêu tốn  : {res.tokens_spent} tokens")
    print(f"⏱️  Độ trễ thực thi : {res.latency_ms:.2f} ms")
    print(f"💭 Tự phản tư      : {res.reflection}")
    print("-" * 72)
    print("📤 KẾT QUẢ:")
    print(res.answer)
    print("=" * 72)


def cmd_sync_teacher(kernel: NexusZeroKernel) -> None:
    print_banner()
    report = kernel.bridge.ingest_teacher_lessons()
    print("🔄 KẾT QUẢ ĐỒNG BỘ BÀI GIẢNG TỪ GEMINI 4 ARGON ULTRA:")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_sleep(kernel: NexusZeroKernel) -> None:
    print_banner()
    report = kernel.evolution.run_sleep_cycle()
    print("🌙 CHU KỲ NGỦ & ĐÚC KẾT TRÍ NHỚ (EBBINGHAUS CONSOLIDATION):")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_skills(kernel: NexusZeroKernel) -> None:
    print_banner()
    skills = kernel.memory.list_skills()
    print(f"🧰 KHO KỸ NĂNG ĐÃ KIỂM DUYỆT ({len(skills)} skills):")
    for idx, s in enumerate(skills, 1):
        print(
            f"  {idx}. [{s.skill_name}] (Thành công: {s.success_count}, Lỗi: {s.fail_count}, "
            f"Độ trễ TB: {s.avg_latency_ms:.1f}ms)\n"
            f"     Mô tả   : {s.description}\n"
            f"     Từ khóa : {', '.join(s.trigger_keywords)}"
        )


def cmd_graph(kernel: NexusZeroKernel, query: str) -> None:
    print_banner()
    ctx = kernel.memory.query_knowledge_context(query, limit=12)
    print("🕸️ ĐỒ THỊ TRI THỨC & QUY TẮC VÀNG (SEMANTIC MEMORY):")
    print(json.dumps(ctx, ensure_ascii=False, indent=2))


def main() -> None:
    _ensure_utf8_console()
    parser = argparse.ArgumentParser(
        description="Project NEXUS-ZERO Cognitive Engine CLI"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Xem trạng thái não bộ, kho kỹ năng và ngân sách token")

    ask_p = sub.add_parser("ask", help="Giao nhiệm vụ cho NEXUS-ZERO")
    ask_p.add_argument("task", type=str, help="Nội dung câu hỏi hoặc nhiệm vụ")

    sub.add_parser(
        "sync-teacher",
        help="Nạp bài giảng & kỹ năng mới từ Giáo viên Gemini 4 Argon Ultra",
    )
    sub.add_parser(
        "sleep",
        help="Chạy chu kỳ Ngủ & Đúc kết ký ức (cắt tỉa nút yếu, đúc kết quy tắc)",
    )
    sub.add_parser("skills", help="Liệt kê các kỹ năng Python đã tự học ở Tầng 0")

    graph_p = sub.add_parser("graph", help="Truy vấn Đồ thị Tri thức & Quy tắc")
    graph_p.add_argument("--query", type=str, default="", help="Từ khóa tìm kiếm")

    args = parser.parse_args()
    kernel = NexusZeroKernel()

    if args.command == "status":
        cmd_status(kernel)
    elif args.command == "ask":
        cmd_ask(kernel, args.task)
    elif args.command == "sync-teacher":
        cmd_sync_teacher(kernel)
    elif args.command == "sleep":
        cmd_sleep(kernel)
    elif args.command == "skills":
        cmd_skills(kernel)
    elif args.command == "graph":
        cmd_graph(kernel, args.query)
    else:
        cmd_status(kernel)


if __name__ == "__main__":
    main()
