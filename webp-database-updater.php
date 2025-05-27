<?php
require_once('wp-load.php');

class WebPDatabaseUpdater {
    private $stats = ['posts' => 0, 'attachments' => 0, 'metadata' => 0, 'options' => 0, 'errors' => 0];
    private $log = [];
    
    public function __construct() {
        if (!current_user_can('administrator')) {
            wp_die('Bạn cần quyền administrator để thực hiện thao tác này.', 'Lỗi quyền truy cập', ['response' => 403]);
        }
    }
    
    private function log($message, $type = 'info') {
        $this->log[] = ['message' => $message, 'type' => $type, 'time' => current_time('H:i:s')];
        $this->flushLog();
    }
    
    private function flushLog() {
        if (ob_get_level()) ob_flush();
        flush();
    }
    
    private function verifyImageExists($image_path) {
        if (strpos($image_path, 'http') === 0) {
            $webp_url = preg_replace('/\.(jpe?g|png)/i', '.webp', $image_path);
            $headers = @get_headers($webp_url);
            return $headers && strpos($headers[0], '200') !== false;
        }
        
        $upload_dir = wp_upload_dir();
        $full_path = $upload_dir['basedir'] . '/' . $image_path;
        $webp_path = preg_replace('/\.(jpe?g|png)$/i', '.webp', $full_path);
        return file_exists($webp_path);
    }
    
    public function scanDatabase() {
        global $wpdb;
        
        $results = [
            'posts' => 0,
            'attachments' => 0,
            'metadata' => 0,
            'options' => 0,
            'total' => 0,
            'details' => []
        ];
        
        $posts = $wpdb->get_results("SELECT ID, post_title FROM {$wpdb->posts} WHERE post_content REGEXP '\\.(jpe?g|png)' OR guid REGEXP '\\.(jpe?g|png)'");
        $results['posts'] = count($posts);
        $results['details']['posts'] = array_slice($posts, 0, 5);
        
        $attachments = $wpdb->get_results("SELECT post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attached_file' AND meta_value REGEXP '\\.(jpe?g|png)$'");
        $results['attachments'] = count($attachments);
        $results['details']['attachments'] = array_slice($attachments, 0, 5);
        
        $metadata_count = $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attachment_metadata'");
        $results['metadata'] = $metadata_count;
        
        $options = $wpdb->get_results("SELECT option_name, option_value FROM {$wpdb->options} WHERE (option_name LIKE '%theme_mods_%' OR option_name LIKE '%widget_%' OR option_name IN ('site_logo', 'site_icon')) AND option_value REGEXP '\\.(jpe?g|png)'");
        $results['options'] = count($options);
        $results['details']['options'] = array_slice($options, 0, 3);
        
        $results['total'] = $results['posts'] + $results['attachments'] + $results['metadata'] + $results['options'];
        
        return $results;
    }
    
    public function performUpdate() {
        global $wpdb;
        
        set_time_limit(300);
        ob_start();
        
        $wpdb->query('START TRANSACTION');
        
        try {
            $this->log('🚀 Bắt đầu quá trình cập nhật database...', 'info');
            $this->updatePostContent();
            $this->updateAttachedFiles();
            $this->updateAttachmentMetadata();
            $this->updateThemeOptions();
            $this->cleanupCache();
            
            $wpdb->query('COMMIT');
            $this->log('✅ Hoàn tất! Tất cả thay đổi đã được lưu.', 'success');
            
        } catch (Exception $e) {
            $wpdb->query('ROLLBACK');
            $this->stats['errors']++;
            $this->log('❌ Lỗi: ' . $e->getMessage(), 'error');
            throw $e;
        }
    }
    
    private function updatePostContent() {
        global $wpdb;
        
        $this->log('📝 Đang quét posts và pages...', 'info');
        
        $posts = $wpdb->get_results("SELECT ID, post_content, guid FROM {$wpdb->posts} WHERE post_content REGEXP '\\.(jpe?g|png)' OR guid REGEXP '\\.(jpe?g|png)'");
        
        $this->log("   Tìm thấy " . count($posts) . " posts cần cập nhật", 'info');
        
        foreach ($posts as $post) {
            $updated_content = preg_replace('/\.(jpe?g|png)(\?[^\\s]*)?/i', '.webp$2', $post->post_content);
            $updated_guid = preg_replace('/\.(jpe?g|png)(\?[^\\s]*)?/i', '.webp$2', $post->guid);
            
            if ($updated_content !== $post->post_content || $updated_guid !== $post->guid) {
                $result = $wpdb->update($wpdb->posts, ['post_content' => $updated_content, 'guid' => $updated_guid], ['ID' => $post->ID], ['%s', '%s'], ['%d']);
                
                if ($result !== false) {
                    $this->stats['posts']++;
                    $this->log("   ✓ Cập nhật post ID: {$post->ID}", 'success');
                }
            }
        }
        
        $this->log("   📊 Đã cập nhật {$this->stats['posts']} posts/pages", 'success');
    }
    
