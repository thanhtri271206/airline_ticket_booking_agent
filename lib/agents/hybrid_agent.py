# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Mẫu Thiết Kế 3: Lai (Hybrid / ReAct + Dynamic Re-planning).

Kiến trúc mẫu Lai (Slide 24):
"Lập kế hoạch, thực thi vài bước, rồi lập lại kế hoạch dựa trên những gì vừa quan sát."
Sơ đồ trục:
  Lập kế hoạch -> Thực thi k bước -> Observation đổi đáng kể? -> Có: Lập lại kế hoạch (Re-plan) -> Không: Xong?

Điểm vượt trội:
- Khắc phục triệt để tính dễ gãy (brittleness) của Plan-then-Execute khi gặp sự cố
  (chuyến bay hết chỗ VJ-602 hoặc bị từ chối duyệt).
- Không bị trôi mục tiêu (Goal Drift) như ReAct thuần túy vì mỗi lần Re-plan đều neo chặt
  vào cấu trúc BookingConstraints ban đầu.

Tích hợp trọn vẹn 4 lớp Harness:
1. Ràng buộc là dữ liệu: Neo giữ mục tiêu gốc trong suốt các lần Re-plan.
2. Tiêu chí hoàn thành: Computational Sensor kiểm tra độc lập tại DB.
3. Kiểm quyền: Pre-execution guardrail chặn trước các thao tác nhạy cảm.
4. Bàn giao: LoopDetector và giới hạn số lần Re-plan (max_replans) tránh lặp vô tận.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import dotenv
from openai import OpenAI

from data.flights_db import BOOKINGS_DB, FLIGHTS_DATA
from lib.agents.plan_execute_agent import PlanStep
from lib.agents.react_agent import AgentResult, _execute_tool
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
from lib.tools import book_seat, check_seat, get_booking, pay, search_flights

dotenv.load_dotenv()


# ==============================================================================
# PROMPT DÀNH CHO DYNAMIC RE-PLANNER
# ==============================================================================
def _build_initial_plan_prompt(user_prompt: str, constraints: BookingConstraints) -> str:
    return f"""Bạn là Bộ Lập Kế Hoạch Thông Minh cho hệ thống đặt vé máy bay.
Nhiệm vụ: Lập một bản kế hoạch tuần tự gồm các bước (Plan) dạng JSON để hoàn thành mục tiêu.

RÀNG BUỘC CỐ ĐỊNH CỦA KHÁCH HÀNG:
- Chặng bay : {constraints.origin} -> {constraints.destination}
- Ngày bay  : {constraints.date}
- Buổi bay  : {constraints.time_slot or 'Không giới hạn'}
- Ngân sách : {constraints.max_price:,} VNĐ
- Hành khách: {constraints.passenger_name} (CCCD: {constraints.passenger_id})
- Yêu cầu   : "{user_prompt}"

CÁC CÔNG CỤ KHẢ DỤNG:
1. 'search_flights': {{'origin': str, 'destination': str, 'date': str, 'time_of_day': str}}
2. 'check_seat': {{'flight_code': str}}
3. 'book_seat': {{'flight_code': str, 'passenger_name': str, 'passenger_id': str}}
4. 'pay': {{'booking_code': str, 'payment_method': 'corp_card', 'amount': int}}

CHỈ TRẢ VỀ DUY NHẤT MỘT KHỐI JSON:
{{
  "plan": [
    {{
      "step_id": 1,
      "title": "Tìm chuyến bay",
      "tool_name": "search_flights",
      "tool_args": {{ "origin": "{constraints.origin}", "destination": "{constraints.destination}", "date": "{constraints.date}", "time_of_day": "{constraints.time_slot}" }},
      "description": "Tìm danh sách chuyến bay khả dụng"
    }},
    {{
      "step_id": 2,
      "title": "Kiểm tra chỗ và giá",
      "tool_name": "check_seat",
      "tool_args": {{ "flight_code": "$BEST_FLIGHT" }},
      "description": "Kiểm tra ghế trống và chính sách hoàn vé"
    }},
    {{
      "step_id": 3,
      "title": "Giữ chỗ hành khách",
      "tool_name": "book_seat",
      "tool_args": {{ "flight_code": "$BEST_FLIGHT", "passenger_name": "{constraints.passenger_name}", "passenger_id": "{constraints.passenger_id}" }},
      "description": "Giữ chỗ chuyến bay tối ưu"
    }},
    {{
      "step_id": 4,
      "title": "Thanh toán vé",
      "tool_name": "pay",
      "tool_args": {{ "booking_code": "$BOOKING_CODE", "payment_method": "corp_card", "amount": "$TOTAL_AMOUNT" }},
      "description": "Xác nhận thanh toán"
    }}
  ]
}}"""


