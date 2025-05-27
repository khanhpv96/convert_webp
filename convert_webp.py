import sys
import os
import gc
from pathlib import Path
from PIL import Image
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QPushButton, QLabel, QProgressBar, QTextEdit,
                            QSpinBox, QGroupBox, QFileDialog, QCheckBox, QFrame,
                            QMessageBox, QSplitter)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor


class ImageConverterThread(QThread):
    progress_updated = pyqtSignal(int, int)
    log_updated = pyqtSignal(str)
    conversion_finished = pyqtSignal()
    
    def __init__(self, files, quality, keep_original):
        super().__init__()
        self.files = files
        self.quality = quality
        self.keep_original = keep_original
        self.processed_count = 0
        
    def run(self):
        total_files = len(self.files)
        
        for i, file_path in enumerate(self.files):
            try:
                input_file = Path(file_path)
                base_name = input_file.stem
                output_file = input_file.parent / f"{base_name}.webp"
                
                with Image.open(input_file) as img:
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    img.save(output_file, "webp", quality=self.quality, optimize=True)
                    self.log_updated.emit(f"✓ Đã chuyển đổi: {input_file.name} → {output_file.name}")
                
                if not self.keep_original:
                    os.remove(input_file)
                    self.log_updated.emit(f"✗ Đã xóa file gốc: {input_file.name}")
                
                self.processed_count += 1
                self.progress_updated.emit(i + 1, total_files)
                
            except Exception as e:
                self.log_updated.emit(f"❌ Lỗi khi xử lý {file_path}: {str(e)}")
        
        self.conversion_finished.emit()


class WebPConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_files = []
        self.converter_thread = None
        self.init_ui()
        self.setup_styles()
        
    def init_ui(self):
        self.setWindowTitle("WebP Image Converter")
        self.setGeometry(100, 100, 900, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        header_label = QLabel("WebP Image Converter")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50; margin-bottom: 10px;")
        main_layout.addWidget(header_label)
        
        self.create_file_selection_group(main_layout)
        self.create_settings_group(main_layout)
        self.create_progress_group(main_layout)
        self.create_log_group(main_layout)
        self.create_control_buttons(main_layout)
        
    def create_file_selection_group(self, parent_layout):
        group = QGroupBox("Chọn File/Thư Mục")
        layout = QVBoxLayout(group)
        
        button_layout = QHBoxLayout()
        
        self.select_files_btn = QPushButton("Chọn Ảnh")
        self.select_files_btn.clicked.connect(self.select_files)
        
        self.select_folder_btn = QPushButton("Chọn Thư Mục")
        self.select_folder_btn.clicked.connect(self.select_folder)
        
        button_layout.addWidget(self.select_files_btn)
        button_layout.addWidget(self.select_folder_btn)
        
        self.file_count_label = QLabel("Chưa chọn file nào")
        self.file_count_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        
        layout.addLayout(button_layout)
        layout.addWidget(self.file_count_label)
        
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
        
    def create_progress_group(self, parent_layout):
        group = QGroupBox("Tiến Trình")
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
        
    def create_log_group(self, parent_layout):
        group = QGroupBox("Nhật Ký Hoạt Động")
        layout = QVBoxLayout(group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        
        clear_log_btn = QPushButton("Xóa Log")
        clear_log_btn.clicked.connect(self.clear_log)
        clear_log_btn.setMaximumWidth(100)
        
        layout.addWidget(self.log_text)
        layout.addWidget(clear_log_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        parent_layout.addWidget(group)
        
    def create_control_buttons(self, parent_layout):
        button_layout = QHBoxLayout()
        
        self.convert_btn = QPushButton("Bắt Đầu Chuyển Đổi")
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setEnabled(False)
        
        self.stop_btn = QPushButton("Dừng")
        self.stop_btn.clicked.connect(self.stop_conversion)
        self.stop_btn.setEnabled(False)
        
        self.clear_memory_btn = QPushButton("Xóa Bộ Nhớ Đệm")
        self.clear_memory_btn.clicked.connect(self.clear_memory)
        
        button_layout.addWidget(self.convert_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_memory_btn)
        
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
            QSpinBox {
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            QCheckBox {
                font-weight: normal;
            }
        """)
        
    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh", "", 
            "Image files (*.jpg *.jpeg *.png);;All files (*.*)"
        )
        if files:
            self.selected_files = files
            self.update_file_count()
            
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục chứa ảnh")
        if folder:
            self.selected_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png')) and not file.lower().endswith('.webp'):
                        self.selected_files.append(os.path.join(root, file))
            self.update_file_count()
            
    def update_file_count(self):
        count = len(self.selected_files)
        if count > 0:
            self.file_count_label.setText(f"Đã chọn {count} ảnh")
            self.file_count_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.convert_btn.setEnabled(True)
            self.total_label.setText(f"Tổng số: {count}")
        else:
            self.file_count_label.setText("Không tìm thấy ảnh nào")
            self.file_count_label.setStyleSheet("color: #dc3545; font-style: italic;")
            self.convert_btn.setEnabled(False)
            
    def start_conversion(self):
        if not self.selected_files:
            return
            
        quality = self.quality_spinbox.value()
        keep_original = self.keep_original_checkbox.isChecked()
        
        self.converter_thread = ImageConverterThread(self.selected_files, quality, keep_original)
        self.converter_thread.progress_updated.connect(self.update_progress)
        self.converter_thread.log_updated.connect(self.update_log)
        self.converter_thread.conversion_finished.connect(self.conversion_finished)
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setValue(0)
        
        self.convert_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_label.setText("Đang chuyển đổi...")
        
        self.converter_thread.start()
        
    def stop_conversion(self):
        if self.converter_thread and self.converter_thread.isRunning():
            self.converter_thread.terminate()
            self.converter_thread.wait()
            self.conversion_finished()
            self.update_log("⚠️ Quá trình chuyển đổi đã bị dừng")
            
    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.processed_label.setText(f"Đã xử lý: {current}")
        self.progress_label.setText(f"Đang xử lý... ({current}/{total})")
        
    def update_log(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
        
    def conversion_finished(self):
        self.progress_label.setText("Hoàn thành!")
        self.convert_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        if self.converter_thread:
            processed = self.converter_thread.processed_count
            total = len(self.selected_files)
            self.update_log(f"🎉 Hoàn thành! Đã xử lý {processed}/{total} ảnh")
            
        QTimer.singleShot(2000, self.clear_memory)
        
    def clear_log(self):
        self.log_text.clear()
        
    def clear_memory(self):
        gc.collect()
        self.update_log("🧹 Đã xóa bộ nhớ đệm")
        
    def closeEvent(self, event):
        if self.converter_thread and self.converter_thread.isRunning():
            reply = QMessageBox.question(
                self, "Xác nhận", 
                "Quá trình chuyển đổi đang chạy. Bạn có muốn dừng và thoát?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.converter_thread.terminate()
                self.converter_thread.wait()
            else:
                event.ignore()
                return
                
        self.clear_memory()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WebP Converter")
    
    window = WebPConverterGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