    private function updateAttachedFiles() {
        global $wpdb;
        
        $this->log('📎 Đang quét attached files...', 'info');
        
        $attached_files = $wpdb->get_results("SELECT meta_id, post_id, meta_value FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attached_file' AND meta_value REGEXP '\\.(jpe?g|png)$'");
        
        $this->log("   Tìm thấy " . count($attached_files) . " attached files", 'info');
        
        foreach ($attached_files as $file) {
            $old_path = $file->meta_value;
            $new_path = preg_replace('/\.(jpe?g|png)$/i', '.webp', $old_path);
            
            if ($this->verifyImageExists($new_path)) {
                $result = $wpdb->update($wpdb->postmeta, ['meta_value' => $new_path], ['meta_id' => $file->meta_id], ['%s'], ['%d']);
                
                if ($result !== false) {
                    $this->stats['attachments']++;
                    $this->log("   ✓ Cập nhật: " . basename($new_path), 'success');
                }
            } else {
                $this->log("   ⚠️ Không tìm thấy: " . basename($new_path), 'warning');
            }
        }
        
        $this->log("   📊 Đã cập nhật {$this->stats['attachments']} attached files", 'success');
    }
    
    private function updateAttachmentMetadata() {
        global $wpdb;
        
        $this->log('🖼️ Đang cập nhật attachment metadata...', 'info');
        
        $attachment_ids = $wpdb->get_col("SELECT post_id FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attachment_metadata'");
        
        $this->log("   Đang xử lý " . count($attachment_ids) . " attachments", 'info');
        
        foreach ($attachment_ids as $post_id) {
            $metadata = wp_get_attachment_metadata($post_id);
            if (!is_array($metadata)) continue;
            
            $updated = false;
            
            if (isset($metadata['file'])) {
                $old_file = $metadata['file'];
                $new_file = preg_replace('/\.(jpe?g|png)$/i', '.webp', $old_file);
                
                if ($new_file !== $old_file && $this->verifyImageExists($new_file)) {
                    $metadata['file'] = $new_file;
                    $updated = true;
                }
            }
            
            if (isset($metadata['sizes']) && is_array($metadata['sizes'])) {
                foreach ($metadata['sizes'] as $size => $data) {
                    if (isset($data['file'])) {
                        $old_size_file = $data['file'];
                        $new_size_file = preg_replace('/\.(jpe?g|png)$/i', '.webp', $old_size_file);
                        
                        if ($new_size_file !== $old_size_file) {
                            $metadata['sizes'][$size]['file'] = $new_size_file;
                            $metadata['sizes'][$size]['mime-type'] = 'image/webp';
                            $updated = true;
                        }
                    }
                }
            }
            
            if ($updated) {
                wp_update_attachment_metadata($post_id, $metadata);
                $this->stats['metadata']++;
                $this->log("   ✓ Cập nhật metadata ID: {$post_id}", 'success');
            }
        }
        
        $this->log("   📊 Đã cập nhật {$this->stats['metadata']} attachment metadata", 'success');
    }
    
    private function updateThemeOptions() {
        global $wpdb;
        
        $this->log('🎨 Đang cập nhật theme options...', 'info');
        
        $options = $wpdb->get_results("SELECT option_id, option_name, option_value FROM {$wpdb->options} WHERE (option_name LIKE '%theme_mods_%' OR option_name LIKE '%widget_%' OR option_name IN ('site_logo', 'site_icon')) AND option_value REGEXP '\\.(jpe?g|png)'");
        
        $this->log("   Tìm thấy " . count($options) . " theme options", 'info');
        
        foreach ($options as $option) {
            $updated_value = preg_replace('/\.(jpe?g|png)(\?[^\\s]*)?/i', '.webp$2', $option->option_value);
            
            if ($updated_value !== $option->option_value) {
                $result = $wpdb->update($wpdb->options, ['option_value' => $updated_value], ['option_id' => $option->option_id], ['%s'], ['%d']);
                
                if ($result !== false) {
                    $this->stats['options']++;
                    $this->log("   ✓ Cập nhật option: {$option->option_name}", 'success');
                }
            }
        }
        
        $this->log("   📊 Đã cập nhật {$this->stats['options']} theme options", 'success');
    }
    
