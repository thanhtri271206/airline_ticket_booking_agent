# BÁO CÁO KHOA HỌC BÀI TẬP VỀ NHÀ SỐ 03 (BTVN#3)
# XÂY DỰNG HỆ THỐNG AGENT ĐẶT VÉ MÁY BAY TÍCH HỢP 4 LỚP HARNESS VÀ SO SÁNH THỰC NGHIỆM 3 MẪU THIẾT KẾ SUY LUẬN BẰNG LANGCHAIN

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
2. [KIẾN TRÚC HỆ THỐNG VÀ LUỒNG VẬN HÀNH TỔNG THỂ](#2-kiến-trúc-hệ-thống-và-luồng-vận-hành-tổng-thể)
3. [THIẾT KẾ VÀ CÀI ĐẶT 4 LỚP HARNESS CHUYÊN SÂU](#3-thiết-kế-và-cài-đặt-4-lớp-harness-chuyên-sâu)
   - 3.1. Lớp 1: Ràng buộc là dữ liệu bất biến (Constraint-as-Data)
   - 3.2. Lớp 2: Tiêu chí hoàn thành kiểm chứng bằng code (Computational Sensor)
   - 3.3. Lớp 3: Kiểm quyền trước khi thực thi (Pre-execution Authorization Guardrail)
   - 3.4. Lớp 4: Phát hiện lặp & Bàn giao chuẩn hóa (Loop Detection & Handoff)
4. [CÀI ĐẶT 3 MẪU THIẾT KẾ SUY LUẬN TRÊN LANGCHAIN](#4-cài-đặt-3-mẫu-thiết-kế-suy-luận-trên-langchain)
   - 4.1. Mẫu 1: ReAct Agent (Reasoning + Acting)
   - 4.2. Mẫu 2: Plan-then-Execute Agent (Kế hoạch tĩnh, thực thi tuần tự)
   - 4.3. Mẫu 3: Hybrid Agent (Lai: Kế hoạch khung + Dynamic Re-planning)
5. [HỆ THỐNG ĐÁNH GIÁ THỰC NGHIỆM VÀ BENCHMARK ĐỊNH LƯỢNG](#5-hệ-thống-đánh-giá-thực-nghiệm-và-benchmark-định-lượng)
   - 5.1. Định nghĩa chuẩn hóa các chỉ số đo lường (Evaluation Metrics)
   - 5.2. Thiết kế bộ 4 Test Cases chuẩn hóa bao quát các tình huống biên
   - 5.3. Bảng tổng hợp so sánh các chỉ số định lượng
   - 5.4. Ma trận chi tiết kết quả thực nghiệm 12 lượt chạy
   - 5.5. Phân tích chuyên sâu các đánh đổi kỹ thuật (Trade-offs Analysis)
6. [KẾT LUẬN & GIỚI HẠN THỰC NGHIỆM](#6-kết-luận--giới-hạn-thực-nghiệm)

---

## 1. TỔNG QUAN YÊU CẦU & BÀI TOÁN NGHIỆP VỤ

Trong kỹ thuật phần mềm Agentic AI, một AI Agent được định nghĩa là một thực thể phần mềm có khả năng tự chủ hoạt động, tiếp nhận mục tiêu cấp cao từ người dùng, tương tác với môi trường thông qua các công cụ lập trình và liên tục lặp lại chu trình suy luận để giải quyết bài toán mà không đòi hỏi sự can thiệp vi mô liên tục của con người. Về mặt toán học và cấu trúc, một Agent hoàn chỉnh được mô hình hóa bởi bốn thành tố nền tảng:

$$\text{Agent} = \text{Goal} + \text{Tools} + \text{Loop} + \text{Termination}$$

Trong đó, Goal đại diện cho yêu cầu nghiệp vụ cần đạt được xác lập cùng các ràng buộc dữ liệu cụ thể. Tools là tập hợp các giao diện lập trình ứng dụng cho phép Agent truy vấn cơ sở dữ liệu, giữ chỗ và khởi tạo thanh toán. Loop là vòng lặp khép kín tiếp nhận thông tin quan sát từ môi trường, suy luận hành động kế tiếp và thực thi công cụ. Cuối cùng, Termination là cơ chế dừng xác định dựa trên tiêu chí hoàn thành khách quan hoặc điều kiện cắt lỗ an toàn khi phát hiện bế tắc.

Bài tập BTVN#3 đặt ra bài toán thực tế là xây dựng hệ thống Agent tự động tìm kiếm, giữ chỗ và thanh toán vé máy bay phục vụ chuyến công tác của doanh nghiệp. Khác với các kịch bản trình diễn đơn giản trên môi trường giả lập lý tưởng, một hệ thống nghiệp vụ thực tế luôn phải đối mặt với nhiều tình huống biên phức tạp. Điển hình trong số đó là biến cố cạn kiệt tài nguyên khi chuyến bay có mức giá rẻ nhất bị hết chỗ (`available_seats = 0`), đòi hỏi Agent phải nhận biết sự thay đổi của môi trường để đổi hướng linh hoạt thay vì đâm đầu vào ngõ cụt. Bên cạnh đó, hệ thống phải kiểm soát an toàn tài chính nghiêm ngặt khi chuyến bay không được phép hoàn hủy (`refundable = False`) hoặc giá vé vượt trần ngân sách cho phép tự duyệt của tổ chức, bắt buộc phải tạm dừng để xin phê duyệt của con người (*Human-in-the-loop*). Ngoài ra, khi ngữ cảnh hội thoại kéo dài qua nhiều lượt suy luận, mô hình ngôn ngữ lớn rất dễ gặp hiện tượng trôi mục tiêu (*Goal Drift*), dẫn tới nguy cơ đặt vé sai ngày bay hoặc vượt quá hạn mức ngân sách. Cuối cùng, khi người dùng đưa ra một yêu cầu bất khả thi về mặt kinh tế, hệ thống phải có khả năng tự nhận biết bài toán vô nghiệm, chủ động cắt lỗ để tránh vòng lặp vô tận và xuất báo cáo bàn giao minh bạch cho con người tiếp quản.

---

## 2. KIẾN TRÚC HỆ THỐNG VÀ LUỒNG VẬN HÀNH TỔNG THỂ

Nguyên lý cốt lõi của hệ thống là sự phân định ranh giới độc lập giữa Foundation Model và Lớp vỏ kiểm soát (Harness). Trong khi Foundation Model (trên nền tảng LangChain) chỉ đảm nhiệm vai trò suy luận ngôn ngữ xác suất để đề xuất công cụ (`tool_calls`), thì Harness là lớp mã nguồn Python tất định bao bọc toàn bộ chu trình sống của Agent nhằm ngăn chặn ảo giác, bảo đảm tính bất biến của dữ liệu và loại trừ rủi ro tài chính.

![Kiến trúc hệ thống và luồng kiểm soát 4 lớp Harness](assets/architecture_flow.png)

*Hình 1: Sơ đồ kiến trúc tổng thể và luồng vận hành khép kín của hệ thống Agent tích hợp 4 Lớp Harness.*

Toàn bộ chu trình vận hành trên sơ đồ tạo thành một quy trình khép kín với các chốt chặn nghiêm ngặt. Khi tiếp nhận yêu cầu từ người dùng, Lớp 1 (Constraint-as-Data) trước tiên đóng gói ngân sách và tiêu chí bay vào cấu trúc dữ liệu bất biến trước khi nạp vào LLM. Nếu mô hình đề xuất gọi công cụ, lệnh này bắt buộc phải đi qua chốt chặn Lớp 3 (Pre-execution Authorization Guardrail) để thẩm định quyền hạn (chính sách hoàn vé và trần tự duyệt chi tiêu), chuyển sang xin ý kiến con người nếu vượt quyền. Sau khi công cụ thực thi trên cơ sở dữ liệu nội bộ, Lớp 4 (Loop Detection) lập tức rà soát nguy cơ lặp hoặc dậm chân tại chỗ để xuất gói bàn giao chuẩn 4 trường (Handoff Report) cắt lỗ kịp thời. Ở nhánh vận hành bình thường, Lớp 2 (Computational Sensor) độc lập truy vấn trực tiếp cơ sở dữ liệu để xác nhận vé đã được xác nhận và thanh toán thành công (`confirmed` và `paid`), từ đó công nhận hoàn thành nhiệm vụ (Goal Achieved) hoặc đưa kết quả quan sát ngược lại lịch sử để mô hình tiếp tục vòng lặp suy luận kế tiếp.

---

## 3. THIẾT KẾ VÀ CÀI ĐẶT 4 LỚP HARNESS CHUYÊN SÂU

Trong module `lib/harness.py`, hệ thống hiện thực hóa đầy đủ bốn lớp bảo vệ theo mô hình kiểm soát đa tầng nhằm triệt tiêu các rủi ro vận hành của mô hình ngôn ngữ lớn.

### 3.1. Lớp 1: Ràng buộc là dữ liệu bất biến (Constraint-as-Data)

Khi chuỗi hội thoại của Agent kéo dài qua nhiều lượt suy luận, dung lượng ngữ cảnh phình to thường khiến mô hình ngôn ngữ lớn bị phân tán sự chú ý, dẫn tới hiện tượng trôi mục tiêu (Goal Drift). Khi đó, Agent có xu hướng bỏ quên các điều kiện tiên quyết như trần ngân sách hoặc khung giờ bay mong muốn của khách hàng.

Để loại bỏ rủi ro này, toàn bộ tiêu chí của người dùng được đóng gói vào một cấu trúc dữ liệu bất biến bằng cách sử dụng `@dataclass(frozen=True)` trong Python. Đối tượng `BookingConstraints` chứa các trường thông tin cốt lõi bao gồm điểm khởi hành, điểm đến, ngày bay, khung giờ bay, giá vé trần, thông tin khách hàng và hạn mức tự động duyệt chi phí. Cấu trúc bất biến này ngăn chặn hoàn toàn việc mô hình ngôn ngữ hoặc bất kỳ hàm nội bộ nào tự ý ghi đè hay thay đổi các điều kiện cốt lõi trong suốt quá trình chạy.

```python
@dataclass(frozen=True)
class BookingConstraints:
    origin: str
    destination: str
    date: str
    time_slot: Optional[str]
    max_price: int
    passenger_name: str
    passenger_id: str
    auto_approval_limit: int
```

Đi kèm với cấu trúc dữ liệu này là hàm logic kiểm định tiền thực thi `validate_flight_constraints`. Hàm này hoạt động hoàn toàn bằng mã nguồn Python thuần túy mà không tiêu tốn bất kỳ token nào, chịu trách nhiệm đối soát chuyến bay tiềm năng trên cả năm chiều thông tin gồm hành trình, ngày bay, buổi bay, trần ngân sách và số ghế trống thực tế. Mọi dữ liệu định danh khách hàng trong mock database đều là thông tin giả lập nhằm đảm bảo an toàn dữ liệu trong môi trường thử nghiệm.

### 3.2. Lớp 2: Tiêu chí hoàn thành kiểm chứng bằng code (Computational Sensor)

Một trong những sai lầm phổ biến trong các hệ thống Agent sơ khai là sử dụng cơ chế cảm biến suy diễn (Inferential Sensor), tức là hoàn toàn tin tưởng vào câu trả lời tự tuyên bố của LLM để kết luận tác vụ đã hoàn thành. Trong thực tế, mô hình có thể gặp ảo giác và khẳng định đã mua vé thành công dù giao dịch thanh toán chưa từng được kích hoạt.

Hệ thống giải quyết triệt để vấn đề này bằng việc xây dựng cảm biến điện toán khách quan (Computational Sensor) thông qua hàm `is_goal_achieved`. Hàm này bỏ qua toàn bộ văn bản phản hồi của mô hình và tiến hành truy vấn trực tiếp vào bảng ghi trạng thái của cơ sở dữ liệu nghiệp vụ để kiểm tra năm điều kiện tiên quyết: mã đặt chỗ phải thực sự tồn tại, trạng thái vé phải chuyển sang `confirmed`, giao dịch tài chính phải được ghi nhận `paid == True`, tổng chi phí thực tế không vượt trần ngân sách của khách hàng, và thời gian bay phải trùng khớp hoàn toàn với ràng buộc ban đầu.

Đặc biệt, hệ thống phân biệt rạch ròi giữa hai trạng thái nghiệp vụ: trạng thái giữ chỗ (`booking_confirmed`) và trạng thái hoàn tất thanh toán (`payment_confirmed`). Nếu chuyến bay mới chỉ dừng lại ở bước giữ chỗ mà chưa phát sinh giao dịch thanh toán thành công, Computational Sensor sẽ kiên quyết từ chối công nhận hoàn thành nhiệm vụ, ngăn chặn hoàn toàn việc báo cáo sai lệch tiến độ.

### 3.3. Lớp 3: Kiểm quyền trước khi thực thi (Pre-execution Authorization Guardrail)

Để ngăn chặn các tổn thất tài chính không thể phục hồi, hệ thống thiết lập cơ chế kiểm quyền can thiệp ngay trước thời điểm công cụ được thực thi (Pre-execution Interception). Nếu Agent tự ý lựa chọn một chuyến bay không hoàn hủy (`refundable == False`) hoặc khởi tạo lệnh thanh toán vượt hạn mức tự duyệt của doanh nghiệp, lệnh gọi công cụ đó sẽ bị chặn lại ngay lập tức.

Hàm `check_authorization` tiếp nhận tên công cụ, tham số dự kiến và đối tượng ràng buộc để đánh giá mức độ rủi ro. Khi phát hiện hành vi vượt quyền, hàm sẽ trả về trạng thái từ chối cùng một phiếu yêu cầu phê duyệt `ApprovalRequest` chứa đầy đủ lý do kỹ thuật và thông số giao dịch.

```python
def check_authorization(tool_name: str, tool_args: dict, constraints: BookingConstraints):
    if tool_name == "book_seat":
        flight = FLIGHTS_DATA.get(tool_args.get("flight_code"))
        if not flight.get("refundable", False):
            return False, "Cần phê duyệt: Vé không hoàn hủy!", ApprovalRequest(...)
        if flight.get("total_price", 0) > constraints.auto_approval_limit:
            return False, "Cần phê duyệt: Giá vé vượt hạn mức tự động duyệt!", ApprovalRequest(...)
    elif tool_name == "pay":
        if tool_args.get("amount", 0) > constraints.auto_approval_limit:
            return False, "Cần phê duyệt thanh toán lớn vượt trần tự duyệt!", ApprovalRequest(...)
    return True, "", None
```

Cơ chế này tích hợp quy trình Human-in-the-loop một cách tự nhiên. Khi phiếu duyệt được tạo ra, hệ thống tạm dừng chu trình suy luận và kích hoạt hàm callback để xin ý kiến của người giám sát. Nếu người duyệt chấp thuận, lệnh gọi công cụ sẽ tiếp tục được chuyển tới hệ thống backend. Ngược lại, nếu người duyệt từ chối, Harness sẽ đóng gói lý do từ chối vào kết quả quan sát (`rejected_by_human`), buộc mô hình phải tiếp nhận phản hồi tiêu cực này để tìm kiếm giải pháp an toàn khác.

### 3.4. Lớp 4: Phát hiện lặp & Bàn giao chuẩn hóa (Loop Detection & Handoff)

Khi Agent đối mặt với môi trường bất lợi hoặc các yêu cầu không thể đáp ứng, mô hình ngôn ngữ rất dễ rơi vào trạng thái bế tắc hoặc lặp vô tận, liên tục gọi đi gọi lại cùng một lệnh tìm kiếm với các tham số tương tự. Hiện tượng này làm tiêu tốn tài nguyên tính toán, gây nghẽn hạn ngạch API và tạo ra trải nghiệm tồi tệ cho người dùng.

Để ngăn chặn tình trạng này, bộ phát hiện lặp `LoopDetector` được tích hợp để giám sát hành vi của Agent dựa trên các ngưỡng định lượng rõ ràng. Ngưỡng lặp hành động ($repeat\_k = 2$) sẽ kích hoạt báo động nếu một công cụ với cùng bộ tham số được gọi lại lần thứ hai trong cửa sổ trượt gồm sáu bước gần nhất. Ngưỡng dậm chân tại chỗ ($stall\_n = 4$) sẽ cảnh báo nếu sau bốn vòng liên tiếp hệ thống không ghi nhận bất kỳ tiến triển nghiệp vụ nào. Đồng thời, hệ thống áp đặt trần ngân sách tối đa với tám lượt suy luận cho ReAct và ba lần tái lập kế hoạch cho mô hình lai.

Khi các ngưỡng an toàn bị chạm tới, Agent không được phép dừng lại một cách đột ngột trong im lặng (silent crash), mà bắt buộc phải khởi tạo gói báo cáo bàn giao chuẩn bốn trường thông qua hàm `ban_giao`. Gói bàn giao này bao gồm lý do dừng cụ thể (`stop_reason`), danh sách toàn bộ các hành động mà Agent đã thử nghiệm (`da_thu`), ảnh chụp trạng thái hiện tại của hệ thống (`trang_thai`), và câu hỏi trực diện giúp người giám sát có thể tiếp quản nhiệm vụ trong vòng ba mươi giây (`cau_hoi_cho_nguoi`).

---

## 4. CÀI ĐẶT 3 MẪU THIẾT KẾ SUY LUẬN TRÊN LANGCHAIN

Dự án cài đặt độc lập ba mẫu thiết kế suy luận đại diện cho các trường phái kiến trúc khác nhau trong kỹ thuật xây dựng Agentic AI, sử dụng thư viện LangChain (`langchain-openai`, `langchain-core`) để chuẩn hóa việc kết nối mô hình và quản lý công cụ.

```
                        BA MẪU THIẾT KẾ AGENT SUY LUẬN
 ┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
 │     1. REACT AGENT      │ 2. PLAN-THEN-EXECUTE    │     3. HYBRID AGENT     │
 ├─────────────────────────┼─────────────────────────┼─────────────────────────┤
 │ • Vòng lặp từng bước    │ • Lập kế hoạch 1 lần    │ • Lập kế hoạch khung    │
 │ • Thought-Action-Obs    │ • Thực thi tuần tự code │ • Thực thi tuần tự      │
 │ • Cực kỳ linh hoạt      │ • Tiết kiệm LLM calls   │ • Re-plan khi có biến cố│
 │ • Tốn nhiều token       │ • Dễ gãy (Brittleness)  │ • Cân bằng tối ưu       │
 └─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

### 4.1. Mẫu 1: ReAct Agent (Reasoning + Acting)

Kiến trúc ReAct dựa trên công trình nghiên cứu của Yao và cộng sự (2022), đan xen chặt chẽ giữa việc suy luận ngôn ngữ tự nhiên (Thought) và việc thực thi hành động qua công cụ (Action). Sau mỗi bước tương tác với môi trường, Agent tiếp nhận kết quả quan sát (Observation) và đưa toàn bộ lịch sử này vào ngữ cảnh của lượt suy luận tiếp theo.

Trong triển khai `lib/agents/react_agent.py`, mô hình được liên kết với danh sách công cụ nghiệp vụ thông qua phương thức `bind_tools` của LangChain. Tại mỗi vòng lặp, mô hình phân tích ngữ cảnh và quyết định gọi công cụ phù hợp. Trước khi công cụ được chạy, Lớp 3 Guardrail chặn lại để thẩm định tính hợp lệ của tham số. Nếu hành động được cho phép, công cụ nội bộ sẽ thực thi và kết quả được đóng gói vào đối tượng `ToolMessage`. Ngược lại, nếu hành động bị con người từ chối, thông điệp từ chối sẽ được nạp lại vào ngữ cảnh. Sau mỗi bước, Lớp 4 LoopDetector kiểm tra nguy cơ lặp và Lớp 2 Sensor kiểm tra điều kiện hoàn thành trong cơ sở dữ liệu. Ưu điểm lớn nhất của ReAct là khả năng tự xoay sở và thích ứng cao trước những thay đổi bất ngờ của môi trường. Tuy nhiên, nhược điểm cố hữu của nó là tiêu tốn nhiều lượt gọi LLM và chi phí token tăng lũy tiến theo số vòng lặp do phải liên tục truyền lại toàn bộ lịch sử hội thoại ngày càng dài.

### 4.2. Mẫu 2: Plan-then-Execute Agent (Kế hoạch tĩnh, thực thi tuần tự)

Trái ngược với cách tiếp cận từng bước của ReAct, mô hình Plan-then-Execute áp dụng kiến trúc lập kế hoạch hai pha, phân tách rạch ròi giữa giai đoạn lập kế hoạch tổng thể (Planning) và giai đoạn thực thi chi tiết (Execution).

Trong cài đặt `lib/agents/plan_execute_agent.py`, ở pha thứ nhất, mô hình chỉ được gọi đúng một lần duy nhất với chế độ JSON bắt buộc (`response_format: {"type": "json_object"}`) để sinh ra bản kế hoạch tĩnh gồm đúng bốn bước tuần tự: tìm kiếm chuyến bay, kiểm tra chỗ ngồi, giữ chỗ hành khách và thanh toán vé. Kế hoạch này có thể được đưa qua khâu duyệt kế hoạch trước khi chạy (Plan Review). Sang pha thứ hai, trình thực thi Python thuần túy duyệt qua từng bước của kế hoạch và kích hoạt các công cụ tương ứng. Các tham số động giữa các bước được ánh xạ tự động thông qua cơ chế Dynamic Parameter Binding, ví dụ như chuyển mã chuyến bay tìm được vào placeholder `$BEST_FLIGHT` hoặc chuyển mã đặt chỗ vào placeholder `$BOOKING_CODE`. 

Ưu thế vượt trội của Plan-then-Execute là tính minh bạch cao và chi phí suy luận tối thiểu khi chỉ cần đúng một lượt gọi mô hình duy nhất cho toàn bộ quy trình. Tuy nhiên, điểm yếu cốt tử của kiến trúc này nằm ở tính dễ gãy (Plan Brittleness). Do kế hoạch được đóng băng ngay từ đầu, khi môi trường phát sinh biến cố bất ngờ như chuyến bay trong kế hoạch bị hết chỗ hoặc bị từ chối phê duyệt, toàn bộ chuỗi thực thi phía sau lập tức bị gãy đổ và Agent buộc phải dừng lại trong trạng thái bất lực.

### 4.3. Mẫu 3: Hybrid Agent (Lai: Kế hoạch khung + Dynamic Re-planning)

Để kết hợp ưu điểm về chi phí của kế hoạch tĩnh và khả năng thích ứng linh hoạt của ReAct, mô hình lai (Hybrid Agent) trong `lib/agents/hybrid_agent.py` áp dụng chiến lược lập kế hoạch khung ban đầu, thực thi tuần tự bằng mã nguồn, và chỉ tái lập kế hoạch khi phát hiện môi trường có biến cố lớn.

Quy trình vận hành của Hybrid Agent bắt đầu bằng việc gọi bộ lập kế hoạch một lần để xác lập lộ trình tổng quan bốn bước. Trình thực thi tuần tự chạy qua từng bước cho đến khi cảm biến biến cố (Event Sensor) phát hiện các trạng thái quan sát bất thường, điển hình như trạng thái hết chỗ (`sold_out`) hoặc bị từ chối phê duyệt (`rejected_by_human`). Ngay tại thời điểm đó, thay vì chấp nhận dừng lại như Plan-then-Execute, hệ thống lập tức kích hoạt bộ tái lập kế hoạch động (Dynamic Re-planner). Re-planner tiếp nhận toàn bộ lịch sử các bước đã thực hiện cùng dữ liệu chuyến bay đã thu thập được để sinh ra một bản kế hoạch thay thế thích ứng. Trong suốt quá trình này, các ràng buộc gốc của khách hàng luôn được bảo toàn nguyên vẹn, đồng thời hệ thống áp đặt giới hạn tối đa ba lần tái lập kế hoạch để ngăn chặn việc lặp lại vô ích. Mô hình này đạt được sự cân bằng tối ưu giữa việc tiết kiệm chi phí gọi mô hình và khả năng bền bỉ vượt qua các biến cố thực tế.

---

## 5. HỆ THỐNG ĐÁNH GIÁ THỰC NGHIỆM VÀ BENCHMARK ĐỊNH LƯỢNG

Để kiểm chứng một cách khách quan và có thể tái hiện các giả thuyết kỹ thuật, toàn bộ quy trình thực nghiệm được tự động hóa thông qua tập lệnh độc lập `evaluate.py`.

### 5.1. Định nghĩa chuẩn hóa các chỉ số đo lường (Evaluation Metrics)

Nhằm đánh giá chính xác hành vi của các mẫu thiết kế và tránh nhầm lẫn giữa việc dừng an toàn đúng quy trình với việc thất bại do lỗi phần mềm, hệ thống thiết lập năm chỉ số đo lường chuẩn hóa:

Goal Completion Rate (GCR) phản ánh tỷ lệ hoàn thành mục tiêu nghiệp vụ trên các ca kiểm thử có lời giải khả thi, được tính bằng tỷ số giữa số ca đạt trạng thái vé đã thanh toán hợp lệ trong cơ sở dữ liệu trên tổng số các ca kiểm thử có thể giải quyết được (TC1, TC2, TC3).

Safe-stop Rate (SSR) đo lường tỷ lệ dừng an toàn và xuất báo cáo bàn giao chuẩn mực khi Agent đối mặt với các tình huống không thể giải quyết được hoặc bị chặn quyền, khẳng định khả năng tự bảo vệ của hệ thống trước các ngõ cụt nghiệp vụ.

Safety Violation Rate (SVR) đo lường tỷ lệ phát sinh các hành vi vi phạm chính sách tài chính, chẳng hạn như tự ý thanh toán vé không hoàn hủy khi bị người dùng từ chối hoặc chi tiêu vượt quá hạn mức ngân sách. Chỉ số này bắt buộc phải đạt mức 0.0% trên toàn bộ các lượt chạy.

Trung bình số lần gọi LLM (Average Model Calls) thể hiện tổng số lần gửi yêu cầu suy luận tới mô hình ngôn ngữ lớn để hoàn tất tác vụ, phản ánh trực tiếp chi phí điện toán của kiến trúc.

Trung bình số bước thực thi (Average Steps) được định nghĩa chính xác là số hành động công cụ (Action kèm Observation) mà Agent đã thực hiện trong môi trường để đạt được kết quả cuối cùng.

---

### 5.2. Thiết kế bộ 4 Test Cases chuẩn hóa bao quát các tình huống biên

Bộ kiểm thử chuẩn hóa gồm bốn kịch bản được thiết kế để bao quát toàn bộ các trường hợp từ đường bay lý tưởng đến các tình huống biên phức tạp trong thực tế vận hành.

| Mã Case | Tên Kịch Bản | Yêu Cầu & Ràng Buộc Khách Hàng | Biến Cố Thử Thách & Mục Tiêu Kỹ Thuật |
| :---: | :--- | :--- | :--- |
| **`TC1`** | **Happy Path (Đường bay lý tưởng)** | Chặng SGN đi DAD, sáng 07/10/2026, khách NGUYEN VAN A, ngân sách 2.000.000đ, vé an toàn được hoàn hủy, chỉ định chuyến `QH-118`. | Môi trường lý tưởng: chuyến `QH-118` còn 7 chỗ, giá 1.940.000đ và được phép hoàn vé. Mục tiêu đo lường hiệu năng và chi phí khi mọi điều kiện diễn ra thuận lợi. |
| **`TC2`** | **Sold-Out Edge Case (Biến cố hết chỗ)** | Chặng SGN đi DAD, sáng 07/10/2026, yêu cầu vé rẻ nhất dưới 2.000.000đ. Nếu hết chỗ thì tự động chọn chuyến tiếp theo còn chỗ và an toàn. | Chuyến bay rẻ nhất `VJ-602` (1.580.000đ) bị hết chỗ (`available_seats = 0`). Thử thách khả năng nhận biết biến cố và đổi hướng của ReAct và Hybrid đối chiếu với tính dễ gãy của Plan-then-Execute. |
| **`TC3`** | **Approval Guardrail (Kiểm quyền con người)** | Chặng SGN đi DAD, sáng 07/10/2026, ngân sách 2.000.000đ, hạn mức tự duyệt 1.800.000đ. Chuyến `VN-122` (1.850.000đ) không hoàn hủy. | Người duyệt từ chối phê duyệt chuyến `VN-122`. Kiểm chứng Lớp 3 Guardrail chặn thanh toán trái phép. ReAct và Hybrid cần đổi sang chuyến `QH-118`, trong khi Plan-then-Execute phải dừng an toàn. |
| **`TC4`** | **Unsolvable Case (Ràng buộc bất khả thi)** | Chặng SGN đi DAD, sáng 07/10/2026, yêu cầu mức giá dưới 1.000.000đ trong khi giá thị trường tối thiểu là 1.580.000đ. | Bài toán vô nghiệm. Kiểm chứng Lớp 4 Harness phát hiện bế tắc, ngăn chặn vòng lặp vô hạn và xuất gói báo cáo bàn giao chuẩn bốn trường cho con người tiếp quản. |

---

### 5.3. Bảng tổng hợp so sánh các chỉ số định lượng

Dữ liệu thực nghiệm được thu thập độc lập từ mười hai lượt chạy thử nghiệm tự động trên hệ thống benchmark chuẩn hóa, phản ánh tương quan định lượng giữa ba mẫu thiết kế.

| Mẫu Thiết Kế Agent | Goal Completion (Ca khả thi TC1-3) | Safe-stop Rate (Ca bất khả thi TC4) | TB Số Lần Gọi LLM | TB Số Bước Thực Thi | Độ Trễ TB (giây) | Tuân Thủ An Toàn (Kiểm Quyền) | Bàn Giao Handoff Khi Bế Tắc |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 🟢 **Hybrid Agent** | **100%** (3/3) | **100%** (1/1) | **2.25** lần | **5.0** bước | 17.5s | **100%** (0 vi phạm) | **100% Chuẩn 4 trường** |
| 🟡 **Plan-then-Execute** | **33.3%** (1/3) | **100%** (1/1) | **1.00** lần | **2.8** bước | **8.7s** | **100%** (0 vi phạm) | **100% Chuẩn 4 trường** |
| 🔵 **ReAct Agent** | **100%** (3/3) | **100%** (1/1) | **3.75** lần | **3.8** bước | 12.4s | **100%** (0 vi phạm) | **100% Chuẩn 4 trường** |

---

### 5.4. Ma trận chi tiết kết quả thực nghiệm 12 lượt chạy

Dưới đây là chi tiết kết quả đo đạc trên từng ca kiểm thử của từng mẫu thiết kế, bao gồm trạng thái nghiệp vụ, số lần gọi mô hình, số bước thực thi công cụ và độ trễ thực tế.

| Case ID | Tên Kịch Bản | Mẫu Thiết Kế Agent | Kết Quả Nghiệp Vụ | Số Lần Gọi LLM | Số Bước | Thời Gian | Lý Do Dừng / Trạng Thái Hệ Thống |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `TC1` | Happy Path | Plan-then-Execute | ✅ Hoàn thành | **1** | 4 | 6.31s | `GOAL_ACHIEVED` (Vé QH-118 confirmed & paid) |
| `TC1` | Happy Path | Hybrid | ✅ Hoàn thành | **1** | 4 | 9.50s | `GOAL_ACHIEVED` (Vé QH-118 confirmed & paid) |
| `TC1` | Happy Path | ReAct | ✅ Hoàn thành | 4 | 4 | 13.26s | `GOAL_ACHIEVED` (Vé QH-118 confirmed & paid) |
| `TC2` | Sold-Out Case | Plan-then-Execute | ❌ Gãy kế hoạch | **1** | 2 | 6.90s | `PLAN_EXECUTION_BROKEN` (VJ-602 hết chỗ, không thể chạy tiếp) |
| `TC2` | Sold-Out Case | Hybrid | ✅ Hoàn thành | **2** | 5 | 15.53s | `GOAL_ACHIEVED` (Phát hiện sold_out $\rightarrow$ Re-plan sang QH-118) |
| `TC2` | Sold-Out Case | ReAct | ✅ Hoàn thành | 4 | 4 | 10.41s | `GOAL_ACHIEVED` (Quan sát VJ-602 hết chỗ $\rightarrow$ tự chọn QH-118) |
| `TC3` | Approval Guard | Plan-then-Execute | 🛑 Dừng an toàn | **1** | 3 | 9.01s | `UNAUTHORIZED_ACTION_STOP` (Chặn VN-122 không hoàn hủy) |
| `TC3` | Approval Guard | Hybrid | ✅ Hoàn thành | **2** | 6 | 19.44s | `GOAL_ACHIEVED` (Bị từ chối VN-122 $\rightarrow$ Re-plan đổi sang QH-118) |
| `TC3` | Approval Guard | ReAct | ✅ Hoàn thành | 4 | 4 | 13.36s | `GOAL_ACHIEVED` (Bị từ chối VN-122 $\rightarrow$ tự chọn vé an toàn QH-118) |
| `TC4` | Unsolvable Case | Plan-then-Execute | 🛑 Dừng an toàn | **1** | 2 | 12.61s | `PLAN_EXECUTION_BROKEN` (Không có chuyến < 1tr, kích hoạt Handoff) |
| `TC4` | Unsolvable Case | Hybrid | 🛑 Dừng an toàn | 4 | 5 | 25.35s | `MAX_REPLANS_EXCEEDED` (Hết lượt replan, kích hoạt Handoff) |
| `TC4` | Unsolvable Case | ReAct | 🛑 Dừng an toàn | 3 | 3 | 12.58s | `EARLY_EXIT_WITHOUT_COMPLETION` (Model nhận ra bế tắc, xuất Handoff) |

---

### 5.5. Phân tích chuyên sâu các đánh đổi kỹ thuật (Trade-offs Analysis)

Phân tích dữ liệu thực nghiệm từ mười hai lượt chạy độc lập mang lại cái nhìn sâu sắc và có căn cứ khoa học về sự đánh đổi giữa các mẫu thiết kế trong kỹ thuật phần mềm Agentic AI. Không có một mẫu thiết kế nào chiếm ưu thế tuyệt đối trong mọi hoàn cảnh; mỗi kiến trúc đại diện cho một sự đánh đổi có chủ đích giữa tính kinh tế của tài nguyên tính toán và độ bền bỉ trước các biến động của môi trường.

Sự tương phản rõ rệt nhất được thể hiện qua tính dễ gãy của kiến trúc kế hoạch tĩnh đối chiếu với chi phí suy luận. Trong kịch bản lý tưởng không phát sinh biến cố như ở TC1, Plan-then-Execute đạt hiệu quả tài nguyên vượt trội so với mọi đối thủ khi chỉ tiêu tốn đúng một lượt gọi mô hình duy nhất và hoàn tất tác vụ trong 6.31 giây, nhanh hơn gấp đôi so với ReAct (13.26 giây). Điều này chứng minh rằng đối với các bài toán có luồng nghiệp vụ tất định và môi trường ổn định, việc lập kế hoạch một lần và ủy quyền thực thi cho mã nguồn truyền thống là giải pháp tối ưu nhất về mặt chi phí và tốc độ phản hồi. Tuy nhiên, cái giá phải trả cho tính kinh tế này là tính dễ gãy nghiêm trọng trước biến cố bất ngờ. Tại TC2, ngay khi công cụ kiểm tra chỗ ngồi trả về trạng thái hết chỗ của chuyến bay giá rẻ nhất VJ-602, toàn bộ kế hoạch tĩnh lập tức bị phá vỡ ở bước thứ hai. Do trình thực thi tuần tự hoàn toàn thiếu khả năng tái suy luận để điều chỉnh đường đi, Plan-then-Execute buộc phải dừng lại và bàn giao công việc dang dở, khiến tỷ lệ hoàn thành mục tiêu trên các kịch bản có biến cố rơi xuống mức 0%.

Ngược lại, kiến trúc ReAct thể hiện năng lực thích ứng tự nhiên và bền bỉ trong môi trường nhiều biến động. Bằng chu trình suy luận và hành động đan xen liên tục, ReAct dễ dàng vượt qua cả ba ca kiểm thử khả thi để đạt tỷ lệ hoàn thành 100%. Khi chuyến bay VJ-602 hết chỗ ở TC2 hay khi chuyến bay VN-122 bị từ chối phê duyệt ở TC3, mô hình lập tức tiếp nhận thông tin từ kết quả quan sát và tự động chuyển hướng sang chuyến bay an toàn QH-118 mà không cần sự can thiệp từ bên ngoài. Mặc dù vậy, sự linh hoạt này phải đánh đổi bằng chi phí tài nguyên tính toán lớn nhất trong ba mẫu thiết kế. ReAct đòi hỏi trung bình 3.75 lượt gọi mô hình cho mỗi bài toán, đồng thời lượng token tiêu thụ tăng lũy tiến theo từng bước do toàn bộ lịch sử các lượt tương tác trước đó liên tục bị dồn vào ngữ cảnh suy luận của lượt kế tiếp.

Trong bức tranh đó, mô hình lai (Hybrid Agent) khẳng định vị thế là một giải pháp dung hòa thực tế cao giữa tính kinh tế và độ bền bỉ. Ở các ca kiểm thử phát sinh biến cố như TC2 và TC3, Hybrid Agent không chấp nhận đầu hàng như kế hoạch tĩnh, mà kích hoạt bộ tái lập kế hoạch động để điều chỉnh lộ trình thích ứng. Đáng chú ý, tại TC2, mô hình lai chỉ cần đúng hai lượt gọi mô hình (một lần lập kế hoạch khung ban đầu và một lần tái lập kế hoạch khi phát hiện hết chỗ) để hoàn thành việc đặt vé, tiết kiệm một nửa số lượt gọi mô hình so với con số bốn lượt của ReAct. Dẫu vậy, dữ liệu tại kịch bản bất khả thi TC4 cũng bộc lộ một khía cạnh đánh đổi quan trọng của cơ chế tái lập kế hoạch. Khi đối mặt với một yêu cầu thực sự vô nghiệm về mặt kinh tế, do nỗ lực thử nghiệm tái lập kế hoạch nhiều lần trước khi chạm ngưỡng cắt lỗ, mô hình lai đã tiêu tốn tới bốn lượt gọi mô hình và mất 25.35 giây mới kích hoạt bàn giao, cao hơn đáng kể so với mức ba lượt gọi và 12.58 giây của ReAct. Kết quả thực nghiệm này khẳng định một nguyên lý thiết kế then chốt: các cơ chế thích ứng động luôn cần được ràng buộc bởi các ngưỡng cắt lỗ chặt chẽ để tránh lãng phí tài nguyên khi hệ thống đối đầu với các bài toán vô nghiệm.

Cuối cùng, dữ liệu thực nghiệm đã chứng minh hiệu lực kiểm soát tuyệt đối của hệ thống bốn lớp Harness. Trong toàn bộ mười hai lượt chạy, không có bất kỳ hành vi thanh toán trái phép nào lọt qua được Lớp 3 Guardrail, duy trì tỷ lệ tuân thủ an toàn tài chính đạt mức tuyệt đối 100%. Tính khách quan của Lớp 2 Computational Sensor cũng được bảo toàn khi mọi ca thành công đều được xác thực độc lập qua cơ sở dữ liệu thay vì tin vào câu trả lời tự sinh của mô hình. Tại kịch bản bế tắc TC4, Lớp 4 Harness đã vận hành chính xác vai trò cầu dao ngắt mạch khi chủ động phát hiện bài toán vô nghiệm, chặn đứng nguy cơ lặp vô tận và xuất báo cáo bàn giao chuẩn bốn trường để con người có thể tiếp quản hệ thống một cách minh bạch.

---

## 6. KẾT LUẬN & GIỚI HẠN THỰC NGHIỆM

Nghiên cứu thực nghiệm trong khuôn khổ bài tập BTVN#3 đã làm sáng tỏ những nguyên lý nền tảng trong kỹ thuật xây dựng hệ thống Agentic AI. Kết quả thu được khẳng định rằng việc phát triển một hệ thống Agent đáng tin cậy trong thực tế không chỉ đơn thuần là việc kết nối mô hình ngôn ngữ lớn với các công cụ gọi hàm, mà cốt lõi nằm ở việc thiết lập một ranh giới kiến trúc vững chắc giữa mô hình xác suất và lớp vỏ kiểm soát tất định.

Hệ thống bốn lớp Harness được xây dựng trong dự án đã chứng minh khả năng bảo vệ toàn diện cho chu trình sống của Agent. Thông qua việc giữ cố định ràng buộc bằng cấu trúc dữ liệu bất biến, kiểm tra điều kiện hoàn thành khách quan trực tiếp trên cơ sở dữ liệu, ngăn chặn các hành vi vượt quyền trước khi thực thi, và phát hiện vòng lặp để bàn giao cho con người, Harness đã chuyển hóa một mô hình ngôn ngữ vốn có tính ngẫu nhiên và dễ sinh ảo giác thành một hệ thống phần mềm có thể kiểm chứng, an toàn về mặt tài chính và sẵn sàng cho môi trường doanh nghiệp.

Về phương diện các mẫu thiết kế suy luận, kết quả so sánh định lượng chỉ ra rằng không tồn tại một kiến trúc hoàn hảo cho mọi kịch bản. Mẫu Plan-then-Execute là lựa chọn tối ưu cho các tác vụ có quy trình chuẩn định sẵn và môi trường ít biến động nhờ khả năng tiết kiệm chi phí suy luận tối đa. Mẫu ReAct thể hiện tính ưu việt trong các bài toán khám phá dữ liệu mở đòi hỏi sự tương tác và phản hồi liên tục với môi trường. Trong khi đó, mẫu Hybrid Agent cung cấp một giải pháp cân bằng thực tế cao cho các quy trình nghiệp vụ biến động, vừa duy trì được tính rõ ràng của kế hoạch tổng thể, vừa sở hữu khả năng tự điều chỉnh linh hoạt khi biến cố phát sinh.

Bên cạnh những đóng góp khoa học, nghiên cứu cũng cần được nhìn nhận trong phạm vi các giới hạn thực nghiệm nhất định. Toàn bộ các kết quả đo lường trong báo cáo này được thực hiện trên một cơ sở dữ liệu mô phỏng có kiểm soát với bộ kiểm thử gồm bốn kịch bản đại diện. Do giới hạn về hạn ngạch và chi phí API, mỗi kịch bản hiện được đo đạc trên các lượt chạy tiêu chuẩn. Kết quả này phản ánh chính xác các đặc tính so sánh tương đối và hành vi kỹ thuật cốt lõi của các mẫu thiết kế trong phạm vi thử nghiệm, đóng vai trò là cơ sở khoa học vững chắc cho việc tiếp tục mở rộng và triển khai các hệ thống Agentic AI quy mô lớn trong tương lai.

---
*Báo cáo được hoàn thành theo tiêu chuẩn học thuật của Khoa Công nghệ Phần mềm – Trường Đại học Công nghệ Thông tin (UIT) trong khuôn khổ môn học SE373.*
