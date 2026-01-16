# WebP Image Converter & Database Updater

Bộ công cụ hoàn chỉnh để chuyển đổi ảnh sang WebP và cập nhật database WordPress.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.0%2B-green.svg)
![PHP](https://img.shields.io/badge/PHP-7.4%2B-purple.svg)
![WordPress](https://img.shields.io/badge/WordPress-5.0%2B-blue.svg)

## Tổng quan

Dự án bao gồm 2 công cụ:
1. **Desktop App** (Python/PyQt6) - Convert ảnh sang WebP với giao diện GUI
2. **Web Tool** (PHP) - Cập nhật references trong WordPress database

## Cấu trúc dự án

```
webp-converter-toolkit/
├── main.py                        # Desktop converter app
├── webp-database-updater.php      # WordPress database updater
└── README.md
```

## Tool 1: Desktop WebP Converter (main.py)

### Tính năng
- Giao diện GUI thân thiện với PyQt6
- Chọn file hoặc thư mục để convert hàng loạt
- Thống kê dung lượng tiết kiệm real-time
- Tùy chỉnh chất lượng WebP (1-100%)
- Tùy chọn giữ lại file gốc
- Progress bar và log chi tiết

### Cài đặt
```bash
pip install PyQt6 Pillow send2trash
python main.py
```

### Sử dụng
1. Chạy `python main.py`
2. Chọn ảnh hoặc thư mục
3. Điều chỉnh chất lượng (mặc định 85%)
4. Nhấn "Bắt Đầu Chuyển Đổi"

## Tool 2: WordPress Database Updater (webp-database-updater.php)

### Tính năng
- Quét database trước khi cập nhật
- Hỗ trợ cả local files và CDN
- Real-time processing với logs
- Transaction safety (auto rollback)
- Giao diện web chuyên nghiệp

### Cài đặt
1. Upload file lên thư mục gốc WordPress
2. Truy cập: `https://domain.com/webp-database-updater.php`

### Sử dụng
1. **Backup database** trước khi dùng
2. Nhấn "Quét Database" để xem preview
3. Nhấn "Bắt Đầu Xử Lý" để cập nhật

## Workflow khuyến nghị

### Bước 1: Convert ảnh
```bash
# Chạy desktop app
python main.py
# Chọn thư mục wp-content/uploads
# Convert tất cả ảnh sang WebP
```

### Bước 2: Cập nhật database
```bash
# Upload webp-database-updater.php lên WordPress root
# Truy cập qua browser và chạy tool
```

### Bước 3: Dọn dẹp
```bash
# Xóa file updater sau khi hoàn thành
rm webp-database-updater.php
```

## Yêu cầu hệ thống

### Desktop App
- Python 3.8+
- PyQt6
- Pillow (PIL)

### Web Tool  
- PHP 7.4+
- WordPress 5.0+
- MySQL 5.7+
- Quyền Administrator

## Bảng database được cập nhật

| Bảng | Mô tả |
|------|-------|
| `wp_posts` | Nội dung bài viết và GUID |
| `wp_postmeta` | File đính kèm và metadata |
| `wp_options` | Theme settings, widgets, logo |

## CDN Support

Tool web tự động xử lý:
- Local paths: `/wp-content/uploads/image.jpg`
- CDN URLs: `https://img.domain.com/image.jpg`  
- Query parameters: `image.jpg?v=123`

## Troubleshooting

### Desktop App
```bash
# Lỗi module not found
pip install PyQt6 Pillow

# Lỗi permission trên Linux/Mac
chmod +x main.py
```

### Web Tool
```php
// Tăng memory limit nếu cần
ini_set('memory_limit', '512M');
ini_set('max_execution_time', 600);
```

## Lưu ý quan trọng

⚠️ **Luôn backup database** trước khi dùng web tool

⚠️ **Test trên staging** trước khi chạy production

⚠️ **Verify WebP files** tồn tại trước khi update database

## Screenshots

### Desktop App
- Giao diện modern với thống kê real-time
- Progress bar và logs chi tiết
- Tùy chỉnh chất lượng WebP

### Web Tool  
- Scan database trước khi xử lý
- Real-time processing logs
- Professional responsive design

## License

MIT License - Sử dụng tự do cho mọi mục đích.

---

**Tip**: Chạy desktop app với chất lượng 85% cho kết quả tối ưu giữa chất lượng và dung lượng.