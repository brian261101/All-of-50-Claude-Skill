# Bộ skill Claude

Nơi chứa các skill tôi viết cho Claude Code. Danh sách tải về hiển thị tại
**https://brian261101.github.io/#claude-skills** — trang đó đọc thẳng cấu trúc
thư mục của repo này, nên **không có bước build nào cả**.

## Thêm một skill

### Cách 1 — kéo thả (dễ nhất)

Kéo **thư mục skill** thả vào file **`Them skill.bat`**. Script tự lấy tên từ
`name:` trong `SKILL.md`, chiếm một ô trống, rồi commit và push.

Chạy từ dòng lệnh cũng được:

```bash
python add-skill.py "C:\duong\dan\den\skill"
python add-skill.py "C:\duong\dan\den\skill" ten-khac   # đặt tên khác
```

Lần đầu phải lấy repo về máy:

```bash
git clone https://github.com/brian261101/All-of-50-Claude-Skill.git
cd All-of-50-Claude-Skill
```

### Cách 2 — bằng tay

1. Chép thư mục skill vào một ô trống bất kỳ trong `skills/` (`slot-01` … `slot-50`).
2. Đổi tên thư mục `slot-NN` thành tên skill, xoá `.gitkeep` trong đó.
3. `git add -A && git commit -m "Thêm skill X" && git push`.

### Cách 3 — qua giao diện web GitHub

Vào `skills/<ô trống>`, bấm **Add file → Upload files**, kéo các file của skill
vào rồi **Commit changes**.

> Giao diện web **không đổi tên thư mục được**. Muốn đổi thì mở file trong thư
> mục đó, bấm bút chì sửa, rồi thay đường dẫn ở ô tên file — ví dụ đổi
> `slot-02/SKILL.md` thành `Equipment_tech/SKILL.md`. GitHub tự tạo thư mục mới
> và bỏ thư mục cũ.

Trang web tự xuất hiện thêm một dòng tải về. Không phải sửa gì bên trang web,
không phải cập nhật danh sách nào.

## Quy ước

| | |
|---|---|
| Một thư mục được coi là **skill đã xuất bản** | khi nó chứa file `SKILL.md` |
| Thư mục chỉ có `.gitkeep` | là ô trống, trang web bỏ qua |
| Thư mục bắt đầu bằng `_` | bị bỏ qua (ví dụ `_template`) |
| Tên hiển thị | lấy từ `name:` trong `SKILL.md`, không có thì lấy tên thư mục |
| Phần giới thiệu | lấy từ `description:` trong `SKILL.md` |

Nghĩa là `SKILL.md` phải mở đầu bằng khối frontmatter:

```yaml
---
name: ten-skill
description: Một câu mô tả skill làm gì và khi nào nên dùng.
---
```

## Nút tải về hoạt động thế nào

Trang web lấy danh sách file của repo bằng **một** lệnh gọi GitHub API, rồi tải
từng file của skill qua `raw.githubusercontent.com` và **nén thành .zip ngay
trong trình duyệt**. Không qua dịch vụ trung gian nào, không cần máy chủ.

## Cài một skill đã tải

Giải nén thư mục skill vào một trong hai chỗ:

```
<thư mục dự án>/.claude/skills/<tên-skill>/      chỉ dùng trong dự án đó
~/.claude/skills/<tên-skill>/                     dùng ở mọi dự án
```

Mở Claude Code, gõ `/` rồi chọn tên skill.
