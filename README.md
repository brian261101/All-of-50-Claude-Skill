# Bộ skill Claude

Nơi chứa các skill tôi viết cho Claude Code. Danh sách tải về hiển thị tại
**https://brian261101.github.io/#claude-skills** — trang đó đọc thẳng cấu trúc
thư mục của repo này, nên **không có bước build nào cả**.

## Thêm một skill

1. Chép thư mục skill vào một ô trống bất kỳ trong `skills/` (`slot-01` … `slot-50`).
2. Đổi tên thư mục `slot-NN` thành tên skill.
3. `git add . && git commit && git push`.

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
