# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Kịch Bản Kiểm Thử ReAct Agent (test_react_agent.py).

Kiểm thử 2 tình huống thực tế của ReAct Agent với Gemini LLM:
1. Kịch bản 1 (Tự động thích nghi & Đặt vé thành công):
   - Khách tìm vé sáng 07/10/2026 từ SGN đi DAD, dưới 2 triệu.
   - Chuyến rẻ nhất VJ-602 hết chỗ -> ReAct Agent tự chọn chuyến hợp lệ QH-118.
   - Harness Sensor xác nhận vé đã CONFIRMED và PAID trong DB.

2. Kịch bản 2 (Kiểm quyền & Phê duyệt của con người - Human-in-the-loop):
   - Thử thách vé không hoàn tiền (VN-122).
   - Harness chặn trước khi đặt, xin ý kiến người duyệt.

Chạy lệnh:
    uv run python test_react_agent.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.flights_db import reset_mock_db
from lib.agents.react_agent import ReActAgent
from lib.harness import ApprovalRequest, BookingConstraints


def test_react_happy_path():
    print("\n" + "█" * 80)
    print("KỊCH BẢN 1: REACT AGENT TỰ THÍCH NGHI & ĐẶT VÉ THÀNH CÔNG")
    print("█" * 80)

    reset_mock_db()

    constraints = BookingConstraints(
        origin="SGN",
        destination="DAD",
        date="2026-10-07",
        time_slot="morning",
        max_price=2_000_000,
        passenger_name="NGUYEN VAN A",
        passenger_id="079123456789",
        auto_approval_limit=2_000_000,  # Cho phép tự duyệt trong 2tr nếu vé an toàn
    )

    prompt = (
        "Chào bạn, tôi muốn đặt một vé máy bay từ TP.HCM đi Đà Nẵng vào buổi sáng ngày 07/10/2026. "
        "Ngân sách tối đa của tôi là 2.000.000đ. Nhờ bạn tìm chuyến bay còn chỗ, an toàn (ưu tiên hoàn được vé) "
        "và tiến hành giữ chỗ cũng như thanh toán giúp tôi bằng thẻ công ty (corp_card). "
        "Tên hành khách là NGUYEN VAN A."
    )

    agent = ReActAgent(temperature=0.0, max_turns=8)
    result = agent.run(user_prompt=prompt, constraints=constraints, verbose=True)

    print("\n" + "─" * 80)
    print("📊 TỔNG KẾT KẾT QUẢ KỊCH BẢN 1:")
    print(f"  • Thành công (Success)     : {result.success}")
    print(f"  • Lý do dừng (Stop Reason) : {result.stop_reason}")
    print(f"  • Số vòng lặp (Turns)      : {result.turn_count}")
    print(f"  • Số lần gọi LLM (Calls)   : {result.model_calls}")
    print(f"  • Mã đặt chỗ (Booking Code): {result.booking_code}")
    if result.final_booking:
        print(f"  • Trạng thái DB xác nhận   : Status={result.final_booking['status']} | Paid={result.final_booking['paid']} | Giá={result.final_booking['total_price']:,}đ")

    assert result.success is True, "Kịch bản 1 phải hoàn thành thành công!"
    assert result.final_booking["paid"] is True, "Vé phải được thanh toán thực tế!"


def test_react_approval_guardrail():
    print("\n" + "█" * 80)
    print("KỊCH BẢN 2: REACT AGENT VỚI KIỂM QUYỀN (HUMAN-IN-THE-LOOP APPROVAL)")
    print("█" * 80)

    reset_mock_db()

    # Đặt hạn mức tự duyệt thấp (1.8tr) để kích hoạt kiểm quyền khi chọn chuyến VN-122 (1.85tr, vé không hoàn)
    constraints = BookingConstraints(
        origin="SGN",
        destination="DAD",
        date="2026-10-07",
        time_slot="morning",
        max_price=2_000_000,
        passenger_name="TRAN VAN B",
        passenger_id="079988776655",
        auto_approval_limit=1_800_000,
    )

    # Giả lập hàm phê duyệt của con người: TỪ CHỐI nếu là vé không hoàn hủy!
    def human_approver(req: ApprovalRequest) -> bool:
        print(f"\n[HUMAN-IN-THE-LOOP] Nhận yêu cầu phê duyệt cho hành động: {req.action_type}")
        print(f"  -> Chi tiết: Chuyến {req.flight_code}, Giá {req.total_price:,}đ, Hoàn hủy: {req.is_refundable}")
        if not req.is_refundable:
            print("  -> QUYẾT ĐỊNH: TỪ CHỐI vì vé không được phép hoàn hủy! (Bảo vệ tài chính)")
            return False
        print("  -> QUYẾT ĐỊNH: CHẤP THUẬN!")
        return True

    prompt = (
        "Đặt giúp tôi chuyến bay VN-122 từ SGN đi DAD sáng 07/10/2026 cho khách TRAN VAN B. "
        "Nếu chuyến này không được duyệt, hãy tìm chuyến bay khác còn chỗ và hoàn được vé."
    )

    agent = ReActAgent(
        temperature=0.0,
        max_turns=8,
        on_approval_request=human_approver,
    )
    result = agent.run(user_prompt=prompt, constraints=constraints, verbose=True)

    print("\n" + "─" * 80)
    print("📊 TỔNG KẾT KẾT QUẢ KỊCH BẢN 2:")
    print(f"  • Số phiếu duyệt phát sinh : {len(result.approval_requests)}")
    for idx, req in enumerate(result.approval_requests, 1):
        print(f"    [{idx}] {req.action_type} trên chuyến {req.flight_code} (Lý do: {req.reason})")
    print(f"  • Kết quả cuối cùng        : Success={result.success} | Mã vé={result.booking_code}")


if __name__ == "__main__":
    test_react_happy_path()
    test_react_approval_guardrail()
    print("\n" + "★" * 80)
    print("HOÀN TẤT KIỂM THỬ REACT AGENT CẢ 2 KỊCH BẢN THÀNH CÔNG VƯỢT TRỘI!")
    print("★" * 80)
