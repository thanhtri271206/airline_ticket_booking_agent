# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Mẫu Thiết Kế 1: ReAct Agent (Reasoning + Acting).

Kiến trúc ReAct (Yao et al., 2022) kết hợp chu trình:
  Suy luận (Thought) -> Hành động (Action) -> Quan sát (Observation) -> Suy luận tiếp...

Tích hợp trọn vẹn 4 lớp Harness:
1. Ràng buộc là dữ liệu: Giữ cố định BookingConstraints, chống trôi mục tiêu (Slide 60, 62).
2. Tiêu chí hoàn thành: Computational Sensor độc lập kiểm chứng qua DB (Slide 43, 44).
3. Kiểm quyền: Pre-execution guardrail chặn trước khi gọi tool (Slide 41, 504).
4. Bàn giao: LoopDetector bắt lặp/bế tắc và tạo báo cáo chuẩn 4 trường (Slide 45, 48).
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import dotenv
from openai import OpenAI

from data.flights_db import BOOKINGS_DB, FLIGHTS_DATA
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
# SCHEMA CÔNG CỤ THEO CHUẨN OPENAI-COMPATIBLE
# ==============================================================================
OPENAI_FLIGHT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Tìm kiếm danh sách chuyến bay theo điểm đi, điểm đến, ngày bay và buổi bay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Điểm đi (vd: 'SGN', 'TP.HCM')"},
                    "destination": {"type": "string", "description": "Điểm đến (vd: 'DAD', 'Đà Nẵng')"},
                    "date": {"type": "string", "description": "Ngày bay định dạng 'YYYY-MM-DD' (vd: '2026-10-07')"},
                    "time_of_day": {
                        "type": "string",
                        "enum": ["morning", "afternoon", "evening", "all"],
                        "description": "Buổi bay mong muốn ('morning', 'afternoon', 'evening')",
                    },
                },
                "required": ["origin", "destination", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_seat",
            "description": "Kiểm tra số ghế trống thực tế, chi tiết giá và chính sách hoàn hủy của một chuyến bay cụ thể.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_code": {"type": "string", "description": "Mã chuyến bay (vd: 'VN-122', 'QH-118', 'VJ-602')"}
                },
                "required": ["flight_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_seat",
            "description": "Thực hiện giữ chỗ hành khách trên chuyến bay, tạo mã đặt chỗ PNR ở trạng thái 'held'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_code": {"type": "string", "description": "Mã chuyến bay chọn đặt"},
                    "passenger_name": {"type": "string", "description": "Họ và tên hành khách (viết hoa không dấu hoặc có dấu)"},
                    "passenger_id": {"type": "string", "description": "Số CMND/CCCD hoặc mã định danh của hành khách"},
                },
                "required": ["flight_code", "passenger_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pay",
            "description": "Thực hiện thanh toán tiền vé máy bay cho mã đặt chỗ đã giữ chỗ, chuyển trạng thái sang 'confirmed'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_code": {"type": "string", "description": "Mã đặt chỗ PNR nhận từ book_seat (vd: 'BK-4XJ2')"},
                    "payment_method": {"type": "string", "description": "Phương thức thanh toán (vd: 'corp_card', 'bank_transfer')"},
                    "amount": {"type": "integer", "description": "Số tiền thanh toán (phải khớp đúng giá vé)"},
                },
                "required": ["booking_code", "payment_method", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_booking",
            "description": "Tra cứu trạng thái thực tế của vé từ cơ sở dữ liệu hệ thống.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_code": {"type": "string", "description": "Mã đặt chỗ cần tra cứu"}
                },
                "required": ["booking_code"],
            },
        },
    },
]

TOOL_MAP = {
    "search_flights": search_flights,
    "check_seat": check_seat,
    "book_seat": book_seat,
    "pay": pay,
    "get_booking": get_booking,
}


