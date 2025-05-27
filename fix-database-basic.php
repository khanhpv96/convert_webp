<?php
// Đặt file này trong thư mục gốc của WordPress
require_once('wp-load.php');

// Kiểm tra quyền admin
function check_admin() {
    if (!current_user_can('administrator')) {
        die('Bạn cần đăng nhập với quyền administrator để thực hiện thao tác này.');
    }
}

function update_image_references() {
    global $wpdb;
    
    echo "<div style='font-family: monospace; white-space: pre-line;'>";
    echo "Bắt đầu cập nhật references...\n";
    
    // 1. Cập nhật URLs trong posts
    $posts_updated = $wpdb->query("
        UPDATE {$wpdb->posts} 
        SET post_content = REPLACE(post_content, '.jpg', '.webp'),
            post_content = REPLACE(post_content, '.jpeg', '.webp'),
            post_content = REPLACE(post_content, '.png', '.webp'),
            guid = REPLACE(guid, '.jpg', '.webp'),
            guid = REPLACE(guid, '.jpeg', '.webp'),
            guid = REPLACE(guid, '.png', '.webp')
        WHERE post_content LIKE '%.jpg%' 
           OR post_content LIKE '%.jpeg%'
           OR post_content LIKE '%.png%'
           OR guid LIKE '%.jpg%'
           OR guid LIKE '%.jpeg%'
           OR guid LIKE '%.png%'
    ");
    
    echo "- Đã cập nhật {$posts_updated} posts\n";
    
    // 2. Cập nhật _wp_attached_file trong postmeta
    $attached_files_updated = $wpdb->query("
        UPDATE {$wpdb->postmeta} 
        SET meta_value = REPLACE(REPLACE(REPLACE(meta_value, '.jpg', '.webp'), '.jpeg', '.webp'), '.png', '.webp')
        WHERE meta_key = '_wp_attached_file'
        AND (
            meta_value LIKE '%.jpg'
            OR meta_value LIKE '%.jpeg'
            OR meta_value LIKE '%.png'
        )
    ");
    
    echo "- Đã cập nhật {$attached_files_updated} attached files\n";
    
    // 3. Cập nhật _wp_attachment_metadata
    $attachment_meta_ids = $wpdb->get_col("
        SELECT post_id 
        FROM {$wpdb->postmeta} 
        WHERE meta_key = '_wp_attachment_metadata'
    ");
    
    $meta_updated = 0;
    foreach ($attachment_meta_ids as $post_id) {
        $metadata = wp_get_attachment_metadata($post_id);
        if (!is_array($metadata)) continue;
        
        $updated = false;
        
        // Cập nhật file chính
        if (isset($metadata['file'])) {
            $metadata['file'] = preg_replace('/\.(jpe?g|png)$/i', '.webp', $metadata['file']);
            $updated = true;
        }
        
        // Cập nhật các size khác
        if (isset($metadata['sizes']) && is_array($metadata['sizes'])) {
            foreach ($metadata['sizes'] as $size => $data) {
                if (isset($data['file'])) {
                    $metadata['sizes'][$size]['file'] = preg_replace('/\.(jpe?g|png)$/i', '.webp', $data['file']);
                    $metadata['sizes'][$size]['mime-type'] = 'image/webp';
                    $updated = true;
                }
            }
        }
        
        if ($updated) {
            wp_update_attachment_metadata($post_id, $metadata);
            $meta_updated++;
        }
    }
    
    echo "- Đã cập nhật {$meta_updated} attachment metadata\n";
    
    // 4. Cập nhật option và theme mods
    $options_updated = $wpdb->query("
        UPDATE {$wpdb->options}
        SET option_value = REPLACE(REPLACE(REPLACE(
            option_value, 
            '.jpg', '.webp'),
            '.jpeg', '.webp'),
            '.png', '.webp'
        )
        WHERE option_name LIKE '%theme_mods_%'
           OR option_name LIKE '%widget_%'
           OR option_name IN ('site_logo', 'site_icon')
    ");
    
    echo "- Đã cập nhật {$options_updated} theme/widget options\n";
    
    // 5. Làm sạch cache
    wp_cache_flush();
    echo "- Đã xóa cache\n";
    
    echo "\nHoàn tất cập nhật database!</div>";
}

// HTML Interface
?>
<!DOCTYPE html>
<html>
<head>
    <title>Cập nhật WebP References</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .warning { color: red; margin: 20px 0; }
        .button { 
            display: inline-block;
            padding: 10px 20px;
            background-color: #0073aa;
            color: white;
            text-decoration: none;
            border-radius: 3px;
            margin: 10px 0;
        }
        .button.warning { background-color: #dc3545; }
        .button:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="container">
        <?php
        // Kiểm tra quyền admin
        check_admin();

        if (!isset($_POST['confirm'])) {
            // Hiển thị form xác nhận
            ?>
            <h1>Cập nhật WebP References</h1>
            <div class="warning">
                <strong>Cảnh báo:</strong> 
                <ul>
                    <li>Hãy đảm bảo bạn đã backup database trước khi thực hiện.</li>
                    <li>Đảm bảo tất cả ảnh đã được convert sang webp thành công.</li>
                    <li>Nên thực hiện trên môi trường test trước.</li>
                </ul>
            </div>
            <form method="post">
                <input type="hidden" name="confirm" value="1">
                <button type="submit" class="button">Bắt đầu Cập nhật</button>
                <a href="<?php echo admin_url(); ?>" class="button warning">Hủy</a>
            </form>
            <?php
        } else {
            // Thực hiện cập nhật
            update_image_references();
            ?>
            <a href="<?php echo admin_url(); ?>" class="button">Quay lại Dashboard</a>
            <?php
        }
        ?>
    </div>
</body>
</html>