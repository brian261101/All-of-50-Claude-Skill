---
name: ghi-bien-ban-hop
description: Ghi âm cuộc họp, chuyển giọng nói tiếng Việt thành chữ ngay trên máy (Whisper large-v3-turbo, âm thanh không rời khỏi máy) và xuất biên bản cuộc họp Word .docx đúng thể thức hành chính Việt Nam - quốc hiệu, tiêu ngữ, thời gian, thành phần, nội dung, kết luận, chữ ký, phụ lục toàn văn có mốc thời gian; sau đó Claude đọc bản chuyển chữ để viết phần tóm tắt và kết luận vào biên bản. Dùng skill này mỗi khi người dùng muốn ghi âm cuộc họp, làm hoặc soạn biên bản họp, chuyển file ghi âm (mp3, m4a, wav, mp4) thành văn bản hay biên bản, gỡ băng ghi âm, tóm tắt cuộc họp, điền kết luận vào biên bản Word - ví dụ "ghi âm biên bản cuộc họp", "làm biên bản từ file ghi âm này", "gỡ băng buổi họp sáng nay", "soạn biên bản họp giao ban", "meeting minutes from this recording" - kể cả khi không nhắc tới chữ skill. Chạy trên Windows với Claude Code hoặc tab Code của ứng dụng Claude.
compatibility: Windows 10/11, Python 3.10 trở lên, micro. Lần đầu cần Internet để cài thư viện và tải mô hình nhận dạng giọng nói khoảng 1,6 GB.
---

# Ghi biên bản họp

Bộ công cụ gồm ba phần, Claude điều phối:

| File | Việc |
|---|---|
| `Ghi bien ban hop.bat` | Người dùng bấm đúp: tự cài thư viện, tải mô hình, mở cửa sổ ghi âm |
| `scripts/ghi_bien_ban_hop.py` | Không tham số: cửa sổ ghi âm. `--setup`: tải mô hình. `--file`: chuyển file ghi âm có sẵn thành biên bản, không mở cửa sổ |
| `scripts/dien_bien_ban.py` | Điền mục II (tóm tắt) và III (kết luận) vào biên bản đã xuất |

Biên bản xuất ra để trống mục II và III bằng dòng chấm, vì máy chỉ chép lại được lời nói,
còn tóm tắt và kết luận cần người hiểu nội dung, tức là Claude hoặc thư ký.

Dưới đây `SKILL_DIR` là thư mục chứa file SKILL.md này. Luôn dùng đường dẫn tuyệt đối và
đặt trong ngoặc kép, vì tên file có dấu cách và tiếng Việt.

## 1. Kiểm tra trước khi dùng (lần đầu trên mỗi máy)

1. `python -c "import faster_whisper, sounddevice, docx"`. Lỗi thì cài:
   `python -m pip install -r "SKILL_DIR/requirements.txt"`.
   Chưa có Python thì báo người dùng (cài từ python.org, tick "Add python.exe to PATH",
   hoặc `winget install -e --id Python.Python.3.13 --scope user`). Đừng tự cài phần mềm hệ thống.
2. `python "SKILL_DIR/scripts/ghi_bien_ban_hop.py" --setup`. Lần đầu lệnh này tải khoảng
   1,6 GB từ Hugging Face: nói trước với người dùng về dung lượng rồi chạy nền, vì mất vài phút.
   Các lần sau lệnh xong ngay.

Máy yếu, hoặc người dùng muốn tải ít hơn: đặt biến môi trường `GHI_BIEN_BAN_MODEL=small`
(khoảng 0,5 GB, nhưng sai tiếng Việt nhiều hơn rõ rệt) cho cả lệnh `--setup` lẫn lúc chạy.

## 2. Chọn đường đi

- **Cuộc họp sắp diễn ra hoặc đang diễn ra**: làm A, xong làm C.
- **Đã có file ghi âm**: làm B, xong làm C.
- **Đã có biên bản xuất từ công cụ này, cần tóm tắt và kết luận**: làm C.
- **Chỉ có ghi chú gõ tay, không có ghi âm**: không cần công cụ này. Soạn biên bản trực tiếp
  (skill docx), theo cùng bố cục ở mục C.

