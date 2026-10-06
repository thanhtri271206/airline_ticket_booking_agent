# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Kịch Bản Kiểm Thử Mẫu Lai (test_hybrid_agent.py).

Kiểm thử kịch bản cốt lõi thể hiện ưu thế vượt trội của mẫu Lai (Slide 24):
- Tình huống chuyến bay rẻ nhất VJ-602 bị HẾT CHỖ (Sold-Out Edge Case).
- Trong khi Plan-then-Execute bị gãy và dừng lại, mẫu Lai phát hiện "Observation đổi đáng kể",
  kích hoạt Dynamic Re-planner để lập lại kế hoạch thích ứng và hoàn tất đặt vé thành công!

Chạy lệnh:
    uv run python test_hybrid_agent.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.flights_db import reset_mock_db
from lib.agents.hybrid_agent import HybridAgent
from lib.harness import BookingConstraints


def test_hybrid_adaptive_replanning():
    print("\n" + "█" * 80)
    print("KỊCH BẢN KIỂM THỬ MẪU LAI: TỰ THÍCH ỨNG BẰNG DYNAMIC RE-PLANNING (SLIDE 24)")
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
        auto_approval_limit=2_000_000,
    )

    prompt = (
        "Chào bạn, hãy đặt giúp tôi chuyến bay rẻ nhất từ SGN đi DAD vào sáng ngày 07/10/2026 "
        "dưới 2 triệu cho khách NGUYEN VAN A. Nếu chuyến bay rẻ nhất hết chỗ, hãy tự động lập lại "
        "kế hoạch để đặt chuyến bay tiếp theo còn chỗ và an toàn giúp tôi."
    )

    agent = HybridAgent(temperature=0.0, max_replans=3)
    result = agent.run(user_prompt=prompt, constraints=constraints, verbose=True)

    print("\n" + "─" * 80)
    print("📊 TỔNG KẾT KẾT QUẢ MẪU LAI (HYBRID AGENT):")
    print(f"  • Thành công (Success)     : {result.success}")
    print(f"  • Lý do dừng (Stop Reason) : {result.stop_reason}")
    print(f"  • Số lượt thực thi (Turns) : {result.turn_count}")
    print(f"  • Số lần gọi LLM (Calls)   : {result.model_calls} (1 lần Initial Plan + 1 lần Re-plan thích ứng)")
    print(f"  • Mã đặt chỗ (Booking Code): {result.booking_code}")
    if result.final_booking:
        print(f"  • Trạng thái DB xác nhận   : Status={result.final_booking['status']} | Paid={result.final_booking['paid']} | Giá={result.final_booking['total_price']:,}đ | Chuyến={result.final_booking['flight_code']}")

    assert result.success is True, "Mẫu Lai phải vượt qua được tình huống hết chỗ nhờ Re-planning!"
    assert result.final_booking["paid"] is True, "Vé phải được xác nhận thanh toán thành công!"


if __name__ == "__main__":
    test_hybrid_adaptive_replanning()
    print("\n" + "★" * 80)
    print("HOÀN TẤT KIỂM THỬ MẪU LAI: CHỨNG MINH THÀNH CÔNG NGUYÊN LÝ SLIDE 24!")
    print("★" * 80)
