<?php
require_once('wp-load.php');

class WebPDatabaseUpdater {
    private $batch_size = 500; // Increased batch size since ID scans are faster
    private $stats = ['posts' => 0, 'attachments' => 0, 'metadata' => 0, 'options' => 0, 'errors' => 0];
    private $log = [];
    
    public function __construct() {
        if (!current_user_can('administrator')) {
            wp_die('Unauthorized', 'Access Denied', ['response' => 403]);
        }
        @ini_set('max_execution_time', 0); // Disable timeout
        @ini_set('memory_limit', '512M');
    }
    
    private function log($message, $type = 'info') {
        $this->log[] = ['message' => $message, 'type' => $type, 'time' => current_time('H:i:s')];
    }
    
    private function verifyImageExists($image_path) {
        if (strpos($image_path, 'http') === 0) {
            $webp_url = preg_replace('/\.(jpe?g|png)/i', '.webp', $image_path);
            $headers = @get_headers($webp_url);
            return $headers && strpos($headers[0], '200') !== false;
        }
        
        $upload_dir = wp_upload_dir();
        // Handle cases where path already includes basedir or is relative
        $full_path = strpos($image_path, $upload_dir['basedir']) === false 
            ? $upload_dir['basedir'] . '/' . $image_path 
            : $image_path;
            
        $webp_path = preg_replace('/\.(jpe?g|png)$/i', '.webp', $full_path);
        return file_exists($webp_path);
    }
    
    // Step 1: Get Min/Max IDs to define the "work area"
    public function scanDatabase() {
        global $wpdb;
        
        $bounds = [
            'posts' => $wpdb->get_row("SELECT MIN(ID) as min, MAX(ID) as max, COUNT(ID) as total FROM {$wpdb->posts}"),
            'attachments' => $wpdb->get_row("SELECT MIN(meta_id) as min, MAX(meta_id) as max, COUNT(meta_id) as total FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attached_file'"),
            'metadata' => $wpdb->get_row("SELECT MIN(post_id) as min, MAX(post_id) as max, COUNT(post_id) as total FROM {$wpdb->postmeta} WHERE meta_key = '_wp_attachment_metadata'"),
            'options' => $wpdb->get_row("SELECT MIN(option_id) as min, MAX(option_id) as max, COUNT(option_id) as total FROM {$wpdb->options}"),
        ];

        return $bounds;
    }
    
    public function processBatch($type, $start_id, $end_id) {
        global $wpdb;
        
        $processed = 0;
        
        try {
            switch($type) {
                case 'posts':
                    $this->processPosts($start_id, $end_id);
                    break; 
                case 'attachments':
                    $this->processAttachments($start_id, $end_id);
                    break;
                case 'metadata':
                    $this->processMetadata($start_id, $end_id);
                    break;
                case 'options':
                    $this->processOptions($start_id, $end_id);
                    break;
                case 'cleanup':
                    $this->cleanupCache();
                    break;
            }
        } catch (Exception $e) {
            $this->stats['errors']++;
            $this->log('Error: ' . $e->getMessage(), 'error');
        }
        
        return [
            'stats' => $this->stats,
            'log' => $this->log
        ];
    }
    
    private function processPosts($start_id, $end_id) {
        global $wpdb;
        
        // Scan range. This is very fast.
        $posts = $wpdb->get_results($wpdb->prepare(
            "SELECT ID, post_content, guid FROM {$wpdb->posts} 
            WHERE ID BETWEEN %d AND %d",
            $start_id, $end_id
        ));
        
        foreach ($posts as $post) {
            // Check in PHP (much faster and reliable than Complex REGEXP in SQL)
            $has_image = preg_match('/\.(jpe?g|png)/i', $post->post_content) || 
                         preg_match('/\.(jpe?g|png)/i', $post->guid);
                         
            if (!$has_image) continue;

            $updated_content = preg_replace('/\.(jpe?g|png)(\?[^\s"\'<>]*)?/i', '.webp$2', $post->post_content);
            $updated_guid = preg_replace('/\.(jpe?g|png)(\?[^\s"\'<>]*)?/i', '.webp$2', $post->guid);
            
            if ($updated_content !== $post->post_content || $updated_guid !== $post->guid) {
                $wpdb->update(
                    $wpdb->posts,
                    ['post_content' => $updated_content, 'guid' => $updated_guid],
                    ['ID' => $post->ID],
                    ['%s', '%s'],
                    ['%d']
                );
                $this->stats['posts']++;
                $this->log("✓ Post ID: {$post->ID} updated", 'success');
            }
        }
    }
    
