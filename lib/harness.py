# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Bộ 4 Lớp Harness Kiểm Soát Agent Đặt Vé Máy Bay.

Đây là lớp vỏ kiểm soát an toàn và tính toán khách quan (Harness Layer) do lập trình
viên viết, độc lập hoàn toàn với trí nhớ và phán đoán chủ quan của LLM (Slide 10, 11).

Bao gồm đủ 4 lớp theo yêu cầu:
1. Ràng buộc là dữ liệu (Constraint-as-Data):
   - Đóng gói yêu cầu của người dùng thành cấu trúc dữ liệu cố định (BookingConstraints).
   - Chống trôi mục tiêu (Goal Drift) khi lịch sử hội thoại dài ra (Slide 60, 62).
2. Tiêu chí hoàn thành kiểm bằng code (Computational Completion Sensor):
   - Độc lập với lời tự tuyên bố của LLM.
   - Kiểm chứng trực tiếp trong Database: confirmed, paid, đúng chuyến, đúng giá (Slide 43, 44).
3. Kiểm quyền (Pre-execution Authorization Guardrail):
   - Chạy TRƯỚC khi thực thi tool (Slide 41, 504).
   - Ngăn chặn các hành động nhạy cảm hoặc có rủi ro tài chính cao: vé không hoàn hủy
     (refundable=False) hoặc số tiền vượt hạn mức phê duyệt tự động.
4. Phát hiện lặp & Bàn giao (Loop Detection & Handoff):
   - Bắt 3 tín hiệu bế tắc: trùng action, trùng observation, không tiến triển (Slide 45, 46).
   - Khi dừng bất thường: Bàn giao chuẩn 4 trường cho con người tiếp quản (Slide 48).