def _execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Thực thi tool Python nội bộ."""
    fn = TOOL_MAP.get(name)
    if not fn:
        return {"status": "error", "error_code": "tool_not_found", "hint": f"Không có tool '{name}'"}
    try:
        return fn(**args)
    except Exception as e:
        return {"status": "error", "error_code": "execution_failed", "details": str(e)}


# ==============================================================================
# KẾT QUẢ THỰC THI (AGENT RESULT)
# ==============================================================================
@dataclass
class AgentResult:
    """Đóng gói toàn bộ kết quả thực thi phục vụ Benchmark & Báo cáo."""

    agent_type: str  # 'ReAct', 'Plan-then-Execute', 'Hybrid'
    success: bool  # Đạt tiêu chí kiểm chứng khách quan hay chưa
    stop_reason: str  # Lý do dừng (GOAL_ACHIEVED, LOOP_DETECTED, BUDGET_EXCEEDED...)
    turn_count: int  # Số vòng lặp đã chạy
    model_calls: int  # Số lần gọi LLM
    booking_code: Optional[str] = None
    final_booking: Optional[Dict[str, Any]] = None
    handoff_report: Optional[Dict[str, Any]] = None
    approval_requests: List[ApprovalRequest] = field(default_factory=list)
    trajectory: List[Dict[str, Any]] = field(default_factory=list)


# ==============================================================================
# PROMPT HỆ THỐNG
# ==============================================================================
def _build_react_system_prompt(constraints: BookingConstraints) -> str:
    return f"""Bạn là Trợ lý AI chuyên nghiệp phụ trách đặt vé máy bay theo mô hình ReAct (Reasoning + Acting).
Ở mỗi lượt, hãy phân tích kỹ tình huống, đề xuất gọi tool phù hợp, quan sát kết quả rồi thực hiện bước kế tiếp.

RÀNG BUỘC CỐ ĐỊNH CỦA KHÁCH HÀNG (BẮT BUỘC TUÂN THỦ):
- Điểm đi (Origin)       : {constraints.origin}
- Điểm đến (Destination) : {constraints.destination}
- Ngày bay (Date)        : {constraints.date}
- Buổi bay (Time Slot)   : {constraints.time_slot or 'Không giới hạn'}
- Ngân sách tối đa       : {constraints.max_price:,} VNĐ
- Tên hành khách         : {constraints.passenger_name}
- Số CCCD/Định danh      : {constraints.passenger_id}

QUY TRÌNH THỰC HIỆN BẮT BUỘC:
1. Gọi 'search_flights' để tìm danh sách chuyến bay khớp ngày và buổi.
2. Với các chuyến tìm thấy, gọi 'check_seat' để xem số ghế trống và chính sách hoàn vé.
   - NÉ TRÁNH các chuyến đã hết chỗ (available_seats = 0).
   - NÉ TRÁNH các chuyến vượt ngân sách {constraints.max_price:,}đ.
   - ƯU TIÊN chuyến bay còn chỗ, trong ngân sách và có thể hoàn hủy (refundable = True).
3. Gọi 'book_seat' để giữ chỗ cho hành khách {constraints.passenger_name}.
4. Gọi 'pay' để thanh toán vé qua 'corp_card' với đúng số tiền vé.

