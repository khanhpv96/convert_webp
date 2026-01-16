import sys
import os
import gc
import re
from pathlib import Path
from PIL import Image
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QLabel, QProgressBar, QTextEdit,
                            QSpinBox, QGroupBox, QFileDialog, QCheckBox, QFrame,
                            QMessageBox, QGridLayout, QTabWidget, QTableWidget,
                            QTableWidgetItem, QHeaderView, QLineEdit, QRadioButton,
                            QButtonGroup, QComboBox, QAbstractItemView)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor
import send2trash


class ImageConverterThread(QThread):
    progress_updated = pyqtSignal(int, int)
    log_updated = pyqtSignal(str)
    stats_updated = pyqtSignal(int, int)
    conversion_finished = pyqtSignal()
    
    def __init__(self, files, quality, keep_original):
        super().__init__()
        self.files = files
        self.quality = quality
        self.keep_original = keep_original
        self.processed_count = 0
        self.total_original_size = 0
        self.total_converted_size = 0
        self.is_running = True
        
    def run(self):
        total_files = len(self.files)
        
        for i, file_path in enumerate(self.files):
            if not self.is_running:
                break
                
            try:
                input_file = Path(file_path)
                base_name = input_file.stem
                output_file = input_file.parent / f"{base_name}.webp"
                
                original_size = input_file.stat().st_size
                self.total_original_size += original_size
                
                with Image.open(input_file) as img:
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    img.save(output_file, "webp", quality=self.quality, optimize=True)
                
                converted_size = output_file.stat().st_size
                self.total_converted_size += converted_size
                
                size_reduction = ((original_size - converted_size) / original_size) * 100
                
                self.log_updated.emit(f"✓ {input_file.name} → {output_file.name}")
                self.log_updated.emit(f"   Gốc: {self.format_size(original_size)} | WebP: {self.format_size(converted_size)} | Giảm: {size_reduction:.1f}%")
                
                if not self.keep_original:
                    os.remove(input_file)
                    self.log_updated.emit(f"✗ Đã xóa file gốc: {input_file.name}")
                
                self.processed_count += 1
                self.progress_updated.emit(i + 1, total_files)
                self.stats_updated.emit(self.total_original_size, self.total_converted_size)
                
            except Exception as e:
                self.log_updated.emit(f"❌ Lỗi khi xử lý {file_path}: {str(e)}")
        
        self.conversion_finished.emit()
    
    def stop(self):
        self.is_running = False
        
    def format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


class FileDeleteThread(QThread):
    progress_updated = pyqtSignal(int, int)
    log_updated = pyqtSignal(str)
    stats_updated = pyqtSignal(int, int)
    deletion_finished = pyqtSignal()
    
    def __init__(self, files, use_recycle_bin):
        super().__init__()
        self.files = files
        self.use_recycle_bin = use_recycle_bin
        self.deleted_count = 0
        self.total_size = 0
        self.is_running = True
        
    def run(self):
        total_files = len(self.files)
        
        for i, file_path in enumerate(self.files):
            if not self.is_running:
                break
                
            try:
                file_obj = Path(file_path)
                file_size = file_obj.stat().st_size
                
                if self.use_recycle_bin:
                    send2trash.send2trash(str(file_obj))
                    self.log_updated.emit(f"🗑️ Đã chuyển vào thùng rác: {file_obj.name}")
                else:
                    os.remove(file_obj)
                    self.log_updated.emit(f"✗ Đã xóa vĩnh viễn: {file_obj.name}")
                
                self.total_size += file_size
                self.deleted_count += 1
                self.progress_updated.emit(i + 1, total_files)
                self.stats_updated.emit(self.deleted_count, self.total_size)
                
            except Exception as e:
                self.log_updated.emit(f"❌ Lỗi khi xóa {file_path}: {str(e)}")
        
        self.deletion_finished.emit()
    
    def stop(self):
        self.is_running = False


class WebPConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_files = []
        self.all_scanned_files = []
        self.converter_thread = None
        self.delete_thread = None
        self.init_ui()
        self.setup_styles()
        
    def init_ui(self):
        self.setWindowTitle("WebP Image Converter & File Manager")
        self.setGeometry(100, 100, 1200, 900)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        header_label = QLabel("WebP Image Converter & File Manager")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        main_layout.addWidget(header_label)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e9ecef;
                color: #495057;
                padding: 10px 20px;
                margin-right: 5px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #007bff;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #d0d4d8;
            }
        """)
        
        self.convert_tab = QWidget()
        self.delete_tab = QWidget()
        
        self.setup_convert_tab()
        self.setup_delete_tab()
        
        self.tab_widget.addTab(self.convert_tab, "🔄 Chuyển Đổi")
        self.tab_widget.addTab(self.delete_tab, "🗑️ Xóa File")
        
        main_layout.addWidget(self.tab_widget)
        
        self.create_shared_components(main_layout)
        
    def setup_convert_tab(self):
        layout = QVBoxLayout(self.convert_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.create_file_selection_group(layout)
        self.create_filter_group(layout)
        self.create_settings_group(layout)
        self.create_preview_table(layout, "convert")
        self.create_convert_control_buttons(layout)
        
    def setup_delete_tab(self):
        layout = QVBoxLayout(self.delete_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.create_delete_source_group(layout)
        self.create_delete_criteria_group(layout)
        self.create_delete_safety_group(layout)
        self.create_preview_table(layout, "delete")
        self.create_delete_control_buttons(layout)
        
    def create_file_selection_group(self, parent_layout):
        group = QGroupBox("Chọn File/Thư Mục")
        layout = QVBoxLayout(group)
        
        button_layout = QHBoxLayout()
        
        self.select_files_btn = QPushButton("📁 Chọn Ảnh")
        self.select_files_btn.clicked.connect(self.select_files)
        
        self.select_folder_btn = QPushButton("📂 Chọn Thư Mục")
        self.select_folder_btn.clicked.connect(self.select_folder)
        
        button_layout.addWidget(self.select_files_btn)
        button_layout.addWidget(self.select_folder_btn)
        
        self.file_count_label = QLabel("Chưa chọn file nào")
        self.file_count_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        
        layout.addLayout(button_layout)
        layout.addWidget(self.file_count_label)
        
        parent_layout.addWidget(group)
        
    def create_filter_group(self, parent_layout):
        group = QGroupBox("⚙️ Bộ Lọc File")
        main_layout = QVBoxLayout(group)
        
        formats_layout = QHBoxLayout()
        formats_label = QLabel("Định dạng cần chuyển đổi:")
        formats_layout.addWidget(formats_label)
        
        self.filter_jpg_cb = QCheckBox("JPG/JPEG")
        self.filter_jpg_cb.setChecked(True)
        self.filter_jpg_cb.stateChanged.connect(self.apply_filters)
        
        self.filter_png_cb = QCheckBox("PNG")
        self.filter_png_cb.setChecked(True)
        self.filter_png_cb.stateChanged.connect(self.apply_filters)
        
        self.filter_bmp_cb = QCheckBox("BMP")
        self.filter_bmp_cb.setChecked(False)
        self.filter_bmp_cb.stateChanged.connect(self.apply_filters)
        
        self.filter_tiff_cb = QCheckBox("TIFF")
        self.filter_tiff_cb.setChecked(False)
        self.filter_tiff_cb.stateChanged.connect(self.apply_filters)
        
        self.filter_gif_cb = QCheckBox("GIF")
        self.filter_gif_cb.setChecked(False)
        self.filter_gif_cb.stateChanged.connect(self.apply_filters)
        
        formats_layout.addWidget(self.filter_jpg_cb)
        formats_layout.addWidget(self.filter_png_cb)
        formats_layout.addWidget(self.filter_bmp_cb)
        formats_layout.addWidget(self.filter_tiff_cb)
        formats_layout.addWidget(self.filter_gif_cb)
        formats_layout.addStretch()
        
        pattern_layout = QGridLayout()
        
        prefix_label = QLabel("Tiền tố (prefix):")
        self.filter_prefix_input = QLineEdit()
        self.filter_prefix_input.setPlaceholderText("VD: IMG_, photo_")
        self.filter_prefix_input.textChanged.connect(self.apply_filters)
        
        suffix_label = QLabel("Hậu tố (suffix):")
        self.filter_suffix_input = QLineEdit()
        self.filter_suffix_input.setPlaceholderText("VD: _old, _backup")
        self.filter_suffix_input.textChanged.connect(self.apply_filters)
        
        pattern_layout.addWidget(prefix_label, 0, 0)
        pattern_layout.addWidget(self.filter_prefix_input, 0, 1)
        pattern_layout.addWidget(suffix_label, 0, 2)
        pattern_layout.addWidget(self.filter_suffix_input, 0, 3)
        
        self.filter_regex_cb = QCheckBox("🔧 Chế độ Regex")
        self.filter_regex_cb.stateChanged.connect(self.apply_filters)
        
        self.filtered_count_label = QLabel("0/0 files sẽ được chuyển đổi")
        self.filtered_count_label.setStyleSheet("color: #007bff; font-weight: bold; font-size: 13px;")
        
        main_layout.addLayout(formats_layout)
        main_layout.addLayout(pattern_layout)
        main_layout.addWidget(self.filter_regex_cb)
        main_layout.addWidget(self.filtered_count_label)
        
        parent_layout.addWidget(group)
        
    def create_settings_group(self, parent_layout):
        group = QGroupBox("Cài Đặt Chuyển Đổi")
        layout = QHBoxLayout(group)
        
        quality_layout = QVBoxLayout()
        quality_label = QLabel("Chất lượng WebP:")
        self.quality_spinbox = QSpinBox()
        self.quality_spinbox.setRange(1, 100)
        self.quality_spinbox.setValue(85)
        self.quality_spinbox.setSuffix("%")
        self.quality_spinbox.setFixedHeight(35)
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_spinbox)
        
        self.keep_original_checkbox = QCheckBox("Giữ lại file gốc")
        self.keep_original_checkbox.setChecked(False)
        
        layout.addLayout(quality_layout)
        layout.addStretch()
        layout.addWidget(self.keep_original_checkbox)
        
        parent_layout.addWidget(group)
        
    def create_delete_source_group(self, parent_layout):
        group = QGroupBox("📂 Chọn Nguồn")
        layout = QVBoxLayout(group)
        
        button_layout = QHBoxLayout()
        
        self.delete_select_files_btn = QPushButton("📁 Chọn Files")
        self.delete_select_files_btn.clicked.connect(self.delete_select_files)
        
        self.delete_select_folder_btn = QPushButton("📂 Chọn Thư Mục")
        self.delete_select_folder_btn.clicked.connect(self.delete_select_folder)
        
        button_layout.addWidget(self.delete_select_files_btn)
        button_layout.addWidget(self.delete_select_folder_btn)
        
        self.delete_file_count_label = QLabel("Chưa chọn file nào")
        self.delete_file_count_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        
        layout.addLayout(button_layout)
        layout.addWidget(self.delete_file_count_label)
        
        parent_layout.addWidget(group)
        
    def create_delete_criteria_group(self, parent_layout):
        group = QGroupBox("🎯 Điều Kiện Xóa")
        main_layout = QVBoxLayout(group)
        
        formats_layout = QHBoxLayout()
        formats_label = QLabel("Định dạng cần xóa:")
        formats_layout.addWidget(formats_label)
        
        self.delete_filter_webp_cb = QCheckBox("WEBP")
        self.delete_filter_webp_cb.setChecked(False)
        self.delete_filter_webp_cb.stateChanged.connect(self.apply_delete_filters)
        
        self.delete_filter_jpg_cb = QCheckBox("JPG/JPEG")
        self.delete_filter_jpg_cb.setChecked(False)
        self.delete_filter_jpg_cb.stateChanged.connect(self.apply_delete_filters)
        
        self.delete_filter_png_cb = QCheckBox("PNG")
        self.delete_filter_png_cb.setChecked(False)
        self.delete_filter_png_cb.stateChanged.connect(self.apply_delete_filters)
        
        self.delete_filter_bmp_cb = QCheckBox("BMP")
        self.delete_filter_bmp_cb.setChecked(False)
        self.delete_filter_bmp_cb.stateChanged.connect(self.apply_delete_filters)
        
        self.delete_filter_tiff_cb = QCheckBox("TIFF")
        self.delete_filter_tiff_cb.setChecked(False)
        self.delete_filter_tiff_cb.stateChanged.connect(self.apply_delete_filters)
        
        self.delete_filter_gif_cb = QCheckBox("GIF")
        self.delete_filter_gif_cb.setChecked(False)
        self.delete_filter_gif_cb.stateChanged.connect(self.apply_delete_filters)
        
        formats_layout.addWidget(self.delete_filter_webp_cb)
        formats_layout.addWidget(self.delete_filter_jpg_cb)
        formats_layout.addWidget(self.delete_filter_png_cb)
        formats_layout.addWidget(self.delete_filter_bmp_cb)
        formats_layout.addWidget(self.delete_filter_tiff_cb)
        formats_layout.addWidget(self.delete_filter_gif_cb)
        formats_layout.addStretch()
        
        pattern_layout = QGridLayout()
        
        prefix_label = QLabel("Tiền tố:")
        self.delete_prefix_input = QLineEdit()
        self.delete_prefix_input.setPlaceholderText("VD: temp_, old_")
        self.delete_prefix_input.textChanged.connect(self.apply_delete_filters)
        
        suffix_label = QLabel("Hậu tố:")
        self.delete_suffix_input = QLineEdit()
        self.delete_suffix_input.setPlaceholderText("VD: _backup, _tmp")
        self.delete_suffix_input.textChanged.connect(self.apply_delete_filters)
        
        pattern_layout.addWidget(prefix_label, 0, 0)
        pattern_layout.addWidget(self.delete_prefix_input, 0, 1)
        pattern_layout.addWidget(suffix_label, 0, 2)
        pattern_layout.addWidget(self.delete_suffix_input, 0, 3)
        
        self.delete_regex_cb = QCheckBox("🔧 Chế độ Regex")
        self.delete_regex_cb.stateChanged.connect(self.apply_delete_filters)
        
        self.delete_filtered_count_label = QLabel("0/0 files sẽ được xóa")
        self.delete_filtered_count_label.setStyleSheet("color: #dc3545; font-weight: bold; font-size: 13px;")
        
        main_layout.addLayout(formats_layout)
        main_layout.addLayout(pattern_layout)
        main_layout.addWidget(self.delete_regex_cb)
        main_layout.addWidget(self.delete_filtered_count_label)
        
        parent_layout.addWidget(group)
        
    def create_delete_safety_group(self, parent_layout):
        group = QGroupBox("🛡️ Cài Đặt An Toàn")
        layout = QHBoxLayout(group)
        
        self.use_recycle_bin_cb = QCheckBox("🗑️ Chuyển vào Thùng Rác (khuyến nghị)")
        self.use_recycle_bin_cb.setChecked(True)
        self.use_recycle_bin_cb.setStyleSheet("font-weight: bold; color: #28a745;")
        
        warning_label = QLabel("⚠️ Bỏ tick = Xóa vĩnh viễn!")
        warning_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        
        layout.addWidget(self.use_recycle_bin_cb)
        layout.addStretch()
        layout.addWidget(warning_label)
        
        parent_layout.addWidget(group)
        
    def create_preview_table(self, parent_layout, mode):
        group = QGroupBox("👁️ Xem Trước Danh Sách File")
        layout = QVBoxLayout(group)
        
        if mode == "convert":
            self.preview_table = QTableWidget()
            table = self.preview_table
        else:
            self.delete_preview_table = QTableWidget()
            table = self.delete_preview_table
            
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["✓", "Tên File", "Kích Thước", "Định Dạng", "Đường Dẫn"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setMaximumHeight(200)
        
        button_layout = QHBoxLayout()
        
        if mode == "convert":
            select_all_btn = QPushButton("Chọn Tất Cả")
            select_all_btn.clicked.connect(self.select_all_preview)
            deselect_all_btn = QPushButton("Bỏ Chọn Tất Cả")
            deselect_all_btn.clicked.connect(self.deselect_all_preview)
        else:
            select_all_btn = QPushButton("Chọn Tất Cả")
            select_all_btn.clicked.connect(self.select_all_delete_preview)
            deselect_all_btn = QPushButton("Bỏ Chọn Tất Cả")
            deselect_all_btn.clicked.connect(self.deselect_all_delete_preview)
        
        select_all_btn.setMaximumWidth(150)
        deselect_all_btn.setMaximumWidth(150)
        
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        
        layout.addWidget(table)
        layout.addLayout(button_layout)
        
        parent_layout.addWidget(group)
        
    def create_convert_control_buttons(self, parent_layout):
        button_layout = QHBoxLayout()
        
        self.convert_btn = QPushButton("▶️ Bắt Đầu Chuyển Đổi")
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setEnabled(False)
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                font-size: 14px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        
        self.stop_convert_btn = QPushButton("⏹️ Dừng")
        self.stop_convert_btn.clicked.connect(self.stop_conversion)
        self.stop_convert_btn.setEnabled(False)
        
        button_layout.addWidget(self.convert_btn)
        button_layout.addWidget(self.stop_convert_btn)
        button_layout.addStretch()
        
        parent_layout.addLayout(button_layout)
        
    def create_delete_control_buttons(self, parent_layout):
        button_layout = QHBoxLayout()
        
        self.delete_btn = QPushButton("🗑️ Xóa Files Đã Chọn")
        self.delete_btn.clicked.connect(self.start_deletion)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                font-size: 14px;
                min-height: 25px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        
        self.stop_delete_btn = QPushButton("⏹️ Dừng")
        self.stop_delete_btn.clicked.connect(self.stop_deletion)
        self.stop_delete_btn.setEnabled(False)
        
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.stop_delete_btn)
        button_layout.addStretch()
        
        parent_layout.addLayout(button_layout)
        
    def create_shared_components(self, parent_layout):
        self.create_progress_group(parent_layout)
        self.create_stats_group(parent_layout)
        self.create_log_group(parent_layout)
        self.create_bottom_buttons(parent_layout)
        
    def create_progress_group(self, parent_layout):
        group = QGroupBox("📊 Tiến Trình")
        layout = QVBoxLayout(group)
        
        self.progress_label = QLabel("Sẵn sàng...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        stats_layout = QHBoxLayout()
        self.processed_label = QLabel("Đã xử lý: 0")
        self.total_label = QLabel("Tổng số: 0")
        
        stats_layout.addWidget(self.processed_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self.total_label)
        
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addLayout(stats_layout)
        
        parent_layout.addWidget(group)
        
    def create_stats_group(self, parent_layout):
        group = QGroupBox("📈 Thống Kê")
        layout = QGridLayout(group)
        
        self.stat_label_1 = QLabel("Dung lượng gốc:")
        self.stat_value_1 = QLabel("0 B")
        self.stat_value_1.setStyleSheet("font-weight: bold; color: #6c757d;")
        
        self.stat_label_2 = QLabel("Dung lượng mới:")
        self.stat_value_2 = QLabel("0 B")
        self.stat_value_2.setStyleSheet("font-weight: bold; color: #007bff;")
        
        self.stat_label_3 = QLabel("Đã tiết kiệm:")
        self.stat_value_3 = QLabel("0 B (0%)")
        self.stat_value_3.setStyleSheet("font-weight: bold; color: #28a745;")
        
        layout.addWidget(self.stat_label_1, 0, 0)
        layout.addWidget(self.stat_value_1, 0, 1)
        layout.addWidget(self.stat_label_2, 0, 2)
        layout.addWidget(self.stat_value_2, 0, 3)
        layout.addWidget(self.stat_label_3, 1, 0)
        layout.addWidget(self.stat_value_3, 1, 1, 1, 3)
        
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        
        parent_layout.addWidget(group)
        
    def create_log_group(self, parent_layout):
        group = QGroupBox("📝 Nhật Ký Hoạt Động")
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        
        clear_log_btn = QPushButton("🧹 Xóa Log")
        clear_log_btn.clicked.connect(self.clear_log)
        clear_log_btn.setMaximumWidth(100)
        
        layout.addWidget(self.log_text)
        layout.addWidget(clear_log_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        parent_layout.addWidget(group)
        
    def create_bottom_buttons(self, parent_layout):
        button_layout = QHBoxLayout()
        
        self.clear_memory_btn = QPushButton("🧹 Xóa Bộ Nhớ Đệm")
        self.clear_memory_btn.clicked.connect(self.clear_memory)
        
        self.reset_stats_btn = QPushButton("🔄 Reset Thống Kê")
        self.reset_stats_btn.clicked.connect(self.reset_stats)
        
        button_layout.addWidget(self.reset_stats_btn)
        button_layout.addWidget(self.clear_memory_btn)
        button_layout.addStretch()
        
        parent_layout.addLayout(button_layout)
        
    def setup_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #495057;
            }
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
            QProgressBar {
                border: 2px solid #dee2e6;
                border-radius: 6px;
                text-align: center;
                background-color: #e9ecef;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 4px;
            }
            QTextEdit {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                background-color: #f8f9fa;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
            QSpinBox, QLineEdit {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            QCheckBox {
                font-weight: normal;
            }
            QLabel {
                font-weight: normal;
            }
            QTableWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 8px;
                border: 1px solid #dee2e6;
                font-weight: bold;
            }
        """)
        
    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh", "", 
            "Image files (*.jpg *.jpeg *.png *.bmp *.tiff *.gif);;All files (*.*)"
        )
        if files:
            self.all_scanned_files = files
            self.apply_filters()
            
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa ảnh")
        if folder:
            self.all_scanned_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif')) and not file.lower().endswith('.webp'):
                        self.all_scanned_files.append(os.path.join(root, file))
            self.apply_filters()
            
    def apply_filters(self):
        if not hasattr(self, 'all_scanned_files'):
            return
            
        allowed_extensions = []
        if self.filter_jpg_cb.isChecked():
            allowed_extensions.extend(['.jpg', '.jpeg'])
        if self.filter_png_cb.isChecked():
            allowed_extensions.append('.png')
        if self.filter_bmp_cb.isChecked():
            allowed_extensions.append('.bmp')
        if self.filter_tiff_cb.isChecked():
            allowed_extensions.extend(['.tiff', '.tif'])
        if self.filter_gif_cb.isChecked():
            allowed_extensions.append('.gif')
            
        prefix = self.filter_prefix_input.text()
        suffix = self.filter_suffix_input.text()
        use_regex = self.filter_regex_cb.isChecked()
        
        self.selected_files = []
        
        for file_path in self.all_scanned_files:
            file_obj = Path(file_path)
            file_name = file_obj.stem
            file_ext = file_obj.suffix.lower()
            
            if allowed_extensions and file_ext not in allowed_extensions:
                continue
                
            if use_regex:
                try:
                    if prefix and not re.match(prefix, file_name):
                        continue
                    if suffix and not re.search(suffix + '$', file_name):
                        continue
                except re.error:
                    pass
            else:
                if prefix and not file_name.startswith(prefix):
                    continue
                if suffix and not file_name.endswith(suffix):
                    continue
                    
            self.selected_files.append(file_path)
            
        self.update_file_count()
        self.update_preview_table()
        
    def update_file_count(self):
        total_count = len(self.all_scanned_files) if hasattr(self, 'all_scanned_files') else 0
        filtered_count = len(self.selected_files)
        
        if filtered_count > 0:
            self.file_count_label.setText(f"Đã chọn {total_count} ảnh")
            self.file_count_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.filtered_count_label.setText(f"{filtered_count}/{total_count} files sẽ được chuyển đổi")
            self.convert_btn.setEnabled(True)
            self.total_label.setText(f"Tổng số: {filtered_count}")
        else:
            if total_count > 0:
                self.file_count_label.setText(f"Đã chọn {total_count} ảnh")
                self.filtered_count_label.setText(f"0/{total_count} files (tất cả bị lọc)")
                self.filtered_count_label.setStyleSheet("color: #dc3545; font-weight: bold; font-size: 13px;")
            else:
                self.file_count_label.setText("Chưa chọn file nào")
                self.filtered_count_label.setText("0/0 files sẽ được chuyển đổi")
            self.file_count_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
            self.convert_btn.setEnabled(False)
            
    def update_preview_table(self):
        self.preview_table.setRowCount(0)
        
        for file_path in self.selected_files:
            file_obj = Path(file_path)
            file_size = file_obj.stat().st_size
            
            row = self.preview_table.rowCount()
            self.preview_table.insertRow(row)
            
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            
            self.preview_table.setCellWidget(row, 0, checkbox_widget)
            self.preview_table.setItem(row, 1, QTableWidgetItem(file_obj.name))
            self.preview_table.setItem(row, 2, QTableWidgetItem(self.format_size(file_size)))
            self.preview_table.setItem(row, 3, QTableWidgetItem(file_obj.suffix.upper()))
            self.preview_table.setItem(row, 4, QTableWidgetItem(str(file_obj.parent)))
            
    def select_all_preview(self):
        for row in range(self.preview_table.rowCount()):
            checkbox_widget = self.preview_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(True)
                
    def deselect_all_preview(self):
        for row in range(self.preview_table.rowCount()):
            checkbox_widget = self.preview_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(False)
                
    def delete_select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn files để xóa", "", 
            "All files (*.*)"
        )
        if files:
            self.all_delete_files = files
            self.apply_delete_filters()
            
    def delete_select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if folder:
            self.all_delete_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    self.all_delete_files.append(os.path.join(root, file))
            self.apply_delete_filters()
            
    def apply_delete_filters(self):
        if not hasattr(self, 'all_delete_files'):
            return
            
        allowed_extensions = []
        if self.delete_filter_webp_cb.isChecked():
            allowed_extensions.append('.webp')
        if self.delete_filter_jpg_cb.isChecked():
            allowed_extensions.extend(['.jpg', '.jpeg'])
        if self.delete_filter_png_cb.isChecked():
            allowed_extensions.append('.png')
        if self.delete_filter_bmp_cb.isChecked():
            allowed_extensions.append('.bmp')
        if self.delete_filter_tiff_cb.isChecked():
            allowed_extensions.extend(['.tiff', '.tif'])
        if self.delete_filter_gif_cb.isChecked():
            allowed_extensions.append('.gif')
            
        prefix = self.delete_prefix_input.text()
        suffix = self.delete_suffix_input.text()
        use_regex = self.delete_regex_cb.isChecked()
        
        self.selected_delete_files = []
        
        for file_path in self.all_delete_files:
            file_obj = Path(file_path)
            file_name = file_obj.stem
            file_ext = file_obj.suffix.lower()
            
            if allowed_extensions and file_ext not in allowed_extensions:
                continue
                
            if use_regex:
                try:
                    if prefix and not re.match(prefix, file_name):
                        continue
                    if suffix and not re.search(suffix + '$', file_name):
                        continue
                except re.error:
                    pass
            else:
                if prefix and not file_name.startswith(prefix):
                    continue
                if suffix and not file_name.endswith(suffix):
                    continue
                    
            self.selected_delete_files.append(file_path)
            
        self.update_delete_file_count()
        self.update_delete_preview_table()
        
    def update_delete_file_count(self):
        total_count = len(self.all_delete_files) if hasattr(self, 'all_delete_files') else 0
        filtered_count = len(self.selected_delete_files) if hasattr(self, 'selected_delete_files') else 0
        
        if filtered_count > 0:
            self.delete_file_count_label.setText(f"Đã quét {total_count} files")
            self.delete_file_count_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.delete_filtered_count_label.setText(f"{filtered_count}/{total_count} files sẽ được xóa")
            self.delete_btn.setEnabled(True)
        else:
            if total_count > 0:
                self.delete_file_count_label.setText(f"Đã quét {total_count} files")
                self.delete_filtered_count_label.setText(f"0/{total_count} files (tất cả bị lọc)")
            else:
                self.delete_file_count_label.setText("Chưa chọn file nào")
                self.delete_filtered_count_label.setText("0/0 files sẽ được xóa")
            self.delete_file_count_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
            self.delete_btn.setEnabled(False)
            
    def update_delete_preview_table(self):
        self.delete_preview_table.setRowCount(0)
        
        if not hasattr(self, 'selected_delete_files'):
            return
            
        for file_path in self.selected_delete_files:
            file_obj = Path(file_path)
            file_size = file_obj.stat().st_size
            
            row = self.delete_preview_table.rowCount()
            self.delete_preview_table.insertRow(row)
            
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            
            self.delete_preview_table.setCellWidget(row, 0, checkbox_widget)
            self.delete_preview_table.setItem(row, 1, QTableWidgetItem(file_obj.name))
            self.delete_preview_table.setItem(row, 2, QTableWidgetItem(self.format_size(file_size)))
            self.delete_preview_table.setItem(row, 3, QTableWidgetItem(file_obj.suffix.upper()))
            self.delete_preview_table.setItem(row, 4, QTableWidgetItem(str(file_obj.parent)))
            
    def select_all_delete_preview(self):
        for row in range(self.delete_preview_table.rowCount()):
            checkbox_widget = self.delete_preview_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(True)
                
    def deselect_all_delete_preview(self):
        for row in range(self.delete_preview_table.rowCount()):
            checkbox_widget = self.delete_preview_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(False)
                
    def start_conversion(self):
        selected_files_to_convert = []
        for row in range(self.preview_table.rowCount()):
            checkbox_widget = self.preview_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                selected_files_to_convert.append(self.selected_files[row])
        
        if not selected_files_to_convert:
            QMessageBox.warning(self, "Cảnh báo", "Không có file nào được chọn để chuyển đổi!")
            return
            
        self.reset_stats()
        
        quality = self.quality_spinbox.value()
        keep_original = self.keep_original_checkbox.isChecked()
        
        self.converter_thread = ImageConverterThread(selected_files_to_convert, quality, keep_original)
        self.converter_thread.progress_updated.connect(self.update_progress)
        self.converter_thread.log_updated.connect(self.update_log)
        self.converter_thread.stats_updated.connect(self.update_convert_stats)
        self.converter_thread.conversion_finished.connect(self.conversion_finished)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_files_to_convert))
        self.progress_bar.setValue(0)
        
        self.convert_btn.setEnabled(False)
        self.stop_convert_btn.setEnabled(True)
        self.progress_label.setText("Đang chuyển đổi...")
        
        self.stat_label_1.setText("Dung lượng gốc:")
        self.stat_label_2.setText("Dung lượng WebP:")
        self.stat_label_3.setText("Đã tiết kiệm:")
        
        self.converter_thread.start()
        
    def stop_conversion(self):
        if self.converter_thread and self.converter_thread.isRunning():
            self.converter_thread.stop()
            self.converter_thread.wait()
            self.conversion_finished()
            self.update_log("⚠️ Quá trình chuyển đổi đã bị dừng")
            
    def start_deletion(self):
        selected_files_to_delete = []
        for row in range(self.delete_preview_table.rowCount()):
            checkbox_widget = self.delete_preview_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                selected_files_to_delete.append(self.selected_delete_files[row])
        
        if not selected_files_to_delete:
            QMessageBox.warning(self, "Cảnh báo", "Không có file nào được chọn để xóa!")
            return
            
        use_recycle = self.use_recycle_bin_cb.isChecked()
        action_text = "chuyển vào thùng rác" if use_recycle else "XÓA VĨNH VIỄN"
        
        total_size = sum(Path(f).stat().st_size for f in selected_files_to_delete)
        
        msg = f"Bạn có chắc chắn muốn {action_text} {len(selected_files_to_delete)} files?\n\n"
        msg += f"Tổng dung lượng: {self.format_size(total_size)}\n\n"
        if not use_recycle:
            msg += "⚠️ CẢNH BÁO: Files sẽ bị xóa vĩnh viễn và KHÔNG THỂ KHÔI PHỤC!"
        
        reply = QMessageBox.question(
            self, "Xác nhận xóa", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        self.reset_stats()
        
        self.delete_thread = FileDeleteThread(selected_files_to_delete, use_recycle)
        self.delete_thread.progress_updated.connect(self.update_progress)
        self.delete_thread.log_updated.connect(self.update_log)
        self.delete_thread.stats_updated.connect(self.update_delete_stats)
        self.delete_thread.deletion_finished.connect(self.deletion_finished)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(selected_files_to_delete))
        self.progress_bar.setValue(0)
        
        self.delete_btn.setEnabled(False)
        self.stop_delete_btn.setEnabled(True)
        self.progress_label.setText("Đang xóa files...")
        
        self.stat_label_1.setText("Files đã xóa:")
        self.stat_label_2.setText("Dung lượng giải phóng:")
        self.stat_label_3.setText("")
        self.stat_value_3.setText("")
        
        self.delete_thread.start()
        
    def stop_deletion(self):
        if self.delete_thread and self.delete_thread.isRunning():
            self.delete_thread.stop()
            self.delete_thread.wait()
            self.deletion_finished()
            self.update_log("⚠️ Quá trình xóa đã bị dừng")
            
    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.processed_label.setText(f"Đã xử lý: {current}")
        self.progress_label.setText(f"Đang xử lý... ({current}/{total})")
        
    def update_log(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
        
    def update_convert_stats(self, original_size, converted_size):
        self.stat_value_1.setText(self.format_size(original_size))
        self.stat_value_2.setText(self.format_size(converted_size))
        
        if original_size > 0:
            saved_size = original_size - converted_size
            saved_percentage = (saved_size / original_size) * 100
            self.stat_value_3.setText(f"{self.format_size(saved_size)} ({saved_percentage:.1f}%)")
        else:
            self.stat_value_3.setText("0 B (0%)")
            
    def update_delete_stats(self, deleted_count, total_size):
        self.stat_value_1.setText(f"{deleted_count} files")
        self.stat_value_2.setText(self.format_size(total_size))
            
    def reset_stats(self):
        self.stat_value_1.setText("0 B")
        self.stat_value_2.setText("0 B")
        self.stat_value_3.setText("0 B (0%)")
        self.processed_label.setText("Đã xử lý: 0")
        
    def format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
        
    def conversion_finished(self):
        self.progress_label.setText("Hoàn thành!")
        self.convert_btn.setEnabled(True)
        self.stop_convert_btn.setEnabled(False)
        
        if self.converter_thread:
            processed = self.converter_thread.processed_count
            total = self.progress_bar.maximum()
            total_original = self.converter_thread.total_original_size
            total_converted = self.converter_thread.total_converted_size
            
            if total_original > 0:
                total_saved = total_original - total_converted
                total_percentage = (total_saved / total_original) * 100
                self.update_log(f"🎉 Hoàn thành! Đã xử lý {processed}/{total} ảnh")
                self.update_log(f"📊 Tổng kết: Tiết kiệm {self.format_size(total_saved)} ({total_percentage:.1f}%)")
            
        QTimer.singleShot(2000, self.clear_memory)
        
    def deletion_finished(self):
        self.progress_label.setText("Hoàn thành!")
        self.delete_btn.setEnabled(True)
        self.stop_delete_btn.setEnabled(False)
        
        if self.delete_thread:
            deleted = self.delete_thread.deleted_count
            total = self.progress_bar.maximum()
            total_size = self.delete_thread.total_size
            
            action_text = "chuyển vào thùng rác" if self.use_recycle_bin_cb.isChecked() else "xóa"
            self.update_log(f"🎉 Hoàn thành! Đã {action_text} {deleted}/{total} files")
            self.update_log(f"📊 Tổng dung lượng giải phóng: {self.format_size(total_size)}")
            
        self.apply_delete_filters()
        QTimer.singleShot(2000, self.clear_memory)
        
    def clear_log(self):
        self.log_text.clear()
        
    def clear_memory(self):
        gc.collect()
        self.update_log("🧹 Đã xóa bộ nhớ đệm")
        
    def closeEvent(self, event):
        if (self.converter_thread and self.converter_thread.isRunning()) or \
           (self.delete_thread and self.delete_thread.isRunning()):
            reply = QMessageBox.question(
                self, "Xác nhận", 
                "Có tiến trình đang chạy. Bạn có muốn dừng và thoát?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.converter_thread and self.converter_thread.isRunning():
                    self.converter_thread.stop()
                    self.converter_thread.wait()
                if self.delete_thread and self.delete_thread.isRunning():
                    self.delete_thread.stop()
                    self.delete_thread.wait()
            else:
                event.ignore()
                return
                
        self.clear_memory()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WebP Converter & File Manager")
    
    window = WebPConverterGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()