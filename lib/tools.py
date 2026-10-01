# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Bộ Tool Đặt Vé Máy Bay.

Bao gồm 4 tool nghiệp vụ chính và 1 tool kiểm chứng chéo (Cross-validation):
1. search_flights: Tìm danh sách chuyến bay theo chặng, ngày, buổi.
2. check_seat: Kiểm tra số ghế trống, giá tổng (gồm thuế phí), chính sách hoàn vé.
3. book_seat: Giữ chỗ cho hành khách, tạo mã đặt chỗ PNR (trạng thái: held).
4. pay: Thanh toán hóa đơn đặt chỗ, chuyển trạng thái sang confirmed.
5. get_booking: Tra cứu trạng thái thực tế của vé từ hệ thống (phục vụ Harness).

Mọi tool đều trả về cấu trúc dict chuẩn JSON kèm các mã trạng thái rõ ràng (Slide 13, 65).
"""
import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from data.flights_db import BOOKINGS_DB, FLIGHTS_DATA, TRANSACTIONS_DB


def _normalize(s: str) -> str:
    """Chuẩn hóa chuỗi tìm kiếm (chữ thường, bỏ khoảng trắng thừa)."""
    return " ".join(s.strip().lower().split()) if s else ""


# ==============================================================================
# TOOL 1: TÌM KIẾM CHUYẾN BAY (SEARCH FLIGHTS)
# ==============================================================================
def search_flights(
    origin: str,
    destination: str,
    date: str,
    time_of_day: Optional[str] = None,
) -> Dict[str, Any]:
    """Tìm kiếm danh sách chuyến bay theo điểm đi, điểm đến, ngày bay và buổi bay.

    Args:
        origin: Mã sân bay hoặc tên thành phố xuất phát (vd: 'SGN', 'TP.HCM', 'Hồ Chí Minh').
        destination: Mã sân bay hoặc tên thành phố đến (vd: 'DAD', 'Đà Nẵng').
        date: Ngày bay theo định dạng 'YYYY-MM-DD' (vd: '2026-10-07') hoặc 'DD/MM/YYYY'.
        time_of_day: Buổi bay mong muốn ('morning', 'afternoon', 'evening' hoặc None nếu xem tất cả).

    Returns:
        dict: Trạng thái tìm kiếm, số lượng tìm thấy và danh sách chuyến bay tóm tắt.
    """
    orig_norm = _normalize(origin)
    dest_norm = _normalize(destination)
    time_norm = _normalize(time_of_day) if time_of_day else ""

    # Map tên thành phố về mã sân bay cơ bản
    city_map = {
        "hồ chí minh": "sgn", "tphcm": "sgn", "tp.hcm": "sgn", "sài gòn": "sgn", "sgn": "sgn",
        "đà nẵng": "dad", "da nang": "dad", "dad": "dad",
        "hà nội": "han", "ha noi": "han", "han": "han",
    }
    origin_code = city_map.get(orig_norm, orig_norm)
    dest_code = city_map.get(dest_norm, dest_norm)

    # Chuẩn hóa ngày nếu truyền dạng 07/10/2026 -> 2026-10-07
    if "/" in date:
        parts = date.split("/")
        if len(parts) == 3:
            date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"

    matched = []
    for f in FLIGHTS_DATA:
        f_orig = f["origin"].lower()
        f_dest = f["destination"].lower()
        if f_orig == origin_code and f_dest == dest_code and f["date"] == date:
            if time_norm and time_norm not in ["tat ca", "all", ""]:
                # Nếu có lọc theo buổi sáng/chiều/tối
                if time_norm in ["sang", "sáng", "morning"] and f["time_slot"] != "morning":
                    continue
                if time_norm in ["chieu", "chiều", "afternoon"] and f["time_slot"] != "afternoon":
                    continue
                if time_norm in ["toi", "tối", "evening"] and f["time_slot"] != "evening":
                    continue
            matched.append(f)

    if not matched:
        return {
            "status": "not_found",
            "matched_count": 0,
            "flights": [],
            "hint": f"Không tìm thấy chuyến bay nào từ {origin} đi {destination} vào ngày {date}. Hãy kiểm tra lại ngày bay hoặc sân bay.",
        }

    # Trả về kết quả tóm tắt (Structured Observation)
    summary_list = []
    for f in matched:
        est_price = f["base_price"] + f["tax_and_fees"]
        summary_list.append({
            "flight_code": f["flight_code"],
            "airline": f["airline"],
            "date": f["date"],
            "depart_time": f["depart_time"],
            "arrive_time": f["arrive_time"],
            "time_slot": f["time_slot"],
            "estimated_total_price": est_price,
            "aircraft": f["aircraft"],
        })

    return {
        "status": "ok",
        "matched_count": len(matched),
        "flights": summary_list,
        "hint": "Cần gọi 'check_seat' với mã chuyến bay cụ thể để biết chính xác số ghế trống và chính sách hoàn vé trước khi đặt.",
    }


# ==============================================================================
# TOOL 2: KIỂM TRA CHỖ VÀ GIÁ THỰC TẾ (CHECK SEAT)
# ==============================================================================
def check_seat(flight_code: str) -> Dict[str, Any]:
    """Kiểm tra số ghế trống thực tế, chi tiết giá và chính sách hoàn vé của một chuyến bay.

    Args:
        flight_code: Mã chuyến bay (vd: 'VN-122', 'VJ-602', 'QH-118').

    Returns:
        dict: Chi tiết ghế trống, giá cuối cùng, chính sách hoàn tiền và ghi chú.
    """
    code_clean = flight_code.strip().upper()
    flight = next((f for f in FLIGHTS_DATA if f["flight_code"].upper() == code_clean), None)

    if not flight:
        all_codes = [f["flight_code"] for f in FLIGHTS_DATA]
        return {
            "status": "error",
            "error_code": "flight_not_found",
            "queried_code": flight_code,
            "hint": f"Mã chuyến bay '{flight_code}' không tồn tại. Các chuyến bay khả dụng: {', '.join(all_codes[:4])}",
        }

    total_price = flight["base_price"] + flight["tax_and_fees"]

    # EDGE CASE 1: HẾT CHỖ
    if flight["available_seats"] <= 0:
        return {
            "status": "sold_out",
            "flight_code": flight["flight_code"],
            "airline": flight["airline"],
            "available_seats": 0,
            "total_price": total_price,
            "hint": "Chuyến bay này ĐÃ HẾT CHỖ. Vui lòng chọn chuyến bay khác trong danh sách đã tìm.",
        }

    # CÒN CHỖ
    return {
        "status": "ok",
        "flight_code": flight["flight_code"],
        "airline": flight["airline"],
        "origin": flight["origin"],
        "destination": flight["destination"],
        "date": flight["date"],
        "depart_time": flight["depart_time"],
        "time_slot": flight["time_slot"],
        "available_seats": flight["available_seats"],
        "base_price": flight["base_price"],
        "tax_and_fees": flight["tax_and_fees"],
        "total_price": total_price,
        "refundable": flight["refundable"],
        "baggage_included": flight["baggage_included"],
        "notes": flight["notes"],
        "hint": "Nếu chuyến bay phù hợp với ràng buộc, hãy gọi 'book_seat' để giữ chỗ.",
    }


# ==============================================================================
# TOOL 3: GIỮ CHỖ HÀNH KHÁCH (BOOK SEAT)
# ==============================================================================
def book_seat(flight_code: str, passenger_name: str, passenger_id: Optional[str] = "ID-DEFAULT") -> Dict[str, Any]:
    """Giữ chỗ cho hành khách trên một chuyến bay cụ thể và cấp mã đặt chỗ (PNR).

    Args:
        flight_code: Mã chuyến bay đã chọn (vd: 'QH-118').
        passenger_name: Họ tên đầy đủ của hành khách (vd: 'NGUYEN VAN A').
        passenger_id: Số CMND/CCCD hoặc mã định danh của hành khách.

    Returns:
        dict: Mã đặt chỗ PNR, trạng thái 'held', tổng tiền và hạn chót thanh toán.
    """
    code_clean = flight_code.strip().upper()
    flight = next((f for f in FLIGHTS_DATA if f["flight_code"].upper() == code_clean), None)

    if not flight:
        return {
            "status": "error",
            "error_code": "flight_not_found",
            "hint": f"Không tìm thấy chuyến bay {flight_code} để đặt chỗ.",
        }

    if flight["available_seats"] <= 0:
        return {
            "status": "error",
            "error_code": "seat_unavailable",
            "hint": f"Chuyến bay {flight_code} đã hết chỗ, không thể thực hiện giữ chỗ.",
        }

    # Sinh mã PNR (Booking Code) gồm 6 ký tự viết hoa ngẫu nhiên
    pnr_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    booking_code = f"BK-{pnr_suffix}"

    total_price = flight["base_price"] + flight["tax_and_fees"]
    now = datetime.now()
    expires_at = (now + timedelta(minutes=15)).strftime("%H:%M:%S")

    # Giảm số ghế trống tạm thời
    flight["available_seats"] -= 1

    # Lưu vào database trạng thái đơn hàng
    booking_record = {
        "booking_code": booking_code,
        "flight_code": flight["flight_code"],
        "airline": flight["airline"],
        "passenger_name": passenger_name.strip().upper(),
        "passenger_id": passenger_id,
        "origin": flight["origin"],
        "destination": flight["destination"],
        "date": flight["date"],
        "depart_time": flight["depart_time"],
        "time_slot": flight["time_slot"],
        "total_price": total_price,
        "refundable": flight["refundable"],
        "status": "held",                # 'held' -> đang giữ chỗ, chưa thanh toán
        "paid": False,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": expires_at,
    }
    BOOKINGS_DB[booking_code] = booking_record

    return {
        "status": "held",
        "booking_code": booking_code,
        "flight_code": flight["flight_code"],
        "airline": flight["airline"],
        "passenger_name": booking_record["passenger_name"],
        "depart_date": flight["date"],
        "depart_time": flight["depart_time"],
        "total_amount": total_price,
        "refundable": flight["refundable"],
        "expires_at": expires_at,
        "hint": f"Đã giữ chỗ thành công mã {booking_code}. Cần gọi 'pay' để hoàn tất thanh toán trước khi vé bị hủy.",
    }


# ==============================================================================
# TOOL 4: THANH TOÁN VÉ (PAY)
# ==============================================================================
def pay(booking_code: str, payment_method: str, amount: int) -> Dict[str, Any]:
    """Thực hiện thanh toán tiền vé máy bay cho mã đặt chỗ đã giữ.

    Args:
        booking_code: Mã đặt chỗ PNR nhận được từ book_seat (vd: 'BK-4XJ2').
        payment_method: Phương thức thanh toán (vd: 'corp_card', 'bank_transfer', 'credit_card').
        amount: Số tiền thanh toán (phải khớp đúng tổng tiền của đơn giữ chỗ).

    Returns:
        dict: Kết quả thanh toán, mã giao dịch (transaction_id) và trạng thái 'confirmed'.
    """
    b_code = booking_code.strip().upper()
    booking = BOOKINGS_DB.get(b_code)

    if not booking:
        return {
            "status": "error",
            "error_code": "booking_not_found",
            "hint": f"Mã đặt chỗ '{booking_code}' không tồn tại trên hệ thống thanh toán.",
        }

    if booking["status"] == "confirmed" and booking["paid"]:
        return {
            "status": "already_paid",
            "booking_code": b_code,
            "message": "Đơn đặt vé này đã được thanh toán trước đó.",
        }

    # Kiểm tra số tiền
    if int(amount) != int(booking["total_price"]):
        return {
            "status": "error",
            "error_code": "amount_mismatch",
            "required_amount": booking["total_price"],
            "provided_amount": amount,
            "hint": f"Số tiền thanh toán ({amount:,}đ) không khớp với giá vé ({booking['total_price']:,}đ).",
        }

    # Sinh mã giao dịch thành công
    txn_id = f"TXN-{random.randint(100000, 999999)}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Cập nhật trạng thái trong database
    booking["status"] = "confirmed"
    booking["paid"] = True
    booking["payment_method"] = payment_method
    booking["transaction_id"] = txn_id
    booking["paid_at"] = now

    TRANSACTIONS_DB[txn_id] = {
        "transaction_id": txn_id,
        "booking_code": b_code,
        "amount": amount,
        "payment_method": payment_method,
        "timestamp": now,
        "status": "success",
    }

    return {
        "status": "confirmed",
        "booking_code": b_code,
        "transaction_id": txn_id,
        "flight_code": booking["flight_code"],
        "passenger_name": booking["passenger_name"],
        "depart_date": booking["date"],
        "depart_time": booking["depart_time"],
        "amount_paid": amount,
        "paid": True,
        "message": f"Thanh toán thành công {amount:,}đ qua {payment_method}. Vé đã được xác nhận (CONFIRMED).",
    }


# ==============================================================================
# TOOL 5 (CROSS-VALIDATION): TRA CỨU VÉ ĐÃ ĐẶT (GET BOOKING)
# ==============================================================================
def get_booking(booking_code: str) -> Dict[str, Any]:
    """Tra cứu trực tiếp trạng thái hiện tại của vé máy bay từ cơ sở dữ liệu.

    Công cụ này được Harness dùng để kiểm chứng chéo độc lập (Computational Sensor),
    không dựa vào phán đoán chủ quan của model (Slide 43, 44).
    """
    b_code = booking_code.strip().upper()
    booking = BOOKINGS_DB.get(b_code)
    if not booking:
        return {"status": "not_found", "booking_code": b_code}
    return dict(booking)


# ==============================================================================
# ĐÓNG GÓI DÀNH CHO LANGCHAIN (LANGCHAIN TOOLS)
# ==============================================================================
def get_flight_tools():
    """Trả về danh sách 4 tool nghiệp vụ được bọc bởi LangChain @tool."""
    try:
        from langchain_core.tools import tool
        return [
            tool(search_flights),
            tool(check_seat),
            tool(book_seat),
            tool(pay),
            tool(get_booking),
        ]
    except ImportError:
        # Nếu chưa cài langchain, trả về danh sách hàm Python thuần
        return [search_flights, check_seat, book_seat, pay, get_booking]