"""

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from data.flights_db import BOOKINGS_DB, FLIGHTS_DATA


# ==============================================================================
# LỚP 1: RÀNG BUỘC LÀ DỮ LIỆU (CONSTRAINT-AS-DATA) · SLIDE 60, 62
# ==============================================================================
@dataclass(frozen=True)
class BookingConstraints:
    """Cấu trúc dữ liệu bất biến (immutable) lưu trữ toàn bộ ràng buộc của người dùng.

    Được lưu cố định tại Harness để ngăn chặn 'Goal Drift' (Agent quên yêu cầu ban đầu
    khi chuỗi hội thoại dài ra).
    """

    origin: str  # Điểm khởi hành (vd: 'SGN')
    destination: str  # Điểm đến (vd: 'DAD')
    date: str  # Ngày bay chuẩn 'YYYY-MM-DD' (vd: '2026-10-07')
    time_slot: Optional[str] = "morning"  # 'morning', 'afternoon', 'evening' hoặc None
    max_price: int = 2_000_000  # Ngân sách trần (VNĐ)
    passenger_name: str = "NGUYEN VAN A"  # Tên hành khách
    passenger_id: str = "079123456789"  # CCCD/Định danh
    auto_approval_limit: int = 1_800_000  # Ngưỡng chi tiêu tối đa tự động duyệt (VNĐ)


def validate_flight_constraints(
    flight: Dict[str, Any], constraints: BookingConstraints
) -> Tuple[bool, List[str]]:
    """Kiểm tra một chuyến bay có thỏa mãn toàn bộ ràng buộc hay không.

    Hàm này chạy hoàn toàn bằng logic Python, không tốn token, dùng để lọc hoặc
    ngăn Agent chọn chuyến bay vi phạm yêu cầu của khách.

    Returns:
        (is_valid: bool, violations: List[str])
    """
    violations = []

    # 1. Kiểm tra chặng bay
    if flight.get("origin", "").upper() != constraints.origin.upper():
        violations.append(
            f"Sai điểm đi: yêu cầu {constraints.origin}, thực tế {flight.get('origin')}"
        )
    if flight.get("destination", "").upper() != constraints.destination.upper():
        violations.append(
            f"Sai điểm đến: yêu cầu {constraints.destination}, thực tế {flight.get('destination')}"
        )

    # 2. Kiểm tra ngày bay
    if flight.get("date") != constraints.date:
        violations.append(
            f"Sai ngày bay: yêu cầu {constraints.date}, thực tế {flight.get('date')}"
        )

    # 3. Kiểm tra buổi bay (nếu có yêu cầu)
    if constraints.time_slot and flight.get("time_slot") != constraints.time_slot:
        violations.append(
            f"Sai buổi bay: yêu cầu {constraints.time_slot}, thực tế {flight.get('time_slot')}"
        )

    # 4. Kiểm tra ngân sách trần
    total_price = flight.get("total_price")
    if total_price is None:
        total_price = flight.get("base_price", 0) + flight.get("tax_and_fees", 0)

    if total_price > constraints.max_price:
        violations.append(
            f"Vượt ngân sách: giá {total_price:,}đ > trần {constraints.max_price:,}đ"
        )

    # 5. Kiểm tra tình trạng chỗ trống
    if flight.get("available_seats", 0) <= 0:
        violations.append(f"Hết chỗ: chuyến {flight.get('flight_code')} đã có 0 ghế trống")

    return (len(violations) == 0, violations)


# ==============================================================================
# LỚP 2: TIÊU CHÍ HOÀN THÀNH KIỂM BẰNG CODE (COMPUTATIONAL SENSOR) · SLIDE 43, 44
# ==============================================================================
def is_goal_achieved(
    booking_code: str,
    constraints: BookingConstraints,
    bookings_db: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Computational Sensor xác nhận tác vụ đã hoàn tất khách quan.

    Quy tắc logic kiểm chứng trực tiếp từ Database:
    1. get_booking(code) tồn tại
    2. status == 'confirmed'
    3. paid is True
    4. total_price <= constraints.max_price
    5. date == constraints.date
    6. time_slot == constraints.time_slot (nếu có yêu cầu)

    Returns:
        (achieved: bool, check_details: dict)
    """
    db = bookings_db if bookings_db is not None else BOOKINGS_DB
    b_code = booking_code.strip().upper() if booking_code else ""
    record = db.get(b_code)

    details = {
        "booking_code": b_code,
        "exists_in_db": record is not None,
        "status_confirmed": False,
        "is_paid": False,
        "within_budget": False,
        "correct_date": False,
        "correct_time_slot": False,
        "failure_reasons": [],
    }

    if not record:
        details["failure_reasons"].append(f"Mã đặt chỗ '{b_code}' không tồn tại trong hệ thống")
        return False, details

    # Kiểm tra trạng thái và thanh toán
    details["status_confirmed"] = record.get("status") == "confirmed"
    details["is_paid"] = record.get("paid") is True

    if not details["status_confirmed"]:
        details["failure_reasons"].append(
            f"Trạng thái vé chưa 'confirmed' (hiện tại: {record.get('status')})"
        )
    if not details["is_paid"]:
        details["failure_reasons"].append("Vé chưa được thanh toán thành công (paid = False)")

    # Kiểm tra ngân sách
    actual_price = record.get("total_price", 0)
    details["within_budget"] = actual_price <= constraints.max_price
    if not details["within_budget"]:
        details["failure_reasons"].append(
            f"Giá vé thực tế ({actual_price:,}đ) vượt ngân sách ({constraints.max_price:,}đ)"
        )

    # Kiểm tra ngày bay
    details["correct_date"] = record.get("date") == constraints.date
    if not details["correct_date"]:
        details["failure_reasons"].append(
            f"Ngày bay ({record.get('date')}) không khớp yêu cầu ({constraints.date})"
        )

    # Kiểm tra buổi bay
    if constraints.time_slot:
        details["correct_time_slot"] = record.get("time_slot") == constraints.time_slot
        if not details["correct_time_slot"]:
            details["failure_reasons"].append(
                f"Buổi bay ({record.get('time_slot')}) không khớp ({constraints.time_slot})"
            )
    else:
        details["correct_time_slot"] = True

    achieved = (
        details["exists_in_db"]
        and details["status_confirmed"]
        and details["is_paid"]
        and details["within_budget"]
        and details["correct_date"]
        and details["correct_time_slot"]
    )

    return achieved, details


# ==============================================================================
# LỚP 3: KIỂM QUYỀN TRƯỚC KHI THỰC THI (PRE-EXECUTION GUARDRAIL) · SLIDE 41, 504
# ==============================================================================
@dataclass
class ApprovalRequest:
    """Phiếu yêu cầu phê duyệt khi Agent chạm tới hành động vượt thẩm quyền."""

    action_type: str  # 'NON_REFUNDABLE_BOOKING' hoặc 'EXCEED_BUDGET'
    tool_name: str  # 'book_seat' hoặc 'pay'
    tool_args: Dict[str, Any]  # Tham số dự định truyền vào tool
    flight_code: str  # Mã chuyến bay liên quan
    airline: str  # Tên hãng
    total_price: int  # Số tiền giao dịch
    is_refundable: bool  # Chính sách hoàn vé
    reason: str  # Lý do cần xin phê duyệt
    timestamp: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


