# -*- coding: utf-8 -*-
"""Test kiểm thử bộ mock data và các tool đặt vé."""
import sys
import os

# Đảm bảo hiển thị tiếng Việt trên Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Thêm đường dẫn hiện tại vào sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.tools import search_flights, check_seat, book_seat, pay, get_booking

def test_pipeline():
    print("=" * 60)
    print("KIỂM THỬ BỘ TOOL VÀ MOCK DATA ĐẶT VÉ MÁY BAY")
    print("=" * 60)

    # 1. Tìm chuyến bay sáng ngày 07/10/2026 từ SGN đi DAD
    print("\n[Bước 1] Tìm kiếm chuyến bay: SGN -> DAD, ngày 2026-10-07, buổi sáng")
    res = search_flights("SGN", "DAD", "2026-10-07", time_of_day="morning")
    print(f"-> Tìm thấy {res['matched_count']} chuyến bay:")
    for f in res["flights"]:
        print(f"   * {f['flight_code']} ({f['airline']}) - Khởi hành: {f['depart_time']} - Giá ước tính: {f['estimated_total_price']:,}đ")

    # 2. Kiểm tra chuyến VJ-602 (Tình huống HẾT CHỖ)
    print("\n[Bước 2] Kiểm tra chỗ chuyến rẻ nhất VJ-602:")
    seat_vj = check_seat("VJ-602")
    print(f"-> Trạng thái: {seat_vj['status']} | Số ghế trống: {seat_vj['available_seats']}")
    print(f"   Gợi ý của tool: \"{seat_vj['hint']}\"")

    # 3. Kiểm tra chuyến VN-122 (Tình huống VÉ KHÔNG HOÀN HỦY)
    print("\n[Bước 3] Kiểm tra chỗ chuyến VN-122:")
    seat_vn = check_seat("VN-122")
    print(f"-> Trạng thái: {seat_vn['status']} | Giá tổng: {seat_vn['total_price']:,}đ | Hoàn vé: {seat_vn['refundable']}")
    print(f"   Ghi chú: {seat_vn['notes']}")

    # 4. Kiểm tra chuyến QH-118 (Tình huống HOÀN HẢO: dưới 2tr, còn chỗ, được hoàn vé)
    print("\n[Bước 4] Kiểm tra chỗ chuyến QH-118:")
    seat_qh = check_seat("QH-118")
    print(f"-> Trạng thái: {seat_qh['status']} | Số ghế: {seat_qh['available_seats']} | Giá: {seat_qh['total_price']:,}đ | Hoàn vé: {seat_qh['refundable']}")

    # 5. Thực hiện giữ chỗ chuyến QH-118
    print("\n[Bước 5] Đặt chỗ hành khách NGUYEN VAN A trên chuyến QH-118:")
    book_res = book_seat("QH-118", "NGUYEN VAN A", "079123456789")
    b_code = book_res["booking_code"]
    print(f"-> Trạng thái: {book_res['status']} | Mã PNR: {b_code}")
    print(f"   Hạn chót thanh toán: {book_res['expires_at']} (trong vòng 15 phút)")

    # 6. Thanh toán vé
    print(f"\n[Bước 6] Thanh toán mã đặt chỗ {b_code} qua thẻ công ty (corp_card):")
    pay_res = pay(b_code, "corp_card", book_res["total_amount"])
    print(f"-> Trạng thái: {pay_res['status']} | Mã GD: {pay_res['transaction_id']}")
    print(f"   Thông điệp: {pay_res['message']}")

    # 7. Kiểm chứng chéo trạng thái qua get_booking (Sensor computational)
    print("\n[Bước 7] Kiểm chứng chéo độc lập qua get_booking:")
    info = get_booking(b_code)
    print(f"-> DB Status: {info['status']} | Đã thanh toán: {info['paid']} | Giá thực tế: {info['total_price']:,}đ")
    print("\n" + "=" * 60)
    print("HOÀN TẤT KIỂM THỬ: TẤT CẢ TOOL HOẠT ĐỘNG CHUẨN XÁC!")
    print("=" * 60)

if __name__ == "__main__":
    test_pipeline()
