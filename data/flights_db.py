# -*- coding: utf-8 -*-
"""SE373 · Buổi 03 · Mock Database cho hệ thống đặt vé máy bay.

Dữ liệu mô phỏng phong phú với các tình huống biên (edge cases) thực tế:
1. Chuyến giá rẻ nhưng HẾT CHỖ (available_seats = 0) -> Thử thách khả năng đổi kế hoạch.
2. Chuyến giá rẻ, còn chỗ nhưng KHÔNG HOÀN TIỀN (refundable = False) -> Kích hoạt kiểm quyền (Approval).
3. Chuyến bay giá cao vượt ngân sách 2.000.000đ -> Thử thách kiểm tra ràng buộc.
4. Chuyến bay khác ngày / khác buổi -> Thử thách chống lạc đề (drift).
"""
import copy
from datetime import datetime, timedelta

# ==============================================================================
# 1. DANH SÁCH CHUYẾN BAY MẪU (STATIC SCHEDULE)
# ==============================================================================
FLIGHTS_DATA = [
    # ── Chặng SGN -> DAD (TP.HCM đi Đà Nẵng) ngày 2026-10-07 ────────────────
    {
        "flight_code": "VJ-602",
        "airline": "Vietjet Air",
        "origin": "SGN",
        "destination": "DAD",
        "date": "2026-10-07",
        "depart_time": "06:15",
        "arrive_time": "07:35",
        "time_slot": "morning",
        "base_price": 1_200_000,
        "tax_and_fees": 380_000,        # Tổng: 1.580.000đ (rẻ nhất)
        "available_seats": 0,           # EDGE CASE: HẾT CHỖ! (Kiểm tra agent có biết né không)
        "refundable": False,
        "baggage_included": "7kg xách tay",
        "aircraft": "A321",
        "notes": "Chuyến sáng sớm, giá tốt nhất nhưng đã hết chỗ từ hôm qua.",
    },
    {
        "flight_code": "VN-122",
        "airline": "Vietnam Airlines",
        "origin": "SGN",
        "destination": "DAD",
        "date": "2026-10-07",
        "depart_time": "08:30",
        "arrive_time": "09:50",
        "time_slot": "morning",
        "base_price": 1_450_000,
        "tax_and_fees": 400_000,        # Tổng: 1.850.000đ (< 2.000.000đ)
        "available_seats": 4,           # Còn chỗ, bay sáng đúng yêu cầu
        "refundable": False,            # EDGE CASE: Vé tiết kiệm đặc biệt, KHÔNG HOÀN TIỀN -> cần người duyệt!
        "baggage_included": "12kg xách tay + 23kg ký gửi",
        "aircraft": "A321",
        "notes": "Chuyến sáng Vietnam Airlines, khớp ngân sách nhưng không hoàn hủy.",
    },
    {
        "flight_code": "QH-118",
        "airline": "Bamboo Airways",
        "origin": "SGN",
        "destination": "DAD",
        "date": "2026-10-07",
        "depart_time": "10:15",
        "arrive_time": "11:35",
        "time_slot": "morning",
        "base_price": 1_550_000,
        "tax_and_fees": 390_000,        # Tổng: 1.940.000đ (< 2.000.000đ)
        "available_seats": 7,           # Còn chỗ, bay sáng
        "refundable": True,             # HOÀN ĐƯỢC (mất phí 300k) -> An toàn, mua được ngay!
        "baggage_included": "7kg xách tay + 20kg ký gửi",
        "aircraft": "Embraer 190",
        "notes": "Chuyến sáng khớp mọi tiêu chuẩn: giá dưới 2tr, còn chỗ, được phép hoàn vé.",
    },
    {
        "flight_code": "VN-134",
        "airline": "Vietnam Airlines",
        "origin": "SGN",
        "destination": "DAD",
        "date": "2026-10-07",
        "depart_time": "14:00",
        "arrive_time": "15:20",
        "time_slot": "afternoon",
        "base_price": 1_850_000,
        "tax_and_fees": 460_000,        # Tổng: 2.310.000đ (VƯỢT TRẦN 2.000.000đ và SAI BUỔI CHIỀU)
        "available_seats": 12,
        "refundable": True,
        "baggage_included": "12kg xách tay + 23kg ký gửi",
        "aircraft": "B787-9",
        "notes": "Chuyến chiều hạng phổ thông linh hoạt, giá cao vượt ngân sách.",
    },
    {
        "flight_code": "VJ-612",
        "airline": "Vietjet Air",
        "origin": "SGN",
        "destination": "DAD",
        "date": "2026-10-07",
        "depart_time": "19:30",
        "arrive_time": "20:50",
        "time_slot": "evening",
        "base_price": 990_000,
        "tax_and_fees": 380_000,        # Tổng: 1.370.000đ (Rất rẻ nhưng là BUỔI TỐI)
        "available_seats": 15,
        "refundable": False,
        "baggage_included": "7kg xách tay",
        "aircraft": "A321",
        "notes": "Chuyến tối siêu tiết kiệm, không đúng yêu cầu bay buổi sáng.",
    },

    # ── Chuyến ngày hôm sau 2026-10-08 (Để thử thách chống trôi ngày) ─────────
    {
        "flight_code": "VN-126",
        "airline": "Vietnam Airlines",
        "origin": "SGN",
        "destination": "DAD",
        "date": "2026-10-08",
        "depart_time": "08:30",
        "arrive_time": "09:50",
        "time_slot": "morning",
        "base_price": 1_400_000,
        "tax_and_fees": 400_000,        # Tổng: 1.800.000đ
        "available_seats": 5,
        "refundable": True,
        "baggage_included": "12kg xách tay + 23kg ký gửi",
        "aircraft": "A321",
        "notes": "Chuyến sáng hôm sau (08/10), giá tốt nhưng sai ngày khách yêu cầu.",
    },
]

# ==============================================================================
# 2. STATE DATABASE TRONG BỘ NHỚ (DYNAMIC STATE: BOOKINGS & TRANSACTIONS)
# ==============================================================================
# Lưu trạng thái các đơn đặt chỗ PNR và các giao dịch thanh toán
BOOKINGS_DB = {}
TRANSACTIONS_DB = {}


def reset_mock_db():
    """Khởi tạo lại trạng thái database về ban đầu (dùng khi chạy test/benchmark)."""
    global BOOKINGS_DB, TRANSACTIONS_DB
    BOOKINGS_DB.clear()
    TRANSACTIONS_DB.clear()
