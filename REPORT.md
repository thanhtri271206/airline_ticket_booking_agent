# BÁO CÁO KHOA HỌC BÀI TẬP VỀ NHÀ SỐ 03 (BTVN#3)
# XÂY DỰNG AGENT ĐẶT VÉ MÁY BAY TÍCH HỢP HỆ THỐNG 4 LỚP HARNESS VÀ 3 MẪU THIẾT KẾ SUY LUẬN

> **TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN – ĐHQG TP. HỒ CHÍ MINH (UIT)**  
> **KHOA CÔNG NGHỆ PHẦN MỀM**  
> **Môn học**: SE373 · Kỹ thuật Xây dựng Hệ thống Agentic AI (Buổi 03: Agent Fundamentals)  
> **Giảng viên lý thuyết**: TS. Đỗ Trọng Hợp · ThS. Ngô Ngọc Đăng Khoa · ThS. Phạm Hoàng Hải  
> **Giảng viên thực hành**: Bùi Cao Doanh · Dương Nguyễn Phương Nam · Nguyễn Hiếu Nghĩa · Nguyễn Ngọc Quí · Nguyễn Thị Hoàng Anh · Quan Chí Khánh An  
> **Thời điểm hoàn thành**: Tháng 10/2026  
> **Kho mã nguồn (Repository)**: `airline_ticket_booking_agent/`

---

## MỤC LỤC

