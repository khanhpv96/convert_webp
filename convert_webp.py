import os
from PIL import Image

def convert_to_webp(input_file, output_file, quality=80):
    """
    Convert image to WebP format while preserving transparency
    """
    try:
        with Image.open(input_file) as img:
            # Keep original mode for PNG files with transparency
            if img.format == 'PNG' and img.mode == 'RGBA':
                # Save directly with alpha channel
                img.save(output_file, "webp", quality=quality, lossless=False)
            else:
                # For other formats, convert to RGB
                img = img.convert("RGB")
                img.save(output_file, "webp", quality=quality)
            return True
    except Exception as e:
        print(f"Lỗi khi chuyển đổi {input_file}: {str(e)}")
        return False

def main():
    # Đường dẫn đến thư mục uploads
    directory_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    
    # Độ chất lượng ảnh WebP (từ 0 đến 100)
    quality = 80
    
    # Đếm số lượng ảnh đã xử lý
    processed_count = 0
    failed_count = 0
    
    # Lặp qua tất cả các file trong thư mục và các thư mục con
    for root, dirs, files in os.walk(directory_path):
        for filename in files:
            # Kiểm tra file có phần mở rộng là .jpg, .jpeg hoặc .png và không phải .webp
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')) and not filename.lower().endswith('.webp'):
                input_file = os.path.join(root, filename)
                base_name = os.path.splitext(filename)[0]
                output_file = os.path.join(root, f"{base_name}.webp")
                
                print(f"Đang xử lý: {filename}")
                
                # Chuyển đổi ảnh
                if convert_to_webp(input_file, output_file, quality):
                    # Kiểm tra file output đã được tạo thành công
                    if os.path.exists(output_file):
                        # Xóa ảnh gốc sau khi chuyển đổi thành công
                        os.remove(input_file)
                        print(f"✓ Đã chuyển đổi và xóa: {filename}")
                        processed_count += 1
                    else:
                        print(f"✗ Không thể tạo file output: {filename}")
                        failed_count += 1
                else:
                    print(f"✗ Không thể chuyển đổi: {filename}")
                    failed_count += 1
    
    # In thống kê
    print("\nKết quả chuyển đổi:")
    print(f"- Số ảnh đã xử lý thành công: {processed_count}")
    print(f"- Số ảnh thất bại: {failed_count}")
    print("Hoàn tất quá trình chuyển đổi và nén ảnh.")

if __name__ == "__main__":
    main()