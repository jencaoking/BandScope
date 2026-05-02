#!/usr/bin/env python3
"""
RPK Tool GUI - 小米手环 RPK 应用拆包分析工具
Windows 11 风格图形用户界面
"""

import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
    QProgressBar, QFileDialog, QFrame, QSplitter, QGroupBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QTabWidget, QMessageBox
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QCoreApplication, QMimeData, QPoint, QRect
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QDragEnterEvent, QDropEvent, QBrush
)

from unpacker import RPKUnpacker
from jsc_decompiler import JSCDecompiler
from ux_parser import UXParser
from js_beautifier import JSBeautifier
from manifest_parser import ManifestParser
from analyzer import RPKAnalyzer


class Windows11Style:
    PRIMARY_COLOR = QColor(0, 120, 212)
    PRIMARY_HOVER = QColor(16, 110, 190)
    PRIMARY_PRESSED = QColor(0, 89, 162)
    
    BACKGROUND = QColor(255, 255, 255)
    SURFACE = QColor(248, 249, 250)
    SURFACE_ELEVATED = QColor(255, 255, 255)
    
    TEXT_PRIMARY = QColor(32, 33, 36)
    TEXT_SECONDARY = QColor(95, 99, 104)
    TEXT_TERTIARY = QColor(154, 160, 166)
    
    BORDER = QColor(218, 220, 224)
    BORDER_LIGHT = QColor(232, 234, 237)
    
    SUCCESS = QColor(60, 186, 84)
    WARNING = QColor(251, 188, 5)
    ERROR = QColor(234, 67, 53)
    INFO = QColor(66, 133, 244)
    
    CORNER_RADIUS_SMALL = 8
    CORNER_RADIUS_MEDIUM = 12
    CORNER_RADIUS_LARGE = 16
    
    SHADOW_SMALL = "0 2px 4px rgba(0,0,0,0.05)"
    SHADOW_MEDIUM = "0 4px 12px rgba(0,0,0,0.08)"
    SHADOW_LARGE = "0 8px 24px rgba(0,0,0,0.12)"


class Windows11Button(QPushButton):
    def __init__(self, text, parent=None, variant="primary"):
        super().__init__(text, parent)
        self.variant = variant
        self.init_style()
    
    def init_style(self):
        self.setMinimumHeight(36)
        self.setMinimumWidth(100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style()
    
    def update_style(self):
        if self.variant == "primary":
            bg_color = Windows11Style.PRIMARY_COLOR.name()
            hover_bg = Windows11Style.PRIMARY_HOVER.name()
            pressed_bg = Windows11Style.PRIMARY_PRESSED.name()
            text_color = "#ffffff"
        elif self.variant == "secondary":
            bg_color = Windows11Style.SURFACE.name()
            hover_bg = Windows11Style.BORDER_LIGHT.name()
            pressed_bg = Windows11Style.BORDER.name()
            text_color = Windows11Style.TEXT_PRIMARY.name()
        else:
            bg_color = "transparent"
            hover_bg = Windows11Style.SURFACE.name()
            pressed_bg = Windows11Style.BORDER_LIGHT.name()
            text_color = Windows11Style.TEXT_SECONDARY.name()
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: {Windows11Style.CORNER_RADIUS_SMALL}px;
                padding: 8px 16px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton:pressed {{
                background-color: {pressed_bg};
            }}
            QPushButton:disabled {{
                background-color: {Windows11Style.SURFACE.name()};
                color: {Windows11Style.TEXT_TERTIARY.name()};
            }}
        """)


class Windows11LineEdit(QLineEdit):
    def __init__(self, parent=None, placeholder=""):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.init_style()
    
    def init_style(self):
        self.setMinimumHeight(36)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Windows11Style.SURFACE.name()};
                border: 1px solid {Windows11Style.BORDER.name()};
                border-radius: {Windows11Style.CORNER_RADIUS_SMALL}px;
                padding: 0 12px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                color: {Windows11Style.TEXT_PRIMARY.name()};
            }}
            QLineEdit:hover {{
                border-color: {Windows11Style.TEXT_TERTIARY.name()};
            }}
            QLineEdit:focus {{
                border-color: {Windows11Style.PRIMARY_COLOR.name()};
                border-width: 2px;
                outline: none;
            }}
        """)


