---
name: pipe-wall-thickness-check
description: Soát xét một bản tính chiều dày thành ống theo ASME B31.3 / B31.1 / B31.8 - kiểm tra phương trình, hệ số, nguồn ứng suất cho phép, dung sai chế tạo, và các mục thường bị bỏ sót như chiều dày đặt hàng tối thiểu, MAWP và nhánh thành dày. Dùng khi có file tính chiều dày ống cần kiểm tra, hoặc khi cần lập một bản tính mới từ đầu.
---

# Soát xét bản tính chiều dày thành ống

## Mục đích

Kiểm tra một bản tính chiều dày thành ống chịu áp suất trong, hoặc lập mới,
theo đúng bộ tiêu chuẩn áp dụng. Skill này tập trung vào những chỗ thực tế hay
sai, không phải nhắc lại lý thuyết.

## Trước tiên: xác định bộ tiêu chuẩn

Phải chốt trước khi tính, vì mỗi bộ dùng phương trình và bộ hệ số khác nhau.

| Bộ | Phương trình | Nguồn ứng suất |
|---|---|---|
| ASME B31.3 §304.1.2 (3a) | `t = P·D / (2(S·E·W + P·Y))` | Bảng A-1, tại **nhiệt độ thiết kế** |
| ASME B31.1 §104.1.2 (3) | `tm = P·D / (2(S·E + P·y)) + A` | Bảng A của B31.1 |
| ASME B31.8 §841.1.1 | `t = P·D / (2·S·F·E·T)` | **SMYS**, kèm hệ số F theo Class Location |

Rồi: `tm = t + c`, và chiều dày danh nghĩa phải đặt hàng là `tm / (1 − dung sai)`.

## Danh sách soát xét

1. **Ứng suất cho phép S lấy ở đúng nhiệt độ thiết kế chưa**, và từ bản Bảng A-1
   nào. Ghi rõ nguồn ngay trong bản tính.
2. **Mác vật liệu ghi kép** kiểu `304/304L` hay `316/316L`: trị số của mác L
   **thấp hơn**. Chỉ được dùng trị số mác thường khi chứng chỉ vật liệu (MTR)
   chứng minh đạt mác đó.
3. **Trích dẫn bảng kích thước**: thép carbon là **B36.10M**, thép không gỉ là
   **B36.19M**. Rất hay bị ghi nhầm.
4. **Dải nhiệt độ ghi trong bản tính có bao được nhiệt độ thiết kế không** —
   hay ghi `−29 đến 38` rồi lại khai nhiệt độ thiết kế 50 °C.
5. **Hệ số E** theo dạng sản phẩm: ống đúc 1,0; ống hàn thấp hơn, tra Bảng A-1B.
6. **Hệ số W** theo Bảng 302.3.5, bằng 1,0 dưới 427 °C.
7. **Hệ số Y** theo Bảng 304.1.1, bằng 0,4 với thép ở T ≤ 482 °C.
8. **Kiểm tra `t < D₀/6`**. Nếu không thoả thì phương trình (3a) không còn áp
   dụng: phải dùng `Y = (d + 2c)/(D₀ + d + 2c)` và xét thêm §304.1.2 (b).
9. **Dung sai chế tạo** đã trừ chưa — thường 12,5 % với ống đúc.
10. **Dư ăn mòn c** có hợp lý với lưu chất không. Nếu `c` lớn hơn `t` nhiều lần
    thì chiều dày hoàn toàn do dư ăn mòn quyết định, không phải do áp suất —
    nêu rõ điều đó và xem lại trị số.

## Những mục hay thiếu

- **Chiều dày đặt hàng tối thiểu** `tm / (1 − dung sai)` — con số người mua hàng
  thật sự cần, khác với `tm`.
- **MAWP tính ngược** từ ống đã chọn: `P_max = 2·S·E·W·t_av / (D₀ − 2·Y·t_av)`
  với `t_av = T_nom(1 − dung sai) − c`. Cho thấy biên dự trữ thực tế.
- **Chiều dày tối thiểu về kết cấu** do spec dự án quy định, nếu có.
- **Áp suất ngoài / chân không** — phương trình trên không xét.
- **Cấp áp suất mặt bích** theo B16.5 ở nhiệt độ thiết kế, kiểm riêng.

## Vật liệu theo nhiệt độ

Mốc thường dùng khi sàng lọc, vẫn phải tra §323.2.2 và Hình 323.2.2A cho từng
trường hợp:

| Vật liệu | Mốc nhiệt độ thấp |
|---|---|
| Thép carbon (A106 Gr.B) | −29 °C, dưới mức này phải thử va đập |
| A333 Gr.6 | −45 °C |
| A333 Gr.3 | −101 °C |
| A333 Gr.8 / A353 (9 % Ni) | −196 °C |
| Inox austenit (304/316) | −198 °C |

Kết luận phải tính **cả hai phía**: chiều dày đủ mà vật liệu không dùng được ở
nhiệt độ thiết kế thì vẫn là không đạt.

## Quy tắc

1. Không tự điền ứng suất cho phép từ trí nhớ. Hỏi người dùng, hoặc yêu cầu tra
   Bảng A-1. Nhập sai S thì ra ống mỏng hơn mức an toàn và **không phép kiểm tra
   nào phía sau phát hiện được**.
2. Mọi trị số tra bảng phải ghi rõ nguồn.
3. Nêu rõ bản tính này chỉ xét áp suất trong, chưa xét tải bền vững, tải thỉnh
   thoảng, giãn nở nhiệt và mỏi.
4. Không kết luận "đạt" khi còn mục chưa kiểm tra được — liệt kê mục đó ra.

## Công cụ liên quan

Bản tính tự động chạy trong trình duyệt:
<https://brian261101.github.io/pipe-thickness-web/>