def check_authorization(
    tool_name: str,
    tool_args: Dict[str, Any],
    constraints: BookingConstraints,
    flights_data: Optional[List[Dict[str, Any]]] = None,
    bookings_db: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str], Optional[ApprovalRequest]]:
    """Chạy TRƯỚC khi thực thi tool.

    Kiểm tra xem hành động mà model đề xuất có vượt thẩm quyền tự quyết hay không.

    Quy tắc kiểm quyền (Slide 41):
    1. Khi gọi 'book_seat':
       - Nếu vé là loại KHÔNG HOÀN HỦY (refundable == False) -> CẦN NGƯỜI DUYỆT!
       - Vì một khi đã đặt và thanh toán vé không hoàn, rủi ro tài chính là mất trắng tiền.
    2. Khi gọi 'pay' hoặc 'book_seat':
       - Nếu tổng giá vé vượt hạn mức tự duyệt (total_price > constraints.auto_approval_limit)
         -> CẦN NGƯỜI DUYỆT!

    Returns:
        (is_authorized: bool, reason: Optional[str], approval_req: Optional[ApprovalRequest])
    """
    f_data = flights_data if flights_data is not None else FLIGHTS_DATA
    b_db = bookings_db if bookings_db is not None else BOOKINGS_DB

    # Kiểm quyền với book_seat
    if tool_name == "book_seat":
        f_code = tool_args.get("flight_code", "").strip().upper()
        flight = next((f for f in f_data if f["flight_code"].upper() == f_code), None)
        if not flight:
            # Nếu chuyến bay không có trong DB, cho phép chạy tiếp để tool tự ném lỗi chuẩn
            return True, None, None

        total_price = flight.get("base_price", 0) + flight.get("tax_and_fees", 0)
        is_refundable = flight.get("refundable", True)

        # Vi phạm 1: Vé không hoàn tiền
        if not is_refundable:
            approval_req = ApprovalRequest(
                action_type="NON_REFUNDABLE_BOOKING",
                tool_name=tool_name,
                tool_args=tool_args,
                flight_code=flight["flight_code"],
                airline=flight["airline"],
                total_price=total_price,
                is_refundable=False,
                reason=(
                    f"Chuyến bay {flight['flight_code']} là loại VÉ KHÔNG HOÀN HỦY "
                    f"(Non-refundable). Cần người dùng phê duyệt trước khi giữ chỗ."
                ),
            )
            return (
                False,
                f"Cần phê duyệt: Chuyến {flight['flight_code']} không được phép hoàn hủy.",
                approval_req,
            )

        # Vi phạm 2: Vượt hạn mức chi tiêu tự động
        if total_price > constraints.auto_approval_limit:
            approval_req = ApprovalRequest(
                action_type="EXCEED_BUDGET",
                tool_name=tool_name,
                tool_args=tool_args,
                flight_code=flight["flight_code"],
                airline=flight["airline"],
                total_price=total_price,
                is_refundable=is_refundable,
                reason=(
                    f"Giá vé {total_price:,}đ vượt hạn mức tự động duyệt "
                    f"({constraints.auto_approval_limit:,}đ). Cần xác nhận ngân sách."
                ),
            )
            return (
                False,
                f"Cần phê duyệt: Giá vé {total_price:,}đ vượt hạn mức tự động duyệt.",
                approval_req,
            )

    # Kiểm quyền với pay
    elif tool_name == "pay":
        b_code = tool_args.get("booking_code", "").strip().upper()
        amount = tool_args.get("amount", 0)
        booking = b_db.get(b_code)

        if booking and amount > constraints.auto_approval_limit:
            approval_req = ApprovalRequest(
                action_type="EXCEED_BUDGET",
                tool_name=tool_name,
                tool_args=tool_args,
                flight_code=booking.get("flight_code", "N/A"),
                airline=booking.get("airline", "N/A"),
                total_price=amount,
                is_refundable=booking.get("refundable", True),
                reason=(
                    f"Số tiền thanh toán {amount:,}đ vượt hạn mức tự động duyệt "
                    f"({constraints.auto_approval_limit:,}đ)."
                ),
            )
            return (
                False,
                f"Cần phê duyệt thanh toán số tiền lớn: {amount:,}đ.",
                approval_req,
            )

    return True, None, None


