# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Mẫu Thiết Kế 2: Plan-then-Execute Agent.

Kiến trúc Plan-then-Execute (Slide 22, 23):
- Gọi Model một lần để sinh trọn vẹn bản kế hoạch tổng thể (Plan).
- Con người hoặc Harness duyệt kế hoạch trước khi chạy (Plan Review).
- Executor thực thi tuần tự từng bước trong kế hoạch.

Đánh đổi cốt lõi:
- Ưu điểm: Lộ trình rõ ràng, duyệt được trước, tiết kiệm số lần gọi Model (Slide 22).
- Nhược điểm: Kém linh hoạt khi môi trường thay đổi bất ngờ (chuyến bay hết chỗ VJ-602),
  dễ làm gãy toàn bộ chuỗi thực thi phía sau (Slide 23).

Tích hợp trọn vẹn 4 lớp Harness:
1. Ràng buộc là dữ liệu: Cung cấp trực tiếp vào prompt của Planner để lập kế hoạch chuẩn xác.
2. Tiêu chí hoàn thành: Computational Sensor kiểm tra vé sau bước thanh toán cuối cùng.
3. Kiểm quyền: Pre-execution guardrail chặn trước các bước book_seat/pay nhạy cảm.
4. Bàn giao: Báo cáo chi tiết nếu kế hoạch bị gãy giữa chừng do dữ liệu biến động.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import dotenv
from openai import OpenAI

from data.flights_db import BOOKINGS_DB, FLIGHTS_DATA
from lib.agents.react_agent import AgentResult, _execute_tool
from lib.tools import book_seat, check_seat, get_booking, pay, search_flights
from lib.harness import (
    ApprovalRequest,
    BookingConstraints,
    ban_giao,
    check_authorization,
    format_handoff_report,
    is_goal_achieved,
)

dotenv.load_dotenv()


# ==============================================================================
# CẤU TRÚC KẾ HOẠCH (STRUCTURED PLAN DEFINITION)
# ==============================================================================
@dataclass
class PlanStep:
    """Mỗi bước trong bản kế hoạch tổng thể do Planner sinh ra."""

    step_id: int
    title: str
    tool_name: str
    tool_args: Dict[str, Any]
    description: str


# ==============================================================================
# PROMPT DÀNH CHO BỘ LẬP KẾ HOẠCH (PLANNER PROMPT)
# ==============================================================================
def _build_planner_prompt(user_prompt: str, constraints: BookingConstraints) -> str:
    return f"""Bạn là Chuyên gia Lập Kế Hoạch (Planner) cho hệ thống đặt vé máy bay tự động.
Nhiệm vụ của bạn là phân tích yêu cầu của khách hàng và sinh ra một BẢN KẾ HOẠCH TUẦN TỰ (Sequential Plan) gồm đúng 4 bước theo định dạng JSON.

YÊU CẦU & RÀNG BUỘC CỦA KHÁCH HÀNG:
- Điểm đi (Origin)       : {constraints.origin}
- Điểm đến (Destination) : {constraints.destination}
- Ngày bay (Date)        : {constraints.date}
- Buổi bay (Time Slot)   : {constraints.time_slot or 'Không giới hạn'}
- Ngân sách trần         : {constraints.max_price:,} VNĐ
- Tên hành khách         : {constraints.passenger_name}
- Số CCCD/Định danh      : {constraints.passenger_id}
- Lời dặn của khách      : "{user_prompt}"

CÁC CÔNG CỤ KHẢ DỤNG:
1. 'search_flights': {{'origin': str, 'destination': str, 'date': str, 'time_of_day': str}}
2. 'check_seat': {{'flight_code': str}}
3. 'book_seat': {{'flight_code': str, 'passenger_name': str, 'passenger_id': str}}
4. 'pay': {{'booking_code': str, 'payment_method': str, 'amount': int}}

LƯU Ý QUAN TRỌNG VỀ THAM SỐ ĐỘNG:
- Với bước 'book_seat', nếu chưa biết chính xác mã chuyến bay rẻ nhất, hãy điền placeholder: {{'flight_code': '$BEST_FLIGHT'}}
- Với bước 'pay', hãy điền placeholder: {{'booking_code': '$BOOKING_CODE', 'amount': '$TOTAL_AMOUNT', 'payment_method': 'corp_card'}}

BẮT BUỘC CHỈ TRẢ VỀ DUY NHẤT MỘT KHỐI JSON (không kèm văn bản giải thích thừa nào khác) theo schema sau:
{{
  "plan": [
    {{
      "step_id": 1,
      "title": "Tìm kiếm chuyến bay",
      "tool_name": "search_flights",
      "tool_args": {{ ... }},
      "description": "Tìm các chuyến bay khớp ngày và buổi"
    }},
    {{
      "step_id": 2,
      "title": "Kiểm tra chỗ và giá chuyến bay tiềm năng",
      "tool_name": "check_seat",
      "tool_args": {{ ... }},
      "description": "Kiểm tra chi tiết ghế trống và chính sách hoàn vé"
    }},
    {{
      "step_id": 3,
      "title": "Giữ chỗ hành khách",
      "tool_name": "book_seat",
      "tool_args": {{ ... }},
      "description": "Đặt chỗ hành khách"
    }},
    {{
      "step_id": 4,
      "title": "Thanh toán vé máy bay",
      "tool_name": "pay",
      "tool_args": {{ ... }},
      "description": "Thanh toán vé bằng corp_card"
    }}
  ]
}}"""