    private function cleanupCache() {
        $this->log('🧹 Đang xóa cache...', 'info');
        
        wp_cache_flush();
        
        if (function_exists('wp_cache_clear_cache')) {
            wp_cache_clear_cache();
            $this->log('   ✓ W3 Total Cache cleared', 'success');
        }
        
        if (function_exists('rocket_clean_domain')) {
            rocket_clean_domain();
            $this->log('   ✓ WP Rocket cache cleared', 'success');
        }
        
        $this->log('   ✓ WordPress cache cleared', 'success');
    }
    
    public function getStats() { return $this->stats; }
    public function getLog() { return $this->log; }
}

$updater = new WebPDatabaseUpdater();

if (isset($_POST['action']) && $_POST['action'] === 'scan' && wp_verify_nonce($_POST['_wpnonce'], 'webp_scan')) {
    $scan_results = $updater->scanDatabase();
}

if (isset($_POST['action']) && $_POST['action'] === 'update' && wp_verify_nonce($_POST['_wpnonce'], 'webp_update')) {
    ?>
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WordPress WebP Database Updater</title>
        <style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:20px}.container{max-width:900px;margin:0 auto;background:white;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.1);overflow:hidden}.header{background:linear-gradient(135deg,#2c3e50,#34495e);color:white;padding:30px;text-align:center}.header h1{font-size:28px;margin-bottom:10px;font-weight:600}.header p{opacity:0.9;font-size:16px}.content{padding:40px}.log-container{background:#f8f9fa;border-radius:12px;padding:25px;margin-top:30px;height:400px;overflow-y:auto;border:2px solid #dee2e6}.log-entry{display:flex;align-items:flex-start;margin-bottom:10px;padding:8px;border-radius:6px;font-family:'Monaco','Menlo',monospace;font-size:13px;animation:slideIn 0.3s ease}.log-entry.info{background:#e3f2fd;color:#1565c0}.log-entry.success{background:#e8f5e8;color:#2e7d32}.log-entry.warning{background:#fff3e0;color:#f57c00}.log-entry.error{background:#ffebee;color:#c62828}.log-time{background:rgba(0,0,0,0.1);padding:2px 8px;border-radius:12px;font-size:11px;margin-right:10px;min-width:60px;text-align:center}.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin:20px 0}.stat-card{background:linear-gradient(135deg,#f8f9fa,#e9ecef);padding:20px;border-radius:12px;text-align:center;border:2px solid #dee2e6}.stat-number{font-size:24px;font-weight:700;color:#2c3e50;margin-bottom:5px}.stat-label{color:#6c757d;font-size:12px;text-transform:uppercase;letter-spacing:0.5px}.button{display:inline-block;padding:15px 30px;border:none;border-radius:8px;font-size:16px;font-weight:600;text-decoration:none;cursor:pointer;transition:all 0.3s ease;margin:10px 10px 10px 0}.button-primary{background:linear-gradient(135deg,#667eea,#764ba2);color:white}.button-primary:hover{transform:translateY(-2px);box-shadow:0 10px 25px rgba(102,126,234,0.4)}@keyframes slideIn{from{opacity:0;transform:translateX(-20px)}to{opacity:1;transform:translateX(0)}}@media (max-width:768px){.content{padding:20px}.header{padding:20px}.header h1{font-size:24px}.stats-grid{grid-template-columns:1fr}}</style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 WordPress WebP Database Updater</h1>
                <p>Đang cập nhật database...</p>
            </div>
            
            <div class="content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number" id="posts-count">0</div>
                        <div class="stat-label">Posts/Pages</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="attachments-count">0</div>
                        <div class="stat-label">File đính kèm</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="metadata-count">0</div>
                        <div class="stat-label">Metadata</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number" id="options-count">0</div>
                        <div class="stat-label">Theme Options</div>
                    </div>
                </div>
                
                <div class="log-container">
                    <h3 style="margin-bottom:20px;color:#2c3e50">📋 Quá trình xử lý real-time:</h3>
                    <div id="log-entries"></div>
                </div>
                
                <div id="completion-area" style="display:none;text-align:center;margin-top:30px">
                    <a href="<?php echo admin_url(); ?>" class="button button-primary">🏠 Về Dashboard</a>
                </div>
            </div>
        </div>
        
        <script>
        let logContainer = document.getElementById('log-entries');
        let completionArea = document.getElementById('completion-area');
        
        function addLogEntry(message, type, time) {
            let entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            entry.innerHTML = '<span class="log-time">' + time + '</span><span>' + message + '</span>';
            logContainer.appendChild(entry);
            logContainer.scrollTop = logContainer.scrollHeight;
        }
        
        function updateStats(stats) {
            document.getElementById('posts-count').textContent = stats.posts;
            document.getElementById('attachments-count').textContent = stats.attachments;
            document.getElementById('metadata-count').textContent = stats.metadata;
            document.getElementById('options-count').textContent = stats.options;
        }
        
        function startProcessing() {
            fetch('<?php echo $_SERVER['PHP_SELF']; ?>', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'action=process&_wpnonce=<?php echo wp_create_nonce('webp_update'); ?>'
            })
            .then(response => response.json())
            .then(data => {
                data.log.forEach(entry => {
                    addLogEntry(entry.message, entry.type, entry.time);
                });
                updateStats(data.stats);
                
                if (data.success) {
                    addLogEntry('🎉 Hoàn thành tất cả! Database đã được cập nhật thành công.', 'success', new Date().toLocaleTimeString());
                    completionArea.style.display = 'block';
                } else {
                    addLogEntry('❌ Có lỗi xảy ra: ' + data.error, 'error', new Date().toLocaleTimeString());
                    completionArea.style.display = 'block';
                }
            })
            .catch(error => {
                addLogEntry('❌ Lỗi kết nối: ' + error.message, 'error', new Date().toLocaleTimeString());
                completionArea.style.display = 'block';
            });
        }
        
        startProcessing();
        </script>
    </body>
    </html>
    <?php
    exit;
}

