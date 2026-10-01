# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · File Test Độc Lập 4 Lớp Harness (test_harness.py).

Chạy kiểm thử xác minh tính đúng đắn của 4 lớp Harness trước khi tích hợp vào Agent:
1. Ràng buộc là dữ liệu (Constraint-as-Data)
2. Tiêu chí hoàn thành kiểm bằng code (Computational Sensor)
3. Kiểm quyền trước khi gọi tool (Pre-execution Guardrail)
4. Phát hiện lặp & Bàn giao (Loop Detection & Handoff)

Chạy lệnh:
    python test_harness.py
"""

import os
import sys

# Đảm bảo hiển thị UTF-8 trên Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.flights_db import BOOKINGS_DB, FLIGHTS_DATA, reset_mock_db
from lib.harness import (
    ApprovalRequest,
    BookingConstraints,
    LoopDetector,
    ban_giao,
    check_authorization,
    format_handoff_report,
    is_goal_achieved,
    validate_flight_constraints,
)
from lib.tools import book_seat, check_seat, pay


def test_layer_1_constraints():
    print("\n" + "=" * 78)
    print("TEST LỚP 1: RÀNG BUỘC LÀ DỮ LIỆU (CONSTRAINT-AS-DATA)")
    print("=" * 78)

    constraints = BookingConstraints(
        origin="SGN",
        destination="DAD",
        date="2026-10-07",
        time_slot="morning",
        max_price=2_000_000,
        passenger_name="NGUYEN VAN A",
    )
    print(f"📌 Ràng buộc cố định của khách: {constraints}\n")

    # Kiểm tra từng chuyến bay trong dữ liệu mẫu
    for f in FLIGHTS_DATA:
        is_valid, violations = validate_flight_constraints(f, constraints)
        status_icon = "✅ HỢP LỆ" if is_valid else "❌ VI PHẠM"
        print(f"Chuyến {f['flight_code']} ({f['airline']}) -> {status_icon}")
        if not is_valid:
            for v in violations:
                print(f"   ⚠️  {v}")


def test_layer_2_completion_sensor():
    print("\n" + "=" * 78)
    print("TEST LỚP 2: TIÊU CHÍ HOÀN THÀNH KIỂM BẰNG CODE (COMPUTATIONAL SENSOR)")
    print("=" * 78)

    reset_mock_db()
    constraints = BookingConstraints(
        origin="SGN",
        destination="DAD",
        date="2026-10-07",
        time_slot="morning",
        max_price=2_000_000,
    )

    # 1. Đặt chỗ chuyến QH-118 nhưng CHƯA thanh toán (Mới chỉ 'held')
    print("1. Giữ chỗ chuyến QH-118 (trạng thái: held)...")
    res_book = book_seat("QH-118", "NGUYEN VAN A")
    b_code = res_book["booking_code"]

    achieved, details = is_goal_achieved(b_code, constraints)
    print(f"-> Kết quả kiểm tra Sensor: achieved = {achieved}")
    print(f"   Lý do chưa xong: {details['failure_reasons']}")
    assert achieved is False, "Lỗi: Đơn hàng mới 'held' chưa thể đạt tiêu chí hoàn thành!"

    # 2. Thanh toán thành công (Chuyển sang 'confirmed')
    print("\n2. Thực hiện thanh toán tiền vé...")
    pay(b_code, "corp_card", res_book["total_amount"])

    achieved, details = is_goal_achieved(b_code, constraints)
    print(f"-> Kết quả kiểm tra Sensor: achieved = {achieved}")
    print(f"   Chi tiết: Confirmed={details['status_confirmed']}, Paid={details['is_paid']}, WithinBudget={details['within_budget']}")
    assert achieved is True, "Lỗi: Đơn hàng đã confirmed và paid phải đạt tiêu chí hoàn thành!"
    print("✅ Sensor Computational hoạt động chính xác 100%!")


def test_layer_3_authorization_guardrail():
    print("\n" + "=" * 78)
    print("TEST LỚP 3: KIỂM QUYỀN TRƯỚC KHI THỰC THI (PRE-EXECUTION GUARDRAIL)")
    print("=" * 78)

    constraints = BookingConstraints(
        origin="SGN",
        destination="DAD",
        date="2026-10-07",
        time_slot="morning",
        max_price=2_000_000,
        auto_approval_limit=1_800_000,  # Ngưỡng tự động duyệt: 1.8tr
    )

    # Case 1: Chuyến VN-122 là vé KHÔNG HOÀN HỦY (refundable=False)
    print("1. Thử gọi book_seat cho chuyến VN-122 (Vé không hoàn hủy)...")
    is_auth, reason, approval_req = check_authorization(
        tool_name="book_seat",
        tool_args={"flight_code": "VN-122", "passenger_name": "NGUYEN VAN A"},
        constraints=constraints,
    )
    print(f"-> Được phép chạy ngay? : {is_auth}")
    print(f"   Lý do chặn         : {reason}")
    if approval_req:
        print(f"   Phiếu duyệt        : Action={approval_req.action_type} | Giá={approval_req.total_price:,}đ | Refundable={approval_req.is_refundable}")
    assert is_auth is False, "Lỗi: Vé không hoàn tiền bắt buộc phải bị chặn xin phê duyệt!"

    # Case 2: Chuyến QH-118 là vé hoàn được (refundable=True) nhưng giá 1.94tr (> hạn mức 1.8tr)
    print("\n2. Thử gọi book_seat cho chuyến QH-118 (Giá 1.940.000đ > hạn mức tự duyệt 1.800.000đ)...")
    is_auth, reason, approval_req = check_authorization(
        tool_name="book_seat",
        tool_args={"flight_code": "QH-118", "passenger_name": "NGUYEN VAN A"},
        constraints=constraints,
    )
    print(f"-> Được phép chạy ngay? : {is_auth}")
    print(f"   Lý do chặn         : {reason}")
    if approval_req:
        print(f"   Phiếu duyệt        : Action={approval_req.action_type} | Giá={approval_req.total_price:,}đ")
    assert is_auth is False, "Lỗi: Giá vượt hạn mức tự duyệt phải bị chặn!"

    # Case 3: Nâng hạn mức lên 2.0tr, chuyến QH-118 hoàn được -> ĐƯỢC PHÉP CHẠY NGAY
    print("\n3. Thử lại chuyến QH-118 với hạn mức tự duyệt 2.000.000đ...")
    constraints_high_limit = BookingConstraints(
        origin="SGN", destination="DAD", date="2026-10-07",
        auto_approval_limit=2_000_000
    )
    is_auth, reason, approval_req = check_authorization(
        tool_name="book_seat",
        tool_args={"flight_code": "QH-118", "passenger_name": "NGUYEN VAN A"},
        constraints=constraints_high_limit,
    )
    print(f"-> Được phép chạy ngay? : {is_auth}")
    assert is_auth is True, "Lỗi: Chuyến vé hoàn được trong hạn mức phải được thông qua!"
    print("✅ Guardrail Pre-execution kiểm soát quyền hạn hoàn hảo!")


def test_layer_4_loop_and_handoff():
    print("\n" + "=" * 78)
    print("TEST LỚP 4: PHÁT HIỆN LẶP & BÀN GIAO (LOOP DETECTOR & HANDOFF)")
    print("=" * 78)

    det = LoopDetector(window=6, repeat_k=2)
    history_calls = []

    # Giả lập Agent bị kẹt: gọi check_seat liên tục cho chuyến VJ-602 (đã hết chỗ)
    print("Giả lập Agent lặp lại cùng hành động check_seat('VJ-602')...")
    actions = [
        ("check_seat", {"flight_code": "VJ-602"}),
        ("check_seat", {"flight_code": "VN-122"}),
        ("check_seat", {"flight_code": "VJ-602"}),  # Trùng lần thứ 2 trong cửa sổ 6 vòng -> Báo động!
    ]

    for round_num, (tool, args) in enumerate(actions, 1):
        history_calls.append(f"{tool}({args})")
        warning = det.check(tool, args)
        print(f"[Vòng {round_num}] {tool}({args}) -> {warning or 'Bình thường'}")
        if warning:
            # Tạo báo cáo bàn giao chuẩn 4 trường
            report = ban_giao(
                ly_do=warning,
                da_thu=history_calls,
                trang_thai={"so_chuyen_da_xem": 2, "chuyen_con_cho": 1},
                cau_hoi="Chuyến VJ-602 đã hết chỗ nhưng agent liên tục kiểm tra lại. Bạn có muốn chuyển sang chuyến QH-118 không?",
            )
            print("\n" + format_handoff_report(report))
            assert "LOOP" in warning, "Lỗi: LoopDetector phải bắt được vòng lặp trùng action!"
            break

    print("✅ LoopDetector và cơ chế Handoff đã phát hiện và bàn giao thành công!")


if __name__ == "__main__":
    test_layer_1_constraints()
    test_layer_2_completion_sensor()
    test_layer_3_authorization_guardrail()
    test_layer_4_loop_and_handoff()
    print("\n" + "★" * 78)
    print("TẤT CẢ 4 LỚP HARNESS ĐÃ VƯỢT QUA KIỂM THỬ XÁC MINH ĐỘC LẬP!")
    print("★" * 78)