class Windows11ComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_style()
    
    def init_style(self):
        self.setMinimumHeight(36)
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {Windows11Style.SURFACE.name()};
                border: 1px solid {Windows11Style.BORDER.name()};
                border-radius: {Windows11Style.CORNER_RADIUS_SMALL}px;
                padding: 0 12px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                color: {Windows11Style.TEXT_PRIMARY.name()};
            }}
            QComboBox:hover {{
                border-color: {Windows11Style.TEXT_TERTIARY.name()};
            }}
            QComboBox:focus {{
                border-color: {Windows11Style.PRIMARY_COLOR.name()};
                border-width: 2px;
                outline: none;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%235f6368'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
                width: 16px;
                height: 16px;
            }}
        """)


class Windows11GroupBox(QGroupBox):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.init_style()
    
    def init_style(self):
        self.setStyleSheet(f"""
            QGroupBox {{
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 600;
                color: {Windows11Style.TEXT_PRIMARY.name()};
                border: 1px solid {Windows11Style.BORDER.name()};
                border-radius: {Windows11Style.CORNER_RADIUS_MEDIUM}px;
                padding-top: 16px;
                margin-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background-color: {Windows11Style.BACKGROUND.name()};
            }}
        """)


class DropZone(QFrame):
    dropped = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        self.drag_over = False
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = QLabel()
        self.icon_label.setStyleSheet("font-size: 32px;")
        self.icon_label.setText("📁")
        layout.addWidget(self.icon_label)
        
        self.text_label = QLabel("拖放 RPK/JSC 文件或目录到此处")
        self.text_label.setStyleSheet(f"color: {Windows11Style.TEXT_SECONDARY.name()}; font-family: 'Segoe UI', sans-serif;")
        layout.addWidget(self.text_label)
        
        self.update_style()
    
    def update_style(self):
        border_color = Windows11Style.PRIMARY_COLOR if self.drag_over else Windows11Style.BORDER
        bg_color = "rgba(0, 120, 212, 0.05)" if self.drag_over else Windows11Style.SURFACE.name()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 2px dashed {border_color.name()};
                border-radius: {Windows11Style.CORNER_RADIUS_MEDIUM}px;
            }}
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drag_over = True
            self.update_style()
    
    def dragLeaveEvent(self, event):
        self.drag_over = False
        self.update_style()
    
    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.endswith('.rpk') or file_path.endswith('.jsc') or os.path.isdir(file_path):
                    self.dropped.emit(file_path)
                    break
        self.drag_over = False
        self.update_style()


class WorkerThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str, dict)
    
    def __init__(self, task_type, input_path, output_path=None):
        super().__init__()
        self.task_type = task_type
        self.input_path = input_path
        self.output_path = output_path
    
    def run(self):
        try:
            if self.task_type == "unpack":
                self.execute_unpack()
            elif self.task_type == "decompile":
                self.execute_decompile()
            elif self.task_type == "beautify":
                self.execute_beautify()
            elif self.task_type == "ux_split":
                self.execute_ux_split()
            elif self.task_type == "ux_merge":
                self.execute_ux_merge()
            elif self.task_type == "info":
                self.execute_info()
            elif self.task_type == "analyze":
                self.execute_analyze()
        except Exception as e:
            self.finished.emit(False, str(e), {})
    
    def execute_unpack(self):
        unpacker = RPKUnpacker(self.input_path)
        if not unpacker.validate():
            self.finished.emit(False, "无效的 RPK 文件", {})
            return
        
        self.progress.emit(10, "正在验证 RPK 文件...")
        
        output_dir = self.output_path or self.input_path.replace('.rpk', '_unpacked')
        result = unpacker.unpack(output_dir)
        
        self.progress.emit(100, "解包完成")
        self.finished.emit(True, f"解包完成: {output_dir}", {
            'file_count': result['file_count'],
            'output_dir': output_dir
        })
    
    def execute_decompile(self):
        input_path = Path(self.input_path)
        if input_path.is_file():
            files = [input_path]
        elif input_path.is_dir():
            files = list(input_path.rglob("*.jsc"))
        else:
            self.finished.emit(False, "无效的路径", {})
            return
        
        if not files:
            self.finished.emit(False, "未找到 .jsc 文件", {})
            return
        
        decompiler = JSCDecompiler()
        output_dir = self.output_path or str(input_path.parent / "decompiled")
        os.makedirs(output_dir, exist_ok=True)
        
        success_count = 0
        total_files = len(files)
        
        for i, jsc_file in enumerate(files):
            self.progress.emit(int((i + 1) / total_files * 100), f"反编译: {jsc_file.name}")
            try:
                result = decompiler.decompile(str(jsc_file))
                if result:
                    out_path = os.path.join(output_dir, jsc_file.stem + ".js")
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(result)
                    success_count += 1
            except Exception:
                pass
        
        self.finished.emit(True, f"反编译完成，成功: {success_count}/{total_files}", {
            'success_count': success_count,
            'total_files': total_files,
            'output_dir': output_dir
        })
    
    def execute_beautify(self):
        beautifier = JSBeautifier()
        input_path = Path(self.input_path)
        
        if input_path.is_file():
            files = [input_path]
        elif input_path.is_dir():
            files = list(input_path.rglob("*.js"))
        else:
            self.finished.emit(False, "无效的路径", {})
            return
        
        success_count = 0
        total_files = len(files)
        
        for i, js_file in enumerate(files):
            self.progress.emit(int((i + 1) / total_files * 100), f"美化: {js_file.name}")
            try:
                beautifier.beautify_file(str(js_file))
                success_count += 1
            except Exception:
                pass
        
        self.finished.emit(True, f"美化完成，成功: {success_count}/{total_files}", {
            'success_count': success_count,
            'total_files': total_files
        })
    
    def execute_ux_split(self):
        parser = UXParser()
        input_path = Path(self.input_path)
        
        if input_path.is_file():
            files = [input_path]
        elif input_path.is_dir():
            files = list(input_path.rglob("*.ux"))
        else:
            self.finished.emit(False, "无效的路径", {})
            return
        
        if not files:
            self.finished.emit(False, "未找到 .ux 文件", {})
            return
        
        output_dir = self.output_path or str(input_path.parent / "ux_split")
        os.makedirs(output_dir, exist_ok=True)
        
        success_count = 0
        total_files = len(files)
        
        for i, ux_file in enumerate(files):
            self.progress.emit(int((i + 1) / total_files * 100), f"解析: {ux_file.name}")
            try:
                parser.split(str(ux_file), output_dir)
                success_count += 1
            except Exception:
                pass
        
        self.finished.emit(True, f"UX 解析完成，成功: {success_count}/{total_files}", {
            'success_count': success_count,
            'total_files': total_files,
            'output_dir': output_dir
        })
    
    def execute_ux_merge(self):
        parser = UXParser()
        input_path = Path(self.input_path)
        output_dir = self.output_path or str(input_path.parent / "ux_merged")
        os.makedirs(output_dir, exist_ok=True)
        
        groups = parser.find_groups(str(input_path))
        if not groups:
            self.finished.emit(False, "未找到可合并的文件组", {})
            return
        
        for i, group in enumerate(groups):
            self.progress.emit(int((i + 1) / len(groups) * 100), f"合并: {group['name']}")
            parser.merge(group, output_dir)
        
        self.finished.emit(True, f"UX 合并完成，共 {len(groups)} 个文件", {
            'merged_count': len(groups),
            'output_dir': output_dir
        })
    
    def execute_info(self):
        unpacker = RPKUnpacker(self.input_path)
        if not unpacker.validate():
            self.finished.emit(False, "无效的 RPK 文件", {})
            return
        
        file_size = os.path.getsize(self.input_path)
        
        manifest = ManifestParser()
        info = manifest.parse_rpk(self.input_path)
        
        analyzer = RPKAnalyzer()
        stats = analyzer.analyze_rpk(self.input_path)
        
        result = {
            'file_size': file_size,
            'manifest': info,
            'stats': stats
        }
        
        self.finished.emit(True, "获取信息完成", result)
    
    def execute_analyze(self):
        analyzer = RPKAnalyzer()
        report = analyzer.full_analysis(self.input_path)
        
        result = {
            'api_calls': dict(report.get('api_calls', {})),
            'strings': report.get('strings', []),
            'urls': report.get('urls', []),
            'hardcoded': report.get('hardcoded', {})
        }
        
        self.finished.emit(True, "分析完成", result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPK Tool - 小米手环 RPK 分析工具")
        self.setMinimumSize(900, 600)
        
        self.current_file = None
        self.worker_thread = None
        
        self.init_ui()
        self.init_connections()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)
        
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {Windows11Style.BACKGROUND.name()};
            }}
            QWidget {{
                font-family: 'Segoe UI', sans-serif;
            }}
        """)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        
        title_label = QLabel("RPK Tool")
        title_label.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 600;
            color: {Windows11Style.TEXT_PRIMARY.name()};
        """)
        header_layout.addWidget(title_label)
        
        subtitle_label = QLabel("小米手环 RPK 应用拆包分析工具")
        subtitle_label.setStyleSheet(f"""
            font-size: 14px;
            color: {Windows11Style.TEXT_SECONDARY.name()};
        """)
        header_layout.addWidget(subtitle_label)
        
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        file_group = Windows11GroupBox("文件选择")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(12)
        
        self.drop_zone = DropZone()
        file_layout.addWidget(self.drop_zone)
        
        browse_layout = QHBoxLayout()
        browse_layout.setSpacing(12)
        
        self.file_path_edit = Windows11LineEdit(placeholder="选择 RPK/JSC 文件或目录")
        browse_layout.addWidget(self.file_path_edit)
        
        self.browse_button = Windows11Button("浏览", variant="secondary")
        browse_layout.addWidget(self.browse_button)
        
        file_layout.addLayout(browse_layout)
        main_layout.addWidget(file_group)
        
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {Windows11Style.BORDER.name()};
                border-radius: {Windows11Style.CORNER_RADIUS_MEDIUM}px;
                background-color: {Windows11Style.BACKGROUND.name()};
            }}
            QTabBar::tab {{
                background-color: {Windows11Style.SURFACE.name()};
                border: none;
                border-radius: {Windows11Style.CORNER_RADIUS_SMALL}px {Windows11Style.CORNER_RADIUS_SMALL}px 0 0;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 500;
                color: {Windows11Style.TEXT_SECONDARY.name()};
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {Windows11Style.BACKGROUND.name()};
                color: {Windows11Style.TEXT_PRIMARY.name()};
                border-bottom: 2px solid {Windows11Style.PRIMARY_COLOR.name()};
            }}
            QTabBar::tab:hover:not(:selected) {{
                background-color: {Windows11Style.BORDER_LIGHT.name()};
            }}
        """)
        
        unpack_tab = QWidget()
        self.init_unpack_tab(unpack_tab)
        tabs.addTab(unpack_tab, "解包")
        
        decompile_tab = QWidget()
        self.init_decompile_tab(decompile_tab)
        tabs.addTab(decompile_tab, "反编译")
        
        ux_tab = QWidget()
        self.init_ux_tab(ux_tab)
        tabs.addTab(ux_tab, "UX 处理")
        
        info_tab = QWidget()
        self.init_info_tab(info_tab)
        tabs.addTab(info_tab, "信息")
        
        analyze_tab = QWidget()
        self.init_analyze_tab(analyze_tab)
        tabs.addTab(analyze_tab, "分析")
        
        main_layout.addWidget(tabs)
        
        progress_group = Windows11GroupBox("进度")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setSpacing(8)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                height: 8px;
                border-radius: 4px;
                background-color: {Windows11Style.SURFACE.name()};
            }}
            QProgressBar::chunk {{
                background-color: {Windows11Style.PRIMARY_COLOR.name()};
                border-radius: 4px;
            }}
        """)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(f"color: {Windows11Style.TEXT_SECONDARY.name()}; font-size: 13px;")
        progress_layout.addWidget(self.status_label)
        
        main_layout.addWidget(progress_group)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Windows11Style.SURFACE.name()};
                border: 1px solid {Windows11Style.BORDER.name()};
                border-radius: {Windows11Style.CORNER_RADIUS_SMALL}px;
                padding: 12px;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                color: {Windows11Style.TEXT_PRIMARY.name()};
            }}
        """)
        main_layout.addWidget(self.output_text)
    
    def init_unpack_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        output_layout = QHBoxLayout()
        output_layout.setSpacing(12)
        
        self.unpack_output_edit = Windows11LineEdit(placeholder="输出目录")
        output_layout.addWidget(self.unpack_output_edit)
        
        self.unpack_browse_button = Windows11Button("浏览", variant="secondary")
        output_layout.addWidget(self.unpack_browse_button)
        
        layout.addLayout(output_layout)
        
        self.unpack_button = Windows11Button("开始解包")
        layout.addWidget(self.unpack_button)
    
    def init_decompile_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        output_layout = QHBoxLayout()
        output_layout.setSpacing(12)
        
        self.decompile_output_edit = Windows11LineEdit(placeholder="输出目录")
        output_layout.addWidget(self.decompile_output_edit)
        
        self.decompile_browse_button = Windows11Button("浏览", variant="secondary")
        output_layout.addWidget(self.decompile_browse_button)
        
        layout.addLayout(output_layout)
        
        self.decompile_button = Windows11Button("开始反编译")
        layout.addWidget(self.decompile_button)
        
        self.beautify_button = Windows11Button("美化 JS", variant="secondary")
        layout.addWidget(self.beautify_button)
    
    def init_ux_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        output_layout = QHBoxLayout()
        output_layout.setSpacing(12)
        
        self.ux_output_edit = Windows11LineEdit(placeholder="输出目录")
        output_layout.addWidget(self.ux_output_edit)
        
        self.ux_browse_button = Windows11Button("浏览", variant="secondary")
        output_layout.addWidget(self.ux_browse_button)
        
        layout.addLayout(output_layout)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        self.ux_split_button = Windows11Button("拆分 UX")
        button_layout.addWidget(self.ux_split_button)
        
        self.ux_merge_button = Windows11Button("合并 UX", variant="secondary")
        button_layout.addWidget(self.ux_merge_button)
        
        layout.addLayout(button_layout)
    
    def init_info_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        self.info_tree = QTreeWidget()
        self.info_tree.setHeaderLabels(["字段", "值"])
        self.info_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.info_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.info_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {Windows11Style.SURFACE.name()};
                border: 1px solid {Windows11Style.BORDER.name()};
                border-radius: {Windows11Style.CORNER_RADIUS_SMALL}px;
                font-size: 13px;
            }}
            QTreeWidget::item {{
                padding: 4px 8px;
            }}
            QTreeWidget::item:hover {{
                background-color: {Windows11Style.BORDER_LIGHT.name()};
            }}
        """)
        layout.addWidget(self.info_tree)
        
        self.info_button = Windows11Button("获取信息")
        layout.addWidget(self.info_button)
    
    def init_analyze_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        self.analyze_tree = QTreeWidget()
        self.analyze_tree.setHeaderLabels(["项目", "详情"])
        self.analyze_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.analyze_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.analyze_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {Windows11Style.SURFACE.name()};
                border: 1px solid {Windows11Style.BORDER.name()};
                border-radius: {Windows11Style.CORNER_RADIUS_SMALL}px;
                font-size: 13px;
            }}
            QTreeWidget::item {{
                padding: 4px 8px;
            }}
            QTreeWidget::item:hover {{
                background-color: {Windows11Style.BORDER_LIGHT.name()};
            }}
        """)
        layout.addWidget(self.analyze_tree)
        
        self.analyze_button = Windows11Button("开始分析")
        layout.addWidget(self.analyze_button)
    
    def init_connections(self):
        self.drop_zone.dropped.connect(self.handle_dropped_file)
        self.browse_button.clicked.connect(self.browse_path)
        
        self.unpack_browse_button.clicked.connect(lambda: self.browse_folder(self.unpack_output_edit))
        self.unpack_button.clicked.connect(self.execute_unpack)
        
        self.decompile_browse_button.clicked.connect(lambda: self.browse_folder(self.decompile_output_edit))
        self.decompile_button.clicked.connect(self.execute_decompile)
        self.beautify_button.clicked.connect(self.execute_beautify)
        
        self.ux_browse_button.clicked.connect(lambda: self.browse_folder(self.ux_output_edit))
        self.ux_split_button.clicked.connect(self.execute_ux_split)
        self.ux_merge_button.clicked.connect(self.execute_ux_merge)
        
        self.info_button.clicked.connect(self.execute_info)
        self.analyze_button.clicked.connect(self.execute_analyze)
    
    def handle_dropped_file(self, file_path):
        self.current_file = file_path
        self.file_path_edit.setText(file_path)
        self.append_output(f"已选择文件: {file_path}")
    
    def browse_file(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters(["RPK Files (*.rpk)", "JSC Files (*.jsc)", "All Files (*)"])
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, False)
        
        if dialog.exec():
            selected_files = dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                self.current_file = file_path
                self.file_path_edit.setText(file_path)
                self.append_output(f"已选择文件: {file_path}")
    
    def browse_path(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.FileMode.Any)
        dialog.setNameFilters(["RPK Files (*.rpk)", "JSC Files (*.jsc)", "Directories", "All Files (*)"])
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        
        if dialog.exec():
            selected_files = dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                self.current_file = file_path
                self.file_path_edit.setText(file_path)
                if os.path.isdir(file_path):
                    self.append_output(f"已选择目录: {file_path}")
                else:
                    self.append_output(f"已选择文件: {file_path}")
    
    def browse_folder(self, line_edit):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            ""
        )
        if folder_path:
            line_edit.setText(folder_path)
    
    def execute_unpack(self):
        if not self.validate_input():
            return
        
        self.start_worker("unpack", self.unpack_output_edit.text())
    
    def execute_decompile(self):
        if not self.validate_input():
            return
        
        self.start_worker("decompile", self.decompile_output_edit.text())
    
    def execute_beautify(self):
        if not self.validate_input():
            return
        
        self.start_worker("beautify", None)
    
    def execute_ux_split(self):
        if not self.validate_input():
            return
        
        self.start_worker("ux_split", self.ux_output_edit.text())
    
    def execute_ux_merge(self):
        if not self.validate_input():
            return
        
        self.start_worker("ux_merge", self.ux_output_edit.text())
    
    def execute_info(self):
        if not self.validate_input():
            return
        
        self.start_worker("info", None)
    
    def execute_analyze(self):
        if not self.validate_input():
            return
        
        self.start_worker("analyze", None)
    
    def validate_input(self):
        if not self.file_path_edit.text():
            QMessageBox.warning(self, "警告", "请先选择文件或目录")
            return False
        return True
    
    def start_worker(self, task_type, output_path):
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "警告", "已有任务在执行中")
            return
        
        self.progress_bar.setValue(0)
        self.status_label.setText("处理中...")
        self.set_buttons_enabled(False)
        
        self.worker_thread = WorkerThread(task_type, self.file_path_edit.text(), output_path)
        self.worker_thread.progress.connect(self.update_progress)
        self.worker_thread.finished.connect(self.handle_worker_finished)
        self.worker_thread.start()
    
    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        self.append_output(f"[{value}%] {message}")
    
    def handle_worker_finished(self, success, message, data):
        self.progress_bar.setValue(100)
        self.status_label.setText("完成" if success else "失败")
        self.set_buttons_enabled(True)
        
        if success:
            self.append_output(f"✓ {message}")
            
            if data:
                if 'manifest' in data:
                    self.populate_info_tree(data)
                elif 'api_calls' in data:
                    self.populate_analyze_tree(data)
        else:
            self.append_output(f"✗ {message}")
            QMessageBox.error(self, "错误", message)
    
    def populate_info_tree(self, data):
        self.info_tree.clear()
        
        file_size = data.get('file_size', 0)
        manifest = data.get('manifest', {})
        stats = data.get('stats', {})
        
        file_item = QTreeWidgetItem(self.info_tree, ["文件信息", ""])
        QTreeWidgetItem(file_item, ["文件路径", self.file_path_edit.text()])
        QTreeWidgetItem(file_item, ["文件大小", f"{file_size:,} 字节 ({file_size/1024:.1f} KB)"])
        
        if manifest:
            app_item = QTreeWidgetItem(self.info_tree, ["应用信息", ""])
            QTreeWidgetItem(app_item, ["包名", manifest.get("package", "N/A")])
            QTreeWidgetItem(app_item, ["名称", manifest.get("name", "N/A")])
            QTreeWidgetItem(app_item, ["版本", manifest.get("versionName", "N/A")])
            QTreeWidgetItem(app_item, ["版本号", str(manifest.get("versionCode", "N/A"))])
            QTreeWidgetItem(app_item, ["最低平台", str(manifest.get("minPlatformVersion", "N/A"))])
            QTreeWidgetItem(app_item, ["图标", manifest.get("icon", "N/A")])
            
            features = manifest.get("features", [])
            if features:
                features_item = QTreeWidgetItem(app_item, ["功能特性", ""])
                for f in features:
                    QTreeWidgetItem(features_item, [f.get("name", "unknown"), ""])
            
            router = manifest.get("router", {})
            pages = router.get("pages", {})
            if pages:
                pages_item = QTreeWidgetItem(app_item, ["页面路由", ""])
                for page, config in pages.items():
                    QTreeWidgetItem(pages_item, [page, config.get("component", "?")])
        
        if stats:
            stats_item = QTreeWidgetItem(self.info_tree, ["文件统计", ""])
            for ext, stat in sorted(stats.items()):
                QTreeWidgetItem(stats_item, [ext, f"{stat['count']} 个文件, {stat['size']:,} B"])
    
    def populate_analyze_tree(self, data):
        self.analyze_tree.clear()
        
        api_calls = data.get('api_calls', {})
        strings = data.get('strings', [])
        urls = data.get('urls', [])
        hardcoded = data.get('hardcoded', {})
        
        if api_calls:
            api_item = QTreeWidgetItem(self.analyze_tree, ["API 调用", f"共 {len(api_calls)} 个"])
            for api, count in sorted(api_calls.items(), key=lambda x: x[1], reverse=True)[:20]:
                QTreeWidgetItem(api_item, [api, f"{count} 次"])
        
        if strings:
            strings_item = QTreeWidgetItem(self.analyze_tree, ["关键字符串", f"共 {len(strings)} 个"])
            for s in strings[:30]:
                QTreeWidgetItem(strings_item, [s, ""])
        
        if urls:
            urls_item = QTreeWidgetItem(self.analyze_tree, ["网络端点", f"共 {len(urls)} 个"])
            for url in urls:
                QTreeWidgetItem(urls_item, [url, ""])
        
        if hardcoded:
            hardcoded_item = QTreeWidgetItem(self.analyze_tree, ["硬编码配置", f"共 {len(hardcoded)} 个"])
            for key, value in hardcoded.items():
                QTreeWidgetItem(hardcoded_item, [key, str(value)])
    
    def append_output(self, text):
        self.output_text.append(text)
        self.output_text.verticalScrollBar().setValue(self.output_text.verticalScrollBar().maximum())
    
    def set_buttons_enabled(self, enabled):
        self.unpack_button.setEnabled(enabled)
        self.decompile_button.setEnabled(enabled)
        self.beautify_button.setEnabled(enabled)
        self.ux_split_button.setEnabled(enabled)
        self.ux_merge_button.setEnabled(enabled)
        self.info_button.setEnabled(enabled)
        self.analyze_button.setEnabled(enabled)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("RPK Tool")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())