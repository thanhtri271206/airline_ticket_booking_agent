# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Kịch Bản Kiểm Thử Plan-then-Execute Agent (test_plan_execute_agent.py).

Kiểm thử 2 tình huống phản ánh đúng ưu/nhược điểm theo Slide 22, 23:
1. Kịch bản 1 (Ưu điểm - Happy Path):
   - Kế hoạch rõ ràng, được duyệt trước (Human Review), chỉ tốn 1 lần gọi LLM.
   - Thực thi thành công vé QH-118.
2. Kịch bản 2 (Nhược điểm - Gãy kế hoạch khi gặp biến cố):
   - Kế hoạch tĩnh chọn chuyến rẻ nhất VJ-602.
   - Thực tế VJ-602 bị HẾT CHỖ -> Kế hoạch bị gãy tại bước 2.
   - Harness kích hoạt Handoff bàn giao an toàn cho con người.

Chạy lệnh:
    uv run python test_plan_execute_agent.py
"""

import os
import sys
from typing import List

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.flights_db import reset_mock_db
from lib.agents.plan_execute_agent import PlanExecuteAgent, PlanStep
from lib.harness import BookingConstraints


def test_plan_execute_happy_path():
    print("\n" + "█" * 80)
    print("KỊCH BẢN 1: PLAN-THEN-EXECUTE THÀNH CÔNG VỚI DUYỆT KẾ HOẠCH TRƯỚC")
    print("█" * 80)

    reset_mock_db()

    constraints = BookingConstraints(
        origin="SGN",
        destination="DAD",
        date="2026-10-07",
        time_slot="morning",
        max_price=2_000_000,
        passenger_name="LE VAN C",
        passenger_id="079112233445",
        auto_approval_limit=2_000_000,
    )

    prompt = (
        "Lập kế hoạch và đặt giúp tôi vé máy bay chuyến QH-118 từ TP.HCM đi Đà Nẵng "
        "sáng 07/10/2026 cho khách LE VAN C. Thanh toán bằng corp_card."
    )

    # Giả lập duyệt kế hoạch trước khi chạy (Human Review - Slide 22)
    def plan_reviewer(plan: List[PlanStep]) -> bool:
        print("\n[HUMAN REVIEW] Xem xét toàn bộ lộ trình kế hoạch:")
        for s in plan:
            print(f"  ✓ Bước {s.step_id}: {s.title} ({s.tool_name})")
        print("  -> QUYẾT ĐỊNH: ĐỒNG Ý CHO PHÉP THỰC THI TOÀN BỘ KẾ HOẠCH!")
        return True

    agent = PlanExecuteAgent(on_plan_review=plan_reviewer)
    result = agent.run(user_prompt=prompt, constraints=constraints, verbose=True)

    print("\n" + "─" * 80)
    print("📊 TỔNG KẾT KẾT QUẢ KỊCH BẢN 1:")
    print(f"  • Thành công (Success)     : {result.success}")
    print(f"  • Lý do dừng (Stop Reason) : {result.stop_reason}")
    print(f"  • Số bước thực thi (Steps) : {result.turn_count}")
    print(f"  • Số lần gọi LLM (Calls)   : {result.model_calls} (CỰC KỲ TIẾT KIỆM: chỉ gọi 1 lần Planner!)")
    print(f"  • Mã đặt chỗ (Booking Code): {result.booking_code}")

    assert result.success is True, "Kịch bản 1 phải hoàn thành thành công!"
    assert result.model_calls == 1, "Plan-then-Execute chỉ gọi LLM đúng 1 lần cho bước lập kế hoạch!"


def test_plan_execute_brittleness_failure():
    print("\n" + "█" * 80)
    print("KỊCH BẢN 2: THỰC NGHIỆM TÍNH DỄ GÃY CỦA KẾ HOẠCH TĨNH (PLAN BRITTLENESS)")
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
    )

    prompt = (
        "Hãy đặt vé máy bay rẻ nhất sáng 07/10/2026 từ SGN đi DAD cho NGUYEN VAN A. "
        "Hãy chọn chuyến bay rẻ nhất tìm được."
    )

    agent = PlanExecuteAgent()
    result = agent.run(user_prompt=prompt, constraints=constraints, verbose=True)

    print("\n" + "─" * 80)
    print("📊 TỔNG KẾT KẾT QUẢ KỊCH BẢN 2:")
    print(f"  • Thành công (Success)     : {result.success} (Kế hoạch bị gãy do chuyến rẻ nhất VJ-602 hết chỗ)")
    print(f"  • Lý do dừng (Stop Reason) : {result.stop_reason}")
    print(f"  • Bàn giao Harness kích hoạt: {'CÓ' if result.handoff_report else 'KHÔNG'}")
    if result.handoff_report:
        print(f"    Lý do bàn giao: {result.handoff_report['stop_reason']}")
        print(f"    Hỏi người dùng : {result.handoff_report['cau_hoi_cho_nguoi']}")

    assert result.success is False, "Kế hoạch tĩnh bị gãy khi gặp vé hết chỗ, không thể tự thích nghi!"
    assert result.stop_reason == "PLAN_EXECUTION_BROKEN"
    assert result.handoff_report is not None, "Harness phải tạo gói bàn giao khi kế hoạch gãy!"


if __name__ == "__main__":
    test_plan_execute_happy_path()
    test_plan_execute_brittleness_failure()
    print("\n" + "★" * 80)
    print("HOÀN TẤT KIỂM THỬ PLAN-THEN-EXECUTE: TÁI HIỆN CHUẨN XÁC ĐẶC TÍNH SLIDE 22 & 23!")
    print("★" * 80)