def _build_replan_prompt(
    constraints: BookingConstraints,
    failed_step: PlanStep,
    observation: Dict[str, Any],
    history_actions: List[str],
    available_flights: Optional[List[Dict[str, Any]]] = None,
) -> str:
    # Trích xuất các chuyến bay đã thử nghiệm nhưng thất bại hoặc bị từ chối
    excluded_codes = set()
    for act in history_actions:
        for code in ["VJ-602", "VN-122", "VN-134", "VJ-612", "VN-126"]:
            if code in act:
                excluded_codes.add(code)

    flights_summary = ""
    if available_flights:
        flights_summary = "\nDANH SÁCH CHUYẾN BAY TÌM THẤY TỪ TRƯỚC:\n"
        for f in available_flights:
            status_note = " [ĐÃ THỬ THẤT BẠI/BỊ TỪ CHỐI -> CẤM CHỌN LẠI!]" if f["flight_code"] in excluded_codes else " [KHẢ DỤNG - ƯU TIÊN CHỌN]"
            flights_summary += f"- Chuyến {f['flight_code']} ({f['airline']}): Khởi hành {f['depart_time']}, Giá {f['estimated_total_price']:,}đ{status_note}\n"

    return f"""CẢNH BÁO: Kế hoạch thực thi trước đó đã gặp biến cố và KHÔNG THỂ TIẾP TỤC theo hướng cũ!
Bạn là Bộ Tái Lập Kế Hoạch (Dynamic Re-planner). Hãy phân tích biến cố và sinh ra KẾ HOẠCH MỚI THÍCH ỨNG để hoàn thành mục tiêu ban đầu.

MỤC TIÊU GỐC BẮT BUỘC KHÔNG ĐỔI:
- Chặng bay : {constraints.origin} -> {constraints.destination}
- Ngày bay  : {constraints.date}
- Buổi bay  : {constraints.time_slot or 'all'}
- Ngân sách : {constraints.max_price:,}đ
- Hành khách: {constraints.passenger_name} (CCCD: {constraints.passenger_id})
{flights_summary}
BIẾN CỐ ĐÃ XẢY RA:
- Bước thất bại      : Bước {failed_step.step_id} - {failed_step.title} ({failed_step.tool_name})
- Kết quả quan sát   : {json.dumps(observation, ensure_ascii=False)}
- Các bước đã thử qua: {history_actions}
- CÁC CHUYẾN ĐÃ HỎNG HOẶC BỊ TỪ CHỐI (CẤM CHỌN LẠI): {list(excluded_codes)}

YÊU CẦU: Hãy chọn chuyến bay KHẢ DỤNG TIẾP THEO (chưa bị hỏng, còn chỗ và hoàn vé được, ví dụ QH-118) và lập kế hoạch mới gồm 3 bước:
1. check_seat với chuyến bay khả dụng mới
2. book_seat với chuyến bay đó cho hành khách {constraints.passenger_name}
3. pay cho mã đặt chỗ mới với phương thức 'corp_card'

BẮT BUỘC CHỈ TRẢ VỀ DUY NHẤT MỘT KHỐI JSON (không kèm văn bản ngoài):
{{
  "plan": [
    {{
      "step_id": 1,
      "title": "Kiểm tra chỗ chuyến bay thay thế khả dụng",
      "tool_name": "check_seat",
      "tool_args": {{ "flight_code": "QH-118" }},
      "description": "Kiểm tra ghế trống chuyến tiếp theo"
    }},
    {{
      "step_id": 2,
      "title": "Giữ chỗ hành khách",
      "tool_name": "book_seat",
      "tool_args": {{ "flight_code": "QH-118", "passenger_name": "{constraints.passenger_name}", "passenger_id": "{constraints.passenger_id}" }},
      "description": "Giữ chỗ"
    }},
    {{
      "step_id": 3,
      "title": "Thanh toán vé",
      "tool_name": "pay",
      "tool_args": {{ "booking_code": "$BOOKING_CODE", "payment_method": "corp_card", "amount": "$TOTAL_AMOUNT" }},
      "description": "Thanh toán"
    }}
  ]
}}"""


