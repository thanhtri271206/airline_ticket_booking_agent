# Airline Ticket Booking Agent · Hệ Thống Agent Đặt Vé Máy Bay

Dự án cài đặt và đánh giá thực nghiệm hệ thống AI Agent đặt vé máy bay tự động, tích hợp **Hệ thống 4 Lớp Kiểm Soát (Harness)** và **3 Mẫu Thiết Kế Suy Luận (ReAct, Plan-then-Execute, Hybrid Agent)** bằng framework **LangChain**.

---

## 1. Cấu Trúc Thư Mục Dự Án

```
airline_ticket_booking_agent/
├── .env.example                 <- File mẫu cấu hình biến môi trường
├── pyproject.toml               <- Khai báo gói và cấu hình môi trường uv
├── data/
│   ├── __init__.py
│   └── flights_db.py            <- Mock Database mô phỏng chuyến bay và giao dịch đặt vé
├── lib/
│   ├── __init__.py
│   ├── tools.py                 <- 4 Tools nghiệp vụ (search, check, book, pay) + get_booking
│   ├── harness.py               <- ĐẦY ĐỦ 4 LỚP HARNESS (Constraint, Sensor, Guardrail, Handoff)
│   └── agents/
│       ├── __init__.py
│       ├── react_agent.py       <- Mẫu 1: ReAct Agent
│       ├── plan_execute_agent.py<- Mẫu 2: Plan-then-Execute Agent
│       └── hybrid_agent.py      <- Mẫu 3: Hybrid Agent (ReAct + Dynamic Re-planning)
├── test_harness.py              <- Bộ unit test kiểm tra độc lập 4 Lớp Harness
├── test_react_agent.py          <- Unit test cho ReAct Agent
├── test_plan_execute_agent.py   <- Unit test cho Plan-then-Execute Agent
├── test_hybrid_agent.py         <- Unit test cho Hybrid Agent
├── evaluate.py                  <- Kịch bản Benchmark đánh giá so sánh tự động 12 lượt
├── benchmark_summary.md         <- Báo cáo tổng kết benchmark định dạng Markdown
├── benchmark_results.json       <- Dữ liệu đo lường thô chi tiết định dạng JSON
├── HANDOFF.md                   <- Tài liệu bàn giao kỹ thuật tiến trình dự án
├── REPORT.md                    <- Báo cáo khoa học phân tích chi tiết của bài tập
└── README.md                    <- Hướng dẫn cài đặt và tái hiện thực nghiệm này
```

---

## 2. Hướng Dẫn Cài Đặt & Chạy Hệ Thống

Dự án sử dụng trình quản lý gói hiện đại **uv** của Python để đảm bảo tốc độ cài đặt tối ưu và môi trường cô lập tuyệt đối.

### Bước 1: Khởi tạo môi trường ảo và cài đặt thư viện

Tại thư mục gốc của dự án `airline_ticket_booking_agent`, thực thi lệnh sau:

```bash
uv sync
```

Công cụ `uv` sẽ tự động tạo môi trường ảo `.venv` và đồng bộ toàn bộ các thư viện khai báo trong `pyproject.toml` (bao gồm `langchain`, `langchain-openai`, `langchain-core`, `pydantic`, `python-dotenv`).

### Bước 2: Thiết lập biến môi trường

Sao chép file cấu hình mẫu `.env.example` thành `.env`:

```bash
cp .env.example .env
```

Mở file `.env` và cung cấp cấu hình kết nối API phù hợp:

```env
# API Key của nhà cung cấp LLM
GEMINI_API_KEY="your_api_key_here"

# Endpoint tương thích chuẩn OpenAI (OpenAI-compatible Base URL)
# Ví dụ khi chạy qua 9Router / OpenClaw cục bộ:
OPENAI_BASE_URL="http://localhost:20128/v1"

# Hoặc khi kết nối trực tiếp tới Google AI Studio v1beta:
# OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"

# Tên mô hình LLM sử dụng
OPENAI_MODEL="gemini-3.6-flash-medium"
```

---

## 3. Chạy Kiểm Thử Độc Lập (Unit Tests)

Trước khi chạy toàn bộ hệ thống đánh giá so sánh, bạn có thể kiểm thử độc lập từng thành phần kiến trúc:

```bash
# 1. Kiểm thử độc lập 4 Lớp Harness (Constraint, Sensor, Guardrail, LoopDetector & Handoff)
uv run python test_harness.py

# 2. Kiểm thử Mẫu 1: ReAct Agent
uv run python test_react_agent.py

# 3. Kiểm thử Mẫu 2: Plan-then-Execute Agent
uv run python test_plan_execute_agent.py

# 4. Kiểm thử Mẫu 3: Hybrid Agent
uv run python test_hybrid_agent.py
```

---

## 4. Chạy Kịch Bản Benchmark So Sánh Toàn Diện

Để tái hiện lại toàn bộ kết quả đo lường định lượng giữa 3 mẫu thiết kế Agent trên 4 ca kiểm thử chuẩn hóa (tổng cộng 12 lượt chạy độc lập), chạy lệnh:

```bash
uv run python evaluate.py
```

### Quá trình thực thi tự động:
1. Hệ thống tự động thiết lập lại cơ sở dữ liệu (`reset_mock_db`) trước mỗi lượt chạy để bảo đảm tính cô lập.
2. Bộ điều phối `BenchmarkEngine` tuần tự đánh giá từng Agent trên từng Test Case (`TC1` Happy Path, `TC2` Sold-Out, `TC3` Approval Guardrail, `TC4` Unsolvable).
3. Cơ chế `Resilient Rate-Limit Backoff` được tự động kích hoạt để điều hòa tần suất gọi API, chống nghẽn mã lỗi 429.
4. Sau khi hoàn tất 12 lượt chạy, hệ thống in bảng ma trận kết quả định lượng chi tiết lên màn hình terminal, đồng thời tự động xuất dữ liệu ra hai file:
   - `benchmark_summary.md`: Báo cáo bảng biểu tổng hợp định dạng Markdown.
   - `benchmark_results.json`: Dữ liệu đo lường thô chi tiết (thời gian, số lần gọi LLM, số bước, lý do dừng).

Chi tiết phân tích lý thuyết, ranh giới kiến trúc và đánh giá chuyên sâu có tại file [REPORT.md](REPORT.md).
