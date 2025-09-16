#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
文件内容对比 - UI模块

这个模块包含文件内容对比工具的所有图形用户界面实现，包括：
- 主窗口布局
- 文件选择界面
- 对比结果显示
- 文件预览功能
- 差异高亮显示

该模块依赖于file_diff_core模块提供的核心功能。
"""

from __future__ import annotations
import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import webbrowser

# 导入核心功能模块
from file_diff_core import (
    supported_formats,
    get_file_type,
    compare_files,
    compare_directories,
    generate_diff_report,
    FileNotSupportedError,
    FileReadError
)

# UI字体配置
DEFAULT_FONT_SIZE = 9
DEFAULT_FONT_FAMILY = "Microsoft YaHei UI"  # Windows 默认字体

# 主题模式 - 默认使用浅色模式
THEME_LIGHT = 'light'
THEME_DARK = 'dark'
current_theme = THEME_LIGHT

# 窗口模式 - 默认使用系统窗口
WINDOW_MODE_SYSTEM = 'system'
WINDOW_MODE_BORDERLESS = 'borderless'
current_window_mode = WINDOW_MODE_SYSTEM

class FileDiffApp:
    """
    文件内容对比工具的主应用类，负责创建和管理所有UI组件以及处理用户交互。
    """
    def __init__(self, root):
        """
        初始化文件对比工具应用。
        
        Args:
            root: Tkinter根窗口对象
        """
        self.root = root
        self.root.title('文件内容对比工具')
        
        # 根据窗口模式决定是否创建自定义标题栏
        self.custom_title_bar = None
        
        # 默认启用无边框模式（延迟到界面创建完成后）
        global current_window_mode
        current_window_mode = WINDOW_MODE_BORDERLESS
        
        # 不再创建菜单栏，改用界面按钮
        # self._create_menu()
        
        # Windows DPI感知设置
        try:
            if sys.platform.startswith('win'):
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 启用DPI感知
        except Exception:
            pass  # 忽略DPI设置失败
        
        # 字体配置
        try:
            self.default_font = tk.font.nametofont("TkDefaultFont")
            self.default_font.configure(family=DEFAULT_FONT_FAMILY, size=DEFAULT_FONT_SIZE)
            
            # 配置默认字体
            self.root.option_add("*Font", self.default_font)
        except Exception:
            pass  # 字体配置失败时使用系统默认
        
        # 窗口初始化 - 使用自适应大小，允许手动调整窗口
        self.root.geometry('1400x900')  # 增大默认窗口大小
        self.root.minsize(800, 700)     # 调整最小尺寸，确保底部内容可见
        self._min_window_width = 800    # 最小窗口宽度
        
        # 启用窗口大小调整
        self.root.resizable(True, True)  # 允许水平和垂直调整大小
        
        # 线程控制
        self.stop_flag = threading.Event()
        self.q = queue.Queue()
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'end_time': None,
            'compared_files': 0,
            'same_files': 0,
            'different_files': 0,
            'errors_count': 0,
        }
        
        # 缓存当前选择的文件路径
        self.file1_path = tk.StringVar()
        self.file2_path = tk.StringVar()
        self.dir1_path = tk.StringVar()
        self.dir2_path = tk.StringVar()
        
        # 对比选项
        self.ignore_whitespace = tk.BooleanVar(value=True)
        self.recursive_compare = tk.BooleanVar(value=True)
        
        # 创建标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 确保底部状态栏有足够的空间
        self.root.update_idletasks()
        current_height = self.root.winfo_height()
        if current_height < 700:
            self.root.geometry(f"1400x700")  # 确保最小高度
        
        # 创建各个功能标签页
        self._create_file_compare_tab()
        self._create_dir_compare_tab()
        
        # 创建底部状态和日志区域
        self._create_status_and_log()
        
        # 启动日志处理线程
        self._drain()
        
        # 绑定窗口事件
        self.root.bind('<Configure>', self._on_configure)
        
        # 延迟启用无边框模式（等待界面完全创建）
        self.root.after(100, self._enable_borderless_mode)
        
        # 延迟进行窗口居中，确保所有组件都已渲染完成
        self.root.after(200, self._center_window)
    
    def _create_file_compare_tab(self):
        """创建文件对比标签页"""
        # 创建标签页容器
        file_tab = ttk.Frame(self.notebook)
        self.notebook.add(file_tab, text="文件对比")
        
        # 创建主框架
        main_frame = ttk.Frame(file_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建文件选择区域
        select_frame = ttk.LabelFrame(main_frame, text="选择文件")
        select_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 文件1选择
        ttk.Label(select_frame, text="文件1:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(select_frame, textvariable=self.file1_path, width=80).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(select_frame, text="浏览...", command=self._browse_file1).grid(row=0, column=2, padx=5, pady=5)
        
        # 文件2选择
        ttk.Label(select_frame, text="文件2:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(select_frame, textvariable=self.file2_path, width=80).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(select_frame, text="浏览...", command=self._browse_file2).grid(row=1, column=2, padx=5, pady=5)
        
        # 选项区域
        options_frame = ttk.LabelFrame(main_frame, text="对比选项")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 忽略空白字符选项
        ttk.Checkbutton(options_frame, text="忽略空白字符差异", variable=self.ignore_whitespace).pack(side=tk.LEFT, padx=10, pady=5)
        
        # 对比按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 左侧功能按钮
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(left_buttons, text="开始对比", command=self._start_file_compare, width=20).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(left_buttons, text="清空结果", command=self._clear_file_results, width=20).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(left_buttons, text="生成报告", command=self._generate_file_report, width=20).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 右侧主题切换按钮
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT, padx=5, pady=5)
        
        self.theme_button = ttk.Button(right_buttons, text="🌙 深色模式", command=self.toggle_theme, width=15)
        self.theme_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 预览区域
        preview_frame = ttk.LabelFrame(main_frame, text="文件预览")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建分割窗格以显示两个文件的预览
        self.preview_paned = ttk.PanedWindow(preview_frame, orient=tk.HORIZONTAL)
        self.preview_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 文件1预览
        file1_preview_frame = ttk.Frame(self.preview_paned, width=400, height=400)
        self.preview_paned.add(file1_preview_frame, weight=1)
        
        self.file1_preview_label = ttk.Label(file1_preview_frame, text="文件1预览", relief=tk.SUNKEN)
        self.file1_preview_label.pack(fill=tk.X, side=tk.TOP)
        
        self.file1_preview_text = scrolledtext.ScrolledText(file1_preview_frame, wrap=tk.WORD)
        self.file1_preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 文件2预览
        file2_preview_frame = ttk.Frame(self.preview_paned, width=400, height=400)
        self.preview_paned.add(file2_preview_frame, weight=1)
        
        self.file2_preview_label = ttk.Label(file2_preview_frame, text="文件2预览", relief=tk.SUNKEN)
        self.file2_preview_label.pack(fill=tk.X, side=tk.TOP)
        
        self.file2_preview_text = scrolledtext.ScrolledText(file2_preview_frame, wrap=tk.WORD)
        self.file2_preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 差异结果区域
        diff_frame = ttk.LabelFrame(main_frame, text="差异结果")
        diff_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.diff_text = scrolledtext.ScrolledText(diff_frame, wrap=tk.WORD)
        self.diff_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _create_dir_compare_tab(self):
        """创建目录对比标签页"""
        # 创建标签页容器
        dir_tab = ttk.Frame(self.notebook)
        self.notebook.add(dir_tab, text="目录对比")
        
        # 创建主框架
        main_frame = ttk.Frame(dir_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建目录选择区域
        select_frame = ttk.LabelFrame(main_frame, text="选择目录")
        select_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 目录1选择
        ttk.Label(select_frame, text="目录1:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(select_frame, textvariable=self.dir1_path, width=80).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(select_frame, text="浏览...", command=self._browse_dir1).grid(row=0, column=2, padx=5, pady=5)
        
        # 目录2选择
        ttk.Label(select_frame, text="目录2:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(select_frame, textvariable=self.dir2_path, width=80).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(select_frame, text="浏览...", command=self._browse_dir2).grid(row=1, column=2, padx=5, pady=5)
        
        # 选项区域
        options_frame = ttk.LabelFrame(main_frame, text="对比选项")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 递归对比选项
        ttk.Checkbutton(options_frame, text="递归对比子目录", variable=self.recursive_compare).pack(side=tk.LEFT, padx=10, pady=5)
        
        # 对比按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 左侧功能按钮
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(left_buttons, text="开始对比", command=self._start_dir_compare, width=20).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(left_buttons, text="清空结果", command=self._clear_dir_results, width=20).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(left_buttons, text="生成报告", command=self._generate_dir_report, width=20).pack(side=tk.LEFT, padx=5, pady=5)
        
        # 右侧主题切换按钮
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT, padx=5, pady=5)
        
        self.dir_theme_button = ttk.Button(right_buttons, text="🌙 深色模式", command=self.toggle_theme, width=15)
        self.dir_theme_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 结果显示区域
        result_frame = ttk.LabelFrame(main_frame, text="目录对比结果")
        result_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建分割窗格显示结果
        self.dir_result_paned = ttk.PanedWindow(result_frame, orient=tk.HORIZONTAL)
        self.dir_result_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 仅在目录1中的文件
        only_dir1_frame = ttk.LabelFrame(self.dir_result_paned, text="仅在目录1中", width=300, height=400)
        self.dir_result_paned.add(only_dir1_frame, weight=1)
        
        self.only_dir1_tree = ttk.Treeview(only_dir1_frame)
        self.only_dir1_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 仅在目录2中的文件
        only_dir2_frame = ttk.LabelFrame(self.dir_result_paned, text="仅在目录2中", width=300, height=400)
        self.dir_result_paned.add(only_dir2_frame, weight=1)
        
        self.only_dir2_tree = ttk.Treeview(only_dir2_frame)
        self.only_dir2_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 内容不同的文件
        diff_files_frame = ttk.LabelFrame(self.dir_result_paned, text="内容不同的文件", width=300, height=400)
        self.dir_result_paned.add(diff_files_frame, weight=1)
        
        self.diff_files_tree = ttk.Treeview(diff_files_frame)
        self.diff_files_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _create_menu(self):
        """创建菜单栏"""
        # 创建菜单栏
        self.menu_bar = tk.Menu(self.root)
        
        # 创建视图菜单
        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        view_menu.add_command(label="切换深色模式", command=self.toggle_theme)
        view_menu.add_separator()
        view_menu.add_command(label="无边框模式", command=self.toggle_window_mode)
        
        # 将视图菜单添加到菜单栏
        self.menu_bar.add_cascade(label="视图", menu=view_menu)
        
        # 设置菜单栏
        self.root.config(menu=self.menu_bar)
    
    def toggle_theme(self):
        """切换深色/浅色主题"""
        global current_theme
        
        if current_theme == THEME_LIGHT:
            current_theme = THEME_DARK
            self._apply_dark_theme()
            new_button_text = "☀️ 浅色模式"
        else:
            current_theme = THEME_LIGHT
            self._apply_light_theme()
            new_button_text = "🌙 深色模式"
            
        # 更新主题按钮文本
        if hasattr(self, 'theme_button') and self.theme_button:
            self.theme_button.config(text=new_button_text)
        if hasattr(self, 'dir_theme_button') and self.dir_theme_button:
            self.dir_theme_button.config(text=new_button_text)
            
        # 主题切换后更新自定义标题栏样式
        if self.custom_title_bar:
            self._update_custom_title_bar()
            
    def toggle_window_mode(self):
        """切换系统窗口/无边框窗口模式"""
        global current_window_mode
        
        if current_window_mode == WINDOW_MODE_SYSTEM:
            current_window_mode = WINDOW_MODE_BORDERLESS
            self._enable_borderless_mode()
        else:
            current_window_mode = WINDOW_MODE_SYSTEM
            self._disable_borderless_mode()
    
    def _apply_light_theme(self):
        """应用浅色主题"""
        try:
            # 获取当前的ttk样式
            style = ttk.Style()
            
            # 设置浅色主题样式 - 按钮
            style.configure(
                "TButton",
                padding=6,
                relief="flat",
                background="#e0e0e0",
                foreground="#000000",
                borderwidth=1
            )
            
            style.map(
                "TButton",
                background=[("active", "#f0f0f0")],
                relief=[("pressed", "sunken")]
            )
            
            # 标签
            style.configure(
                "TLabel",
                background="#f0f0f0",
                foreground="#000000"
            )
            
            # 框架
            style.configure(
                "TFrame",
                background="#f0f0f0"
            )
            
            # 带标签的框架
            style.configure(
                "TLabelframe",
                background="#f0f0f0",
                borderwidth=1,
                relief="flat"
            )
            
            style.configure(
                "TLabelframe.Label",
                background="#f0f0f0",
                foreground="#000000"
            )
            
            # 配置Treeview样式
            style.configure("Treeview",
                background="#ffffff",
                foreground="#000000",
                fieldbackground="#ffffff")
            
            style.configure("Treeview.Heading",
                background="#e0e0e0",
                foreground="#000000")
            
            # 配置PanedWindow样式（分割窗口）
            style.configure("TPanedwindow",
                background="#f0f0f0")
            
            # 配置Notebook样式（标签页）
            style.configure("TNotebook",
                background="#f0f0f0",
                borderwidth=0)
            
            style.configure("TNotebook.Tab",
                background="#e0e0e0",
                foreground="#000000",
                padding=[10, 5],
                borderwidth=0)
            
            style.map("TNotebook.Tab",
                background=[("selected", "#f0f0f0")],
                foreground=[("selected", "#000000")])
            
            # 配置滚动条样式
            style.configure("Vertical.TScrollbar",
                background="#e0e0e0",
                troughcolor="#f0f0f0",
                arrowcolor="#000000")
            
            style.configure("Horizontal.TScrollbar",
                background="#e0e0e0",
                troughcolor="#f0f0f0",
                arrowcolor="#000000")
            
            # 更新根窗口背景色
            self.root.configure(background="#f0f0f0")
            
            # 初始化自定义标题栏样式（如果使用无边框模式）
            style.configure("Custom.TFrame", background="#f0f0f0")
            style.configure("Custom.TLabel", background="#f0f0f0", foreground="#000000")
            style.configure("Window.TButton", background="#e0e0e0", foreground="#000000")
            style.map("Window.TButton", background=[("active", "#d0d0d0")])
            style.configure("WindowClose.TButton", background="#e0e0e0", foreground="#000000")
            style.map("WindowClose.TButton", background=[("active", "#ff4d4d")])
            
            # 安全地更新所有文本框样式
            text_widgets = []
            for widget_name in ['file1_preview_text', 'file2_preview_text', 'diff_text', 
                               'dir1_only_tree', 'dir2_only_tree', 'diff_files_tree']:
                if hasattr(self, widget_name):
                    widget = getattr(self, widget_name)
                    text_widgets.append(widget)
            
            for widget in text_widgets:
                if hasattr(widget, "configure"):
                    if isinstance(widget, scrolledtext.ScrolledText):
                        widget.configure(
                            background="#ffffff",
                            foreground="#000000",
                            insertbackground="#000000"
                        )
                    # 对于ttk.Treeview，我们已经通过style.configure设置了样式，不需要在这里重复设置
            
            print("浅色主题应用成功")
            self.status_var.set("已切换至浅色模式")
        except Exception as ex:
            print(f"应用浅色主题时出错: {str(ex)}")
    
    def _apply_dark_theme(self):
        """应用深色主题"""
        try:
            # 获取当前的ttk样式
            style = ttk.Style()
            
            # 设置深色主题样式 - 按钮
            style.configure(
                "TButton",
                padding=6,
                relief="flat",
                background="#3c3c3c",
                foreground="#ffffff",
                borderwidth=1
            )
            
            style.map(
                "TButton",
                background=[("active", "#4c4c4c")],
                relief=[("pressed", "sunken")]
            )
            
            # 标签
            style.configure(
                "TLabel",
                background="#2d2d2d",
                foreground="#ffffff"
            )
            
            # 框架
            style.configure(
                "TFrame",
                background="#2d2d2d"
            )
            
            # 带标签的框架
            style.configure(
                "TLabelframe",
                background="#2d2d2d",
                borderwidth=1,
                relief="flat"
            )
            
            style.configure(
                "TLabelframe.Label",
                background="#2d2d2d",
                foreground="#ffffff"
            )
            
            # 配置Treeview样式
            style.configure("Treeview",
                background="#1e1e1e",
                foreground="#ffffff",
                fieldbackground="#1e1e1e")
            
            style.configure("Treeview.Heading",
                background="#3c3c3c",
                foreground="#ffffff")
            
            # 配置PanedWindow样式（分割窗口）
            style.configure("TPanedwindow",
                background="#2d2d2d")
            
            # 配置Notebook样式（标签页）
            style.configure("TNotebook",
                background="#2d2d2d",
                borderwidth=0)
            
            style.configure("TNotebook.Tab",
                background="#3c3c3c",
                foreground="#ffffff",
                padding=[10, 5],
                borderwidth=0)
            
            style.map("TNotebook.Tab",
                background=[("selected", "#2d2d2d")],
                foreground=[("selected", "#ffffff")])
            
            # 配置滚动条样式
            style.configure("Vertical.TScrollbar",
                background="#3c3c3c",
                troughcolor="#2d2d2d",
                arrowcolor="#ffffff")
            
            style.configure("Horizontal.TScrollbar",
                background="#3c3c3c",
                troughcolor="#2d2d2d",
                arrowcolor="#ffffff")
            
            # 更新根窗口背景色
            self.root.configure(background="#2d2d2d")
            
            # 初始化自定义标题栏样式（如果使用无边框模式）
            style.configure("Custom.TFrame", background="#2d2d2d")
            style.configure("Custom.TLabel", background="#2d2d2d", foreground="#ffffff")
            style.configure("Window.TButton", background="#3c3c3c", foreground="#ffffff")
            style.map("Window.TButton", background=[("active", "#4c4c4c")])
            style.configure("WindowClose.TButton", background="#3c3c3c", foreground="#ffffff")
            style.map("WindowClose.TButton", background=[("active", "#ff4d4d")])
            
            # 安全地更新所有文本框样式
            text_widgets = []
            for widget_name in ['file1_preview_text', 'file2_preview_text', 'diff_text', 
                               'dir1_only_tree', 'dir2_only_tree', 'diff_files_tree']:
                if hasattr(self, widget_name):
                    widget = getattr(self, widget_name)
                    text_widgets.append(widget)
            
            for widget in text_widgets:
                if hasattr(widget, "configure"):
                    if isinstance(widget, scrolledtext.ScrolledText):
                        widget.configure(
                            background="#1e1e1e",
                            foreground="#ffffff",
                            insertbackground="#ffffff"
                        )
                    # 对于ttk.Treeview，我们已经通过style.configure设置了样式，不需要在这里重复设置
            
            print("深色主题应用成功")
            self.status_var.set("已切换至深色模式")
        except Exception as ex:
            print(f"应用深色主题时出错: {str(ex)}")

    def _enable_borderless_mode(self):
        """启用无边框窗口模式"""
        try:
            # 保存当前窗口状态
            current_geometry = self.root.geometry()
            
            # 移除系统窗口边框，但保持任务栏可见
            self.root.overrideredirect(True)
            
            # 设置窗口属性以确保任务栏可见和可调整大小
            self.root.attributes('-topmost', False)  # 不置顶
            
            # 恢复窗口几何状态
            self.root.geometry(current_geometry)
            
            # 创建自定义标题栏
            self._create_custom_title_bar()
            
            # 创建可调整大小的边框
            self._create_resize_handles()
            
            # 调整标签页位置，避免与自定义标题栏重叠
            self.notebook.pack_forget()
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=40)  # 增加顶部padding
            
            # 确保窗口可以调整大小（注意：resize handles会处理这个）
            # self.root.bind('<Configure>', self._on_borderless_configure)
            
            # 绑定任务栏相关事件
            self._bind_taskbar_events()
            
            # 更新状态栏信息
            self.status_var.set("无边框模式已启用")
            print("无边框模式已启用")
        except Exception as ex:
            print(f"启用无边框模式时出错: {str(ex)}")
    
    def _disable_borderless_mode(self):
        """禁用无边框窗口模式"""
        try:
            # 保存当前窗口状态
            current_geometry = self.root.geometry()
            
            # 恢复系统窗口边框
            self.root.overrideredirect(False)
            
            # 恢复窗口属性
            self.root.attributes('-topmost', False)
            
            # 恢复窗口几何状态
            self.root.geometry(current_geometry)
            
            # 移除自定义标题栏
            if self.custom_title_bar:
                self.custom_title_bar.destroy()
                self.custom_title_bar = None
            
            # 移除调整大小边框
            self._remove_resize_handles()
            
            # 恢复标签页位置
            self.notebook.pack_forget()
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # 恢复默认的configure事件绑定
            self.root.bind('<Configure>', self._on_configure)
            
            # 更新状态栏信息
            self.status_var.set("系统窗口模式已启用")
            print("系统窗口模式已启用")
        except Exception as ex:
            print(f"禁用无边框模式时出错: {str(ex)}")
    
    def _create_custom_title_bar(self):
        """创建自定义标题栏"""
        # 创建标题栏框架
        title_bar_bg = "#2d2d2d" if current_theme == THEME_DARK else "#f0f0f0"
        title_bar_fg = "#ffffff" if current_theme == THEME_DARK else "#000000"
        
        self.custom_title_bar = ttk.Frame(self.root, height=35, style="Custom.TFrame")
        self.custom_title_bar.pack(fill=tk.X, side=tk.TOP)
        
        # 窗口拖动功能
        self.custom_title_bar.bind("<Button-1>", self._start_move)
        self.custom_title_bar.bind("<B1-Motion>", self._on_move)
        
        # 标题标签
        title_label = ttk.Label(
            self.custom_title_bar, 
            text="文件内容对比工具", 
            style="Custom.TLabel"
        )
        title_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # 窗口控制按钮容器
        buttons_frame = ttk.Frame(self.custom_title_bar, style="Custom.TFrame")
        buttons_frame.pack(side=tk.RIGHT)
        
        # 最小化按钮
        min_btn = ttk.Button(
            buttons_frame, 
            text="━", 
            width=3, 
            command=self._minimize_window, 
            style="Window.TButton"
        )
        min_btn.pack(side=tk.LEFT, padx=1)
        
        # 最大化按钮
        max_btn = ttk.Button(
            buttons_frame, 
            text="□", 
            width=3, 
            command=self._maximize_window, 
            style="Window.TButton"
        )
        max_btn.pack(side=tk.LEFT, padx=1)
        
        # 关闭按钮
        close_btn = ttk.Button(
            buttons_frame, 
            text="✕", 
            width=3, 
            command=self._close_window, 
            style="WindowClose.TButton"
        )
        close_btn.pack(side=tk.LEFT, padx=1)
        
        # 初始化窗口控制变量
        self.is_maximized = False
        self.normal_geometry = None
        
        # 绑定双击最大化
        self.custom_title_bar.bind('<Double-Button-1>', lambda e: self._toggle_maximize())
        title_label.bind('<Double-Button-1>', lambda e: self._toggle_maximize())
    
    def _update_custom_title_bar(self):
        """更新自定义标题栏样式"""
        if not self.custom_title_bar:
            return
        
        try:
            # 获取当前样式
            style = ttk.Style()
            
            # 根据当前主题更新自定义标题栏样式
            if current_theme == THEME_DARK:
                style.configure("Custom.TFrame", background="#2d2d2d")
                style.configure("Custom.TLabel", background="#2d2d2d", foreground="#ffffff")
                style.configure("Window.TButton", background="#3c3c3c", foreground="#ffffff")
                style.map("Window.TButton", background=[("active", "#4c4c4c")])
                style.configure("WindowClose.TButton", background="#3c3c3c", foreground="#ffffff")
                style.map("WindowClose.TButton", background=[("active", "#ff4d4d")])
            else:
                style.configure("Custom.TFrame", background="#f0f0f0")
                style.configure("Custom.TLabel", background="#f0f0f0", foreground="#000000")
                style.configure("Window.TButton", background="#e0e0e0", foreground="#000000")
                style.map("Window.TButton", background=[("active", "#d0d0d0")])
                style.configure("WindowClose.TButton", background="#e0e0e0", foreground="#000000")
                style.map("WindowClose.TButton", background=[("active", "#ff4d4d")])
                
            # 刷新标题栏
            self.custom_title_bar.update_idletasks()
        except Exception as ex:
            print(f"更新自定义标题栏样式时出错: {str(ex)}")
    
    def _start_move(self, event):
        """开始拖动窗口"""
        self.x = event.x
        self.y = event.y
    
    def _on_move(self, event):
        """拖动窗口时的回调"""
        if not self.is_maximized:
            x = self.root.winfo_x() + event.x - self.x
            y = self.root.winfo_y() + event.y - self.y
            self.root.geometry(f"+{x}+{y}")
    
    def _minimize_window(self):
        """最小化窗口"""
        try:
            # 无边框模式下使用系统最小化
            if current_window_mode == WINDOW_MODE_BORDERLESS:
                # 临时恢复系统边框以支持最小化
                self.root.overrideredirect(False)
                self.root.iconify()
                # 延迟恢复无边框模式
                self.root.after(100, lambda: self.root.overrideredirect(True))
            else:
                self.root.iconify()
        except Exception:
            # 如果iconify失败，尝试其他方法
            try:
                self.root.state('iconic')
            except Exception:
                # 最后的备选方案
                self.root.state('withdrawn')
                self.root.after(500, lambda: self.root.state('normal'))
    
    def _toggle_maximize(self):
        """切换最大化/恢复状态"""
        if self.is_maximized:
            # 恢复窗口
            self.root.geometry(self.normal_geometry)
            self.is_maximized = False
        else:
            # 保存当前窗口状态
            self.normal_geometry = self.root.geometry()
            # 最大化窗口
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")
            self.is_maximized = True
    
    def _maximize_window(self):
        """最大化/恢复窗口"""
        if self.is_maximized:
            # 恢复窗口
            self.root.geometry(self.normal_geometry)
            self.is_maximized = False
        else:
            # 保存当前窗口状态
            self.normal_geometry = self.root.geometry()
            # 最大化窗口
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.root.geometry(f"{screen_width}x{screen_height}+0+0")
            self.is_maximized = True
    
    def _close_window(self):
        """关闭窗口"""
        self.root.destroy()
    
    def _create_resize_handles(self):
        """创建可调整大小的边框手柄 - 优化稳定性和响应性"""
        self.resize_handles = {}
        self.is_resizing = False
        
        # 创建8个调整手柄（4个角 + 4个边）
        positions = ['nw', 'n', 'ne', 'w', 'e', 'sw', 's', 'se']
        
        for pos in positions:
            # 使用透明背景色隐藏蓝色提示，但保留功能
            handle = tk.Frame(self.root, bg='', bd=0, cursor=self._get_cursor(pos))
            handle.place(x=0, y=0, width=10, height=10)  # 保持足够的交互区域
            
            # 绑定鼠标事件
            handle.bind('<Button-1>', lambda e, p=pos: self._start_resize(e, p))
            handle.bind('<B1-Motion>', lambda e, p=pos: self._on_resize(e, p))
            handle.bind('<ButtonRelease-1>', lambda e: self._end_resize(e))  # 添加释放事件
            
            # 可选：如果需要，只在鼠标悬停时显示手柄
            # handle.bind('<Enter>', lambda e, h=handle: h.configure(bg='#0078d4'))
            # handle.bind('<Leave>', lambda e, h=handle: h.configure(bg=''))
            
            self.resize_handles[pos] = handle
        
        # 延迟初始更新，确保窗口完全渲染
        self.root.after(100, self._update_resize_handles)
        
        # 绑定窗口大小变化事件
        self.root.bind('<Configure>', self._on_configure_resize)
    
    def _remove_resize_handles(self):
        """移除调整大小边框"""
        if hasattr(self, 'resize_handles'):
            for handle in self.resize_handles.values():
                handle.destroy()
            delattr(self, 'resize_handles')
        
        # 移除窗口大小变化事件绑定
        self.root.bind('<Configure>', self._on_configure)
    
    def _get_cursor(self, position):
        """获取指定位置的鼠标光标"""
        cursors = {
            'nw': 'size_nw_se',
            'n': 'size_ns',
            'ne': 'size_ne_sw',
            'w': 'size_we',
            'e': 'size_we',
            'sw': 'size_ne_sw',
            's': 'size_ns',
            'se': 'size_nw_se'
        }
        return cursors.get(position, 'arrow')
    
    def _update_resize_handles(self):
        """更新调整手柄的位置 - 优化性能和稳定性"""
        if not hasattr(self, 'resize_handles'):
            return
        
        try:
            # 获取窗口尺寸
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            
            # 确保有效尺寸
            if width <= 0 or height <= 0:
                return
            
            # 定义手柄位置和尺寸
            positions = {
                'nw': (0, 0, 5, 5),
                'n': (5, 0, max(1, width-10), 5),
                'ne': (max(0, width-5), 0, 5, 5),
                'w': (0, 5, 5, max(1, height-10)),
                'e': (max(0, width-5), 5, 5, max(1, height-10)),
                'sw': (0, max(0, height-5), 5, 5),
                's': (5, max(0, height-5), max(1, width-10), 5),
                'se': (max(0, width-5), max(0, height-5), 5, 5)
            }
            
            # 更新每个手柄的位置
            for pos, (x, y, w, h) in positions.items():
                handle = self.resize_handles[pos]
                if w > 0 and h > 0:  # 确保有效尺寸
                    handle.place(x=x, y=y, width=w, height=h)
                    handle.lift()  # 确保手柄在最上层
                    
        except Exception as ex:
            print(f"更新调整手柄时出错: {ex}")
            # 忽略错误，继续运行
    
    def _start_resize(self, event, position):
        """开始调整大小 - 优化初始状态捕获"""
        try:
            # 确保事件坐标有效
            if event.x_root == 0 and event.y_root == 0:
                return
            
            self.resize_start_x = event.x_root
            self.resize_start_y = event.y_root
            self.resize_start_width = self.root.winfo_width()
            self.resize_start_height = self.root.winfo_height()
            self.resize_start_pos_x = self.root.winfo_x()
            self.resize_start_pos_y = self.root.winfo_y()
            self.resize_position = position
            
            # 标记正在调整大小
            self.is_resizing = True
            
            # 禁用其他手柄，避免冲突
            if hasattr(self, 'resize_handles'):
                for pos, handle in self.resize_handles.items():
                    if pos != position:
                        handle.lower()  # 降低其他手柄的层级
             
        except Exception as ex:
             print(f"开始调整大小失败: {ex}")
             self.is_resizing = False
    
    def _on_resize(self, event, position):
        """处理调整大小 - 优化实时渲染和稳定性"""
        # 检查是否正在调整大小
        if not hasattr(self, 'is_resizing') or not self.is_resizing:
            return
        
        try:
            # 确保事件坐标有效
            if event.x_root == 0 and event.y_root == 0:
                return
            
            dx = event.x_root - self.resize_start_x
            dy = event.y_root - self.resize_start_y
            
            # 设置阈值，避免微小移动导致频繁更新
            if abs(dx) < 2 and abs(dy) < 2:
                return
            
            new_width = self.resize_start_width
            new_height = self.resize_start_height
            new_x = self.resize_start_pos_x
            new_y = self.resize_start_pos_y
            
            # 根据位置调整大小和位置
            if 'e' in position:
                new_width = max(800, self.resize_start_width + dx)
            if 'w' in position:
                new_width = max(800, self.resize_start_width - dx)
                new_x = self.resize_start_pos_x + dx
            if 's' in position:
                new_height = max(700, self.resize_start_height + dy)
            if 'n' in position:
                new_height = max(700, self.resize_start_height - dy)
                new_y = self.resize_start_pos_y + dy
            
            # 应用新的大小和位置
            self.root.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")
            
            # 强制立即更新UI - 优化实时渲染
            self.root.update_idletasks()
            
            # 立即更新手柄位置，确保实时反馈
            self._update_resize_handles()
            
        except Exception as ex:
            print(f"调整大小失败: {ex}")
            self.is_resizing = False
    
    def _end_resize(self, event):
        """结束调整大小 - 清理状态"""
        self.is_resizing = False
        
        # 恢复所有手柄层级
        if hasattr(self, 'resize_handles'):
            for handle in self.resize_handles.values():
                handle.lift()
        
        # 最终更新手柄位置
        self._update_resize_handles()
    
    def _on_configure_resize(self, event):
        """处理窗口配置变化 - 优化实时响应"""
        if event.widget == self.root:
            # 立即处理配置变化，避免延迟
            self._on_configure(event)
            self._on_borderless_configure(event)  # 调用无边框配置处理
            
            # 如果正在调整大小，立即更新手柄
            if self.is_resizing:
                self._update_resize_handles()
            else:
                # 非调整状态下可以延迟更新
                if hasattr(self, '_config_update_id'):
                    self.root.after_cancel(self._config_update_id)
                self._config_update_id = self.root.after(50, self._update_resize_handles)
    
    def _bind_taskbar_events(self):
        """绑定任务栏相关事件"""
        # 确保窗口在任务栏中显示
        self.root.bind('<FocusIn>', self._on_focus_in)
        self.root.bind('<FocusOut>', self._on_focus_out)
        
        # 绑定系统菜单事件（右键点击任务栏图标）
        self.root.bind('<Button-3>', self._on_system_menu)
    
    def _on_focus_in(self, event):
        """窗口获得焦点"""
        # 确保窗口在任务栏中正常显示
        self.root.attributes('-topmost', False)
    
    def _on_focus_out(self, event):
        """窗口失去焦点"""
        # 可以在这里添加失去焦点时的处理
        pass
    
    def _on_system_menu(self, event):
        """处理系统菜单事件"""
        # 可以在这里添加右键菜单
        pass

    def _create_status_and_log(self):
        """创建底部状态和日志区域"""
        # 创建状态条
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))  # 添加底部边距
        
        # 创建日志区域（可选显示）
        self.log_window = None
    
    def _browse_file1(self):
        """浏览并选择第一个文件"""
        file_path = filedialog.askopenfilename(
            title="选择第一个文件",
            filetypes=[("所有支持的文件", "*".join(supported_formats.keys())), ("所有文件", "*")]
        )
        if file_path:
            self.file1_path.set(file_path)
            self._preview_file(file_path, self.file1_preview_text, self.file1_preview_label)
    
    def _browse_file2(self):
        """浏览并选择第二个文件"""
        file_path = filedialog.askopenfilename(
            title="选择第二个文件",
            filetypes=[("所有支持的文件", "*".join(supported_formats.keys())), ("所有文件", "*")]
        )
        if file_path:
            self.file2_path.set(file_path)
            self._preview_file(file_path, self.file2_preview_text, self.file2_preview_label)
    
    def _browse_dir1(self):
        """浏览并选择第一个目录"""
        dir_path = filedialog.askdirectory(title="选择第一个目录")
        if dir_path:
            self.dir1_path.set(dir_path)
    
    def _browse_dir2(self):
        """浏览并选择第二个目录"""
        dir_path = filedialog.askdirectory(title="选择第二个目录")
        if dir_path:
            self.dir2_path.set(dir_path)
    
    def _preview_file(self, file_path: str, text_widget: scrolledtext.ScrolledText, label_widget: ttk.Label):
        """预览文件内容"""
        try:
            # 获取文件名和类型
            file_name = os.path.basename(file_path)
            file_type = get_file_type(file_path)
            
            # 更新标签
            label_widget.config(text=f"{file_name} - {file_type}")
            
            # 尝试导入核心模块的extract_text_from_file函数
            from file_diff_core import extract_text_from_file
            
            # 提取并显示文件内容
            text = extract_text_from_file(file_path)
            
            # 限制显示的内容长度，防止大文件导致UI卡顿
            max_display_length = 100000  # 限制为100KB文本
            if len(text) > max_display_length:
                text = text[:max_display_length] + "\n\n... 内容过长，已截断显示 ..."
            
            # 清空并插入文本
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, text)
        except Exception as e:
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, f"无法预览文件内容: {str(e)}")
    
    def _start_file_compare(self):
        """开始文件对比"""
        file1 = self.file1_path.get().strip()
        file2 = self.file2_path.get().strip()
        
        # 检查文件是否存在
        if not os.path.isfile(file1):
            messagebox.showerror("错误", "第一个文件不存在或路径无效")
            return
        
        if not os.path.isfile(file2):
            messagebox.showerror("错误", "第二个文件不存在或路径无效")
            return
        
        # 更新状态栏
        self.status_var.set("正在对比文件...")
        
        # 清空之前的差异结果
        self.diff_text.delete(1.0, tk.END)
        
        # 在新线程中执行对比操作，避免UI卡顿
        threading.Thread(target=self._compare_files_thread, args=(file1, file2), daemon=True).start()
    
    def _compare_files_thread(self, file1: str, file2: str):
        """文件对比线程"""
        try:
            # 执行文件对比
            result = compare_files(file1, file2, self.ignore_whitespace.get())
            
            # 在主线程中更新UI
            self.root.after(0, self._update_file_compare_result, result, file1, file2)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"对比文件时发生错误: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.status_var.set("就绪"))
    
    def _update_file_compare_result(self, result: dict, file1: str, file2: str):
        """更新文件对比结果UI"""
        # 生成差异报告
        report = generate_diff_report(result, os.path.basename(file1), os.path.basename(file2))
        
        # 显示差异报告
        self.diff_text.delete(1.0, tk.END)
        self.diff_text.insert(tk.END, report)
        
        # 如果文件不同，高亮显示差异
        if not result['is_same'] and result['text1'] and result['text2']:
            # 添加差异高亮标记
            # 这里可以实现更复杂的差异高亮逻辑
            pass
        
        # 更新统计信息
        self.stats['compared_files'] += 1
        if result['is_same']:
            self.stats['same_files'] += 1
            messagebox.showinfo("结果", "两个文件内容完全相同")
        else:
            self.stats['different_files'] += 1
            if result['error']:
                self.stats['errors_count'] += 1
                messagebox.showerror("结果", f"对比文件时发生错误: {result['error']}")
            else:
                messagebox.showinfo("结果", f"两个文件内容不同，相似度: {result['similarity']:.2%}")
    
    def _start_dir_compare(self):
        """开始目录对比"""
        dir1 = self.dir1_path.get().strip()
        dir2 = self.dir2_path.get().strip()
        
        # 检查目录是否存在
        if not os.path.isdir(dir1):
            messagebox.showerror("错误", "第一个目录不存在或路径无效")
            return
        
        if not os.path.isdir(dir2):
            messagebox.showerror("错误", "第二个目录不存在或路径无效")
            return
        
        # 更新状态栏
        self.status_var.set("正在对比目录...")
        
        # 清空之前的结果
        self._clear_dir_results()
        
        # 在新线程中执行对比操作
        threading.Thread(target=self._compare_dirs_thread, args=(dir1, dir2), daemon=True).start()
    
    def _compare_dirs_thread(self, dir1: str, dir2: str):
        """目录对比线程"""
        try:
            # 执行目录对比
            result = compare_directories(dir1, dir2, self.recursive_compare.get())
            
            # 在主线程中更新UI
            self.root.after(0, self._update_dir_compare_result, result)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"对比目录时发生错误: {str(e)}"))
        finally:
            self.root.after(0, lambda: self.status_var.set("就绪"))
    
    def _update_dir_compare_result(self, result: dict):
        """更新目录对比结果UI"""
        # 填充仅在目录1中的文件
        self._fill_tree(self.only_dir1_tree, result['only_in_dir1'])
        
        # 填充仅在目录2中的文件
        self._fill_tree(self.only_dir2_tree, result['only_in_dir2'])
        
        # 填充内容不同的文件
        self._fill_tree(self.diff_files_tree, result['different_files'])
        
        # 显示统计信息
        message = (
            f"目录对比完成！\n\n"
            f"目录1文件总数: {result['total_files_dir1']}\n\n"
            f"目录2文件总数: {result['total_files_dir2']}\n\n"
            f"仅在目录1中: {len(result['only_in_dir1'])} 个文件\n\n"
            f"仅在目录2中: {len(result['only_in_dir2'])} 个文件\n\n"
            f"共同文件: {len(result['same_files']) + len(result['different_files'])} 个文件\n\n"
            f"  - 内容相同: {len(result['same_files'])}\n\n"
            f"  - 内容不同: {len(result['different_files'])} 个文件\n"
            )
        messagebox.showinfo("目录对比结果", message)
    
    def _fill_tree(self, tree: ttk.Treeview, files: list):
        """填充Treeview组件"""
        # 清空树
        for item in tree.get_children():
            tree.delete(item)
        
        # 创建文件树结构
        file_dict = {}
        
        for file_path in files:
            # 分割路径
            parts = file_path.split(os.path.sep)
            current_dict = file_dict
            
            # 构建目录结构
            for i, part in enumerate(parts):
                if part not in current_dict:
                    if i == len(parts) - 1:  # 是文件
                        current_dict[part] = None
                    else:  # 是目录
                        current_dict[part] = {}
                current_dict = current_dict.get(part, {})
        
        # 递归添加节点到树
        self._add_nodes_to_tree("", "", file_dict, tree)
    
    def _add_nodes_to_tree(self, parent: str, path: str, file_dict: dict, tree: ttk.Treeview):
        """递归添加节点到Treeview"""
        for name, children in sorted(file_dict.items()):
            new_path = os.path.join(path, name) if path else name
            if children is None:  # 是文件
                tree.insert(parent, tk.END, text=name, value=(new_path,))
            else:  # 是目录
                node = tree.insert(parent, tk.END, text=name, value=(new_path,))
                self._add_nodes_to_tree(node, new_path, children, tree)
    
    def _clear_file_results(self):
        """清空文件对比结果"""
        self.diff_text.delete(1.0, tk.END)
    
    def _clear_dir_results(self):
        """清空目录对比结果"""
        for tree in [self.only_dir1_tree, self.only_dir2_tree, self.diff_files_tree]:
            for item in tree.get_children():
                tree.delete(item)
    
    def _generate_file_report(self):
        """生成文件对比报告"""
        # 检查是否已经进行过对比
        if not self.diff_text.get(1.0, tk.END).strip():
            messagebox.showinfo("提示", "请先进行文件对比")
            return
        
        # 保存报告文件
        report_path = filedialog.asksaveasfilename(
            title="保存对比报告",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*")]
        )
        
        if report_path:
            try:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(self.diff_text.get(1.0, tk.END))
                messagebox.showinfo("成功", f"报告已保存到: {report_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存报告失败: {str(e)}")
    
    def _generate_dir_report(self):
        """生成目录对比报告"""
        # 检查是否已经进行过对比
        if not (self.only_dir1_tree.get_children() or self.only_dir2_tree.get_children() or self.diff_files_tree.get_children()):
            messagebox.showinfo("提示", "请先进行目录对比")
            return
        
        # 保存报告文件
        report_path = filedialog.asksaveasfilename(
            title="保存对比报告",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*")]
        )
        
        if report_path:
            try:
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write("目录对比报告\n")
                    f.write("=" * 50 + "\n\n")
                    
                    # 写入目录信息
                    f.write(f"目录1: {self.dir1_path.get()}\n")
                    f.write(f"目录2: {self.dir2_path.get()}\n\n")
                    
                    # 写入仅在目录1中的文件
                    f.write("仅在目录1中的文件:\n")
                    for item in self.only_dir1_tree.get_children():
                        f.write(f"  - {self.only_dir1_tree.item(item, 'value')[0]}\n")
                    f.write("\n")
                    
                    # 写入仅在目录2中的文件
                    f.write("仅在目录2中的文件:\n")
                    for item in self.only_dir2_tree.get_children():
                        f.write(f"  - {self.only_dir2_tree.item(item, 'value')[0]}\n")
                    f.write("\n")
                    
                    # 写入内容不同的文件
                    f.write("内容不同的文件:\n")
                    for item in self.diff_files_tree.get_children():
                        f.write(f"  - {self.diff_files_tree.item(item, 'value')[0]}\n")
                    
                messagebox.showinfo("成功", f"报告已保存到: {report_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存报告失败: {str(e)}")
    
    def _on_configure(self, event):
        """窗口大小变化事件处理"""
        pass  # 可以在这里实现窗口自适应逻辑
    
    def _on_borderless_configure(self, event):
        """无边框模式下的窗口配置处理"""
        if event.widget == self.root:
            # 处理无边框窗口的大小调整
            if event.width and event.height:
                # 确保窗口可以调整大小
                self.root.geometry(f"{event.width}x{event.height}")
            
            # 调用常规的configure处理
            self._on_configure(event)
    
    def _maybe_resize_window(self):
        """可能的窗口大小调整处理"""
        # 确保所有组件都能正确显示
        self.root.update_idletasks()
        
        # 检查是否需要调整窗口大小以确保底部内容可见
        current_height = self.root.winfo_height()
        if current_height < 700:
            current_width = self.root.winfo_width()
            self.root.geometry(f"{current_width}x700")
    
    def _center_window(self):
        """
        将窗口居中显示
        
        在UI完全构建完成后调用，让窗口在屏幕中央显示。
        只设置位置，保持窗口的自适应大小。
        """
        try:
            self.root.update_idletasks()  # 确保窗口大小计算完成
            
            # 获取窗口实际大小
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            
            # 如果窗口大小还没有正确计算，使用请求的大小
            if width <= 1 or height <= 1:
                width = self.root.winfo_reqwidth()
                height = self.root.winfo_reqheight()
            
            # 计算居中位置
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width // 2) - (width // 2)
            y = (screen_height // 2) - (height // 2)
            
            # 确保窗口不会超出屏幕边界
            x = max(0, min(x, screen_width - width))
            y = max(0, min(y, screen_height - height))
            
            # 只设置位置，不设置大小
            self.root.geometry(f"+{x}+{y}")
        except Exception:
            # 静默失败，不影响程序运行
            pass
    
    def _drain(self):
        """处理队列中的日志消息"""
        try:
            # 尝试从队列中获取一条消息，但不阻塞
            msg = self.q.get_nowait()
            # 这里可以处理消息（日志显示等）
            self.q.task_done()
        except queue.Empty:
            pass
        
        # 继续监听队列，100毫秒后再次调用
        self.root.after(100, self._drain)

def launch():
    """启动文件对比工具应用"""
    print("启动文件对比工具...")
    try:
        print("创建主窗口...")
        # 创建主窗口
        root = tk.Tk()
        print("主窗口创建成功")
        
        print("设置Win11风格的界面主题...")
        # 设置Win11风格的界面主题
        style = ttk.Style()
        
        # 检查是否支持Windows 11主题
        if sys.platform.startswith('win'):
            try:
                print("尝试设置Windows 11风格的主题...")
                # 尝试设置Windows 11风格的主题
                style.theme_use('clam')  # 使用clam主题作为基础
                
                # 导入主题相关变量
                from file_diff_ui import current_theme, THEME_LIGHT, THEME_DARK
                
                # 检测系统深色模式设置
                try:
                    import ctypes
                    import winreg
                    
                    # 尝试通过注册表检测系统深色模式
                    try:
                        # 打开系统主题设置注册表项
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                            r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
                            # 读取AppsUseLightTheme值
                            value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
                            is_light_mode = value == 1
                            is_dark_mode = not is_light_mode
                            print(f"检测到系统主题: {'深色' if is_dark_mode else '浅色'}")
                    except Exception as e:
                        # 注册表读取失败，尝试使用DWM API检测
                        try:
                            # 加载dwmapi.dll
                            dwmapi = ctypes.WinDLL('dwmapi')
                            # 定义函数参数类型
                            dwmapi.DwmGetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
                            
                            # 获取窗口句柄
                            hwnd = root.winfo_id()
                            # DWMWA_USE_IMMERSIVE_DARK_MODE = 26
                            attribute = ctypes.c_int(26)
                            value = ctypes.c_int(0)
                            value_size = ctypes.c_uint(ctypes.sizeof(value))
                            
                            # 调用DWM API获取窗口属性
                            result = dwmapi.DwmGetWindowAttribute(hwnd, attribute, ctypes.byref(value), value_size)
                            is_dark_mode = result == 0 and value.value == 1
                            print(f"检测到系统主题: {'深色' if is_dark_mode else '浅色'}")
                        except Exception as dwm_e:
                            print(f"注册表和DWM API检测均失败: {str(dwm_e)}")
                            # 默认使用浅色主题
                            is_dark_mode = False
                    
                    # 根据系统设置更新当前主题
                    if is_dark_mode:
                        current_theme = THEME_DARK
                    else:
                        current_theme = THEME_LIGHT
                except Exception as theme_detection_error:
                    print(f"检测系统主题时出错: {str(theme_detection_error)}")
                    print("使用默认主题")
                    # 保持当前默认主题不变
                    pass
                
                # 应用当前主题（可能已根据系统设置更新）
                if current_theme == THEME_DARK:
                    # 设置深色主题样式
                    style.configure(
                        "TButton",
                        padding=6,
                        relief="flat",
                        background="#3c3c3c",
                        foreground="#ffffff",
                        borderwidth=1
                    )
                    
                    style.map(
                        "TButton",
                        background=[("active", "#4c4c4c")],
                        relief=[("pressed", "sunken")]
                    )
                    
                    style.configure(
                        "TLabel",
                        background="#2d2d2d",
                        foreground="#ffffff"
                    )
                    
                    style.configure(
                        "TFrame",
                        background="#2d2d2d"
                    )
                    
                    style.configure(
                        "TLabelframe",
                        background="#2d2d2d",
                        borderwidth=1,
                        relief="flat"
                    )
                    
                    style.configure(
                        "TLabelframe.Label",
                        background="#2d2d2d",
                        foreground="#ffffff"
                    )
                else:
                    # 设置浅色主题样式
                    style.configure(
                        "TButton",
                        padding=6,
                        relief="flat",
                        background="#e0e0e0",
                        foreground="#000000",
                        borderwidth=1
                    )
                    
                    style.map(
                        "TButton",
                        background=[("active", "#d0d0d0")],
                        relief=[("pressed", "sunken")]
                    )
                    
                    style.configure(
                        "TLabel",
                        background="#f0f0f0",
                        foreground="#000000"
                    )
                    
                    style.configure(
                        "TFrame",
                        background="#f0f0f0"
                    )
                    
                    style.configure(
                        "TLabelframe",
                        background="#f0f0f0",
                        borderwidth=1,
                        relief="flat"
                    )
                    
                    style.configure(
                        "TLabelframe.Label",
                        background="#f0f0f0",
                        foreground="#000000"
                    )
                print("Windows 11风格主题设置成功")
            except Exception as ex:
                print(f"Windows 11风格主题设置失败: {str(ex)}")
                pass  # 忽略主题设置失败
        else:
            print("非Windows平台，跳过Windows 11主题设置")
        
        print("创建应用实例...")
        # 创建应用实例
        app = FileDiffApp(root)
        print("应用实例创建成功")
        
        print("启动主循环...")
        # 启动主循环
        root.mainloop()
        
        print("主循环退出")
        return 0
    except Exception as e:
        print(f"启动应用时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1