### A. Ghi trực tiếp trong cuộc họp

Mở cửa sổ cho người dùng:

```bash
cmd //c start "" "SKILL_DIR\Ghi bien ban hop.bat"
```

(Trong PowerShell: `Start-Process "SKILL_DIR\Ghi bien ban hop.bat"`.)

Rồi hướng dẫn ngắn: điền đơn vị, tên cuộc họp, địa điểm, chủ trì, thư ký, thành phần
(mỗi người một dòng; điền sau khi đã bắt đầu ghi cũng được), chọn micro, bấm **Bắt đầu ghi**.
Lời nói hiện thành chữ sau mỗi 20–30 giây. Ô **Ghi chú nhanh** + Enter để ghi kết luận hoặc
phân công kèm mốc giờ. **Tạm dừng** khi giải lao. **Kết thúc và xuất Word** khi họp xong.

Từ lúc mở, cửa sổ đó thuộc về người dùng. Đừng đóng, kill hay khởi động lại tiến trình
`pythonw`/`python` của nó, cũng đừng tự bấm ghi thử, vì người dùng có thể đang ghi một cuộc
họp thật. Ngắt giữa chừng thì file ghi âm vẫn còn nhưng mất bước xuất Word. Claude không nhìn
thấy cửa sổ này, nên hãy dặn người dùng báo lại khi họp xong, rồi làm C.

Mỗi cuộc họp có một thư mục riêng `Documents\Biên bản cuộc họp\<yyyy-mm-dd HHhMM> - <tên>\`:

- `Ghi âm cuộc họp.wav`: ghi liên tục, file vẫn dùng được nếu máy tắt đột ngột
- `Nội dung ghi âm (chuyển chữ).txt`: tự lưu 10 giây một lần trong lúc họp
- `Biên bản - <tên> - dd-mm-yyyy.docx`: tạo khi bấm Kết thúc

Người dùng đổi được thư mục lưu ngay trong cửa sổ. Thư mục đang dùng nằm trong khóa
`out_root` của `%APPDATA%\GhiBienBanHop\settings.json`; không có khóa đó thì là mặc định ở trên.

### B. Chuyển file ghi âm có sẵn

Hỏi nhanh những gì người dùng biết (tên cuộc họp, chủ trì, thư ký, thành phần, giờ bắt đầu),
nhưng đừng bắt họ trả lời mới chạy: trường nào thiếu thì biên bản để dòng chấm.

```bash
python "SKILL_DIR/scripts/ghi_bien_ban_hop.py" --file "D:/ghi am/hop 21-10.m4a" \
  --ten "Họp giao ban tháng 10" --chu-tri "Ông Nguyễn Văn An - Giám đốc" \
  --thu-ky "Bà Trần Thị Bình" --dia-diem "Phòng họp tầng 3" \
  --thanh-phan "Ông Nguyễn Văn An; Ông Lê Văn Cường; Bà Phạm Thị Dung" \
  --bat-dau "2026-10-21 08:30"