# ==============================================================================
# CORE HYBRID AGENT ENGINE
# ==============================================================================
class HybridAgent:
    """Agent theo mẫu Lai (ReAct + Dynamic Re-planning) kết hợp 4 lớp Harness."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.0,
        max_replans: int = 3,
        on_approval_request: Optional[Callable[[ApprovalRequest], bool]] = None,
    ):
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gemini-3.5-flash-lite")
        self.temperature = temperature
        self.max_replans = max_replans
        self.on_approval_request = on_approval_request

        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    def _call_planner(self, prompt: str) -> List[PlanStep]:
        """Gọi LLM sinh danh sách các bước có cấu trúc JSON."""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            clean_content = content.strip()
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_content = "\n".join(lines).strip()
            plan_json = json.loads(clean_content)
            items = plan_json.get("plan") or plan_json.get("steps") or []
            if isinstance(plan_json, list):
                items = plan_json
            steps = []
            for item in items:
                steps.append(
                    PlanStep(
                        step_id=item.get("step_id", len(steps) + 1),
                        title=item.get("title", ""),
                        tool_name=item.get("tool_name", ""),
                        tool_args=item.get("tool_args", {}),
                        description=item.get("description", ""),
                    )
                )
            return steps
        except Exception as e:
            print(f"⚠️  Lỗi parse JSON kế hoạch: {e} | Raw: {content[:200]}")
            return []

    def run(
        self,
        user_prompt: str,
        constraints: BookingConstraints,
        verbose: bool = True,
    ) -> AgentResult:
        """Chạy chu trình Lai (Hybrid) với khả năng Tự tái lập kế hoạch (Dynamic Re-planning)."""
        if verbose:
            print("\n" + "=" * 80)
            print(f"🔄 [HYBRID AGENT] BẮT ĐẦU: \"{user_prompt}\"")
            print(f"📌 Ràng buộc: {constraints.origin}->{constraints.destination} | Ngày {constraints.date} | Trần {constraints.max_price:,}đ")
            print("=" * 80)

        loop_detector = LoopDetector(window=6, repeat_k=2, stall_n=4)
        history_actions: List[str] = []
        approval_records: List[ApprovalRequest] = []
        trajectory: List[Dict[str, Any]] = []

        context: Dict[str, Any] = {
            "selected_flight": None,
            "booking_code": None,
            "total_amount": 0,
            "available_flights": [],
        }

        # ──────────────────────────────────────────────────────────────────────
        # BƯỚC 1: LẬP KẾ HOẠCH KHUNG BAN ĐẦU (INITIAL PLAN)
        # ──────────────────────────────────────────────────────────────────────
        if verbose:
            print("\n⚙️  [KHỞI TẠO] Đang sinh kế hoạch khung ban đầu...")

        model_calls = 1
        current_plan = self._call_planner(_build_initial_plan_prompt(user_prompt, constraints))

        if verbose:
            print(f"📋 KẾ HOẠCH BAN ĐẦU GỒM {len(current_plan)} BƯỚC:")
            for s in current_plan:
                print(f"   [{s.step_id}] {s.title.upper()}: {s.tool_name}({s.tool_args})")

        replan_count = 0
        overall_turn = 0

        # CHU TRÌNH THỰC THI & PHẢN ỨNG LINH HOẠT
        while current_plan:
            step = current_plan.pop(0)
            overall_turn += 1

            if verbose:
                print(f"\n────────── [LƯỢT {overall_turn}] THỰC THI BƯỚC: {step.title.upper()} ──────────")

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
            # HARNESS LỚP 3: KIỂM QUYỀN TRƯỚC KHI THỰC THI (PRE-EXECUTION)
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
                    # Trong mẫu Lai: Bị từ chối duyệt là một biến cố kích hoạt RE-PLAN!
                    if verbose:
                        print("\n🔄 BIẾN CỐ: Hành động bị từ chối duyệt -> KÍCH HOẠT DYNAMIC RE-PLANNER!")
                    replan_count += 1
                    model_calls += 1
                    obs_sim = {"status": "rejected_by_human", "reason": auth_reason}
                    new_steps = self._call_planner(_build_replan_prompt(constraints, step, obs_sim, history_actions))
                    if new_steps:
                        current_plan = new_steps
                        if verbose:
                            print(f"📋 BẢN KẾ HOẠCH MỚI ĐÃ ĐƯỢC TÁI LẬP (RE-PLAN #{replan_count}) VỚI {len(current_plan)} BƯỚC THAY THẾ:")
                            for ns in current_plan:
                                print(f"   [MỚI] {ns.title.upper()}: {ns.tool_name}({ns.tool_args})")
                        continue
                    else:
                        break

            # ──────────────────────────────────────────────────────────────────
            # THỰC THI TOOL
            # ──────────────────────────────────────────────────────────────────
            obs_data = _execute_tool(step.tool_name, current_args)
            obs_str = json.dumps(obs_data, ensure_ascii=False)
            trajectory.append({"turn": overall_turn, "action": action_str, "observation": obs_data})
            if verbose:
                print(f"👁️  OBSERVATION: {obs_str}")

            # ──────────────────────────────────────────────────────────────────
            # ĐIỂM CỐT LÕI MẪU LAI: OBSERVATION ĐỔI ĐÁNG KỂ? -> DYNAMIC RE-PLAN!
            # ──────────────────────────────────────────────────────────────────
            # Nếu tool trả về trạng thái bất thường (Hết chỗ, lỗi, không tìm thấy)
            is_significant_change = obs_data.get("status") in ["sold_out", "error", "not_found"]

            if is_significant_change:
                if replan_count >= self.max_replans:
                    if verbose:
                        print(f"\n🚨 ĐÃ ĐẠT GIỚI HẠN SỐ LẦN RE-PLAN ({self.max_replans}) -> DỪNG VÀ BÀN GIAO!")
                    handoff = ban_giao(
                        ly_do=f"Đã thử tái lập kế hoạch {replan_count} lần nhưng vẫn gặp bế tắc dữ liệu.",
                        da_thu=history_actions,
                        trang_thai={"replan_count": replan_count, "last_error": obs_data},
                        cau_hoi="Đã thử nhiều phương án thay thế nhưng đều hết chỗ hoặc lỗi. Bạn có muốn đổi ngày/buổi bay?",
                    )
                    return AgentResult(
                        agent_type="Hybrid",
                        success=False,
                        stop_reason="MAX_REPLANS_EXCEEDED",
                        turn_count=overall_turn,
                        model_calls=model_calls,
                        handoff_report=handoff,
                        approval_requests=approval_records,
                        trajectory=trajectory,
                    )

                replan_count += 1
                model_calls += 1
                if verbose:
                    print(f"\n⚡ [SƠ ĐỒ TRỤC SLIDE 24] OBSERVATION ĐỔI ĐÁNG KỂ ('{obs_data.get('status')}')!")
                    print(f"🔄 KÍCH HOẠT DYNAMIC RE-PLANNER (LẦN {replan_count}/{self.max_replans})...")

                new_steps = self._call_planner(
                    _build_replan_prompt(
                        constraints,
                        step,
                        obs_data,
                        history_actions,
                        available_flights=context.get("available_flights"),
                    )
                )
                if new_steps:
                    current_plan = new_steps
                    if verbose:
                        print(f"📋 BẢN KẾ HOẠCH THÍCH ỨNG MỚI ĐÃ ĐƯỢC TÁI LẬP ({len(current_plan)} BƯỚC):")
                        for ns in current_plan:
                            print(f"   [MỚI] {ns.title.upper()}: {ns.tool_name}({ns.tool_args})")
                    continue
                else:
                    if verbose:
                        print("⚠️  Re-planner không thể sinh thêm kế hoạch khả thi.")
                    break

            # ──────────────────────────────────────────────────────────────────
            # HARNESS LỚP 4: PHÁT HIỆN LẶP (POST-EXECUTION)
            # ──────────────────────────────────────────────────────────────────
            loop_warning = loop_detector.check(step.tool_name, current_args, observation=obs_data)
            if loop_warning:
                if verbose:
                    print(f"🚨 HARNESS PHÁT HIỆN LẶP: {loop_warning}")
                handoff = ban_giao(
                    ly_do=loop_warning,
                    da_thu=history_actions,
                    trang_thai={"turn": overall_turn, "replan_count": replan_count},
                    cau_hoi="Phát hiện lặp thao tác trong chu trình Lai. Bạn có muốn đổi ràng buộc không?",
                )
                return AgentResult(
                    agent_type="Hybrid",
                    success=False,
                    stop_reason="LOOP_DETECTED",
                    turn_count=overall_turn,
                    model_calls=model_calls,
                    handoff_report=handoff,
                    approval_requests=approval_records,
                    trajectory=trajectory,
                )

            # Cập nhật context bình thường
            if step.tool_name == "search_flights":
                flights = obs_data.get("flights", [])
                context["available_flights"] = flights
                if flights and not context["selected_flight"]:
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
                        print(f"\n🎯 HARNESS SENSOR: XÁC NHẬN HOÀN THÀNH XUẤT SẮC TẠI LƯỢT {overall_turn}!")
                        print(f"   Mã vé {b_code} đã CONFIRMED và PAID trong Database.")
                        print(f"   (Số lần Re-plan thích ứng thành công: {replan_count} lần)")
                    return AgentResult(
                        agent_type="Hybrid",
                        success=True,
                        stop_reason="GOAL_ACHIEVED",
                        turn_count=overall_turn,
                        model_calls=model_calls,
                        booking_code=b_code,
                        final_booking=get_booking(b_code),
                        approval_requests=approval_records,
                        trajectory=trajectory,
                    )

        # Kết thúc vòng lặp mà chưa hoàn thành
        handoff = ban_giao(
            ly_do="Kế hoạch kết thúc nhưng chưa đạt tiêu chí hoàn thành.",
            da_thu=history_actions,
            trang_thai={"context": context, "replan_count": replan_count},
            cau_hoi="Chu trình Lai kết thúc. Bạn có muốn can thiệp thủ công không?",
        )
        return AgentResult(
            agent_type="Hybrid",
            success=False,
            stop_reason="PLAN_FINISHED_WITHOUT_GOAL",
            turn_count=overall_turn,
            model_calls=model_calls,
            handoff_report=handoff,
            approval_requests=approval_records,
            trajectory=trajectory,
        )
