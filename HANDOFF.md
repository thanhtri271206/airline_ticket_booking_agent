# TÀI LIỆU BÀN GIAO TIẾN TRÌNH DỰ ÁN (AGENT HANDOFF DOCUMENT)

> **Môn học**: SE373 · Kỹ thuật xây dựng hệ thống Agentic AI (Buổi 03: Agent Fundamentals) - UIT  
> **Bài tập**: BTVN#3 · Dựng Agent đặt vé máy bay tích hợp Lớp Harness và 3 Mẫu thiết kế suy luận  
> **Thời điểm bàn giao**: 2026-10-01 20:22:00  
> **Trạng thái Git**: Đã hoàn thành 4 nhánh chức năng tương ứng 4 Module đầu tiên.

---

## 1. TỔNG QUAN YÊU CẦU ĐỀ BÀI (BTVN#3)

Theo file yêu cầu gốc [`yeu_cau_btvn.txt`](file:///c:/Users/ADMIN/uit/SE373_Agentic/Buoi_3/yeu_cau_btvn.txt) và Slide bài giảng [`slides_extracted.txt`](file:///c:/Users/ADMIN/uit/SE373_Agentic/Buoi_3/slides_extracted.txt):
1. **Cài đặt đủ 4 lớp Harness**:
   - Ràng buộc là dữ liệu (`Constraint-as-Data` - chống trôi mục tiêu).
   - Tiêu chí hoàn thành kiểm bằng code (`Computational Sensor` - kiểm tra chéo DB khách quan).
   - Kiểm quyền (`Pre-execution Authorization Guardrail` - chặn trước khi gọi tool nếu có rủi ro).
   - Bàn giao (`Handoff` - bắt lặp vòng `LoopDetector` và bàn giao chuẩn 4 trường cho con người).
2. **Cài đặt Agent với 3 mẫu thiết kế**:
   - Mẫu 1: **ReAct** (Reasoning + Acting).
   - Mẫu 2: **Plan-then-Execute** (Lập kế hoạch trước rồi thực thi tuần tự).
   - Mẫu 3: **Lai (Hybrid)** (Lập kế hoạch + Thực thi ReAct + Tự động tái lập kế hoạch `Dynamic Re-planning` khi có biến cố).
3. **Đánh giá hiệu quả của Agent với 3 mẫu thiết kế khác nhau**:
   - Đo lường và so sánh qua các chỉ số khoa học: Success Rate, Steps, LLM Calls, Safety Compliance, Adaptation.
   - Nộp file code Python kèm theo Báo cáo giải thích chi tiết.

---

## 2. HIỆN TRẠNG DỰ ÁN (ĐÃ HOÀN THÀNH 100% CÁC MODULE 1 - 4)

### A. Lịch sử Git Branches & Commits:
| Nhánh Git | Module chức năng | Commit Hash & Thông điệp | Trạng thái |
| :--- | :--- | :--- | :--- |
| `main` | Khởi tạo dự án & Mock Data | `6d382a1` `chore: initial commit with mock database, flight tools and test script` | ✅ Đã hoàn thành |
| `feat/module-1-harness` | **Module 1**: 4 Lớp Harness | `7a81480` `feat(harness): implement 4-layer agent harness with unit tests` | ✅ Đã test & commit |
| `feat/module-2-react-agent` | **Module 2**: ReAct Agent | `6f7a7c0` `feat(agent): implement ReAct agent with 4-layer harness and OpenAI compatibility` | ✅ Đã test & commit |
| `feat/module-3-plan-execute-agent` | **Module 3**: Plan-then-Execute | `95515db` `feat(agent): implement Plan-then-Execute agent with plan review and fragility handling` | ✅ Đã test & commit |
| `feat/module-4-hybrid-agent` | **Module 4**: Mẫu Lai (Hybrid) | `52ff16d` `feat(agent): implement Hybrid agent with dynamic re-planning on significant state change` | ✅ Đã test & commit |

### B. Cấu trúc mã nguồn hiện tại:
```
airline_ticket_booking_agent/
├── .env                         <- Chứa GEMINI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL (ĐÃ IGNORE)
├── .env.example                 <- File mẫu biến môi trường an toàn
├── .gitignore                   <- Đã cấu hình chặn .env, .venv, __pycache__
├── pyproject.toml               <- Khai báo dependencies
├── data/
│   ├── __init__.py
│   └── flights_db.py            <- Mock Database với các edge cases: VJ-602 hết chỗ, VN-122 không hoàn, QH-118 hợp lệ
├── lib/
│   ├── __init__.py
│   ├── tools.py                 <- 4 tool nghiệp vụ (search_flights, check_seat, book_seat, pay) + get_booking
│   ├── harness.py               <- ĐẦY ĐỦ 4 LỚP HARNESS (BookingConstraints, is_goal_achieved, check_authorization, LoopDetector, ban_giao)
│   └── agents/
│       ├── __init__.py
│       ├── react_agent.py       <- Mẫu 1: ReActAgent hoàn chỉnh
│       ├── plan_execute_agent.py<- Mẫu 2: PlanExecuteAgent hoàn chỉnh
│       └── hybrid_agent.py      <- Mẫu 3: HybridAgent hoàn chỉnh với Dynamic Re-planning
├── test_tools.py                <- Test bộ tool ban đầu
├── test_harness.py              <- Test độc lập 4 lớp Harness (uv run python test_harness.py)
├── test_react_agent.py          <- Test ReAct Agent (uv run python test_react_agent.py)
├── test_plan_execute_agent.py   <- Test Plan-then-Execute Agent (uv run python test_plan_execute_agent.py)
├── test_hybrid_agent.py         <- Test Hybrid Agent (uv run python test_hybrid_agent.py)
└── HANDOFF.md                   <- File bàn giao này
```

---

## 3. CÁC ĐẶC TÍNH KỸ THUẬT VÀ PHÁT HIỆN QUAN TRỌNG

1. **Môi trường chạy lệnh**:
   - Luôn sử dụng `uv run python <ten_file.py>` theo chỉ dẫn của người dùng.
2. **Cơ chế Google Gemini OpenAI-compatible Endpoint**:
   - Model: `gemini-3.5-flash-lite` hoặc các model trong `.env`.
   - Endpoint: `https://generativelanguage.googleapis.com/v1beta/openai/`.
   - **Lưu ý sống còn đã giải quyết**: Khi dùng OpenAI client với Google Gemini, mỗi lượt tool call có chứa `thought_signature` trong `extra_content: {"google": {"thought_signature": "..."}}`. Trong cả 3 Agent (`react_agent.py`, `plan_execute_agent.py`, `hybrid_agent.py`), chúng ta đã cấu trúc lịch sử tin nhắn bảo toàn 100% `thought_signature`, đảm bảo không bao giờ bị lỗi 400 Bad Request của Google.
3. **Quy tắc làm việc với Người Dùng**:
   - Luôn tạo nhánh git riêng biệt cho từng module (`feat/...`).
   - Có hệ thống in log trực quan chi tiết thể hiện từng chặng thực thi của Agent (`THOUGHT`, `ACTION`, `PRE-CHECK`, `OBSERVATION`, `POST-CHECK`).
   - Khi hoàn thành module: **Rerun test để in log đầy đủ ra màn hình console**, sau đó giải thích chi tiết code từ **ngữ nghĩa** (*semantics*) đến **cú pháp** (*syntax*). Chỉ commit khi người dùng xác nhận hài lòng.

---

## 4. NHIỆM VỤ TIẾP THEO CHO AGENT Ở PHIÊN LÀM VIỆC MỚI

Bạn (Agent kế tiếp) cần tiến hành triển khai **Module 5** và **Module 6**:

### Bước 1: Tạo nhánh Git cho Module 5:
```bash
git checkout -b feat/module-5-evaluation
```

### Bước 2: Xây dựng Module 5: Kịch bản Đánh giá & Benchmark So sánh (`evaluate.py`)
Tạo file `evaluate.py` chạy benchmark tự động cả 3 Agent (`ReActAgent`, `PlanExecuteAgent`, `HybridAgent`) trên 4 Test Cases chuẩn hóa:
1. **TC1: Happy Path**: Tìm vé sáng 07/10/2026, chọn chuyến an toàn hoàn được tiền `QH-118` (ngân sách 2tr).
   - Đo lường số lượt gọi LLM, số bước lặp, chi phí token khi chạy trơn tru.
2. **TC2: Sold-Out Edge Case (Biến cố hết chỗ)**: Tìm vé rẻ nhất sáng 07/10/2026. Chuyến rẻ nhất `VJ-602` bị HẾT CHỖ.
   - Thể hiện sự tương phản rõ nét:
     * `PlanExecuteAgent`: Bị gãy kế hoạch tĩnh, thất bại (`Success = False`).
     * `ReActAgent`: Tự do đổi sang chuyến khác (`Success = True`).
     * `HybridAgent`: Kích hoạt Re-planning, lập lại kế hoạch thích ứng (`Success = True`).
3. **TC3: Approval Edge Case (Kiểm quyền)**: Chuyến `VN-122` là vé không hoàn hủy (`refundable == False`).
   - Kiểm tra khả năng kiểm soát an toàn của Lớp 3 Harness: Bắt buộc dừng lại xin phê duyệt, không tự ý trừ tiền.
4. **TC4: Unsolvable Case (Bế tắc)**: Khách đòi vé dưới 1.000.000đ buổi sáng (không có chuyến nào thỏa mãn).
   - Kiểm tra khả năng phát hiện bế tắc của Lớp 4 Harness (`LoopDetector` / `Budget Limit`) và xuất báo cáo bàn giao chuẩn 4 trường.

`evaluate.py` cần in ra bảng tổng kết Markdown / ASCII so sánh định lượng:
- **Tỷ lệ thành công (Success Rate %)**
- **Số lần gọi LLM (Average Model Calls)**
- **Số bước thực thi (Average Turns / Steps)**
- **Khả năng thích nghi sự cố (Adaptability / Error Recovery)**
- **Mức độ an toàn (Safety Compliance - Vi phạm kiểm quyền: 0%)**

### Bước 3: Rerun test & In log đầy đủ, viết báo cáo chi tiết Module 5, commit git.

### Bước 4: Soạn thảo Báo cáo Hoàn chỉnh nộp bài (`REPORT.md`)
Tổng hợp toàn bộ kiến thức môn học SE373, phân tích 4 lớp Harness, 3 mẫu thiết kế và bảng số liệu thực nghiệm từ Module 5 thành một báo cáo khoa học bài bản, chuẩn format UIT để bạn sinh viên nộp cho giảng viên.

---
*Tài liệu bàn giao này đã được kiểm chứng và sẵn sàng cho phiên làm việc tiếp theo.*