# ==============================================================================
# CORE PLAN-THEN-EXECUTE AGENT ENGINE
# ==============================================================================
class PlanExecuteAgent:
    """Agent hoạt động theo mô hình Plan-then-Execute tích hợp 4 lớp Harness."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.0,
        on_plan_review: Optional[Callable[[List[PlanStep]], bool]] = None,
        on_approval_request: Optional[Callable[[ApprovalRequest], bool]] = None,
    ):
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gemini-3.5-flash-lite")
        self.temperature = temperature
        self.on_plan_review = on_plan_review
        self.on_approval_request = on_approval_request

        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    def generate_plan(self, user_prompt: str, constraints: BookingConstraints) -> List[PlanStep]:
        """Giai đoạn 1: Gọi Model 1 lần để sinh trọn bản kế hoạch tĩnh (Slide 22)."""
        prompt = _build_planner_prompt(user_prompt, constraints)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            plan_json = json.loads(content)
            steps = []
            for item in plan_json.get("plan", []):
                steps.append(
                    PlanStep(
                        step_id=item.get("step_id", 0),
                        title=item.get("title", ""),
                        tool_name=item.get("tool_name", ""),
                        tool_args=item.get("tool_args", {}),
                        description=item.get("description", ""),
                    )
                )
            return steps
        except Exception as e:
            # Fallback kế hoạch mặc định nếu JSON bị lỗi parse
            return [
                PlanStep(1, "Tìm chuyến bay", "search_flights", {
                    "origin": constraints.origin, "destination": constraints.destination,
                    "date": constraints.date, "time_of_day": constraints.time_slot
                }, "Tìm kiếm các chuyến bay"),
                PlanStep(2, "Kiểm tra chỗ", "check_seat", {"flight_code": "$BEST_FLIGHT"}, "Kiểm tra chuyến rẻ nhất"),
                PlanStep(3, "Giữ chỗ", "book_seat", {
                    "flight_code": "$BEST_FLIGHT", "passenger_name": constraints.passenger_name, "passenger_id": constraints.passenger_id
                }, "Giữ chỗ cho khách"),
                PlanStep(4, "Thanh toán", "pay", {
                    "booking_code": "$BOOKING_CODE", "payment_method": "corp_card", "amount": "$TOTAL_AMOUNT"
                }, "Thanh toán vé"),
            ]

    def run(
        self,
        user_prompt: str,
        constraints: BookingConstraints,
        verbose: bool = True,
    ) -> AgentResult:
        """Chạy chu trình Plan-then-Execute."""
        if verbose:
            print("\n" + "=" * 80)
            print(f"📋 [PLAN-THEN-EXECUTE AGENT] BẮT ĐẦU: \"{user_prompt}\"")
            print(f"📌 Ràng buộc: {constraints.origin}->{constraints.destination} | Ngày {constraints.date} | Trần {constraints.max_price:,}đ")
            print("=" * 80)

        # ──────────────────────────────────────────────────────────────────────
        # GIAI ĐOẠN 1: LẬP KẾ HOẠCH (PLANNING)
        # ──────────────────────────────────────────────────────────────────────
        if verbose:
            print("\n⚙️  [GIAI ĐOẠN 1: PLANNING] Đang yêu cầu Model sinh kế hoạch tổng thể...")

        model_calls = 1
        plan = self.generate_plan(user_prompt, constraints)

        if verbose:
            print(f"📋 BẢN KẾ HOẠCH TỔNG THỂ GỒM {len(plan)} BƯỚC ĐÃ ĐƯỢC THIẾT LẬP:")
            for s in plan:
                print(f"   [{s.step_id}] {s.title.upper()}: {s.tool_name}({s.tool_args})")

        # Duyệt kế hoạch (Human Review - Slide 22)
        if self.on_plan_review:
            is_plan_approved = self.on_plan_review(plan)
            if verbose:
                print(f"👤 KẾT QUẢ DUYỆT KẾ HOẠCH TRƯỚC KHI CHẠY: {'ĐỒNG Ý (APPROVED)' if is_plan_approved else 'TỪ CHỐI (REJECTED)'}")
            if not is_plan_approved:
                handoff = ban_giao(
                    ly_do="Người dùng từ chối bản kế hoạch trước khi thực thi.",
                    da_thu=[],
                    trang_thai={"plan_steps": len(plan)},
                    cau_hoi="Kế hoạch bị từ chối duyệt. Bạn có muốn sửa tiêu chí hay thay đổi lộ trình?",
                )
                return AgentResult(
                    agent_type="Plan-then-Execute",
                    success=False,
                    stop_reason="PLAN_REJECTED_BY_HUMAN",
                    turn_count=1,
                    model_calls=model_calls,
                    handoff_report=handoff,
                )

        # ──────────────────────────────────────────────────────────────────────
        # GIAI ĐOẠN 2: THỰC THI TUẦN TỰ (SEQUENTIAL EXECUTION)
        # ──────────────────────────────────────────────────────────────────────
        if verbose:
            print("\n⚡ [GIAI ĐOẠN 2: EXECUTION] Bắt đầu thực thi tuần tự các bước theo kế hoạch...")

        context: Dict[str, Any] = {
            "selected_flight": None,
            "booking_code": None,
            "total_amount": 0,
        }
        history_actions: List[str] = []
        approval_records: List[ApprovalRequest] = []
        trajectory: List[Dict[str, Any]] = []

        for step_idx, step in enumerate(plan, 1):
            if verbose:
                print(f"\n────────── THỰC THI BƯỚC {step_idx}/{len(plan)}: {step.title.upper()} ──────────")

            # Ánh xạ tham số động (Dynamic Binding)
            current_args = dict(step.tool_args)
            if current_args.get("flight_code") == "$BEST_FLIGHT" and context["selected_flight"]:
                current_args["flight_code"] = context["selected_flight"]
            if current_args.get("booking_code") == "$BOOKING_CODE" and context["booking_code"]:
                current_args["booking_code"] = context["booking_code"]
            if current_args.get("amount") == "$TOTAL_AMOUNT" and context["total_amount"]:
                current_args["amount"] = context["total_amount"]

            action_str = f"{step.tool_name}({json.dumps(current_args, ensure_ascii=False)})"
            history_actions.append(action_str)
            if verbose:
                print(f"🛠️  ACTION: {action_str}")

            # ──────────────────────────────────────────────────────────────────
            # HARNESS LỚP 3: KIỂM QUYỀN TRƯỚC KHI CHẠY TOOL (PRE-EXECUTION)
            # ──────────────────────────────────────────────────────────────────
            is_auth, auth_reason, approval_req = check_authorization(
                tool_name=step.tool_name,
                tool_args=current_args,
                constraints=constraints,
            )

            if not is_auth and approval_req:
                approval_records.append(approval_req)
                if verbose:
                    print(f"🛡️  HARNESS PRE-CHECK CẢNH BÁO: {auth_reason}")
                    print(f"    -> Phiếu duyệt: {approval_req.action_type} | Chuyến: {approval_req.flight_code} | Hoàn vé: {approval_req.is_refundable}")

                is_approved = False
                if self.on_approval_request:
                    is_approved = self.on_approval_request(approval_req)
                    if verbose:
                        print(f"    👤 QUYẾT ĐỊNH CỦA NGƯỜI DUYỆT: {'CHẤP THUẬN (APPROVED)' if is_approved else 'TỪ CHỐI (REJECTED)'}")

                if not is_approved:
                    # Trong Plan-then-Execute, khi 1 bước bị từ chối duyệt -> Cả chuỗi phía sau bị dừng!
                    handoff = ban_giao(
                        ly_do=f"Bước {step_idx} ({step.title}) bị từ chối phê duyệt ({auth_reason}).",
                        da_thu=history_actions,
                        trang_thai={"failed_step": step_idx, "context": context},
                        cau_hoi="Hành động không được phê duyệt. Bạn có muốn đổi chuyến bay khác không?",
                    )
                    if verbose:
                        print("\n" + format_handoff_report(handoff))
                    return AgentResult(
                        agent_type="Plan-then-Execute",
                        success=False,
                        stop_reason="UNAUTHORIZED_ACTION_STOP",
                        turn_count=step_idx,
                        model_calls=model_calls,
                        handoff_report=handoff,
                        approval_requests=approval_records,
                        trajectory=trajectory,
                    )

            # ──────────────────────────────────────────────────────────────────
            # THỰC THI TOOL
            # ──────────────────────────────────────────────────────────────────
            obs_data = _execute_tool(step.tool_name, current_args)
            obs_str = json.dumps(obs_data, ensure_ascii=False)
            trajectory.append({"step": step_idx, "action": action_str, "observation": obs_data})
            if verbose:
                print(f"👁️  OBSERVATION: {obs_str}")

            # ──────────────────────────────────────────────────────────────────
            # ĐÁNH ĐỔI CỦA PLAN-THEN-EXECUTE: GÃY KẾ HOẠCH NẾU GẶP SỰ CỐ (SLIDE 23)
            # ──────────────────────────────────────────────────────────────────
            # Nếu tool trả về trạng thái lỗi hoặc hết chỗ -> Kế hoạch tĩnh bị gãy vì các bước sau không thể chạy tiếp!
            if obs_data.get("status") in ["sold_out", "error", "not_found"]:
                if verbose:
                    print(f"\n💥 KẾ HOẠCH BỊ GÃY TẠI BƯỚC {step_idx}!")
                    print(f"   Lý do: Quan sát trả về trạng thái bất thường '{obs_data.get('status')}'.")
                    print(f"   Kế hoạch tĩnh không có khả năng tự đổi hướng như ReAct (Slide 23).")

                handoff = ban_giao(
                    ly_do=f"Kế hoạch tĩnh bị gãy tại bước {step_idx} ({step.title}): {obs_data.get('hint', 'Dữ liệu bất thường')}",
                    da_thu=history_actions,
                    trang_thai={"failed_step": step_idx, "last_observation": obs_data},
                    cau_hoi="Chuyến bay trong kế hoạch đã hết chỗ/lỗi. Bạn có muốn chuyển sang mẫu ReAct/Lai để tự thích nghi không?",
                )
                if verbose:
                    print("\n" + format_handoff_report(handoff))
                return AgentResult(
                    agent_type="Plan-then-Execute",
                    success=False,
                    stop_reason="PLAN_EXECUTION_BROKEN",
                    turn_count=step_idx,
                    model_calls=model_calls,
                    handoff_report=handoff,
                    approval_requests=approval_records,
                    trajectory=trajectory,
                )

            # Cập nhật context cho bước sau
            if step.tool_name == "search_flights":
                flights = obs_data.get("flights", [])
                if flights:
                    # Nếu bước 2 chưa chỉ định rõ chuyến, ưu tiên chuyến đầu tiên
                    if not context["selected_flight"]:
                        context["selected_flight"] = flights[0]["flight_code"]
                        context["total_amount"] = flights[0].get("estimated_total_price", 0)

            elif step.tool_name == "check_seat":
                context["selected_flight"] = obs_data.get("flight_code")
                context["total_amount"] = obs_data.get("total_price", 0)

            elif step.tool_name == "book_seat":
                context["booking_code"] = obs_data.get("booking_code")
                context["total_amount"] = obs_data.get("total_amount", context["total_amount"])

            elif step.tool_name == "pay":
                # ──────────────────────────────────────────────────────────────
                # HARNESS LỚP 2: TIÊU CHÍ HOÀN THÀNH KIỂM BẰNG CODE
                # ──────────────────────────────────────────────────────────────
                b_code = context["booking_code"]
                achieved, details = is_goal_achieved(b_code, constraints)
                if achieved:
                    if verbose:
                        print(f"\n🎯 HARNESS SENSOR: XÁC NHẬN HOÀN THÀNH KẾ HOẠCH XUẤT SẮC TẠI BƯỚC {step_idx}!")
                        print(f"   Mã vé {b_code} đã CONFIRMED và PAID trong Database.")
                    return AgentResult(
                        agent_type="Plan-then-Execute",
                        success=True,
                        stop_reason="GOAL_ACHIEVED",
                        turn_count=step_idx,
                        model_calls=model_calls,
                        booking_code=b_code,
                        final_booking=get_booking(b_code),
                        approval_requests=approval_records,
                        trajectory=trajectory,
                    )

        # Kết thúc toàn bộ bước mà chưa xác nhận hoàn thành
        handoff = ban_giao(
            ly_do="Đã chạy hết tất cả các bước trong kế hoạch nhưng chưa đạt tiêu chí hoàn thành.",
            da_thu=history_actions,
            trang_thai={"context": context},
            cau_hoi="Kế hoạch kết thúc nhưng vé chưa xác nhận. Bạn có muốn kiểm tra lại không?",
        )
        return AgentResult(
            agent_type="Plan-then-Execute",
            success=False,
            stop_reason="PLAN_FINISHED_WITHOUT_GOAL",
            turn_count=len(plan),
            model_calls=model_calls,
            handoff_report=handoff,
            approval_requests=approval_records,
            trajectory=trajectory,
        )