LƯU Ý: Không tự bịa đặt thông tin. Chỉ dựa vào dữ liệu trả về từ công cụ."""


# ==============================================================================
# CORE REACT AGENT ENGINE
# ==============================================================================
class ReActAgent:
    """ReAct Agent hoàn chỉnh bọc bởi 4 lớp Harness, hỗ trợ OpenAI-compatible endpoint."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.0,
        max_turns: int = 8,
        on_approval_request: Optional[Callable[[ApprovalRequest], bool]] = None,
    ):
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gemini-3.5-flash-lite")
        self.max_turns = max_turns
        self.temperature = temperature
        self.on_approval_request = on_approval_request

        # Khởi tạo client OpenAI tương thích với Google Gemini v1beta OpenAI endpoint
        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )

    def run(
        self,
        user_prompt: str,
        constraints: BookingConstraints,
        verbose: bool = True,
    ) -> AgentResult:
        """Chạy chu trình ReAct hoàn chỉnh."""
        if verbose:
            print("\n" + "=" * 80)
            print(f"🚀 [REACT AGENT] BẮT ĐẦU: \"{user_prompt}\"")
            print(f"📌 Ràng buộc: {constraints.origin}->{constraints.destination} | Ngày {constraints.date} | Trần {constraints.max_price:,}đ")
            print("=" * 80)

        loop_detector = LoopDetector(window=6, repeat_k=2, stall_n=4)
        history_actions: List[str] = []
        approval_records: List[ApprovalRequest] = []
        trajectory: List[Dict[str, Any]] = []

        # Khởi tạo lịch sử tin nhắn
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _build_react_system_prompt(constraints)},
            {"role": "user", "content": user_prompt},
        ]

        model_calls = 0
        current_booking_code = None

        # VÒNG LẶP REACT
        for turn in range(1, self.max_turns + 1):
            if verbose:
                print(f"\n────────── [VÒNG {turn}/{self.max_turns}] SUY LUẬN & HÀNH ĐỘNG ──────────")

            # 1. GỌI MODEL SINH BƯỚC TIẾP THEO
            model_calls += 1
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=OPENAI_FLIGHT_TOOLS,
                temperature=self.temperature,
            )

            assistant_msg_obj = response.choices[0].message
            thought_text = assistant_msg_obj.content or "(Model không xuất lời giải thích, đề xuất gọi tool trực tiếp)"
            if verbose:
                print(f"🧠 THOUGHT: {thought_text.strip()}")

            raw_tool_calls = assistant_msg_obj.tool_calls

            # TRƯỜNG HỢP A: Model KHÔNG gọi tool nữa -> Tự kết thúc
            if not raw_tool_calls:
                if verbose:
                    print("🛑 Model dừng gọi tool và trả lời kết thúc.")

                # Harness Lớp 2: Kiểm chứng hoàn thành độc lập bằng code
                if current_booking_code:
                    achieved, details = is_goal_achieved(current_booking_code, constraints)
                    if achieved:
                        if verbose:
                            print(f"🎯 HARNESS SENSOR: XÁC NHẬN HOÀN THÀNH 100%! (Mã vé {current_booking_code})")
                        return AgentResult(
                            agent_type="ReAct",
                            success=True,
                            stop_reason="GOAL_ACHIEVED",
                            turn_count=turn,
                            model_calls=model_calls,
                            booking_code=current_booking_code,
                            final_booking=get_booking(current_booking_code),
                            approval_requests=approval_records,
                            trajectory=trajectory,
                        )

                handoff = ban_giao(
                    ly_do="Model kết thúc nhưng chưa hoàn tất đặt và thanh toán vé.",
                    da_thu=history_actions,
                    trang_thai={"booking_code": current_booking_code, "model_calls": model_calls},
                    cau_hoi="Model dừng sớm trước khi có vé confirmed. Bạn có muốn tiếp tục không?",
                )
                if verbose:
                    print("\n" + format_handoff_report(handoff))
                return AgentResult(
                    agent_type="ReAct",
                    success=False,
                    stop_reason="EARLY_EXIT_WITHOUT_COMPLETION",
                    turn_count=turn,
                    model_calls=model_calls,
                    booking_code=current_booking_code,
                    handoff_report=handoff,
                    approval_requests=approval_records,
                    trajectory=trajectory,
                )

            # TRƯỜNG HỢP B: Model ĐỀ XUẤT CÁC TOOL CALLS
            # Lưu trữ assistant message chuẩn, BẢO TOÀN thought_signature của Google Gemini
            cleaned_tool_calls = []
            for tc in raw_tool_calls:
                tc_dict = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                # Bảo toàn extra_content chứa thought_signature nếu có từ Google Gemini
                if hasattr(tc, "extra_content") and tc.extra_content:
                    tc_dict["extra_content"] = tc.extra_content
                cleaned_tool_calls.append(tc_dict)

            assistant_msg_dict = {
                "role": "assistant",
                "tool_calls": cleaned_tool_calls,
            }
            if assistant_msg_obj.content:
                assistant_msg_dict["content"] = assistant_msg_obj.content
            messages.append(assistant_msg_dict)

            # Xử lý từng tool call
            for tc in raw_tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except Exception:
                    tool_args = {}

                action_str = f"{tool_name}({json.dumps(tool_args, ensure_ascii=False)})"
                history_actions.append(action_str)
                if verbose:
                    print(f"🛠️  ACTION: {action_str}")

                # ──────────────────────────────────────────────────────────────
                # HARNESS LỚP 3: KIỂM QUYỀN TRƯỚC KHI THỰC THI (PRE-EXECUTION)
                # ──────────────────────────────────────────────────────────────
                is_auth, auth_reason, approval_req = check_authorization(
                    tool_name=tool_name,
                    tool_args=tool_args,
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
                        obs_content = {
                            "status": "rejected_by_human",
                            "reason": auth_reason,
                            "hint": "Người dùng KHÔNG duyệt chuyến bay này (do vé không hoàn tiền hoặc vượt hạn mức). Hãy chọn chuyến bay khác còn chỗ và an toàn!",
                        }
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(obs_content, ensure_ascii=False),
                        })
                        trajectory.append({"turn": turn, "action": action_str, "observation": obs_content, "authorized": False})
                        if verbose:
                            print(f"👁️  OBSERVATION: {json.dumps(obs_content, ensure_ascii=False)}")
                        continue

                # ──────────────────────────────────────────────────────────────
                # THỰC THI TOOL AN TOÀN
                # ──────────────────────────────────────────────────────────────
                obs_data = _execute_tool(tool_name, tool_args)
                obs_str = json.dumps(obs_data, ensure_ascii=False)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": obs_str,
                })
                if verbose:
                    print(f"👁️  OBSERVATION: {obs_str}")

                trajectory.append({"turn": turn, "action": action_str, "observation": obs_data, "authorized": True})

                if tool_name == "book_seat" and obs_data.get("status") == "held":
                    current_booking_code = obs_data.get("booking_code")

                # ──────────────────────────────────────────────────────────────
                # HARNESS LỚP 4: PHÁT HIỆN LẶP (POST-EXECUTION)
                # ──────────────────────────────────────────────────────────────
                loop_warning = loop_detector.check(tool_name, tool_args, observation=obs_data)
                if loop_warning:
                    if verbose:
                        print(f"🚨 HARNESS PHÁT HIỆN LẶP: {loop_warning}")
                    handoff = ban_giao(
                        ly_do=loop_warning,
                        da_thu=history_actions,
                        trang_thai={"so_hanh_dong": len(history_actions), "booking_code": current_booking_code},
                        cau_hoi="Agent bị lặp hành động. Bạn có muốn đổi điều kiện tìm kiếm không?",
                    )
                    if verbose:
                        print("\n" + format_handoff_report(handoff))
                    return AgentResult(
                        agent_type="ReAct",
                        success=False,
                        stop_reason="LOOP_DETECTED",
                        turn_count=turn,
                        model_calls=model_calls,
                        booking_code=current_booking_code,
                        handoff_report=handoff,
                        approval_requests=approval_records,
                        trajectory=trajectory,
                    )

                # ──────────────────────────────────────────────────────────────
                # HARNESS LỚP 2: TIÊU CHÍ HOÀN THÀNH KIỂM BẰNG CODE (POST-EXECUTION)
                # ──────────────────────────────────────────────────────────────
                if tool_name == "pay" and current_booking_code:
                    achieved, details = is_goal_achieved(current_booking_code, constraints)
                    if achieved:
                        if verbose:
                            print(f"\n🎯 HARNESS SENSOR: XÁC NHẬN HOÀN TẤT THÀNH CÔNG TẠI VÒNG {turn}!")
                            print(f"   Mã vé {current_booking_code} đã CONFIRMED và PAID trong Database.")
                        return AgentResult(
                            agent_type="ReAct",
                            success=True,
                            stop_reason="GOAL_ACHIEVED",
                            turn_count=turn,
                            model_calls=model_calls,
                            booking_code=current_booking_code,
                            final_booking=get_booking(current_booking_code),
                            approval_requests=approval_records,
                            trajectory=trajectory,
                        )

        # NẾU HẾT NGÂN SÁCH
        handoff = ban_giao(
            ly_do=f"Đã chạm trần ngân sách {self.max_turns} vòng lặp mà chưa hoàn tất.",
            da_thu=history_actions,
            trang_thai={"model_calls": model_calls, "booking_code": current_booking_code},
            cau_hoi="Hết ngân sách vòng lặp. Bạn có muốn tăng giới hạn hay tiếp quản?",
        )
        if verbose:
            print("\n🚨 DỪNG DO CHẠM TRẦN NGÂN SÁCH (BUDGET EXCEEDED)")
            print(format_handoff_report(handoff))

        return AgentResult(
            agent_type="ReAct",
            success=False,
            stop_reason="BUDGET_EXCEEDED",
            turn_count=self.max_turns,
            model_calls=model_calls,
            booking_code=current_booking_code,
            handoff_report=handoff,
            approval_requests=approval_records,
            trajectory=trajectory,
        )
