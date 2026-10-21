# Ghi biên bản họp

Ghi âm cuộc họp, chuyển giọng nói tiếng Việt thành chữ ngay trong lúc họp, rồi xuất **biên bản
cuộc họp Word (.docx)** đúng thể thức hành chính. Mọi thứ chạy trên máy của bạn: âm thanh không
được gửi đi đâu.

## Dùng ngay, không cần Claude

1. Tải file `.zip` của skill này tại <https://brian261101.github.io/#claude-skills> rồi giải nén.
2. Bấm đúp **`Ghi bien ban hop.bat`**. Lần đầu, file này tự cài thư viện Python và tải mô hình
   nhận dạng giọng nói (khoảng 1,6 GB, mất vài phút). Máy chưa có Python thì nó đề nghị cài giúp.
3. Điền thông tin cuộc họp, bấm **Bắt đầu ghi**. Họp xong bấm **Kết thúc và xuất Word**.

Cửa sổ còn có:
- **Ghi chú nhanh**: gõ kết luận hoặc phân công, nhấn Enter, nội dung được gắn mốc giờ và đưa vào biên bản.
- **Tạm dừng** khi giải lao.
- **Chuyển file ghi âm có sẵn…** cho file mp3, m4a, wav, mp4.

## Dùng như skill của Claude

Giải nén thư mục `ghi-bien-ban-hop` vào:

```
%USERPROFILE%\.claude\skills\ghi-bien-ban-hop\
```

Mở Claude Code (hoặc tab Code trong ứng dụng Claude) và nói, chẳng hạn:

- "ghi âm biên bản cuộc họp giúp tôi"
- "làm biên bản từ file ghi âm D:\Ghi am\hop giao ban.m4a"
- "điền tóm tắt và kết luận vào biên bản vừa xuất"

Claude tự cài đặt nếu cần, mở cửa sổ ghi âm hoặc chuyển file ghi âm, rồi đọc bản chuyển chữ để
viết **mục II (tóm tắt)** và **mục III (kết luận)** vào biên bản. Những chỗ máy nghe chưa chắc
(tên người, con số) được đánh dấu "(cần kiểm tra)".

## Biên bản gồm

- Tên đơn vị, quốc hiệu, tiêu ngữ, số biên bản, địa danh và ngày tháng (ghi theo Nghị định 30/2020/NĐ-CP)
- I. Thời gian, địa điểm, chủ trì, thư ký, thành phần tham dự
- II. Nội dung: ghi chú nhanh của thư ký, phần tóm tắt
- III. Kết luận của người chủ trì
- Chữ ký thư ký và chủ trì
- Phụ lục: toàn văn lời nói kèm mốc `[giờ:phút:giây]` để đối chiếu với file ghi âm

Mỗi cuộc họp lưu riêng một thư mục trong `Documents\Biên bản cuộc họp\`: file ghi âm `.wav`,
bản chuyển chữ `.txt` (tự lưu trong lúc họp) và biên bản `.docx`.

## Yêu cầu

- Windows 10 hoặc 11, có micro
- Python 3.10 trở lên
- Khoảng 2 GB ổ đĩa; cần Internet ở lần chạy đầu

## Giới hạn

- Chưa phân biệt được ai đang nói.
- Bản chuyển chữ tự động có thể sai tên riêng, thuật ngữ và con số, nên cần nghe lại trước khi ký.
- Chạy bằng CPU: chip Intel Core i7 thế hệ 12 chuyển chữ nhanh khoảng 2 lần thời gian thực, đủ theo
  kịp cuộc họp. Máy yếu có thể đặt biến môi trường `GHI_BIEN_BAN_MODEL=small` (nhẹ hơn, kém chính xác hơn).

## Cấu trúc

```
ghi-bien-ban-hop/
├── SKILL.md                  hướng dẫn cho Claude
├── Ghi bien ban hop.bat      bấm đúp để chạy
├── requirements.txt
└── scripts/
    ├── ghi_bien_ban_hop.py   cửa sổ ghi âm; --file chuyển file có sẵn; --setup tải mô hình
    └── dien_bien_ban.py      điền tóm tắt, kết luận vào biên bản
```

Nhận dạng giọng nói dùng [faster-whisper](https://github.com/SYSTRAN/faster-whisper) với mô hình
Whisper large-v3-turbo.