```

Chạy nền: trên CPU đời mới, thời gian chuyển chữ bằng khoảng một nửa độ dài file
(họp 1 giờ thì mất khoảng 30 phút), cộng chừng 20 giây nạp mô hình. Lệnh in tiến độ theo %,
cuối cùng in hai dòng `BIÊN BẢN: <đường dẫn .docx>` và `NỘI DUNG: <đường dẫn .txt>`.
`--don-vi` và `--thu-ky` bỏ trống thì lấy theo lần dùng cửa sổ gần nhất. `--out` để đổi chỗ lưu.

### C. Viết tóm tắt và kết luận

1. **Đọc bản chuyển chữ**: file `.txt` trong thư mục cuộc họp (cũng chính là phụ lục của
   biên bản). Mỗi dòng có dạng `[hh:mm:ss] lời nói`. Dòng `GHI CHÚ:` là thư ký tự gõ trong
   lúc họp, nên tin cậy hơn phần máy nghe.

2. **Viết nội dung**. Đây là văn bản hành chính có chữ ký, nên chính xác quan trọng hơn hay:
   - **Mục II, tóm tắt**: đi theo trình tự cuộc họp, mỗi đoạn một vấn đề hoặc một người báo cáo.
     Viết ở ngôi thứ ba, khách quan, ngắn gọn ("Ông Cường báo cáo tiến độ chế tạo…",
     "Phòng QA/QC đề nghị…"). Giữ đúng số liệu, ngày tháng, tên thiết bị, tên người.
   - **Ai nói**: công cụ không phân biệt người nói. Chỉ ghi tên khi bản chuyển chữ cho thấy rõ
     (người nói tự giới thiệu, chủ trì mời tên). Không rõ thì viết "Ý kiến tham gia: …".
   - **Mục III, kết luận**: đánh số 1, 2, 3… Mỗi ý gồm việc gì, ai hoặc đơn vị nào làm, hạn khi
     nào, nếu cuộc họp có nói. Chỉ đưa vào những gì thật sự được kết luận (thường là chủ trì nói
     cuối buổi, hoặc dòng `GHI CHÚ:`). Cuộc họp không có kết luận rõ thì nói thẳng với người
     dùng, đừng tự nghĩ ra.
   - **Lỗi nhận dạng**: máy hay nghe sai tên riêng, thuật ngữ, số. Sửa lỗi hiển nhiên theo ngữ
     cảnh, còn tên hoặc số chưa chắc thì đánh dấu "(cần kiểm tra)" ngay trong câu và liệt kê lại
     cho người dùng.
   - Không thêm gì mà bản chuyển chữ không có.

3. **Ghi ra file JSON** (UTF-8), đặt cạnh biên bản, ví dụ `noi_dung_bien_ban.json`:

   ```json
   {
     "tom_tat": [
       "**Ông Lê Văn Cường** báo cáo: phân xưởng đã hoàn thành ống cánh tản nhiệt tuần trước; dự kiến nghiệm thu vào thứ Sáu.",
       "Ý kiến tham gia: đề nghị Phòng Thiết kế sớm gửi bản vẽ hoàn công."
     ],
     "ket_luan": [
       "1. Giao Phòng Kỹ thuật gửi bản vẽ hoàn công trước thứ Năm, ngày 23/10/2026.",
       "2. Phòng QA/QC chuẩn bị hồ sơ nghiệm thu, hoàn thành trước thứ Sáu, ngày 24/10/2026."
     ],
     "so": "15/BB-KT",
     "dia_danh": "Tây Ninh"
   }
   ```

   `**chữ**` được in đậm. `so` (số biên bản) và `dia_danh` (địa danh trước "ngày … tháng …")
   chỉ điền khi người dùng cho biết, không có thì bỏ khóa đó đi.

4. **Điền vào biên bản**:

   ```bash
   python "SKILL_DIR/scripts/dien_bien_ban.py" "<đường dẫn .docx>" "<đường dẫn .json>"
   ```

   Lệnh ghi đè lên file biên bản và chỉ thay các dòng chấm của mục II, III. Thêm `-o <file mới>`
   nếu muốn giữ bản gốc. Báo "không còn dòng chấm trống" nghĩa là mục đó đã được điền rồi
   (thường do người dùng sửa tay): hỏi người dùng thay vì ghi đè. Báo "không ghi được" là
   file đang mở trong Word.

5. **Báo lại người dùng**: đường dẫn biên bản, các chỗ "(cần kiểm tra)", và nhắc rằng biên bản
   cần chủ trì và thư ký đọc lại trước khi ký.

## Sự cố thường gặp

- **Micro không thu được tiếng**: Cài đặt Windows > Quyền riêng tư và bảo mật > Micro, bật
  "Cho phép ứng dụng máy tính truy cập micro"; kiểm tra đã chọn đúng micro trong cửa sổ.
- **Log có dòng `cublas64_12.dll is not found`**: bình thường. Máy có card NVIDIA nhưng thiếu
  thư viện CUDA 12 nên chương trình tự chạy bằng CPU, vẫn nhanh gấp khoảng 2 lần thời gian thực.
- **Python báo không mở được file dù file có thật**: đường dẫn dài quá 260 ký tự. Chép file
  ghi âm ra chỗ có đường dẫn ngắn hơn rồi chạy lại.
- Log: `%APPDATA%\GhiBienBanHop\log.txt`. Thông tin cuộc họp lần trước: `settings.json` cùng thư mục.