if (isset($_POST['action']) && $_POST['action'] === 'process' && wp_verify_nonce($_POST['_wpnonce'], 'webp_update')) {
    header('Content-Type: application/json');
    
    try {
        $updater->performUpdate();
        echo json_encode(['success' => true, 'stats' => $updater->getStats(), 'log' => $updater->getLog()]);
    } catch (Exception $e) {
        echo json_encode(['success' => false, 'error' => $e->getMessage(), 'stats' => $updater->getStats(), 'log' => $updater->getLog()]);
    }
    exit;
}
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WordPress WebP Database Updater</title>
    <style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:20px}.container{max-width:900px;margin:0 auto;background:white;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.1);overflow:hidden}.header{background:linear-gradient(135deg,#2c3e50,#34495e);color:white;padding:30px;text-align:center}.header h1{font-size:28px;margin-bottom:10px;font-weight:600}.header p{opacity:0.9;font-size:16px}.content{padding:40px}.warning-box{background:linear-gradient(135deg,#ff7b7b,#ff6b6b);color:white;padding:25px;border-radius:12px;margin-bottom:30px;box-shadow:0 8px 25px rgba(255,107,107,0.3)}.warning-box h3{margin-bottom:15px;font-size:18px;display:flex;align-items:center}.warning-box ul{list-style:none;padding-left:0}.warning-box li{margin:10px 0;padding-left:25px;position:relative}.warning-box li:before{content:"⚠️";position:absolute;left:0}.button{display:inline-block;padding:15px 30px;border:none;border-radius:8px;font-size:16px;font-weight:600;text-decoration:none;cursor:pointer;transition:all 0.3s ease;margin:10px 10px 10px 0}.button-primary{background:linear-gradient(135deg,#667eea,#764ba2);color:white}.button-primary:hover{transform:translateY(-2px);box-shadow:0 10px 25px rgba(102,126,234,0.4)}.button-secondary{background:#f8f9fa;color:#495057;border:2px solid #dee2e6}.button-secondary:hover{background:#e9ecef;transform:translateY(-1px)}.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin:20px 0}.stat-card{background:linear-gradient(135deg,#f8f9fa,#e9ecef);padding:20px;border-radius:12px;text-align:center;border:2px solid #dee2e6}.stat-number{font-size:24px;font-weight:700;color:#2c3e50;margin-bottom:5px}.stat-label{color:#6c757d;font-size:12px;text-transform:uppercase;letter-spacing:0.5px}.preview-section{background:#f8f9fa;border-radius:12px;padding:20px;margin:20px 0;border:1px solid #dee2e6}.preview-box{background:white;border-radius:8px;padding:15px;margin:10px 0;border:1px solid #e9ecef}.preview-box ul{margin:10px 0;padding-left:20px}.preview-box li{margin:5px 0;color:#495057}.scan-results{animation:fadeIn 0.5s ease}.success-message{background:linear-gradient(135deg,#4caf50,#45a049);color:white;padding:25px;border-radius:12px;text-align:center;margin-bottom:30px;box-shadow:0 8px 25px rgba(76,175,80,0.3)}@keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}@media (max-width:768px){.content{padding:20px}.header{padding:20px}.header h1{font-size:24px}.stats-grid{grid-template-columns:1fr}}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 WordPress WebP Database Updater</h1>
            <p>Công cụ chuyên nghiệp để cập nhật references từ JPG/PNG sang WebP</p>
        </div>
        
        <div class="content">
            <div class="warning-box">
                <h3>⚠️ Quan trọng - Đọc kỹ trước khi thực hiện</h3>
                <ul>
                    <li>Đã backup database hoàn chỉnh</li>
                    <li>Tất cả ảnh WebP đã được tạo và upload thành công</li>
                    <li>Đã test trên môi trường staging trước</li>
                    <li>Quá trình này sẽ thay đổi toàn bộ database</li>
                    <li>Có thể mất vài phút để hoàn thành</li>
                </ul>
            </div>
            
            <?php if (!isset($scan_results)): ?>
            
            <form method="post">
                <?php wp_nonce_field('webp_scan'); ?>
                <input type="hidden" name="action" value="scan">
                
                <div style="text-align:center">
                    <button type="submit" class="button button-primary">🔍 Quét Database</button>
                    <a href="<?php echo admin_url(); ?>" class="button button-secondary">← Quay lại Dashboard</a>
                </div>
            </form>
            
            <?php else: ?>
            
            <div class="scan-results">
                <h3 style="color:#2c3e50;margin-bottom:20px">📊 Kết quả quét database:</h3>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number"><?php echo $scan_results['total']; ?></div>
                        <div class="stat-label">Tổng cần cập nhật</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number"><?php echo $scan_results['posts']; ?></div>
                        <div class="stat-label">Posts/Pages</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number"><?php echo $scan_results['attachments']; ?></div>
                        <div class="stat-label">File đính kèm</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number"><?php echo $scan_results['metadata']; ?></div>
                        <div class="stat-label">Metadata</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number"><?php echo $scan_results['options']; ?></div>
                        <div class="stat-label">Theme Options</div>
                    </div>
                </div>
                
                <?php if ($scan_results['total'] > 0): ?>
                
                <div class="preview-section">
                    <h4 style="color:#495057;margin:20px 0 10px">📝 Preview một số items sẽ được cập nhật:</h4>
                    
                    <?php if (!empty($scan_results['details']['posts'])): ?>
                    <div class="preview-box">
                        <strong>Posts/Pages:</strong>
                        <ul>
                            <?php foreach ($scan_results['details']['posts'] as $post): ?>
                            <li>ID: <?php echo $post->ID; ?> - <?php echo esc_html($post->post_title); ?></li>
                            <?php endforeach; ?>
                            <?php if ($scan_results['posts'] > 5): ?>
                            <li><em>... và <?php echo ($scan_results['posts'] - 5); ?> posts khác</em></li>
                            <?php endif; ?>
                        </ul>
                    </div>
                    <?php endif; ?>
                    
                    <?php if (!empty($scan_results['details']['attachments'])): ?>
                    <div class="preview-box">
                        <strong>Attachments:</strong>
                        <ul>
                            <?php foreach ($scan_results['details']['attachments'] as $attachment): ?>
                            <li><?php echo esc_html(basename($attachment->meta_value)); ?></li>
                            <?php endforeach; ?>
                            <?php if ($scan_results['attachments'] > 5): ?>
                            <li><em>... và <?php echo ($scan_results['attachments'] - 5); ?> files khác</em></li>
                            <?php endif; ?>
                        </ul>
                    </div>
                    <?php endif; ?>
                </div>
                
                <div style="text-align:center;margin-top:30px">
                    <form method="post" style="display:inline">
                        <?php wp_nonce_field('webp_update'); ?>
                        <input type="hidden" name="action" value="update">
                        <button type="submit" class="button button-primary">🚀 Bắt Đầu Xử Lý</button>
                    </form>
                    <a href="<?php echo admin_url(); ?>" class="button button-secondary">🏠 Về Dashboard</a>
                    <a href="<?php echo $_SERVER['PHP_SELF']; ?>" class="button button-secondary">🔄 Quét lại</a>
                </div>
                
                <?php else: ?>
                
                <div class="success-message" style="margin-top:30px">
                    <h2>✅ Tuyệt vời!</h2>
                    <p>Không tìm thấy ảnh JPG/PNG nào cần chuyển đổi trong database.</p>
                    <p>Website của bạn đã được tối ưu hoàn toàn!</p>
                </div>
                
                <div style="text-align:center;margin-top:20px">
                    <a href="<?php echo admin_url(); ?>" class="button button-primary">🏠 Về Dashboard</a>
                </div>
                
                <?php endif; ?>
            </div>
            
            <?php endif; ?>
        </div>
    </div>
</body>
</html>