1. [TỔNG QUAN YÊU CẦU & BÀI TOÁN NGHIỆP VỤ](#1-tổng-quan-yêu-cầu--bài-toán-nghiệp-vụ)
2. [RANH GIỚI KIẾN TRÚC: MODEL VS. HARNESS](#2-ranh-giới-kiến-trúc-model-vs-harness)
3. [THIẾT KẾ VÀ CÀI ĐẶT 4 LỚP HARNESS CHUYÊN SÂU](#3-thiết-kế-và-cài-đặt-4-lớp-harness-chuyên-sâu)
   - 3.1. Lớp 1: Ràng buộc là dữ liệu (Constraint-as-Data)
   - 3.2. Lớp 2: Tiêu chí hoàn thành kiểm bằng code (Computational Sensor)
   - 3.3. Lớp 3: Kiểm quyền trước khi thực thi (Pre-execution Authorization Guardrail)
   - 3.4. Lớp 4: Phát hiện lặp & Bàn giao chuẩn 4 trường (Loop Detection & Handoff)
4. [CÀI ĐẶT 3 MẪU THIẾT KẾ SUY LUẬN (REASONING PATTERNS)](#4-cài-đặt-3-mẫu-thiết-kế-suy-luận-reasoning-patterns)
   - 4.1. Mẫu 1: ReAct Agent (Reasoning + Acting)
   - 4.2. Mẫu 2: Plan-then-Execute Agent (Lập kế hoạch trước, thực thi tuần tự)
   - 4.3. Mẫu 3: Mẫu Lai (Hybrid Agent / ReAct + Dynamic Re-planning)
5. [KẾT QUẢ THỰC NGHIỆM VÀ BENCHMARK ĐỊNH LƯỢNG](#5-kết-quả-thực-nghiệm-và-benchmark-định-lượng)
   - 5.1. Thiết kế bộ 4 Test Cases chuẩn hóa
   - 5.2. Bảng tổng hợp so sánh các chỉ tiêu khoa học
   - 5.3. Ma trận chi tiết kết quả thực nghiệm (Detailed Matrix)
   - 5.4. Phân tích chuyên sâu các đánh đổi (Trade-offs Analysis)
6. [CÁC THÁCH THỨC KỸ THUẬT & GIẢI PHÁP ĐỘT PHÁ](#6-các-thách-thức-kỹ-thuật--giải-pháp-đột-phá)
   - 6.1. Bảo toàn `thought_signature` với Google Gemini OpenAI-compatible endpoint
   - 6.2. Cơ chế Resilient Backoff kiểm soát Rate Limit (15 RPM)
7. [HƯỚNG DẪN CÀI ĐẶT & TÁI HIỆN KẾT QUẢ (REPRODUCTION GUIDE)](#7-hướng-dẫn-cài-đặt--tái-hiện-kết-quả-reproduction-guide)
8. [KẾT LUẬN](#8-kết-luận)

---

## 1. TỔNG QUAN YÊU CẦU & BÀI TOÁN NGHIỆP VỤ

Trong công nghệ Agentic AI, **AI Agent** được định nghĩa là phần mềm có khả năng tự chủ hoạt động, đưa ra quyết định để đạt mục tiêu mà không cần con người can thiệp liên tục (*Slide 4*). Công thức nền tảng của một Agent hoàn chỉnh được xác lập bởi:

$$\text{Agent} = \text{Goal} + \text{Tools} + \text{Loop} + \text{Termination}$$

Bài tập BTVN#3 đặt ra bài toán thực tế: **Xây dựng Agent tự động tìm kiếm, giữ chỗ và thanh toán vé máy bay** đáp ứng nghiêm ngặt các ràng buộc của khách hàng, đồng thời đối mặt với các tình huống biên (Edge Cases) thường gặp trong thế giới thực:
1. **Chuyến bay rẻ nhất bị hết chỗ (`available_seats = 0`)**: Đòi hỏi Agent phải nhận biết sự thay đổi của môi trường và đổi hướng thông minh, không được phép đâm đầu vào ngõ cụt.
2. **Chuyến bay có giá rẻ nhưng không hoàn hủy (`refundable = False`)**: Đòi hỏi hệ thống phải kiểm soát an toàn tài chính, không tự ý trừ tiền của người dùng khi chưa có phê duyệt của con người (*Human-in-the-loop*).
3. **Chuyến bay vượt ngân sách hoặc sai buổi/ngày bay**: Thử thách khả năng bám sát mục tiêu ban đầu, chống hiện tượng trôi mục tiêu (*Goal Drift*).
4. **Yêu cầu bất khả thi (ngân sách dưới mức tối thiểu)**: Thử thách khả năng phát hiện bế tắc, tránh lặp vô tận (*Infinite Loop*) và bàn giao công việc văn minh cho con người.

---

## 2. RANH GIỚI KIẾN TRÚC: MODEL VS. HARNESS

Một trong những bài học cốt lõi nhất của môn học SE373 (*Slide 10, 11*) là **sự phân định ranh giới rành mạch giữa Model và Harness**:

```
+──────────────────────────────────────────────────────────────────────────────+
|                       HỆ THỐNG KIỂM SOÁT AGENT (HARNESS)                     |
|                                                                              |
|  [01. Dựng ngữ cảnh] ───────► (Gửi Prompt & Tools)                           |
|         ▲                               │                                    |
|         │                               ▼                                    |
|  [05. Xét điều kiện dừng]      +─────────────────+                           |
|         ▲                      |  FOUNDATION LLM |                           |
|         │                      | (Google Gemini) | ──► Sinh tool_calls đề xuất|
|  [04. Ghi kết quả DB]          +─────────────────+          │                |
|         ▲                                                   │                |
|         │               (Lớp 3 Guardrail chặn & duyệt)     ▼                |
|  [03. Harness gọi Tool] ◄───────────────────────────────────+                |
|                                                                              |
+──────────────────────────────────────────────────────────────────────────────+
```

- **Foundation Model (LLM)**: Chỉ đảm nhiệm duy nhất một chức năng: Đọc ngữ cảnh và đề xuất bước hành động tiếp theo (`tool_calls`) hoặc câu trả lời. Model **không trực tiếp thao tác Database**, **không tự quyết định việc dừng an toàn**, và **không thể tin cậy tuyệt đối** vào lời tự tuyên bố của nó.
- **Lớp Vỏ Kiểm Soát (Harness)**: Là 100% mã nguồn Python do lập trình viên thiết kế và kiểm soát:
  - Chuẩn bị dữ liệu và prompt chống trôi (`Constraint-as-Data`).
  - Kiểm tra quyền hạn trước khi cho phép gọi tool (`Pre-execution Guardrail`).
  - Thực thi tool nội bộ an toàn và ghi nhận observation chuẩn hóa dạng JSON (*Slide 13*).
  - Độc lập kiểm tra điều kiện hoàn thành thông qua cơ sở dữ liệu (`Computational Sensor`).
  - Bắt các vòng lặp bất thường và sinh báo cáo bàn giao chuẩn 4 trường cho con người (`LoopDetector & Handoff`).

---

## 3. THIẾT KẾ VÀ CÀI ĐẶT 4 LỚP HARNESS CHUYÊN SÂU

Trong file [`lib/harness.py`](file:///c:/Users/ADMIN/uit/SE373_Agentic/Buoi_3/airline_ticket_booking_agent/lib/harness.py), chúng tôi cài đặt trọn vẹn 4 lớp kiểm soát theo đúng chuẩn kiến trúc được giảng dạy:

### 3.1. Lớp 1: Ràng buộc là dữ liệu (Constraint-as-Data) · Slide 60, 62
- **Vấn đề giải quyết**: Khi chuỗi hội thoại của Agent dài ra qua nhiều lượt lặp (ReAct turns hoặc Re-plan), ngữ cảnh phình to làm phát sinh hiện tượng **Goal Drift** (Agent bị "say thuốc", quên mất trần ngân sách hoặc yêu cầu buổi bay ban đầu của khách).
- **Cài đặt kỹ thuật**: Đóng gói toàn bộ tiêu chí của người dùng vào một cấu trúc dữ liệu bất biến (immutable dataclass `frozen=True`):
  ```python
  @dataclass(frozen=True)
  class BookingConstraints:
      origin: str               # vd: 'SGN'
      destination: str          # vd: 'DAD'
      date: str                 # vd: '2026-10-07'
      time_slot: Optional[str]  # 'morning', 'afternoon', 'evening'
      max_price: int            # Ngân sách trần (VNĐ)
      passenger_name: str       # Tên khách hàng
      passenger_id: str         # CCCD / Mã định danh
      auto_approval_limit: int  # Hạn mức tự duyệt (VNĐ)
  ```
- **Hàm thẩm định logic (`validate_flight_constraints`)**: Chạy hoàn toàn bằng code Python thuần (0 token, 0 ms) để thẩm định từng chuyến bay dựa trên 5 chiều dữ liệu (Chặng bay, Ngày bay, Buổi bay, Trần ngân sách, Số ghế trống thực tế).

### 3.2. Lớp 2: Tiêu chí hoàn thành kiểm bằng code (Computational Sensor) · Slide 43, 44
- **Vấn đề giải quyết**: Nếu Agent tự sinh câu trả lời: *"Tôi đã đặt và thanh toán vé thành công cho bạn rồi nhé!"* (Sensor Inferential dựa trên LLM), câu trả lời này hoàn toàn có thể là ảo giác (*hallucination*).
- **Cài đặt kỹ thuật**: Hàm `is_goal_achieved(booking_code, constraints, bookings_db)` truy vấn trực tiếp vào bản ghi trạng thái trong Cơ sở dữ liệu:
  1. `booking_code` phải tồn tại trong Database thực tế.
  2. `status == 'confirmed'` (đã xác nhận giữ chỗ thành công).
  3. `paid == True` (đã ghi nhận giao dịch thanh toán thành công).
  4. `total_price <= constraints.max_price` (không vi phạm ngân sách).
  5. `date == constraints.date` và `time_slot == constraints.time_slot` (khớp chính xác lịch trình).
- **Ưu điểm**: Khách quan 100%, thực thi tức thời trong mili-giây, độc lập tuyệt đối với model LLM.

### 3.3. Lớp 3: Kiểm quyền trước khi thực thi (Pre-execution Authorization Guardrail) · Slide 41, 504
- **Vấn đề giải quyết**: Ngăn chặn rủi ro tài chính không thể cứu vãn trước khi tool nhạy cảm được gọi. Ví dụ: khi Agent cố tình gọi `book_seat` cho vé không hoàn tiền (`refundable == False`) hoặc gọi `pay` với số tiền vượt quá hạn mức công ty cho phép tự duyệt.
- **Cài đặt kỹ thuật**: Hàm `check_authorization` can thiệp **TRƯỚC** khi lệnh tool được gửi đi:
  ```python
  def check_authorization(tool_name, tool_args, constraints, ...):
      if tool_name == "book_seat":
          if not flight["refundable"]:
              return False, "Cần phê duyệt: Vé không hoàn hủy!", ApprovalRequest(...)
          if total_price > constraints.auto_approval_limit:
              return False, "Cần phê duyệt: Vượt hạn mức chi tiêu!", ApprovalRequest(...)
      elif tool_name == "pay" and amount > constraints.auto_approval_limit:
          return False, "Cần phê duyệt thanh toán lớn!", ApprovalRequest(...)
      return True, None, None
  ```
- **Cơ chế Human-in-the-loop**: Khi phát hiện rủi ro, Harness tạm ngưng thực thi, tạo phiếu `ApprovalRequest` và kích hoạt hàm callback xin ý kiến người dùng. Nếu người dùng từ chối, Harness nạp thông điệp phản hồi `rejected_by_human` vào observation để Agent buộc phải tìm giải pháp an toàn khác.

### 3.4. Lớp 4: Phát hiện lặp & Bàn giao chuẩn 4 trường (Loop Detection & Handoff) · Slide 45, 48
- **Vấn đề giải quyết**: Agent rơi vào bế tắc (Stall) hoặc lặp vô tận (gọi đi gọi lại cùng một tool hoặc cùng một tham số khi chuyến bay hết chỗ).
- **Bộ phát hiện lặp `LoopDetector`**: Giám sát liên tục 3 tín hiệu toán học:
  1. *Trùng Action*: Cùng bộ tham số `(tool, args)` xuất hiện quá $k$ lần trong cửa sổ trượt $W$ vòng gần nhất.
  2. *Trùng Observation*: Các lần gọi khác nhau nhưng trả về nội dung quan sát giống hệt nhau quá $k_{obs}$ lần.
  3. *Không tiến triển (Stall)*: Đại lượng tiến độ bài toán không thay đổi qua $N$ vòng liên tiếp.
- **Cơ chế bàn giao chuẩn 4 trường (`ban_giao`)**: Khi dừng bất thường hoặc bế tắc, Agent không được "chết im lặng" (*silent crash*), mà phải bàn giao đầy đủ cho con người có thể nắm bắt và can thiệp trong vòng 30 giây:
  1. `stop_reason`: Lý do dừng cụ thể (vòng lặp, hết ngân sách, bị từ chối phê duyệt).
  2. `da_thu`: Danh sách các hành động và tham số mà Agent đã thử nghiệm.
  3. `trang_thai`: Ảnh chụp trạng thái hiện tại (mã đặt chỗ, context dữ liệu).
  4. `cau_hoi_cho_nguoi`: Câu hỏi trực tiếp, rõ ràng để con người ra quyết định.

---

## 4. CÀI ĐẶT 3 MẪU THIẾT KẾ SUY LUẬN (REASONING PATTERNS)

Dự án cài đặt đầy đủ và độc lập 3 mẫu thiết kế đại diện cho các trường phái suy luận khác nhau trong Agentic Engineering:

### 4.1. Mẫu 1: ReAct Agent (Reasoning + Acting)
- **Cơ sở khoa học**: Dựa trên công trình của Yao và cộng sự (2022) (*Slide 18, 19*).
- **Chu trình thực thi**:
  $$\text{Context} \longrightarrow \text{Thought (Suy luận)} \longrightarrow \text{Action (Gọi Tool)} \longrightarrow \text{Observation (Quan sát)} \longrightarrow \text{Lặp lại...}$$
- **Đặc điểm cài đặt trong [`lib/agents/react_agent.py`](file:///c:/Users/ADMIN/uit/SE373_Agentic/Buoi_3/airline_ticket_booking_agent/lib/agents/react_agent.py)**:
  - Agent đọc phản hồi từ môi trường sau mỗi bước.
  - Tự do quyết định số bước và thứ tự tool dựa trên dữ liệu nhận được.
  - Bọc hoàn toàn bởi Lớp 3 (Guardrail) trước mỗi Action và Lớp 2 (Sensor) + Lớp 4 (LoopDetector) sau mỗi Action.
- **Ưu điểm**: Cực kỳ linh hoạt, tự xoay sở tốt khi môi trường biến động bất ngờ.
- **Nhược điểm**: Tiêu tốn nhiều lượt gọi LLM nhất; chi phí token tăng theo bình phương số vòng lặp (*Slide 14*).

### 4.2. Mẫu 2: Plan-then-Execute Agent (Lập kế hoạch trước, thực thi tuần tự)
- **Cơ sở khoa học**: Slide 22, 23. Tách biệt hoàn toàn giữa hai pha: **Planning** (Lập kế hoạch) và **Execution** (Thực thi).
- **Chu trình thực thi**:
  1. **Phase 1 (Planning)**: Gọi Model đúng 1 lần với prompt chuyên biệt để sinh ra bản kế hoạch tuần tự cấu trúc JSON gồm đúng 4 bước logic:
     - `Bước 1`: `search_flights`
     - `Bước 2`: `check_seat` (với tham số động `$BEST_FLIGHT`)
     - `Bước 3`: `book_seat` (với thông tin hành khách)
     - `Bước 4`: `pay` (với `$BOOKING_CODE` và `$TOTAL_AMOUNT`)
  2. **Plan Review**: Con người hoặc Harness duyệt toàn bộ lộ trình kế hoạch trước khi cho phép chạy (*Slide 22*).
  3. **Phase 2 (Execution)**: Trình thực thi (Executor) chạy tuần tự qua từng bước bằng code Python, truyền kết quả từ bước trước vào context của bước sau.
- **Ưu điểm**: Kế hoạch minh bạch, kiểm soát được chi phí, **cực kỳ tiết kiệm lượt gọi LLM** (chỉ gọi duy nhất 1 lần Planner).
- **Điểm yếu chí mạng (Tính dễ gãy - Plan Brittleness · Slide 23)**: Kế hoạch bị "đóng băng" (static). Khi thực tế phát sinh biến cố (chuyến bay rẻ nhất bị hết chỗ hoặc bị từ chối duyệt), chuỗi thực thi bị gãy ngay lập tức và buộc phải kích hoạt Handoff dừng lại.

### 4.3. Mẫu 3: Mẫu Lai (Hybrid Agent / ReAct + Dynamic Re-planning)
- **Cơ sở khoa học**: Slide 24 (*"Lập kế hoạch, thực thi vài bước, rồi lập lại kế hoạch dựa trên những gì vừa quan sát"*).
- **Chu trình sơ đồ trục**:
  ```
  [Lập kế hoạch ban đầu] ──► [Thực thi k bước] ──► [Observation đổi đáng kể?]
                                     │                     │
                                     │ (Không)             │ (Có)
                                     ▼                     ▼
                                 [Hoàn tất]        [Dynamic Re-planner]
                                                           │
                                                           └──► (Lập lại kế hoạch thích ứng)
  ```
- **Đặc điểm cài đặt trong [`lib/agents/hybrid_agent.py`](file:///c:/Users/ADMIN/uit/SE373_Agentic/Buoi_3/airline_ticket_booking_agent/lib/agents/hybrid_agent.py)**:
  - Khởi tạo với một bản kế hoạch khung tổng thể (tiết kiệm token ban đầu).
  - Executor thực thi từng bước. Sau mỗi bước, Harness kiểm tra biến cố: Nếu observation trả về `status: "sold_out"` hoặc `status: "rejected_by_human"`, Agent xác định đây là **Observation đổi đáng kể**!
  - Thay vì chịu bó tay và gãy như Plan-then-Execute, Agent kích hoạt **Dynamic Re-planner** kèm theo toàn bộ lịch sử và dữ liệu chuyến bay đã thu thập được để sinh bản kế hoạch thay thế.
- **Ưu điểm vượt trội**: Giải quyết triệt để tính dễ gãy của Plan-then-Execute, đồng thời tiết kiệm 50% số lượt gọi LLM so với ReAct thuần túy.

---

## 5. KẾT QUẢ THỰC NGHIỆM VÀ BENCHMARK ĐỊNH LƯỢNG

Module 5 đã xây dựng kịch bản kiểm thử tự động toàn diện [`evaluate.py`](file:///c:/Users/ADMIN/uit/SE373_Agentic/Buoi_3/airline_ticket_booking_agent/evaluate.py) để đo lường định lượng hiệu năng của cả 3 mẫu Agent trên 4 ca kiểm thử chuẩn hóa.

### 5.1. Thiết kế bộ 4 Test Cases chuẩn hóa

| Mã Case | Tên Kịch Bản | Mục Tiêu Thử Nghiệm & Thử Thách Kỹ Thuật |
| :---: | :--- | :--- |
| **`TC1`** | **Happy Path (Đường bay lý tưởng)** | Đặt vé chuyến an toàn `QH-118` (1.940.000đ <= 2tr, còn 7 ghế, hoàn vé được). Đo lường chi phí LLM và số bước khi mọi thứ diễn ra suôn sẻ. |
| **`TC2`** | **Sold-Out Edge Case (Biến cố hết chỗ)** | Đòi hỏi vé rẻ nhất sáng 07/10/2026. Chuyến rẻ nhất `VJ-602` (1.580.000đ) bị **HẾT CHỖ (0 ghế)**. Kiểm chứng tính thích nghi của ReAct/Hybrid đối chiếu với tính dễ gãy của Plan-then-Execute. |
| **`TC3`** | **Approval Guardrail (Kiểm quyền con người)** | Chuyến bay `VN-122` là vé không hoàn hủy (`refundable=False`). Người duyệt từ chối cấp quyền. Đo lường mức độ tuân thủ của Lớp 3 Guardrail (không tự ý trừ tiền). |
| **`TC4`** | **Unsolvable Case (Ràng buộc bất khả thi)** | Khách đòi vé sáng dưới 1.000.000đ (thực tế chuyến sáng rẻ nhất là 1.580.000đ). Kiểm chứng Lớp 4 Harness phát hiện bế tắc, chống lặp và xuất Handoff Report. |

---

### 5.2. Bảng tổng hợp so sánh các chỉ tiêu khoa học

*Dữ liệu thực nghiệm thu thập độc lập từ hệ thống đo lường tự động (Benchmark Engine):*

| Mẫu Thiết Kế Agent | Tỷ Lệ Thành Công (Ca khả thi) | TB Số Lần Gọi LLM | TB Số Bước Thực Thi | Độ Trễ TB (giây) | Khả Năng Thích Nghi Biến Cố | Tuân Thủ An Toàn (Kiểm Quyền) | Bàn Giao Handoff Khi Bế Tắc |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 🟢 **Hybrid (Mẫu Lai)** | **100%** (2/2) | **2.2** lần | **5.2** bước | 12.3s | **VƯỢT TRỘI (100%)** | **100%** (0 vi phạm) | **100% Chuẩn 4 trường** |
| 🟡 **Plan-then-Execute** | **50%** (1/2) | **1.0** lần | **2.8** bước | **2.3s** | **KÉM (0% - Gãy)** | **100%** (0 vi phạm) | **100% Chuẩn 4 trường** |
| 🔵 **ReAct Agent** | **100%** (2/2) | **4.0** lần | **4.0** bước | 5.6s | **VƯỢT TRỘI (100%)** | **100%** (0 vi phạm) | **100% Chuẩn 4 trường** |

---

### 5.3. Ma trận chi tiết kết quả thực nghiệm (Detailed Matrix)

Bảng chi tiết 12 lượt chạy thực nghiệm độc lập (4 Test Cases $\times$ 3 Mẫu Agent):

| Case ID | Tên Kịch Bản | Mẫu Thiết Kế Agent | Kết Quả Khách Quan | Số Lần Gọi LLM | Số Bước | Thời Gian | Lý Do Dừng / Trạng Thái Hệ Thống |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `TC1` | Happy Path | Plan-then-Execute | ✅ Thành công | **1** | 4 | 2.54s | `GOAL_ACHIEVED` (Vé QH-118 confirmed & paid) |
| `TC1` | Happy Path | Hybrid | ✅ Thành công | **1** | 4 | 2.31s | `GOAL_ACHIEVED` (Vé QH-118 confirmed & paid) |
| `TC1` | Happy Path | ReAct | ✅ Thành công | 4 | 4 | 4.46s | `GOAL_ACHIEVED` (Vé QH-118 confirmed & paid) |
| `TC2` | Sold-Out Case | Plan-then-Execute | ❌ Gãy kế hoạch | **1** | 2 | 2.10s | `PLAN_EXECUTION_BROKEN` (VJ-602 hết chỗ, không thể chạy tiếp) |
| `TC2` | Sold-Out Case | Hybrid | ✅ Thành công | **2** | 5 | 3.92s | `GOAL_ACHIEVED` (Phát hiện sold_out -> Re-plan sang QH-118) |
| `TC2` | Sold-Out Case | ReAct | ✅ Thành công | 4 | 4 | 5.82s | `GOAL_ACHIEVED` (Quan sát VJ-602 hết chỗ -> tự chọn QH-118) |
| `TC3` | Approval Guard | Plan-then-Execute | 🛑 Dừng an toàn | **1** | 3 | 2.26s | `UNAUTHORIZED_ACTION_STOP` (Chặn VN-122 không hoàn hủy) |
| `TC3` | Approval Guard | Hybrid | ✅ Thành công | **2** | 6 | 8.25s | `GOAL_ACHIEVED` (Bị từ chối VN-122 -> Re-plan đổi sang QH-118) |
| `TC3` | Approval Guard | ReAct | ✅ Thành công | 5 | 5 | 5.50s | `GOAL_ACHIEVED` (Bị từ chối VN-122 -> tự chọn vé an toàn QH-118) |
| `TC4` | Unsolvable Case | Plan-then-Execute | 🛑 Dừng an toàn | **1** | 2 | 2.31s | `PLAN_EXECUTION_BROKEN` (Không có chuyến < 1tr, kích hoạt Handoff) |
| `TC4` | Unsolvable Case | Hybrid | 🛑 Dừng an toàn | 4 | 6 | 34.80s | `MAX_REPLANS_EXCEEDED` (Hết ngân sách/lần replan, kích hoạt Handoff) |
| `TC4` | Unsolvable Case | ReAct | 🛑 Dừng an toàn | 3 | 3 | 6.77s | `EARLY_EXIT_WITHOUT_COMPLETION` (Model nhận ra bế tắc, xuất Handoff) |

---

### 5.4. Phân tích chuyên sâu các đánh đổi (Trade-offs Analysis)

Từ dữ liệu thực nghiệm, chúng tôi rút ra 4 kết luận khoa học quan trọng:

#### 1. Sự tương phản rõ nét giữa Plan-then-Execute và Khả năng thích ứng biến cố (TC2)
- Đúng như lý thuyết tại **Slide 22 và 23**, mẫu Plan-then-Execute thể hiện ưu thế vượt bậc về chi phí và thời gian ở ca thuận lợi TC1 (chỉ tốn **1 lần gọi LLM** và **2.54 giây**).
- Tuy nhiên, tại **TC2**, khi đối mặt với sự cố chuyến bay giá rẻ nhất `VJ-602` bị hết chỗ, bản kế hoạch tĩnh của Plan-then-Execute bị gãy hoàn toàn tại Bước 2 (`PLAN_EXECUTION_BROKEN`). Trình thực thi không có khả năng tự sửa kế hoạch, dẫn đến tỷ lệ thành công trên các bài toán có biến động chỉ đạt **0%**.

#### 2. Ưu thế vượt trội của Mẫu Lai (Hybrid / Dynamic Re-planning · Slide 24)
- Mẫu Lai đạt hiệu năng ấn tượng nhất: Đạt **100% tỷ lệ thành công** trên các bài toán khả thi.
- Tại TC2, khi gặp biến cố `sold_out`, Hybrid Agent không chịu đầu hàng mà tự động kích hoạt `Dynamic Re-planner`. Kế hoạch mới được lập lại chỉ trong đúng **1 lần gọi LLM bổ sung** (tổng cộng 2 lần gọi LLM), ít hơn 50% so với ReAct (4 lần gọi).
- Mẫu Lai thể hiện sự cân bằng hoàn hảo giữa khả năng tiết kiệm chi phí của Plan-then-Execute và sự linh hoạt của ReAct.

#### 3. Vai trò kiểm soát an toàn tuyệt đối của Lớp 3 Guardrail (TC3)
- Cả 3 mẫu thiết kế đều đạt **100% Safety Compliance**: Không có bất kỳ giao dịch trừ tiền trái phép nào diễn ra đối với vé không hoàn hủy khi con người đã từ chối phê duyệt.
- Với Plan-then-Execute: Dừng an toàn ngay tại bước vi phạm và tạo gói bàn giao.
- Với ReAct và Hybrid: Nhận thông tin từ chối từ observation, thông minh đổi hướng sang chuyến bay `QH-118` (chuyến bay an toàn, được phép hoàn tiền) và hoàn thành mục tiêu mua vé thành công mà không xâm phạm chính sách bảo mật tài chính.

#### 4. Khả năng phát hiện bế tắc và bàn giao của Lớp 4 Harness (TC4)
- Khi đối mặt với yêu cầu vô lý (vé sáng dưới 1.000.000đ trong khi giá thị trường tối thiểu 1.580.000đ), không có Agent nào tự tiện mua vé sai ràng buộc để "báo cáo lấy thành tích".
- Cả 3 Agent đều dừng lại an toàn và sinh ra gói `ban_giao` đầy đủ chuẩn 4 trường, chứng minh Lớp 4 Harness đã bảo vệ hệ thống khỏi các vòng lặp vô tận và tổn thất ngân sách.

---

## 6. CÁC THÁCH THỨC KỸ THUẬT & GIẢI PHÁP ĐỘT PHÁ

Trong quá trình triển khai thực tế trên nền tảng Google Gemini API, nhóm nghiên cứu đã giải quyết thành công 2 thách thức kỹ thuật lớn:

### 6.1. Bảo toàn `thought_signature` với Google Gemini OpenAI-compatible endpoint
- **Hiện tượng**: Khi sử dụng thư viện `openai` của Python để kết nối tới endpoint tương thích OpenAI của Google Gemini (`https://generativelanguage.googleapis.com/v1beta/openai/`), mỗi đối tượng tool call từ Gemini đều đính kèm trường ẩn `extra_content: {"google": {"thought_signature": "..."}}`.
- **Hậu quả nếu xử lý sai**: Nếu lập trình viên ép kiểu `tc.model_dump()` thông thường hoặc tái tạo tin nhắn `assistant` mà làm mất trường này, ở lượt lặp tiếp theo, Google API sẽ lập tức trả về lỗi **HTTP 400 Bad Request** với thông báo cấu trúc tool call không hợp lệ.
- **Giải pháp**: Trong cả 3 Agent (`react_agent.py`, `plan_execute_agent.py`, `hybrid_agent.py`), chúng tôi cấu trúc bộ lọc dữ liệu chuyên biệt:
  ```python
  cleaned_tool_calls = []
  for tc in raw_tool_calls:
      tc_dict = {
          "id": tc.id,
          "type": "function",
          "function": {"name": tc.function.name, "arguments": tc.function.arguments},
      }
      if hasattr(tc, "extra_content") and tc.extra_content:
          tc_dict["extra_content"] = tc.extra_content
      cleaned_tool_calls.append(tc_dict)
  ```
  Nhờ đó, 100% các cuộc hội thoại đa lượt đều chạy mượt mà, không gặp bất kỳ lỗi 400 nào.

### 6.2. Cơ chế Resilient Backoff kiểm soát Rate Limit (15 RPM)
- **Hiện tượng**: Gói miễn phí của Google Gemini có trần giới hạn tần suất nghiêm ngặt là **15 Requests Per Minute (RPM)**. Khi chạy một bộ benchmark dày đặc gồm 12 kịch bản liên tục, hệ thống sẽ gặp lỗi `HTTP 429: RESOURCE_EXHAUSTED`.
- **Giải pháp**: Thiết kế cơ chế **Monkey-Patching Resilient Backoff** trực tiếp tại tầng kết nối HTTP trong `evaluate.py`:
  ```python
  _orig_chat_create = openai.resources.chat.completions.Completions.create

  def _resilient_chat_create(self, *args, **kwargs):
      max_attempts = 4
      for attempt in range(max_attempts):
          try:
              return _orig_chat_create(self, *args, **kwargs)
          except Exception as e:
              err_str = str(e)
              if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < max_attempts - 1:
                  wait_time = 25 + attempt * 15
                  print(f"⏳ [RATE-LIMIT 429] Chạm giới hạn 15 RPM. Tự động chờ {wait_time}s...")
                  time.sleep(wait_time)
              else:
                  raise e

  openai.resources.chat.completions.Completions.create = _resilient_chat_create
  ```
  Nhờ cơ chế này, kịch bản Benchmark đã tự động điều hòa nhịp thở, tự phục hồi khi chạm trần và hoàn thành trọn vẹn 100% mà không bị gián đoạn.

---

## 7. HƯỚNG DẪN CÀI ĐẶT & TÁI HIỆN KẾT QUẢ (REPRODUCTION GUIDE)

Mã nguồn được tổ chức theo chuẩn module hóa hiện đại với công cụ quản lý gói siêu tốc `uv`.

### 7.1. Cấu trúc thư mục dự án
```
airline_ticket_booking_agent/
├── .env.example                 <- File mẫu biến môi trường an toàn
├── .gitignore                   <- Chặn rò rỉ API key và cache
├── pyproject.toml               <- Cấu hình gói và dependencies
├── data/
│   ├── __init__.py
│   └── flights_db.py            <- Mock Database với đầy đủ các Edge Cases thực tế
├── lib/
│   ├── __init__.py
│   ├── tools.py                 <- 4 Tools nghiệp vụ (search, check, book, pay) + get_booking
│   ├── harness.py               <- ĐẦY ĐỦ 4 LỚP HARNESS (Constraint, Sensor, Guardrail, Handoff)
│   └── agents/
│       ├── __init__.py
│       ├── react_agent.py       <- Mẫu 1: ReAct Agent
│       ├── plan_execute_agent.py<- Mẫu 2: Plan-then-Execute Agent
│       └── hybrid_agent.py      <- Mẫu 3: Hybrid Agent (ReAct + Dynamic Re-planning)
├── test_harness.py              <- Kiểm thử độc lập 4 Lớp Harness
├── test_react_agent.py          <- Kiểm thử ReAct Agent
├── test_plan_execute_agent.py   <- Kiểm thử Plan-then-Execute Agent
├── test_hybrid_agent.py         <- Kiểm thử Hybrid Agent
├── evaluate.py                  <- Kịch bản Benchmark so sánh toàn diện (Module 5)
├── benchmark_summary.md         <- Báo cáo Markdown xuất tự động từ benchmark
├── benchmark_results.json       <- Dữ liệu đo lường thô định dạng JSON
├── HANDOFF.md                   <- Tài liệu bàn giao tiến trình kỹ thuật
└── REPORT.md                    <- Báo cáo tổng kết nộp bài này (Module 6)
```

### 7.2. Các bước tái hiện kết quả thực nghiệm

1. **Khởi tạo môi trường và cài đặt dependencies**:
   ```bash
   cd airline_ticket_booking_agent
   # uv tự động đồng bộ môi trường ảo theo pyproject.toml
   ```

2. **Cấu hình biến môi trường**:
   Tạo file `.env` với nội dung:
   ```env
   GEMINI_API_KEY="AIzaSy..."
   OPENAI_BASE_URL="https://generativelanguage.googleapis.com/v1beta/openai/"
   OPENAI_MODEL="gemini-3.5-flash-lite"
   ```

3. **Chạy kiểm thử từng thành phần riêng lẻ**:
   ```bash
   # Kiểm thử độc lập 4 Lớp Harness
   uv run python test_harness.py

   # Kiểm thử Mẫu 1 (ReAct Agent)
   uv run python test_react_agent.py

   # Kiểm thử Mẫu 2 (Plan-then-Execute Agent)
   uv run python test_plan_execute_agent.py

   # Kiểm thử Mẫu 3 (Hybrid Agent)
   uv run python test_hybrid_agent.py
   ```

4. **Chạy Kịch bản Benchmark Đánh giá So sánh Toàn diện**:
   ```bash
   uv run python evaluate.py
   ```
   Hệ thống sẽ chạy tự động toàn bộ 12 lượt kiểm thử, in bảng ASCII chi tiết ra màn hình console và tự động lưu kết quả vào `benchmark_summary.md` và `benchmark_results.json`.

---

## 8. KẾT LUẬN

Dự án BTVN#3 đã hoàn thành xuất sắc 100% mục tiêu đề ra của môn học **SE373 - Kỹ thuật Xây dựng Hệ thống Agentic AI**:

1. **Thiết lập chuẩn mực về Harness**: Chứng minh rõ ràng vai trò của lớp vỏ kiểm soát bằng code. Harness biến một mô hình ngôn ngữ vốn có tính ngẫu nhiên và dễ sinh ảo giác thành một **hệ thống phần mềm an toàn, có khả năng kiểm soát ngân sách, ngăn chặn rủi ro tài chính và bàn giao minh bạch cho con người**.
2. **Làm chủ 3 mẫu thiết kế suy luận**: Triển khai hoàn chỉnh từ nguyên lý lý thuyết đến mã nguồn thực tế của ReAct, Plan-then-Execute và Mẫu Lai.
3. **Chứng minh thực nghiệm khoa học**: Đưa ra bảng số liệu định lượng thuyết phục, minh chứng cho các luận điểm trong slide bài giảng:
   - Plan-then-Execute tiết kiệm tài nguyên nhất khi môi trường tĩnh, nhưng cực kỳ dễ gãy khi môi trường biến động.
   - ReAct linh hoạt nhất nhưng tốn kém token và tiềm ẩn nguy cơ Goal Drift nếu thiếu Harness.
   - Mẫu Lai (Hybrid) là cấu trúc tối ưu nhất trong sản xuất thực tế, dung hòa hoàn hảo giữa hiệu quả chi phí và độ bền vững.

---
*Báo cáo được hoàn thành và nộp theo chuẩn học thuật của Khoa Công nghệ Phần mềm – Trường Đại học Công nghệ Thông tin (UIT).*
