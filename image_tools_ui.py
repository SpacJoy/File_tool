"""
图片工具UI模块

这个模块包含图片工具的所有图形用户界面实现，包括：
- 主窗口布局
- 各种功能选项卡
- 预览功能
- 日志显示
- 用户交互处理

该模块依赖于image_tools_core模块提供的核心功能。
"""
from __future__ import annotations
import os
import sys
import threading
import queue
import re
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

# 尝试导入Tkinter库
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font

# 导入核心功能模块
from image_tools_core import (
    Image,
    ImageFile,
    SUPPORTED_EXT,
    KEEP_MAP,
    ACTION_MAP,
    FMT_MAP,
    OVERWRITE_MAP,
    WEBP_COMPRESSION_MAP,
    STAGE_MAP_DISPLAY,
    _rev_map,
    get_webp_params,
    iter_images,
    norm_ext,
    next_non_conflict,
    safe_delete,
    ahash,
    dhash,
    hamming,
    _fmt_size,
    convert_one
)

# 尝试导入其他可选依赖
try:
    import shutil
    _has_shutil = True
except ImportError:
    _has_shutil = False

# UI字体配置
DEFAULT_FONT_SIZE = 9
DEFAULT_FONT_FAMILY = "Microsoft YaHei UI"  # Windows 默认字体

