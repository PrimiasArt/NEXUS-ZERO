# 🧠 Project NEXUS-ZERO
**Hệ Thống Nhận Thức Tự Tiến Hóa Từ Con Số 0 (Self-Evolving Tri-Tier Cognitive Architecture)**

NEXUS-ZERO là một kiến trúc AI tự học và tự rèn kỹ năng mới được thiết kế đặc biệt cho môi trường **hạn chế phần cứng (CPU/RAM thấp)** và **ngân sách Gemini API hạn hẹp**, đồng thời cộng sinh trực tiếp với **Gemini 4 Argon Ultra + MCP** trong Antigravity.

---

## 🚀 Cách Sử Dụng Nhanh

Sử dụng Python 3.14 (`C:\Users\nguye\.local\bin\python3.14.exe` hoặc `uv run`):

```powershell
# 1. Xem trạng thái não bộ, số lượng kỹ năng, đồ thị tri thức và hạn mức Token
C:\Users\nguye\.local\bin\python3.14.exe F:\Project\NEXUS-ZERO\main.py status

# 2. Giao nhiệm vụ cho NEXUS-ZERO (Tự động ưu tiên Tầng 0 tốn 0 token!)
C:\Users\nguye\.local\bin\python3.14.exe F:\Project\NEXUS-ZERO\main.py ask "Phân tích thống kê dãy số [15, 22, 18, 25, 30, 19, 210]"

# 3. Xem danh sách các Kỹ năng Python mà AI đã tự học và kiểm duyệt
C:\Users\nguye\.local\bin\python3.14.exe F:\Project\NEXUS-ZERO\main.py skills

# 4. Xem Đồ thị Tri thức (Semantic Knowledge Graph) & Quy tắc Vàng
C:\Users\nguye\.local\bin\python3.14.exe F:\Project\NEXUS-ZERO\main.py graph --query "thống kê"

# 5. Chạy chu kỳ Ngủ & Đúc kết ký ức (Ebbinghaus Decay + Consolidation)
C:\Users\nguye\.local\bin\python3.14.exe F:\Project\NEXUS-ZERO\main.py sleep
```

---

## 🔑 Kích Hoạt Tầng 1 (`gemini-3.5-flash-lite`) Khi Cần Chạy Độc Lập

Mặc định, NEXUS-ZERO vẫn hoạt động hoàn hảo với **0 API Key** nhờ **Tầng 0 (Local Verified Skills)** và **Tầng 2 (Cầu nối Giáo viên Argon Ultra)**.
Nếu bạn muốn bật thêm **Tầng 1 (`gemini-3.5-flash-lite`)** để AI tự viết Skill ngầm khi không mở Antigravity:

```powershell
$env:GEMINI_API_KEY="AIzaSy..."
$env:NEXUS_DAILY_TOKEN_LIMIT="40000"  # Khóa trần 40,000 tokens/ngày
```
*(Hệ thống `TokenBudgetGovernor` trong `core/budget.py` sẽ tự động lưu cache mọi câu trả lời vào SQLite và ngắt kết nối ngay khi chạm trần ngân sách ngày).*