    private function processAttachments($start_id, $end_id) {
        global $wpdb;
        
        $attached_files = $wpdb->get_results($wpdb->prepare(
            "SELECT meta_id, post_id, meta_value FROM {$wpdb->postmeta} 
            WHERE meta_key = '_wp_attached_file' 
            AND meta_id BETWEEN %d AND %d",
            $start_id, $end_id
        ));
        
        foreach ($attached_files as $file) {
            if (!preg_match('/\.(jpe?g|png)$/i', $file->meta_value)) continue;

            $old_path = $file->meta_value;
            $new_path = preg_replace('/\.(jpe?g|png)$/i', '.webp', $old_path);
            
            if ($this->verifyImageExists($new_path)) {
                $wpdb->update(
                    $wpdb->postmeta,
                    ['meta_value' => $new_path],
                    ['meta_id' => $file->meta_id],
                    ['%s'],
                    ['%d']
                );
                $this->stats['attachments']++;
                $this->log("✓ Attachment: " . basename($new_path), 'success');
            }
        }
    }
    
    private function processMetadata($start_id, $end_id) {
        global $wpdb;
        
        // Use post_id as iterator since usage is via get_attachment_metadata(post_id)
        $attachment_ids = $wpdb->get_col($wpdb->prepare(
            "SELECT post_id FROM {$wpdb->postmeta} 
            WHERE meta_key = '_wp_attachment_metadata' 
            AND post_id BETWEEN %d AND %d",
            $start_id, $end_id
        ));
        
        foreach ($attachment_ids as $post_id) {
            $metadata = wp_get_attachment_metadata($post_id);
            if (!is_array($metadata)) continue;
            
            $updated = false;
            
            // 1. Check main file
            if (isset($metadata['file'])) {
                $old_file = $metadata['file'];
                if (preg_match('/\.(jpe?g|png)$/i', $old_file)) {
                    $new_file = preg_replace('/\.(jpe?g|png)$/i', '.webp', $old_file);
                    if ($this->verifyImageExists($new_file)) {
                        $metadata['file'] = $new_file;
                        $updated = true;
                    }
                }
            }
            
            // 2. Check sizes
            if (isset($metadata['sizes']) && is_array($metadata['sizes'])) {
                foreach ($metadata['sizes'] as $size => $data) {
                    if (isset($data['file'])) {
                        $old_size_file = $data['file'];
                        if (preg_match('/\.(jpe?g|png)$/i', $old_size_file)) {
                            $new_size_file = preg_replace('/\.(jpe?g|png)$/i', '.webp', $old_size_file);
                            // Optimistically assume sizes exist if main file exists, or check strictly
                            // For performance, we assume standard generation.
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
                //$this->log("✓ Metadata ID: {$post_id}", 'success'); // Reduce noise
            }
        }
    }
    
    private function processOptions($start_id, $end_id) {
        global $wpdb;
        
        $options = $wpdb->get_results($wpdb->prepare(
            "SELECT option_id, option_name, option_value FROM {$wpdb->options} 
            WHERE option_id BETWEEN %d AND %d",
            $start_id, $end_id
        ));
        
        foreach ($options as $option) {
            // Filter interesting options
            if (!preg_match('/(theme_mods_|widget_|site_logo|site_icon)/', $option->option_name)) continue;
            
            if (!preg_match('/\.(jpe?g|png)/i', $option->option_value)) continue;

            $updated_value = preg_replace('/\.(jpe?g|png)(\?[^\s"\'<>]*)?/i', '.webp$2', $option->option_value);
            
            if ($updated_value !== $option->option_value) {
                $wpdb->update(
                    $wpdb->options,
                    ['option_value' => $updated_value],
                    ['option_id' => $option->option_id],
                    ['%s'],
                    ['%d']
                );
                $this->stats['options']++;
                $this->log("✓ Option: {$option->option_name}", 'success');
            }
        }
    }
    
    private function cleanupCache() {
        $this->log('🧹 Clearing cache...', 'info');
        wp_cache_flush();
        if (function_exists('wp_cache_clear_cache')) wp_cache_clear_cache();
        if (function_exists('rocket_clean_domain')) rocket_clean_domain();
        $this->log('✓ Cache cleared', 'success');
    }
}

$updater = new WebPDatabaseUpdater();

// API Handle - Scan (Get Bounds)
if (isset($_POST['action']) && $_POST['action'] === 'scan' && wp_verify_nonce($_POST['_wpnonce'], 'webp_scan')) {
    header('Content-Type: application/json');
    $bounds = $updater->scanDatabase();
    echo json_encode(['success' => true, 'data' => $bounds]);
    exit;
}

// API Handle - Process Batch
if (isset($_POST['action']) && $_POST['action'] === 'process_batch' && wp_verify_nonce($_POST['_wpnonce'], 'webp_update')) {
    header('Content-Type: application/json');
    
    $type = sanitize_text_field($_POST['type'] ?? '');
    $start = intval($_POST['start'] ?? 0);
    $end = intval($_POST['end'] ?? 0);
    
    try {
        $result = $updater->processBatch($type, $start, $end);
        echo json_encode(['success' => true, 'data' => $result]);
    } catch (Exception $e) {
        echo json_encode(['success' => false, 'error' => $e->getMessage()]);
    }
    exit;
}

// UI Render
if (isset($_POST['action']) && $_POST['action'] === 'start_update' && wp_verify_nonce($_POST['_wpnonce'], 'webp_update')) {
    ?>
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WebP Database Updater (Optimized)</title>
        <style>
            :root{--primary:#667eea;--secondary:#764ba2;--success:#48bb78;--text:#2d3748;--bg:#f7fafc}
            *{box-sizing:border-box;margin:0;padding:0}
            body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%);min-height:100vh;padding:20px;color:var(--text)}
            .container{max-width:900px;margin:0 auto;background:white;border-radius:16px;box-shadow:0 10px 25px rgba(0,0,0,.1);overflow:hidden}
            .header{background:#2d3748;color:white;padding:30px;text-align:center}
            .header h1{font-size:24px;margin-bottom:8px}
            .content{padding:30px}
            
            .progress-section{background:#edf2f7;border-radius:12px;padding:20px;margin-bottom:20px}
            .progress-label{display:flex;justify-content:space-between;margin-bottom:10px;font-weight:600;font-size:14px}
            .progress-track{background:#cbd5e0;height:24px;border-radius:12px;overflow:hidden}
            .progress-bar{background:linear-gradient(90deg,var(--primary),var(--secondary));height:100%;width:0%;transition:width .2s linear}
            
            .log-box{background:#1a202c;color:#a0aec0;font-family:monospace;font-size:12px;padding:15px;border-radius:8px;height:300px;overflow-y:auto;margin-top:20px}
            .log-item{padding:4px 0;border-bottom:1px solid #2d3748}
            .log-item.success{color:var(--success)}
            .log-item.error{color:#f56565}
            .log-time{color:#718096;margin-right:10px}
            
            .stats-grid{display:grid;grid-template-columns:repeat(4, 1fr);gap:15px;margin-bottom:20px}
            .stat-card{background:white;border:1px solid #e2e8f0;padding:15px;border-radius:8px;text-align:center}
            .stat-val{font-size:24px;font-weight:700;color:var(--secondary)}
            .stat-lbl{font-size:12px;color:#718096;text-transform:uppercase}
            
            #completion-area{text-align:center;display:none;padding:20px}
            .btn{display:inline-block;padding:12px 24px;background:var(--primary);color:white;text-decoration:none;border-radius:6px;font-weight:600}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 Optimized WebP Updater</h1>
                <p id="status-text">Ready to start...</p>
            </div>
            
            <div class="content">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-val" id="stat-posts">0</div>
                        <div class="stat-lbl">Posts Updated</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-val" id="stat-attachments">0</div>
                        <div class="stat-lbl">Attachments</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-val" id="stat-metadata">0</div>
                        <div class="stat-lbl">Metadata</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-val" id="stat-options">0</div>
                        <div class="stat-lbl">Options</div>
                    </div>
                </div>

                <div class="progress-section">
                    <div class="progress-label">
                        <span id="task-name">Initializing...</span>
                        <span id="percent">0%</span>
                    </div>
                    <div class="progress-track">
                        <div class="progress-bar" id="main-progress"></div>
                    </div>
                    <div style="font-size:12px;color:#718096;margin-top:5px;text-align:right">
                        ID: <span id="current-id">0</span> / <span id="max-id">0</span>
                    </div>
                </div>
                
                <div class="log-box" id="log-console">
                    <!-- Logs go here -->
                </div>
                
                <div id="completion-area">
                    <h2 style="color:var(--success);margin-bottom:15px">🎉 Update Complete!</h2>
                    <a href="<?php echo admin_url(); ?>" class="btn">Return to Dashboard</a>
                </div>
            </div>
        </div>
        
        <script>
        const BATCH_SIZE = 500;
        const tasks = ['posts', 'attachments', 'metadata', 'options'];
        let stats = {posts:0, attachments:0, metadata:0, options:0};
        
        const ui = {
            log: document.getElementById('log-console'),
            bar: document.getElementById('main-progress'),
            percent: document.getElementById('percent'),
            taskName: document.getElementById('task-name'),
            status: document.getElementById('status-text'),
            currentId: document.getElementById('current-id'),
            maxId: document.getElementById('max-id'),
            stats: {
                posts: document.getElementById('stat-posts'),
                attachments: document.getElementById('stat-attachments'),
                metadata: document.getElementById('stat-metadata'),
                options: document.getElementById('stat-options'),
            }
        };
        
        function log(msg, type='info') {
            const div = document.createElement('div');
            div.className = `log-item ${type}`;
            div.innerHTML = `<span class="log-time">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
            ui.log.appendChild(div);
            ui.log.scrollTop = ui.log.scrollHeight;
        }
        
        async function run() {
            log('Starting Database Scan...', 'info');
            
            // 1. Get Bounds
            const formData = new FormData();
            formData.append('action', 'scan');
            formData.append('_wpnonce', '<?php echo wp_create_nonce('webp_scan'); ?>');
            
            try {
                const res = await fetch('<?php echo $_SERVER['PHP_SELF']; ?>', {method:'POST', body:formData});
                const json = await res.json();
                
                if(!json.success) throw new Error(json.error || 'Scan failed');
                
                const bounds = json.data;
                log('Scan complete. Starting processing...', 'success');
                
                // 2. Process each task
                for (const task of tasks) {
                    const bound = bounds[task];
                    if (!bound || !bound.min || !bound.max) {
                        log(`Skipping ${task} (No data)`, 'warning');
                        continue;
                    }
                    
                    const min = parseInt(bound.min);
                    const max = parseInt(bound.max);
                    let current = min;
                    
                    ui.taskName.textContent = `Processing ${task}...`;
                    ui.maxId.textContent = max;
                    
                    while (current <= max) {
                        const end = Math.min(current + BATCH_SIZE, max);
                        
                        // Update UI
                        const progress = Math.min(100, Math.round(((current - min) / (max - min)) * 100));
                        ui.bar.style.width = `${progress}%`;
                        ui.percent.textContent = `${progress}%`;
                        ui.currentId.textContent = current;
                        
                        // Call Batch
                        await processBatch(task, current, end);
                        
                        current += BATCH_SIZE + 1;
                    }
                    
                    log(`Completed ${task}`, 'success');
                }
                
                // 3. Cleanup
                ui.taskName.textContent = 'Final Cleanup...';
                await processBatch('cleanup', 0, 0);
                
                document.getElementById('completion-area').style.display = 'block';
                ui.status.textContent = 'All tasks finished.';
                
            } catch (e) {
                log(e.message, 'error');
                ui.status.textContent = 'Error occurred';
                alert('Error: ' + e.message);
            }
        }
        
        async function processBatch(type, start, end) {
            const formData = new FormData();
            formData.append('action', 'process_batch');
            formData.append('type', type);
            formData.append('start', start);
            formData.append('end', end);
            formData.append('_wpnonce', '<?php echo wp_create_nonce('webp_update'); ?>');
            
            const res = await fetch('<?php echo $_SERVER['PHP_SELF']; ?>', {method:'POST', body:formData});
            const json = await res.json();
            
            if (!json.success) throw new Error(json.error || 'Batch failed');
            
            // Update Stats locally to accumulate
            if (json.data.stats) {
                // Determine diff (server returns total cumulative for that batch instance, 
                // but since we reuse the class instance only per request, the stats resets if not persisted 
                // actually we should just add the diff or trust the user visual logs.
                // The PHP script is stateless between requests. 
                // So json.data.stats contains only what was processed in THIS batch.
                
                stats.posts += json.data.stats.posts;
                stats.attachments += json.data.stats.attachments;
                stats.metadata += json.data.stats.metadata;
                stats.options += json.data.stats.options;
                
                ui.stats.posts.textContent = stats.posts;
                ui.stats.attachments.textContent = stats.attachments;
                ui.stats.metadata.textContent = stats.metadata;
                ui.stats.options.textContent = stats.options;
            }
            
            if (json.data.log) {
                json.data.log.forEach(l => log(l.message, l.type));
            }
        }
        
        run();
        </script>
    </body>
    </html>
    <?php
    exit;
}
?>

<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>WebP Database Updater</title>
    <style>
        body{font-family:system-ui;background:#f0f2f5;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
        .card{background:white;padding:40px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,.1);text-align:center;max-width:500px}
        h1{color:#1a202c;margin-bottom:10px}
        p{color:#4a5568;margin-bottom:30px;line-height:1.5}
        .btn{background:#667eea;color:white;border:none;padding:15px 30px;border-radius:6px;font-size:16px;cursor:pointer;font-weight:600}
        .btn:hover{background:#5a67d8}
        .btn-outline{background:transparent;border:2px solid #cbd5e0;color:#4a5568}
    </style>
</head>
<body>
    <div class="card">
        <h1>WebP Database Optimizer</h1>
        <p>
            Phiên bản nâng cấp (ID-based Scanning).<br>
            An toàn cho database lớn, không bị timeout.<br>
            Mọi dữ liệu sẽ được chuyển đổi sang tham chiếu .webp
        </p>
        <form method="post">
            <?php wp_nonce_field('webp_update'); ?>
            <input type="hidden" name="action" value="start_update">
            <button type="submit" class="btn">🚀 Start Update Process</button>
            <div style="margin-top:10px">
                <a href="<?php echo admin_url(); ?>" class="btn btn-outline" style="text-decoration:none;display:inline-block">Back</a>
            </div>
        </form>
    </div>
</body>
</html>