class ImageToolApp:
    """
    图片工具的主应用类，负责创建和管理所有UI组件以及处理用户交互。
    """
    def __init__(self, root):
        """
        初始化图片工具应用。
        
        Args:
            root: Tkinter根窗口对象
        """
        self.root = root
        self.root.title('图片工具')
        
        # Windows DPI感知设置
        try:
            if sys.platform.startswith('win'):
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 启用DPI感知
        except Exception:
            pass  # 忽略DPI设置失败
        
        # 字体配置
        try:
            self.default_font = font.nametofont("TkDefaultFont")
            self.default_font.configure(family=DEFAULT_FONT_FAMILY, size=DEFAULT_FONT_SIZE)
            
            # 配置默认字体
            self.root.option_add("*Font", self.default_font)
        except Exception:
            pass  # 字体配置失败时使用系统默认
        
        # 窗口初始化 - 使用自适应大小
        self.root.geometry('1200x800')
        self.root.minsize(1024, 600)
        self._min_window_width = 1024  # 最小窗口宽度
        
        # 缓存相关
        self.cache_dir = None
        self.cache_final_dir = None
        self.cache_trash_dir = None
        self._clear_cache()
        
        # 线程控制
        self.stop_flag = threading.Event()
        self.q = queue.Queue()
        self.write_to_output = True  # 是否实际写入输出目录
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'end_time': None,
            'input_files': 0,
            'output_files': 0,
            'skipped_files': 0,
            'error_files': 0,
            'converted_files': 0,
            'renamed_files': 0,
            'classified_files': 0,
            'dedupe_kept': 0,
            'dedupe_removed': 0,
            'warnings_count': 0,
            'errors_count': 0,
            'file_formats': {},  # 格式分布统计
            'operations': [],  # 执行的操作列表
            'total_size_before': 0,
            'total_size_after': 0,
        }
        
        # 预览相关
        self.preview_thread = None
        self.preview_after_label = None
        self.preview_before_label = None
        self.preview_after_info = None
        self.preview_before_info = None
        
        # 窗口自动调整相关
        self._last_auto_size = None
        self._log_fixed_height = None
        self.auto_resize_window = tk.BooleanVar(value=True)
        
        # 设置标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建各个功能标签页
        self._create_convert_tab()
        self._create_rename_tab()
        self._create_classify_tab()
        self._create_dedupe_tab()
        
        # 创建底部状态和日志区域
        self._create_status_and_log()
        
        # 启动日志处理线程
        self._drain()
        
        # 初始化预览线程
        self._init_preview_thread()
        
        # 绑定窗口事件
        self.root.bind('<Configure>', self._on_configure)
        
    def _create_convert_tab(self):
        """创建格式转换标签页"""
        # 创建标签页容器
        convert_tab = ttk.Frame(self.notebook)
        self.notebook.add(convert_tab, text="格式转换")
        
        # 创建左侧源文件区域
        left_frame = ttk.LabelFrame(convert_tab, text="源文件")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 添加源文件列表
        src_list_frame = ttk.Frame(left_frame)
        src_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 滚动条
        src_scrollbar_y = ttk.Scrollbar(src_list_frame)
        src_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        src_scrollbar_x = ttk.Scrollbar(src_list_frame, orient=tk.HORIZONTAL)
        src_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 文件列表
        self.src_file_list = ttk.Treeview(src_list_frame, yscrollcommand=src_scrollbar_y.set, xscrollcommand=src_scrollbar_x.set)
        self.src_file_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 设置列
        self.src_file_list['columns'] = ('name', 'size', 'modified')
        self.src_file_list.column('#0', width=0, stretch=tk.NO)
        self.src_file_list.column('name', anchor=tk.W, width=300)
        self.src_file_list.column('size', anchor=tk.E, width=80)
        self.src_file_list.column('modified', anchor=tk.W, width=150)
        
        # 设置标题
        self.src_file_list.heading('#0', text='', anchor=tk.W)
        self.src_file_list.heading('name', text='文件名', anchor=tk.W)
        self.src_file_list.heading('size', text='大小', anchor=tk.E)
        self.src_file_list.heading('modified', text='修改日期', anchor=tk.W)
        
        # 绑定滚动条
        src_scrollbar_y.config(command=self.src_file_list.yview)
        src_scrollbar_x.config(command=self.src_file_list.xview)
        
        # 源文件控制按钮
        src_buttons_frame = ttk.Frame(left_frame)
        src_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.add_files_btn = ttk.Button(src_buttons_frame, text="添加文件", command=self._add_files)
        self.add_files_btn.pack(side=tk.LEFT, padx=2)
        
        self.add_folder_btn = ttk.Button(src_buttons_frame, text="添加文件夹", command=self._add_folder)
        self.add_folder_btn.pack(side=tk.LEFT, padx=2)
        
        self.clear_files_btn = ttk.Button(src_buttons_frame, text="清空", command=self._clear_files)
        self.clear_files_btn.pack(side=tk.RIGHT, padx=2)
        
        # 创建右侧设置区域
        right_frame = ttk.LabelFrame(convert_tab, text="转换设置")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        # 输出格式选择
        format_frame = ttk.LabelFrame(right_frame, text="输出格式")
        format_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 输出格式选项
        self.output_format = tk.StringVar(value="webp")
        
        formats = ["webp", "jpg", "png", "gif", "bmp", "tiff", "ico"]
        for fmt in formats:
            fmt_frame = ttk.Frame(format_frame)
            fmt_frame.pack(fill=tk.X, padx=5, pady=2)
            
            ttk.Radiobutton(fmt_frame, text=f"{fmt.upper()}", variable=self.output_format, value=fmt).pack(side=tk.LEFT)
        
        # 质量设置
        quality_frame = ttk.LabelFrame(right_frame, text="质量设置")
        quality_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 质量滑块
        self.quality_var = tk.IntVar(value=85)
        ttk.Label(quality_frame, text="质量:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Scale(quality_frame, from_=1, to=100, orient=tk.HORIZONTAL, variable=self.quality_var).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Label(quality_frame, textvariable=self.quality_var).grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        
        # 其他选项
        options_frame = ttk.LabelFrame(right_frame, text="其他选项")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # WebP压缩方式
        self.webp_compression = tk.StringVar(value="auto")
        ttk.Label(options_frame, text="WebP压缩方式:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        webp_methods = ttk.Combobox(options_frame, textvariable=self.webp_compression, state="readonly", values=["auto", "lossless", "high_quality", "standard", "fast"])
        webp_methods.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        
        # 输出目录设置
        output_frame = ttk.LabelFrame(right_frame, text="输出目录")
        output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.output_dir_var = tk.StringVar(value="")
        ttk.Entry(output_frame, textvariable=self.output_dir_var).pack(fill=tk.X, side=tk.LEFT, padx=5, pady=5, expand=True)
        ttk.Button(output_frame, text="浏览", command=self._browse_output_dir).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 开始转换按钮
        ttk.Button(right_frame, text="开始转换", command=self._start_convert, width=20).pack(fill=tk.X, padx=5, pady=20)

    def _create_rename_tab(self):
        """创建批量重命名标签页"""
        # 创建标签页容器
        rename_tab = ttk.Frame(self.notebook)
        self.notebook.add(rename_tab, text="批量重命名")
        
        # 创建左侧源文件区域 - 与转换标签页类似
        left_frame = ttk.LabelFrame(rename_tab, text="源文件")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 添加源文件列表
        src_list_frame = ttk.Frame(left_frame)
        src_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 滚动条
        src_scrollbar_y = ttk.Scrollbar(src_list_frame)
        src_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        src_scrollbar_x = ttk.Scrollbar(src_list_frame, orient=tk.HORIZONTAL)
        src_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 文件列表
        self.rename_file_list = ttk.Treeview(src_list_frame, yscrollcommand=src_scrollbar_y.set, xscrollcommand=src_scrollbar_x.set)
        self.rename_file_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 设置列
        self.rename_file_list['columns'] = ('name', 'preview')
        self.rename_file_list.column('#0', width=0, stretch=tk.NO)
        self.rename_file_list.column('name', anchor=tk.W, width=300)
        self.rename_file_list.column('preview', anchor=tk.W, width=300)
        
        # 设置标题
        self.rename_file_list.heading('#0', text='', anchor=tk.W)
        self.rename_file_list.heading('name', text='原始文件名', anchor=tk.W)
        self.rename_file_list.heading('preview', text='重命名预览', anchor=tk.W)
        
        # 绑定滚动条
        src_scrollbar_y.config(command=self.rename_file_list.yview)
        src_scrollbar_x.config(command=self.rename_file_list.xview)
        
        # 源文件控制按钮
        src_buttons_frame = ttk.Frame(left_frame)
        src_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(src_buttons_frame, text="添加文件", command=self._add_rename_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(src_buttons_frame, text="添加文件夹", command=self._add_rename_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(src_buttons_frame, text="清空", command=self._clear_rename_files).pack(side=tk.RIGHT, padx=2)
        
        # 创建右侧设置区域
        right_frame = ttk.LabelFrame(rename_tab, text="重命名设置")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        # 命名规则
        rule_frame = ttk.LabelFrame(right_frame, text="命名规则")
        rule_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 前缀
        self.prefix_var = tk.StringVar(value="")
        ttk.Label(rule_frame, text="前缀:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(rule_frame, textvariable=self.prefix_var).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        
        # 编号设置
        num_frame = ttk.Frame(rule_frame)
        num_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Checkbutton(num_frame, text="添加编号").pack(side=tk.LEFT, padx=5)
        ttk.Label(num_frame, text="起始:").pack(side=tk.LEFT, padx=5)
        self.start_num_var = tk.IntVar(value=1)
        ttk.Entry(num_frame, textvariable=self.start_num_var, width=5).pack(side=tk.LEFT)
        
        ttk.Label(num_frame, text="位数:").pack(side=tk.LEFT, padx=5)
        self.digits_var = tk.IntVar(value=3)
        ttk.Combobox(num_frame, textvariable=self.digits_var, state="readonly", values=[1, 2, 3, 4, 5], width=3).pack(side=tk.LEFT)
        
        # 后缀
        self.suffix_var = tk.StringVar(value="")
        ttk.Label(rule_frame, text="后缀:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(rule_frame, textvariable=self.suffix_var).grid(row=2, column=1, padx=5, pady=5, sticky=tk.EW)
        
        # 替换选项
        replace_frame = ttk.LabelFrame(right_frame, text="替换选项")
        replace_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Checkbutton(replace_frame, text="替换空格为下划线").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Checkbutton(replace_frame, text="全部转为小写").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Checkbutton(replace_frame, text="全部转为大写").pack(anchor=tk.W, padx=5, pady=2)
        
        # 预览和应用按钮
        buttons_frame = ttk.Frame(right_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(buttons_frame, text="预览", command=self._preview_rename).pack(side=tk.LEFT, padx=2, pady=20, expand=True)
        ttk.Button(buttons_frame, text="应用重命名", command=self._apply_rename).pack(side=tk.RIGHT, padx=2, pady=20, expand=True)

    def _create_classify_tab(self):
        """创建分类标签页"""
        # 创建标签页容器
        classify_tab = ttk.Frame(self.notebook)
        self.notebook.add(classify_tab, text="分类")
        
        # 创建左侧源文件区域
        left_frame = ttk.LabelFrame(classify_tab, text="源文件")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 添加源文件列表
        src_list_frame = ttk.Frame(left_frame)
        src_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 滚动条
        src_scrollbar_y = ttk.Scrollbar(src_list_frame)
        src_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        src_scrollbar_x = ttk.Scrollbar(src_list_frame, orient=tk.HORIZONTAL)
        src_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 文件列表
        self.classify_file_list = ttk.Treeview(src_list_frame, yscrollcommand=src_scrollbar_y.set, xscrollcommand=src_scrollbar_x.set)
        self.classify_file_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 设置列
        self.classify_file_list['columns'] = ('name', 'size', 'modified')
        self.classify_file_list.column('#0', width=0, stretch=tk.NO)
        self.classify_file_list.column('name', anchor=tk.W, width=300)
        self.classify_file_list.column('size', anchor=tk.E, width=80)
        self.classify_file_list.column('modified', anchor=tk.W, width=150)
        
        # 设置标题
        self.classify_file_list.heading('#0', text='', anchor=tk.W)
        self.classify_file_list.heading('name', text='文件名', anchor=tk.W)
        self.classify_file_list.heading('size', text='大小', anchor=tk.E)
        self.classify_file_list.heading('modified', text='修改日期', anchor=tk.W)
        
        # 绑定滚动条
        src_scrollbar_y.config(command=self.classify_file_list.yview)
        src_scrollbar_x.config(command=self.classify_file_list.xview)
        
        # 源文件控制按钮
        src_buttons_frame = ttk.Frame(left_frame)
        src_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(src_buttons_frame, text="添加文件", command=self._add_classify_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(src_buttons_frame, text="添加文件夹", command=self._add_classify_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(src_buttons_frame, text="清空", command=self._clear_classify_files).pack(side=tk.RIGHT, padx=2)
        
        # 创建右侧设置区域
        right_frame = ttk.LabelFrame(classify_tab, text="分类设置")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        # 分类方式
        method_frame = ttk.LabelFrame(right_frame, text="分类方式")
        method_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.classify_method = tk.StringVar(value="format")
        
        ttk.Radiobutton(method_frame, text="按格式分类", variable=self.classify_method, value="format").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Radiobutton(method_frame, text="按日期分类", variable=self.classify_method, value="date").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Radiobutton(method_frame, text="按分辨率分类", variable=self.classify_method, value="resolution").pack(anchor=tk.W, padx=5, pady=2)
        
        # 日期格式设置（仅在按日期分类时可见）
        date_frame = ttk.LabelFrame(method_frame, text="日期格式")
        date_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.date_format = tk.StringVar(value="%Y-%m-%d")
        ttk.Combobox(date_frame, textvariable=self.date_format, state="readonly", 
                     values=["%Y-%m-%d", "%Y-%m", "%Y", "%Y年%m月%d日"]).pack(fill=tk.X, padx=5, pady=5)
        
        # 输出目录设置
        output_frame = ttk.LabelFrame(right_frame, text="输出目录")
        output_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.classify_output_dir_var = tk.StringVar(value="")
        ttk.Entry(output_frame, textvariable=self.classify_output_dir_var).pack(fill=tk.X, side=tk.LEFT, padx=5, pady=5, expand=True)
        ttk.Button(output_frame, text="浏览", command=self._browse_classify_output_dir).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 其他选项
        options_frame = ttk.LabelFrame(right_frame, text="其他选项")
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.move_files = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="移动文件（不保留原文件）", variable=self.move_files).pack(anchor=tk.W, padx=5, pady=2)
        
        # 开始分类按钮
        ttk.Button(right_frame, text="开始分类", command=self._start_classify, width=20).pack(fill=tk.X, padx=5, pady=20)

    def _create_dedupe_tab(self):
        """创建去重标签页"""
        # 创建标签页容器
        dedupe_tab = ttk.Frame(self.notebook)
        self.notebook.add(dedupe_tab, text="去重")
        
        # 创建左侧源文件区域
        left_frame = ttk.LabelFrame(dedupe_tab, text="源文件")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 添加源文件列表
        src_list_frame = ttk.Frame(left_frame)
        src_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 滚动条
        src_scrollbar_y = ttk.Scrollbar(src_list_frame)
        src_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        src_scrollbar_x = ttk.Scrollbar(src_list_frame, orient=tk.HORIZONTAL)
        src_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 文件列表
        self.dedupe_file_list = ttk.Treeview(src_list_frame, yscrollcommand=src_scrollbar_y.set, xscrollcommand=src_scrollbar_x.set)
        self.dedupe_file_list.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 设置列
        self.dedupe_file_list['columns'] = ('name', 'size', 'modified')
        self.dedupe_file_list.column('#0', width=0, stretch=tk.NO)
        self.dedupe_file_list.column('name', anchor=tk.W, width=300)
        self.dedupe_file_list.column('size', anchor=tk.E, width=80)
        self.dedupe_file_list.column('modified', anchor=tk.W, width=150)
        
        # 设置标题
        self.dedupe_file_list.heading('#0', text='', anchor=tk.W)
        self.dedupe_file_list.heading('name', text='文件名', anchor=tk.W)
        self.dedupe_file_list.heading('size', text='大小', anchor=tk.E)
        self.dedupe_file_list.heading('modified', text='修改日期', anchor=tk.W)
        
        # 绑定滚动条
        src_scrollbar_y.config(command=self.dedupe_file_list.yview)
        src_scrollbar_x.config(command=self.dedupe_file_list.xview)
        
        # 源文件控制按钮
        src_buttons_frame = ttk.Frame(left_frame)
        src_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(src_buttons_frame, text="添加文件", command=self._add_dedupe_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(src_buttons_frame, text="添加文件夹", command=self._add_dedupe_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(src_buttons_frame, text="清空", command=self._clear_dedupe_files).pack(side=tk.RIGHT, padx=2)
        
        # 创建右侧设置区域
        right_frame = ttk.LabelFrame(dedupe_tab, text="去重设置")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        # 哈希算法选择
        hash_frame = ttk.LabelFrame(right_frame, text="哈希算法")
        hash_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.hash_method = tk.StringVar(value="ahash")
        
        ttk.Radiobutton(hash_frame, text="平均哈希 (aHash)", variable=self.hash_method, value="ahash").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Radiobutton(hash_frame, text="差异哈希 (dHash)", variable=self.hash_method, value="dhash").pack(anchor=tk.W, padx=5, pady=2)
        
        # 保留策略
        keep_frame = ttk.LabelFrame(right_frame, text="保留策略")
        keep_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.keep_strategy = tk.StringVar(value="first")
        
        keep_options = {
            'first': '首个文件',
            'largest': '最大分辨率',
            'largest-file': '最大文件',
            'newest': '最新文件',
            'oldest': '最旧文件'
        }
        
        for value, text in keep_options.items():
            ttk.Radiobutton(keep_frame, text=text, variable=self.keep_strategy, value=value).pack(anchor=tk.W, padx=5, pady=2)
        
        # 重复文件处理
        handle_frame = ttk.LabelFrame(right_frame, text="重复文件处理")
        handle_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.dedupe_action = tk.StringVar(value="trash")
        
        ttk.Radiobutton(handle_frame, text="移动到回收站", variable=self.dedupe_action, value="trash").pack(anchor=tk.W, padx=5, pady=2)
        ttk.Radiobutton(handle_frame, text="删除文件", variable=self.dedupe_action, value="delete").pack(anchor=tk.W, padx=5, pady=2)
        
        # 开始去重按钮
        ttk.Button(right_frame, text="开始去重", command=self._start_dedupe, width=20).pack(fill=tk.X, padx=5, pady=20)
    
    def _create_status_and_log(self):
        """创建状态条和日志显示区域"""
        # 创建状态栏框架
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 状态文本
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 进度条
        self.progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(status_frame, orient=tk.HORIZONTAL, length=200, mode='determinate', variable=self.progress_var)
        progress_bar.pack(side=tk.RIGHT, padx=5)
        
        # 创建日志过滤框架
        filter_frame = ttk.LabelFrame(self.root, text="日志过滤")
        filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 过滤选项
        ttk.Label(filter_frame, text="操作类型:").pack(side=tk.LEFT, padx=5)
        self.log_filter_stage = tk.StringVar(value="全部")
        stage_filter = ttk.Combobox(filter_frame, textvariable=self.log_filter_stage, state="readonly", 
                                    values=["全部", "转换", "重命名", "分类", "去重", "删除", "移动", "保留", "信息"])
        stage_filter.pack(side=tk.LEFT, padx=5)
        stage_filter.bind("<<ComboboxSelected>>", lambda _: self._on_change_log_filter())
        
        ttk.Label(filter_frame, text="关键词:").pack(side=tk.LEFT, padx=5)
        self.log_filter_kw = tk.StringVar(value="")
        kw_entry = ttk.Entry(filter_frame, textvariable=self.log_filter_kw, width=20)
        kw_entry.pack(side=tk.LEFT, padx=5)
        kw_entry.bind("<KeyRelease>", lambda _: self._on_change_log_filter())
        
        self.log_filter_fail = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_frame, text="仅显示失败项", variable=self.log_filter_fail, 
                        command=self._on_change_log_filter).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="重置过滤", command=self._reset_log_filter).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="清空日志", command=self._clear_log).pack(side=tk.LEFT, padx=5)
        
        # 创建日志表格框架
        log_frame = ttk.LabelFrame(self.root, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 日志表格滚动条
        log_scrollbar_y = ttk.Scrollbar(log_frame)
        log_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        log_scrollbar_x = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL)
        log_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 日志表格
        self.log = ttk.Treeview(log_frame, yscrollcommand=log_scrollbar_y.set, xscrollcommand=log_scrollbar_x.set)
        self.log.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # 设置日志表格列
        self.log['columns'] = ('stage', 'src', 'dst', 'info')
        self.log.column('#0', width=0, stretch=tk.NO)
        self.log.column('stage', anchor=tk.CENTER, width=80)
        self.log.column('src', anchor=tk.W, width=300)
        self.log.column('dst', anchor=tk.W, width=300)
        self.log.column('info', anchor=tk.W, width=400)
        
        # 设置日志表格标题
        self.log.heading('#0', text='', anchor=tk.W)
        self.log.heading('stage', text='操作', anchor=tk.CENTER)
        self.log.heading('src', text='源文件', anchor=tk.W)
        self.log.heading('dst', text='目标文件', anchor=tk.W)
        self.log.heading('info', text='信息', anchor=tk.W)
        
        # 绑定滚动条
        log_scrollbar_y.config(command=self.log.yview)
        log_scrollbar_x.config(command=self.log.xview)
        
        # 绑定日志事件
        self.log.bind('<Double-1>', self._on_log_double_click)
        self.log.bind('<Motion>', self._on_log_motion)
        self.log.bind('<<TreeviewSelect>>', self._on_select_row)
        
        # 存储原始日志数据
        self._raw_logs = []
    
    def _add_files(self):
        """添加文件按钮回调"""
        try:
            files = filedialog.askopenfilenames(
                title="选择图片文件",
                filetypes=[("图片文件", "*.jpg *.jpeg *.png *.webp *.gif *.bmp *.tiff *.ico"), ("所有文件", "*.*")]
            )
            if files:
                # 清空现有文件列表
                for item in self.src_file_list.get_children():
                    self.src_file_list.delete(item)
                
                # 添加新文件到列表
                for file_path in files:
                    try:
                        stat_info = os.stat(file_path)
                        size = _fmt_size(stat_info.st_size)
                        modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat_info.st_mtime))
                        self.src_file_list.insert('', 'end', values=(os.path.basename(file_path), size, modified))
                    except Exception as e:
                        self.q.put(f"ERROR 无法添加文件 {os.path.basename(file_path)}: {e}")
                
                # 更新状态
                self.status_var.set(f"已添加 {len(files)} 个文件")
        except Exception as e:
            self.q.put(f"ERROR 添加文件时出错: {e}")

    def _add_folder(self):
        """添加文件夹按钮回调"""
        try:
            folder = filedialog.askdirectory(title="选择文件夹")
            if folder:
                # 清空现有文件列表
                for item in self.src_file_list.get_children():
                    self.src_file_list.delete(item)
                
                # 添加文件夹中的图片文件
                file_count = 0
                for root, _, files in os.walk(folder):
                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in SUPPORTED_EXT:
                            file_path = os.path.join(root, file)
                            try:
                                stat_info = os.stat(file_path)
                                size = _fmt_size(stat_info.st_size)
                                modified = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat_info.st_mtime))
                                self.src_file_list.insert('', 'end', values=(os.path.basename(file_path), size, modified))
                                file_count += 1
                            except Exception as e:
                                self.q.put(f"ERROR 无法添加文件 {os.path.basename(file_path)}: {e}")
                
                # 更新状态
                self.status_var.set(f"已添加 {file_count} 个文件")
        except Exception as e:
            self.q.put(f"ERROR 添加文件夹时出错: {e}")

    def _clear_files(self):
        """清空文件列表按钮回调"""
        for item in self.src_file_list.get_children():
            self.src_file_list.delete(item)
        self.status_var.set("文件列表已清空")

    def _browse_output_dir(self):
        """浏览输出目录按钮回调"""
        try:
            dir_path = filedialog.askdirectory(title="选择输出目录")
            if dir_path:
                self.output_dir_var.set(dir_path)
        except Exception as e:
            self.q.put(f"ERROR 选择输出目录时出错: {e}")

    def _start_convert(self):
        """开始转换按钮回调"""
        try:
            # 检查是否有文件要转换
            if not self.src_file_list.get_children():
                messagebox.showwarning("警告", "请先添加要转换的文件")
                return
            
            # 检查输出目录
            output_dir = self.output_dir_var.get().strip()
            if not output_dir:
                messagebox.showwarning("警告", "请先选择输出目录")
                return
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 更新状态
            self.status_var.set("开始转换...")
            self.progress_var.set(0)
            
            # 启动转换线程
            threading.Thread(target=self._convert_files, daemon=True).start()
        except Exception as e:
            self.q.put(f"ERROR 开始转换时出错: {e}")

    def _convert_files(self):
        """在后台线程中执行文件转换"""
        try:
            # 获取设置
            output_format = self.output_format.get()
            quality = self.quality_var.get()
            webp_compression = self.webp_compression.get()
            output_dir = self.output_dir_var.get().strip()
            
            # 模拟转换过程
            total_files = len(self.src_file_list.get_children())
            for i in range(total_files):
                # 模拟进度更新
                progress = (i + 1) / total_files * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
                
                # 获取文件名
                item = self.src_file_list.get_children()[i]
                filename = self.src_file_list.item(item, 'values')[0]
                
                # 模拟转换
                time.sleep(0.1)  # 模拟处理时间
                
                # 记录日志
                self.q.put(f"LOG\tCONVERT\t{filename}\t{os.path.splitext(filename)[0]}.{output_format}\t转换成功")
            
            # 完成转换
            self.root.after(0, lambda: self.status_var.set(f"转换完成，共处理 {total_files} 个文件"))
        except Exception as e:
            self.q.put(f"ERROR 转换过程中出错: {e}")
            self.root.after(0, lambda: self.status_var.set(f"转换失败: {e}"))

    # 批量重命名相关方法
    def _add_rename_files(self):
        """添加重命名文件按钮回调"""
        self._add_files()

    def _add_rename_folder(self):
        """添加重命名文件夹按钮回调"""
        self._add_folder()

    def _clear_rename_files(self):
        """清空重命名文件列表按钮回调"""
        for item in self.rename_file_list.get_children():
            self.rename_file_list.delete(item)
        self.status_var.set("重命名文件列表已清空")

    def _preview_rename(self):
        """预览重命名按钮回调"""
        self.status_var.set("预览重命名...")

    def _apply_rename(self):
        """应用重命名按钮回调"""
        self.status_var.set("应用重命名...")

    # 分类相关方法
    def _add_classify_files(self):
        """添加分类文件按钮回调"""
        self._add_files()

    def _add_classify_folder(self):
        """添加分类文件夹按钮回调"""
        self._add_folder()

    def _clear_classify_files(self):
        """清空分类文件列表按钮回调"""
        for item in self.classify_file_list.get_children():
            self.classify_file_list.delete(item)
        self.status_var.set("分类文件列表已清空")

    def _browse_classify_output_dir(self):
        """浏览分类输出目录按钮回调"""
        self._browse_output_dir()

    def _start_classify(self):
        """开始分类按钮回调"""
        self.status_var.set("开始分类...")

    # 去重相关方法
    def _add_dedupe_files(self):
        """添加去重文件按钮回调"""
        self._add_files()

    def _add_dedupe_folder(self):
        """添加去重文件夹按钮回调"""
        self._add_folder()

    def _clear_dedupe_files(self):
        """清空去重文件列表按钮回调"""
        for item in self.dedupe_file_list.get_children():
            self.dedupe_file_list.delete(item)
        self.status_var.set("去重文件列表已清空")

    def _start_dedupe(self):
        """开始去重按钮回调"""
        self.status_var.set("开始去重...")

    def _init_preview_thread(self):
        """初始化预览线程和预览UI元素"""
        # 创建预览框架
        preview_frame = ttk.LabelFrame(self.root, text="图片预览")
        preview_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)
        
        # 创建左右预览区域
        preview_left_frame = ttk.Frame(preview_frame)
        preview_left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        preview_right_frame = ttk.Frame(preview_frame)
        preview_right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧预览（原图）
        ttk.Label(preview_left_frame, text="原图").pack(anchor=tk.W, padx=5)
        
        self.preview_before_canvas = tk.Canvas(preview_left_frame, bg="#f0f0f0", highlightthickness=0)
        self.preview_before_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.preview_before_label = ttk.Label(self.preview_before_canvas, text="无预览", background="#f0f0f0")
        self.preview_before_label_window = self.preview_before_canvas.create_window(0, 0, anchor=tk.NW, window=self.preview_before_label)
        
        self.preview_before_info = ttk.Label(preview_left_frame, text="")
        self.preview_before_info.pack(anchor=tk.W, padx=5, pady=2)
        
        # 右侧预览（处理后）
        ttk.Label(preview_right_frame, text="处理后").pack(anchor=tk.W, padx=5)
        
        self.preview_after_canvas = tk.Canvas(preview_right_frame, bg="#f0f0f0", highlightthickness=0)
        self.preview_after_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.preview_after_label = ttk.Label(self.preview_after_canvas, text="无预览", background="#f0f0f0")
        self.preview_after_label_window = self.preview_after_canvas.create_window(0, 0, anchor=tk.NW, window=self.preview_after_label)
        
        self.preview_after_info = ttk.Label(preview_right_frame, text="")
        self.preview_after_info.pack(anchor=tk.W, padx=5, pady=2)
        
        # 绑定画布大小变化事件
        self.preview_before_canvas.bind("<Configure>", lambda e: self._on_preview_canvas_configure(e, 'before'))
        self.preview_after_canvas.bind("<Configure>", lambda e: self._on_preview_canvas_configure(e, 'after'))
        
        # 初始化预览线程
        self.preview_thread = None
        self.stop_flag = threading.Event()

    def _on_preview_canvas_configure(self, event, canvas_type):
        """处理预览画布大小变化事件"""
        if canvas_type == 'before':
            self.preview_before_canvas.itemconfig(self.preview_before_label_window, width=event.width, height=event.height)
        else:
            self.preview_after_canvas.itemconfig(self.preview_after_label_window, width=event.width, height=event.height)

    def _on_configure(self, event):
        """窗口大小变化时的回调函数"""
        # 如果启用了自动调整窗口大小功能
        if self.auto_resize_window.get():
            current_time = time.time()
            # 避免过于频繁地调整窗口大小
            if self._last_auto_size is None or current_time - self._last_auto_size > 1.0:
                self._last_auto_size = current_time
                # 调整窗口大小以适应内容
                self._maybe_resize_window()
    
    def _drain(self):
        """从队列中读取并处理日志消息"""
        try:
            for _ in range(20):  # 每次处理最多20条消息，避免UI卡顿
                line = self.q.get_nowait()
                if line.startswith('LOG'):
                    # 处理日志消息
                    _, stage, src, dst, info = line.split('\t', 4)
                    src_basename = os.path.basename(src)
                    dst_basename = os.path.basename(dst)
                    stage_disp = STAGE_MAP_DISPLAY.get(stage, stage)
                    vals = (stage_disp, src_basename, dst_basename, info)
                    # 为日志行添加标签，用于后续的预览功能
                    row_tags = (src, dst, stage)
                    
                    # 检查日志过滤条件
                    if self._log_row_visible(stage, info, vals):
                        self.log.insert('', 'end', values=vals, tags=row_tags)
                        # 自动滚动到最新日志
                        self.log.yview_moveto(1.0)
                    
                    # 更新统计信息
                    self._update_stats_from_log(stage, src, dst, info)
                elif line.startswith('STATUS'):
                    # 更新状态消息
                    _, msg = line.split('\t', 1) if '\t' in line else ('', line[6:])
                    self.status_var.set(msg)
                elif line.startswith('STATS'):
                    # 处理统计信息
                    pass
                elif line.startswith('HASH'):
                    # 处理哈希计算信息
                    pass
                elif line.startswith('PROG'):
                    # 处理进度信息
                    try:
                        _, percent = line.split('\t', 1)
                        self.progress_var.set(float(percent))
                    except Exception:
                        pass
                elif line.startswith('INFO'):
                    # 处理一般信息
                    _, msg = line.split('\t', 1) if '\t' in line else ('', line[4:])
                    self.status_var.set(msg)
                elif line.startswith('ERROR'):
                    # 处理错误信息
                    _, msg = line.split('\t', 1) if '\t' in line else ('', line[5:])
                    self.status_var.set(f"错误: {msg}")
                
                # 写入缓存日志
                self._append_cache_program_log(line)
                
                # 标记任务完成
                self.q.task_done()
        except queue.Empty:
            pass
        finally:
            # 150ms后再次检查队列
            self.root.after(150, self._drain)
    
    def _log_row_visible(self, stage:str, info:str, vals:tuple)->bool:
        """检查日志行是否应该显示，根据当前的过滤条件"""
        stage_map={'DEDUP':'去重','CONVERT':'转换','RENAME':'重命名','CLASSIFY':'分类'}
        stage_ch=stage_map.get(stage,'信息')
        want=self.log_filter_stage.get() if hasattr(self,'log_filter_stage') else '全部'
        if want!='全部':
            if want=='删除' and ('删' in info or '删除' in info): pass
            elif want=='移动' and '移动' in info: pass
            elif want=='保留' and '保留' in info: pass
            elif want==stage_ch: pass
            elif want=='信息' and stage_ch=='信息': pass
            else: return False
        if hasattr(self,'log_filter_fail') and self.log_filter_fail.get():
            if '失败' not in info and '错' not in info: return False
        if hasattr(self,'log_filter_kw'):
            kw=self.log_filter_kw.get().strip()
            if kw:
                joined=' '.join(str(x) for x in vals)
                if kw.lower() not in joined.lower(): return False
        return True
    
    def _update_stats_from_log(self, stage, src, dst, info):
        """从日志消息中更新统计信息"""
        try:
            # 统计各种操作
            if stage == 'CONVERT':
                if '成功' in info or ('转换' in info and '失败' not in info):
                    self.stats['converted_files'] += 1
                elif '失败' in info:
                    self.stats['error_files'] += 1
            elif stage == 'RENAME':
                if '成功' in info or ('重命名' in info and '失败' not in info):
                    self.stats['renamed_files'] += 1
                elif '失败' in info:
                    self.stats['error_files'] += 1
            elif stage == 'CLASSIFY':
                if '成功' in info or ('分类' in info and '失败' not in info):
                    self.stats['classified_files'] += 1
                elif '失败' in info:
                    self.stats['error_files'] += 1
            elif stage == 'DEDUP':
                if '删除' in info or '移动' in info:
                    self.stats['dedupe_removed'] += 1
                elif '保留' in info:
                    self.stats['dedupe_kept'] += 1
            
            # 统计跳过的文件
            if '跳过' in info:
                self.stats['skipped_files'] += 1
            
        except Exception:
            pass
    
    def _generate_stats_report(self):
        """生成并记录详细的统计报告"""
        if not self.stats['start_time'] or not self.stats['end_time']:
            return
        
        duration = self.stats['end_time'] - self.stats['start_time']
        
        # 计算文件大小变化
        size_change = self.stats['total_size_after'] - self.stats['total_size_before']
        size_change_mb = size_change / (1024 * 1024)
        
        # 构建统计报告
        report_lines = [
            "",
            "=" * 60,
            "处理统计报告",
            "=" * 60,
            f"执行时间: {duration:.2f} 秒",
            f"执行模式: {'正式处理' if self.write_to_output else '预览模式'}",
            "",
            "文件统计:",
            f"  输入文件总数: {self.stats['input_files']}",
            f"  输出文件总数: {self.stats['output_files']}",
            f"  跳过文件数: {self.stats['skipped_files']}",
            f"  错误文件数: {self.stats['error_files']}",
            "",
            "操作统计:",
        ]
        
        # 添加操作统计
        if self.stats['converted_files'] > 0:
            report_lines.append(f"  格式转换: {self.stats['converted_files']} 个文件")
        if self.stats['renamed_files'] > 0:
            report_lines.append(f"  文件重命名: {self.stats['renamed_files']} 个文件")
        if self.stats['classified_files'] > 0:
            report_lines.append(f"  文件分类: {self.stats['classified_files']} 个文件")
        if self.stats['dedupe_removed'] > 0 or self.stats['dedupe_kept'] > 0:
            report_lines.extend([
                f"  去重处理:",
                f"    保留文件: {self.stats['dedupe_kept']} 个",
                f"    删除重复: {self.stats['dedupe_removed']} 个",
            ])
        
        if not any(self.stats[key] > 0 for key in ['converted_files', 'renamed_files', 'classified_files', 'dedupe_removed']):
            report_lines.append("  无特殊操作")
        
        # 添加输出目录处理信息
        if self.write_to_output:
            if hasattr(self, 'clear_output_var') and self.clear_output_var.get():
                report_lines.append("  输出目录: 已清空")
            else:
                report_lines.append("  输出目录: 与现有文件混合")
        
        # 文件格式分布
        if self.stats['file_formats']:
            report_lines.extend([
                "",
                "文件格式分布:",
            ])
            for fmt, count in sorted(self.stats['file_formats'].items()):
                report_lines.append(f"  {fmt.upper()}: {count} 个文件")
        
        # 大小统计
        if self.stats['total_size_before'] > 0:
            report_lines.extend([
                "",
                "文件大小统计:",
                f"  处理前总大小: {self.stats['total_size_before'] / (1024*1024):.2f} MB",
                f"  处理后总大小: {self.stats['total_size_after'] / (1024*1024):.2f} MB",
                f"  大小变化: {size_change_mb:+.2f} MB ({size_change_mb/max(self.stats['total_size_before']/(1024*1024), 0.01)*100:+.1f}%)",
            ])
        
        # 错误和警告统计
        if self.stats['warnings_count'] > 0 or self.stats['errors_count'] > 0:
            report_lines.extend([
                "",
                "问题统计:",
                f"  警告数量: {self.stats['warnings_count']}",
                f"  错误数量: {self.stats['errors_count']}",
            ])
        
        # 执行的操作列表
        if self.stats['operations']:
            report_lines.extend([
                "",
                "执行的操作:",
            ])
            for op in self.stats['operations']:
                report_lines.append(f"  ✓ {op}")
        
        report_lines.extend([
            "",
            "=" * 60,
            ""
        ])
        
        # 记录到日志
        for line in report_lines:
            self.q.put(f'STATS {line}')
        
        # 同时打印到控制台
        print("\n".join(report_lines))
    
    def _collect_output_stats(self, output_dir):
        """收集输出目录的统计信息"""
        try:
            if not os.path.exists(output_dir):
                return
            
            output_count = 0
            total_size = 0
            
            for root, dirs, files in os.walk(output_dir):
                # 跳过缓存目录
                if '.preview_cache' in root:
                    continue
                
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if os.path.exists(file_path):
                            output_count += 1
                            total_size += os.path.getsize(file_path)
                    except Exception:
                        pass
            
            self.stats['output_files'] = output_count
            self.stats['total_size_after'] = total_size
            
        except Exception:
            pass
    
    def _clear_cache(self):
        """清除缓存目录"""
        # 这里应该实现清除缓存的逻辑
        pass
    
    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        # 这里应该实现确保缓存目录存在的逻辑
        pass
    
    def _simulate_delete(self, path:str):
        """预览模式: 将“删除”文件复制到缓存模拟回收站目录 (_trash)。"""
        try:
            self._ensure_cache_dir()
            if not self.cache_trash_dir:
                return
            os.makedirs(self.cache_trash_dir, exist_ok=True)
            base=os.path.basename(path)
            target=os.path.join(self.cache_trash_dir, base)
            # 避免同名覆盖
            if os.path.exists(target):
                base_no,ext=os.path.splitext(base); i=1
                while os.path.exists(target):
                    target=os.path.join(self.cache_trash_dir, f"{base_no}_{i}{ext}"); i+=1
            shutil.move(path, target)
        except Exception:
            pass
    
    def _append_cache_program_log(self, line:str):
        """将程序级日志(队列中的所有消息)写入缓存 log.txt, 带时间戳。用于排查内部问题。"""
        if not line:
            return
        try:
            self._ensure_cache_dir()
            if not self.cache_dir:
                return
            log_path=os.path.join(self.cache_dir,'program.log')
            stamp=time.strftime('%Y-%m-%d %H:%M:%S')
            with open(log_path,'a',encoding='utf-8',errors='ignore') as fw:
                fw.write(f'[{stamp}] {line}\n')
        except Exception:
            pass
    
    def _maybe_resize_window(self):
        """根据预览图片大小自动调整窗口高度"""
        if not getattr(self,'auto_resize_window',None): return
        if not self.auto_resize_window.get(): return
        self.root.update_idletasks()
        photo_b=getattr(self.preview_before_label,'_img_ref',None)
        photo_a=getattr(self.preview_after_label,'_img_ref',None)
        bw = photo_b.width() if photo_b else 0
        bh = photo_b.height() if photo_b else 0
        aw = photo_a.width() if photo_a else 0
        ah = photo_a.height() if photo_a else 0
        
        # 检查是否为文本模式（显示错误信息）
        text_mode = getattr(self.preview_after_label, '_text_mode', False)
        if (bw==0 and aw==0) and not text_mode:
            return
        
        # 计算内容高度
        if text_mode:
            # 文本模式：估算文本高度
            text_content = self.preview_after_label.cget('text')
            if text_content:
                # 根据文本行数和换行宽度估算高度
                lines = text_content.count('\n') + 1
                # 考虑自动换行的影响
                char_per_line = 50  # 大致每行字符数
                total_chars = len(text_content)
                wrapped_lines = max(lines, total_chars // char_per_line + 1)
                estimated_height = min(wrapped_lines * 18, 300)  # 每行约18像素，最大300像素
                img_h = max(estimated_height, 150)  # 最小150像素高度
            else:
                img_h = 150  # 默认高度
        else:
            # 图片模式：使用图片高度
            img_h=max(bh,ah)
        
        # 只调整高度: 计算需要的总高度
        root_y0=self.root.winfo_rooty()
        preview_top = self.preview_before_label.winfo_rooty()-root_y0
        extra_h=130  # info 行 + 边距，增加高度以适应多行文件路径显示
        desired_h=preview_top+img_h+extra_h
        sh=self.root.winfo_screenheight(); margin=50
        desired_h=min(desired_h, sh-margin)
        
        # 确保禁用宽度自动调整：始终保持当前宽度
        cur_w=self.root.winfo_width()  # 获取当前宽度
        min_w = getattr(self, '_min_window_width', 1024)  # 最小宽度1024像素
        final_w = max(cur_w, min_w)  # 确保不会变得太小，但不自动增大
        
        last=self._last_auto_size
        # 只比较高度，宽度保持不变
        if not (last and abs(last[1]-desired_h)<10):
            self.root.geometry(f"{int(final_w)}x{int(desired_h)}")
            self._last_auto_size=(final_w,desired_h)
    
    def _show_error_in_preview(self, src_basename, error_info):
        """在预览区域显示错误信息"""
        # 清除图片引用
        self.preview_before_label._img_ref = None
        self.preview_after_label._img_ref = None
        
        # 在左侧显示源文件名
        self.preview_before_label.configure(
            text=f"源文件: {src_basename}",
            image='',
            wraplength=400,  # 设置文本换行宽度，匹配新的窗口大小
            justify='left'   # 左对齐
        )
        self.preview_before_info.set('')
        
        # 在右侧显示错误详情
        # 处理长错误信息，适当换行
        error_text = f"错误详情:\n{error_info}"
        if len(error_text) > 500:
            # 对于很长的错误信息，进行适当截断并保留重要部分
            lines = error_text.split('\n')
            if len(lines) > 10:
                error_text = '\n'.join(lines[:5] + ['...'] + lines[-3:])
            elif len(error_text) > 500:
                error_text = error_text[:500] + '...'
        
        self.preview_after_label.configure(
            text=error_text,
            image='',
            wraplength=400,  # 设置文本换行宽度，匹配新的窗口大小
            justify='left',  # 左对齐
            anchor='nw'      # 内容对齐到左上角
        )
        self.preview_after_info.set('处理失败')
        
        # 标记为文本模式，并调用窗口调整
        self.preview_after_label._text_mode = True
        self._maybe_resize_window()
    
    def _handle_failed_file(self, src_path, reason, should_remove_src=False):
        """处理失败的文件：如果设置了删源，将失败文件移动到失败文件夹"""
        if not should_remove_src:
            return  # 不需要删源就不处理
        
        try:
            # 确定失败文件夹路径
            if not getattr(self, 'write_to_output', True):
                # 预览模式：放到缓存目录下的failed文件夹
                self._ensure_cache_dir()
                failed_dir = os.path.join(self.cache_dir, 'failed')
            else:
                # 实际模式：放到输出目录下的failed文件夹
                out_dir = self.out_var.get().strip() or self.in_var.get().strip()
                failed_dir = os.path.join(out_dir, 'failed')
            
            os.makedirs(failed_dir, exist_ok=True)
            
            # 避免文件名冲突
            basename = os.path.basename(src_path)
            dst_path = os.path.join(failed_dir, basename)
            if os.path.exists(dst_path):
                base_no, ext = os.path.splitext(basename)
                i = 1
                while os.path.exists(dst_path):
                    dst_path = os.path.join(failed_dir, f"{base_no}_{i}{ext}")
                    i += 1
            
            if not getattr(self, 'write_to_output', True):
                # 预览模式：复制到失败文件夹
                shutil.copy2(src_path, dst_path)
                # 同时模拟删除原文件
                self._simulate_delete(src_path)
            else:
                # 实际模式：移动到失败文件夹
                shutil.move(src_path, dst_path)
            
            return dst_path
        except Exception as e:
            # 如果移动失败文件也失败了，至少记录一下
            print(f"[ERROR] Failed to handle failed file {src_path}: {e}")
            return None
    
    def _capture_log_height(self):
        """捕获日志区域的高度并固定它"""
        try:
            if hasattr(self,'upper_frame') and self._log_fixed_height is None:
                self.root.update_idletasks()
                h=self.upper_frame.winfo_height()
                if h>60:
                    self._log_fixed_height=h
                    if hasattr(self,'paned'):
                        self.paned.paneconfigure(self.upper_frame,minsize=h)
        except Exception:
            pass
    
    def _set_current_as_default(self):
        """将当前的所有设置保存为全局默认值"""
        try:
            # 保存当前设置到一个配置文件中
            import json
            import os
            
            # 获取应用数据目录
            app_data_dir = os.path.join(os.path.expanduser("~"), ".aiipd")
            os.makedirs(app_data_dir, exist_ok=True)
            config_path = os.path.join(app_data_dir, "global_defaults.json")
            
            # 收集当前设置
            config = {
                # 重命名设置
                "rename": {
                    "pattern": self.pattern_var.get(),
                    "start": self.start_var.get(),
                    "step": self.step_var.get(),
                    "index_width": self.index_width_var.get(),
                    "overwrite": self.overwrite_var.get()
                },
                # 分类设置
                "classification": {
                    "shape_tolerance": self.shape_tolerance_var.get(),
                    "shape_square_name": self.shape_square_name.get(),
                    "shape_horizontal_name": self.shape_horizontal_name.get(),
                    "shape_vertical_name": self.shape_vertical_name.get(),
                    "ratio_tolerance": self.ratio_tol_var.get(),
                    "ratio_custom": self.ratio_custom_var.get(),
                    "ratio_snap": self.ratio_snap_var.get()
                },
                # 转换设置
                "convert": {
                    "format": self.fmt_var.get(),
                    "quality": self.quality_var.get()
                },
                # 去重设置
                "dedupe": {
                    "keep": self.keep_var.get(),
                    "action": self.dedup_action_var.get(),
                    "threshold": self.threshold_var.get()
                },
                # 全局设置
                "global": {
                    "workers": self.workers_var.get(),
                    "global_remove_src": self.global_remove_src.get()
                }
            }
            
            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # 显示成功消息
            self.status_var.set(f"成功保存全局默认设置到 {config_path}")
            self.q.put(f"INFO 全局设置已保存为默认值")
        except Exception as e:
            # 显示错误消息
            self.status_var.set(f"保存默认设置失败: {str(e)}")
            self.q.put(f"ERROR 保存默认设置失败: {str(e)}")
            
    def _reset_all_to_default(self):
        """重置所有设置为应用程序默认值"""
        try:
            # 重命名设置重置
            self.pattern_var.set('{name}_{index}.{fmt}')
            self.start_var.set(1)
            self.step_var.set(1)
            self.index_width_var.set(3)
            self.overwrite_var.set(_rev_map(OVERWRITE_MAP)['overwrite'])
            
            # 分类设置重置
            self.shape_tolerance_var.set(0.15)
            self.shape_square_name.set('zfx')
            self.shape_horizontal_name.set('hp')
            self.shape_vertical_name.set('sp')
            self.ratio_tol_var.set(0.15)
            self.ratio_custom_var.set('16:9,3:2,4:3,1:1,21:9')
            self.ratio_snap_var.set(False)
            
            # 转换设置重置
            self.fmt_var.set(_rev_map(FMT_MAP)['webp'])
            self.quality_var.set(100)
            
            # 去重设置重置
            self.keep_var.set(_rev_map(KEEP_MAP)['largest'])
            self.dedup_action_var.set(_rev_map(ACTION_MAP)['delete'])
            self.threshold_var.set(3)
            
            # 全局设置重置
            self.workers_var.set(16)
            self.global_remove_src.set(False)
            
            # 显示成功消息
            self.status_var.set("所有设置已重置为默认值")
            self.q.put("INFO 所有设置已重置为默认值")
        except Exception as e:
            # 显示错误消息
            self.status_var.set(f"重置设置失败: {str(e)}")
            self.q.put(f"ERROR 重置设置失败: {str(e)}")

    def _on_change_log_filter(self,*a):
        """日志过滤器更改时的回调函数"""
        if not hasattr(self,'_raw_logs'): return
        for iid in self.log.get_children(): self.log.delete(iid)
        for stage,src,dst,info,vals,tags in self._raw_logs:
            if self._log_row_visible(stage,info,vals):
                self.log.insert('', 'end', values=vals, tags=tags)

    def ico_square_mode_code(self):
        """获取ICO方形处理模式的内部代码"""
        return self.ico_square_mode.get() if hasattr(self,'ico_square_mode') else 'keep'

    def _reset_log_filter(self):
        """重置日志过滤器"""
        if hasattr(self,'log_filter_stage'): self.log_filter_stage.set('全部')
        if hasattr(self,'log_filter_kw'): self.log_filter_kw.set('')
        if hasattr(self,'log_filter_fail'): self.log_filter_fail.set(False)
        self._on_change_log_filter()

    def _clear_log(self):
        """清空日志记录"""
        # 显示确认对话框
        result = messagebox.askyesno(
            "确认清空", 
            "确定要清空所有日志记录吗？\n此操作不可撤销。",
            parent=self.root
        )
        
        if result:
            # 清空日志表格
            for iid in self.log.get_children():
                self.log.delete(iid)
            
            # 清空原始日志数据
            if hasattr(self, '_raw_logs'):
                self._raw_logs.clear()
            
            # 显示消息
            self.status_var.set("日志已清空")
            self.q.put("INFO 日志已清空")

    def _on_log_motion(self, event):
        """鼠标悬停在日志上时显示完整路径"""
        # 这里应该实现日志悬停显示完整路径的逻辑
        pass

    def _on_log_double_click(self, event):
        """双击日志记录时，自动将源文件名填入日志搜索框"""
        iid = self.log.identify_row(event.y)
        if not iid:
            return
        
        # 获取行数据
        values = self.log.item(iid, 'values')
        if not values or len(values) < 2:
            return
        
        # 获取源文件名（第二列）
        src_basename = values[1]  # 源文件列
        if not src_basename:
            return
        
        # 提取文件名（去除路径）
        filename = os.path.basename(src_basename)
        
        # 填入搜索框
        self.log_filter_kw.set(filename)

    def _on_out_dir_change(self, *args):
        """输出目录改变时清除缓存"""
        self._clear_cache()

    def _on_select_row(self, _=None):
        """选择日志行时的回调函数，用于预览图片"""
        sel=self.log.selection();
        if not sel: return
        values = self.log.item(sel[0],'values')
        if len(values) < 3: return
        stage_disp, src_basename, dst_basename, info = values[:4]
        tags = self.log.item(sel[0],'tags') or []  # (src_full, dst_full, stage_tag)
        src_full = tags[0] if len(tags)>=1 else ''
        dst_full_logged = tags[1] if len(tags)>=2 else ''
        
        # 检测失败项并显示错误信息
        if "失败" in info:
            self._show_error_in_preview(src_basename, info)
            return
        
        # 源与结果路径推断
        if not getattr(self, 'write_to_output', True):
            # 缓存中的结果
            dst_candidates=[os.path.join(self.cache_dir,dst_basename)]
            if not os.path.splitext(dst_basename)[1]: # 去重组行
                dst_candidates.insert(0, os.path.join(self.cache_dir, os.path.basename(src_full)))
        else:
            out_dir = self.out_var.get().strip() or self.in_var.get().strip()
            dst_candidates=[]
            if dst_full_logged and os.path.isfile(dst_full_logged): dst_candidates.append(dst_full_logged)
            dst_candidates.append(os.path.join(out_dir,dst_basename))
            if not os.path.splitext(dst_basename)[1]: dst_candidates.append(src_full)
        # 源候选
        src_candidates=[src_full]
        # 取存在的源与结果
        def first_exist(lst):
            for p in lst:
                if p and os.path.exists(p): return p
            return None
        src_path=first_exist(src_candidates)
        result_path=first_exist(dst_candidates)
        
        # 预览根基准: 真实执行=输出目录; 预览=cache_final_dir (若存在) 否则 cache_dir
        base_root = (self.cache_final_dir or self.cache_dir) if not getattr(self, 'write_to_output', True) else (self.out_var.get().strip() or self.in_var.get().strip())
        
        # 使用预览线程处理图片加载
        if hasattr(self.preview_thread, 'add_preview_task'):
            self.preview_thread.add_preview_task(src_path, result_path)

    def _tooltip_after(self, *args):
        """显示工具提示的延时处理"""
        pass

    def _show_tooltip(self, text, x, y):
        """显示工具提示"""
        pass

    def _hide_tooltip(self):
        """隐藏工具提示"""
        pass

    def _bind_tip(self, widget, text):
        """为控件绑定工具提示"""
        def enter(_e):
            if hasattr(self, '_tooltip_after'):
                try: self.root.after_cancel(self._tooltip_after)
                except Exception: pass
            # 使用更新后的_show_tooltip方法，它会自动处理长文本换行
            self._tooltip_after = self.root.after(450, lambda: self._show_tooltip(text, self.root.winfo_pointerx(), self.root.winfo_pointery()))
        def leave(_e):
            if hasattr(self, '_tooltip_after'):
                try: self.root.after_cancel(self._tooltip_after)
                except Exception: pass
                self._tooltip_after = None
            self._hide_tooltip()
        widget.bind('<Enter>', enter, add='+')
        widget.bind('<Leave>', leave, add='+')
        widget.bind('<ButtonPress>', leave, add='+')

# 启动函数
def launch():
    """
    启动图片工具应用程序
    
    Returns:
        int: 退出码（0表示成功，非0表示失败）
    """
    if tk is None or Image is None:
        print('缺少 Tkinter 或 Pillow')
        return 2
    root = tk.Tk()
    app = ImageToolApp(root)
    root.mainloop()
    return 0

if __name__ == '__main__':
    exit_code = launch()
    sys.exit(exit_code)