# ==============================================================================
# LỚP 4: PHÁT HIỆN LẶP & BÀN GIAO (LOOP DETECTOR & HANDOFF) · SLIDE 45, 48, DEMO 2
# ==============================================================================
class LoopDetector:
    """Bộ phát hiện lặp và bế tắc theo đúng Slide 45, 46 và Demo 2.

    Ba tín hiệu bắt lỗi:
    1. Trùng action: Cùng (tool, args) lặp lại trong cửa sổ N vòng gần nhất.
    2. Trùng observation: Tham số khác nhau nhưng kết quả trả về giống hệt nhau.
    3. Không tiến triển (Stall): Đại lượng đo tiến độ bài toán đứng yên qua N vòng.
    """

    def __init__(self, window: int = 6, repeat_k: int = 2, same_obs_k: int = 3, stall_n: int = 4):
        self.recent = deque(maxlen=window)  # Dấu vân tay (tool, sorted_args)
        self.obs = deque(maxlen=window)  # Dấu vân tay observation
        self.k = repeat_k
        self.k_obs = same_obs_k
        self.n = stall_n
        self.last_progress = None
        self.stall = 0

    def check(
        self,
        tool: str,
        args: Dict[str, Any],
        observation: Optional[Any] = None,
        progress: Optional[Any] = None,
    ) -> Optional[str]:
        """Kiểm tra xem có dấu hiệu lặp hoặc bế tắc không.

        Returns:
            str nếu phát hiện lặp/bế tắc, None nếu bình thường.
        """
        # 1. Trùng action
        fp = (tool, repr(sorted(args.items())))
        if self.recent.count(fp) + 1 >= self.k:
            return (
                f"LOOP · Tool '{tool}' được gọi lại lần thứ {self.recent.count(fp) + 1} "
                f"với cùng tham số trong {self.recent.maxlen} vòng gần nhất"
            )
        self.recent.append(fp)

        # 2. Trùng observation
        if observation is not None:
            ofp = repr(observation)
            if self.obs.count(ofp) + 1 >= self.k_obs:
                return (
                    f"LOOP_OBSERVATION · {self.obs.count(ofp) + 1} lời gọi tool khác nhau "
                    f"nhưng đều nhận cùng một kết quả observation"
                )
            self.obs.append(ofp)

        # 3. Không tiến triển (Stall)
        if progress is not None:
            self.stall = self.stall + 1 if progress == self.last_progress else 0
            self.last_progress = progress
            if self.stall >= self.n:
                return (
                    f"STALL · Đại lượng tiến triển của bài toán đứng yên ở mức "
                    f"'{progress}' suốt {self.stall} vòng liên tiếp"
                )

        return None


def ban_giao(ly_do: str, da_thu: List[str], trang_thai: Dict[str, Any], cau_hoi: str) -> Dict[str, Any]:
    """Tạo gói bàn giao chuẩn 4 trường theo Slide 48 và Demo 2.

    Khi dừng bất thường, tuyệt đối không im lặng, mà bàn giao đủ 4 trường
    để con người có thể tiếp quản và trả lời trong 30 giây:
    1. stop_reason: Lý do dừng cụ thể.
    2. da_thu: Các bước và tham số đã thử.
    3. trang_thai: Ảnh chụp trạng thái hiện tại của phiên làm việc.
    4. cau_hoi_cho_nguoi: Câu hỏi trực tiếp để con người quyết định.
    """
    return {
        "stop_reason": ly_do,
        "da_thu": list(da_thu),
        "trang_thai": dict(trang_thai),
        "cau_hoi_cho_nguoi": cau_hoi,
    }


def format_handoff_report(b: Dict[str, Any]) -> str:
    """Định dạng báo cáo bàn giao trực quan cho người dùng đọc."""
    lines = [
        "╔══════════════════════════════════════════════════════════════════════════════╗",
        "║                     BÁO CÁO BÀN GIAO (AGENT HANDOFF REPORT)                  ║",
        "╚══════════════════════════════════════════════════════════════════════════════╝",
        f"🚨 LÝ DO DỪNG       : {b['stop_reason']}",
        "🛠️  CÁC BƯỚC ĐÃ THỬ  :",
    ]
    for idx, act in enumerate(b.get("da_thu", []), 1):
        lines.append(f"    [{idx}] {act}")
    lines.append(f"📊 TRẠNG THÁI HIỆN TẠI: {b.get('trang_thai', {})}")
    lines.append(f"❓ CÂU HỎI CHO NGƯỜI : {b['cau_hoi_cho_nguoi']}")
    lines.append("──────────────────────────────────────────────────────────────────────────────")
    return "\n".join(lines)
