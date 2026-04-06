"""一条龙模式页面 - 流水线处理"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import threading
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from src.ui.theme import COLORS, FONTS, SPACING
from src.core.image_ops import (
    FMT_MAP, KEEP_MAP, ACTION_MAP, OVERWRITE_MAP,
    norm_ext, ahash, dhash, hamming, convert_one, is_animated_image
)
from src.core.file_ops import safe_delete


@dataclass
class ImgInfo:
    path: str
    size: int
    w: int
    h: int
    ah: int
    dh: int
    mtime: float
    
    @property
    def res(self):
        return self.w * self.h


class PipelinePage:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=COLORS['bg_main'])
        self.log_text = None
        self.step_frames = {}
        self.step_vars = {}
        
        self._init_vars()
        self._build()
    
    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
    
    def pack_forget(self):
        self.frame.pack_forget()
    
    def on_show(self):
        pass
    
    def on_log_entry(self, entry):
        if self.log_text:
            stage = entry.get('stage_disp', '')
            src = os.path.basename(entry.get('src', ''))
            dst = os.path.basename(entry.get('dst', ''))
            info = entry.get('info', '')
            
            color_map = {
                'DEDUP': COLORS['log_dedupe'],
                'CONVERT': COLORS['log_convert'],
                'RENAME': COLORS['log_rename'],
                'CLASSIFY': COLORS['log_classify'],
            }
            color = color_map.get(entry.get('stage'), '#FFFFFF')
            
            self.log_text.configure(state='normal')
            self.log_text.insert('end', f'[{stage}] {src} -> {dst} - {info}\n', 'entry')
            self.log_text.tag_configure('entry', background=color)
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
    
    def _init_vars(self):
        # 步骤开关
        self.step_vars = {
            'dedupe': tk.BooleanVar(value=False),
            'convert': tk.BooleanVar(value=False),
            'classify': tk.BooleanVar(value=False),
            'rename': tk.BooleanVar(value=False),
        }
        
        # 去重配置
        self.dedup_threshold = tk.IntVar(value=3)
        self.dedup_keep = tk.StringVar(value='最大分辨率')
        self.dedup_action = tk.StringVar(value='删除重复')
        self.dedup_move_dir = tk.StringVar()
        
        # 转换配置
        self.conv_fmt = tk.StringVar(value='WebP')
        self.conv_quality = tk.IntVar(value=100)
        self.conv_same = tk.BooleanVar(value=False)
        self.conv_png3 = tk.BooleanVar(value=False)
        self.conv_ico_sizes = {s: tk.BooleanVar(value=(s in (16, 32, 48, 64))) for s in (16, 32, 48, 64, 128, 256)}
        self.conv_ico_keep = tk.BooleanVar(value=False)
        self.conv_ico_square = tk.StringVar(value='fit')
        self.conv_ico_custom = tk.StringVar(value='')
        
        # 分类配置
        self.cls_ratio_enabled = tk.BooleanVar(value=False)
        self.cls_shape_enabled = tk.BooleanVar(value=False)
        self.cls_ratio_tol = tk.DoubleVar(value=0.15)
        self.cls_ratio_custom = tk.StringVar(value='16:9,3:2,4:3,1:1,21:9')
        self.cls_ratio_snap = tk.BooleanVar(value=False)
        self.cls_shape_tol = tk.DoubleVar(value=0.15)
        self.cls_shape_square = tk.StringVar(value='zfx')
        self.cls_shape_horizontal = tk.StringVar(value='hp')
        self.cls_shape_vertical = tk.StringVar(value='sp')
        
        # 重命名配置
        self.rn_pattern = tk.StringVar(value='{name}_{index}.{fmt}')
        self.rn_start = tk.IntVar(value=1)
        self.rn_step = tk.IntVar(value=1)
        self.rn_width = tk.IntVar(value=3)
        self.rn_overwrite = tk.StringVar(value='覆盖原有')
        
        # 通用
        self.workers = tk.IntVar(value=16)
        self.remove_src = tk.BooleanVar(value=False)
    
    def _build(self):
        canvas = tk.Canvas(self.frame, bg=COLORS['bg_main'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient='vertical', command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=COLORS['bg_main'])
        
        scrollable.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scrollable, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 标题
        tk.Label(scrollable, text='一条龙模式', font=('Microsoft YaHei UI', 18, 'bold'),
                fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(16, 8))
        
        tk.Label(scrollable, text='按顺序执行多个处理步骤，一次配置完成所有操作',
                font=('Microsoft YaHei UI', 10), fg=COLORS['text_secondary'],
                bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(0, 16))
        
        # 流程图指示
        flow_frame = tk.Frame(scrollable, bg=COLORS['bg_main'])
        flow_frame.pack(fill='x', padx=24, pady=(0, 16))
        
        steps_flow = ['① 去重', '② 转换', '③ 分类', '④ 重命名']
        for i, label in enumerate(steps_flow):
            bg = COLORS['primary_light'] if i % 2 == 0 else COLORS['bg_card']
            lbl = tk.Label(flow_frame, text=label, font=('Microsoft YaHei UI', 9, 'bold'),
                          fg=COLORS['primary'], bg=bg, padx=12, pady=4, relief='solid',
                          borderwidth=1, highlightbackground=COLORS['border'])
            lbl.pack(side='left', padx=2)
            if i < len(steps_flow) - 1:
                arrow = tk.Label(flow_frame, text='→', font=('Microsoft YaHei UI', 12),
                               fg=COLORS['text_secondary'], bg=COLORS['bg_main'])
                arrow.pack(side='left', padx=2)
        
        # 步骤1：去重
        self._build_dedupe_card(scrollable)
        
        # 步骤2：转换
        self._build_convert_card(scrollable)
        
        # 步骤3：分类
        self._build_classify_card(scrollable)
        
        # 步骤4：重命名
        self._build_rename_card(scrollable)
        
        # 通用设置
        common_card = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                              highlightbackground=COLORS['border'], borderwidth=1)
        common_card.pack(fill='x', padx=24, pady=(0, 16))
        
        tk.Label(common_card, text='通用设置', font=FONTS['subtitle'], fg=COLORS['text_primary'],
                bg=COLORS['bg_card']).pack(anchor='w', padx=20, pady=(12, 8))
        
        common_row = tk.Frame(common_card, bg=COLORS['bg_card'])
        common_row.pack(fill='x', padx=20, pady=8)
        
        tk.Label(common_row, text='线程数', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 6))
        ttk.Spinbox(common_row, from_=1, to=64, textvariable=self.workers, width=5).pack(side='left', padx=(0, 20))
        
        tk.Checkbutton(common_row, text='处理完成后删除源文件', variable=self.remove_src,
                      font=FONTS['body'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left')
        
        # 按钮
        btn_frame = tk.Frame(scrollable, bg=COLORS['bg_main'])
        btn_frame.pack(fill='x', padx=24, pady=(0, 16))
        
        self.btn_preview = tk.Button(btn_frame, text='预览', font=('Microsoft YaHei UI', 10),
                                     bg=COLORS['bg_card'], fg=COLORS['primary'], relief='solid',
                                     borderwidth=1, padx=24, pady=8, cursor='hand2',
                                     command=lambda: self._start(write_to_output=False))
        self.btn_preview.pack(side='right', padx=6)
        
        self.btn_start = tk.Button(btn_frame, text='开始执行', font=('Microsoft YaHei UI', 11, 'bold'),
                                   bg=COLORS['primary'], fg='white', relief='flat',
                                   padx=32, pady=8, cursor='hand2',
                                   command=lambda: self._start(write_to_output=True))
        self.btn_start.pack(side='right', padx=6)
        
        self.btn_cancel = tk.Button(btn_frame, text='取消', font=('Microsoft YaHei UI', 10),
                                    bg=COLORS['error'], fg='white', relief='flat',
                                    padx=24, pady=8, cursor='hand2',
                                    command=self.app._cancel)
        self.btn_cancel.pack(side='right', padx=6)
        
        # 日志
        log_frame = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                            highlightbackground=COLORS['border'], borderwidth=1)
        log_frame.pack(fill='both', expand=True, padx=24, pady=(0, 24))
        
        tk.Label(log_frame, text='处理日志', font=FONTS['subtitle'], fg=COLORS['text_primary'],
                bg=COLORS['bg_card']).pack(anchor='w', padx=16, pady=(10, 4))
        
        self.log_text = tk.Text(log_frame, height=10, font=('Consolas', 9),
                               bg=COLORS['bg_main'], fg=COLORS['text_primary'],
                               relief='flat', state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=12, pady=(0, 12))
    
    def _build_step_header(self, parent, step_num, title, desc, var):
        header = tk.Frame(parent, bg=COLORS['bg_card'])
        header.pack(fill='x', padx=20, pady=(12, 4))
        
        tk.Checkbutton(header, text=f'{step_num}. {title}', variable=var,
                      font=('Microsoft YaHei UI', 12, 'bold'), bg=COLORS['bg_card'],
                      fg=COLORS['text_primary'], selectcolor=COLORS['bg_main'],
                      command=lambda: self._toggle_step(step_num)).pack(side='left')
        
        tk.Label(header, text=desc, font=FONTS['body_small'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(12, 0))
        
        return header
    
    def _toggle_step(self, step_num):
        key_map = {1: 'dedupe', 2: 'convert', 3: 'classify', 4: 'rename'}
        key = key_map.get(step_num)
        if key and key in self.step_frames:
            state = 'normal' if self.step_vars[key].get() else 'disabled'
            for widget in self.step_frames[key].winfo_children():
                try:
                    if isinstance(widget, (tk.Entry, ttk.Spinbox, ttk.Combobox)):
                        widget.configure(state=state if not isinstance(widget, ttk.Combobox) else ('readonly' if state == 'normal' else 'disabled'))
                    elif isinstance(widget, (tk.Checkbutton, tk.Radiobutton)):
                        widget.configure(state=state)
                    elif isinstance(widget, (tk.Frame, ttk.Frame)):
                        for child in widget.winfo_children():
                            try:
                                if isinstance(child, (tk.Entry, ttk.Spinbox, ttk.Combobox)):
                                    child.configure(state=state if not isinstance(child, ttk.Combobox) else ('readonly' if state == 'normal' else 'disabled'))
                                else:
                                    child.configure(state=state)
                            except Exception:
                                pass
                    else:
                        widget.configure(state=state)
                except Exception:
                    pass
    
    def _build_dedupe_card(self, parent):
        card = tk.Frame(parent, bg=COLORS['bg_card'], relief='solid',
                       highlightbackground=COLORS['border'], borderwidth=1)
        card.pack(fill='x', padx=24, pady=(0, 16))
        
        self._build_step_header(card, 1, '去重检测', '检测并处理相似图片', self.step_vars['dedupe'])
        
        body = tk.Frame(card, bg=COLORS['bg_card'])
        body.pack(fill='x', padx=20, pady=8)
        self.step_frames['dedupe'] = body
        
        # 阈值
        row1 = tk.Frame(body, bg=COLORS['bg_card'])
        row1.pack(fill='x', pady=4)
        tk.Label(row1, text='阈值', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        ttk.Spinbox(row1, from_=0, to=32, textvariable=self.dedup_threshold, width=5).pack(side='left', padx=8)
        tk.Label(row1, text='(0=严格, 越大越宽松)', font=FONTS['body_small'],
                fg=COLORS['text_secondary'], bg=COLORS['bg_card']).pack(side='left', padx=8)
        
        # 保留策略
        row2 = tk.Frame(body, bg=COLORS['bg_card'])
        row2.pack(fill='x', pady=4)
        tk.Label(row2, text='保留', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        ttk.Combobox(row2, textvariable=self.dedup_keep, values=list(KEEP_MAP.keys()),
                    width=15, state='readonly').pack(side='left', padx=8)
        ttk.Combobox(row2, textvariable=self.dedup_action, values=list(ACTION_MAP.keys()),
                    width=12, state='readonly').pack(side='left', padx=8)
        
        # 移动目录
        row3 = tk.Frame(body, bg=COLORS['bg_card'])
        row3.pack(fill='x', pady=4)
        tk.Label(row3, text='移动到', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        tk.Entry(row3, textvariable=self.dedup_move_dir, width=30).pack(side='left', fill='x', expand=True, padx=8)
        tk.Button(row3, text='选择', font=FONTS['body_small'], bg=COLORS['primary'], fg='white',
                 relief='flat', padx=8, pady=2, cursor='hand2',
                 command=self.app._pick_move_dir).pack(side='left', padx=4)
        
        # 初始禁用
        self._toggle_step(1)
    
    def _build_convert_card(self, parent):
        card = tk.Frame(parent, bg=COLORS['bg_card'], relief='solid',
                       highlightbackground=COLORS['border'], borderwidth=1)
        card.pack(fill='x', padx=24, pady=(0, 16))
        
        self._build_step_header(card, 2, '格式转换', '批量转换图片格式', self.step_vars['convert'])
        
        body = tk.Frame(card, bg=COLORS['bg_card'])
        body.pack(fill='x', padx=20, pady=8)
        self.step_frames['convert'] = body
        
        # 格式和质量
        row1 = tk.Frame(body, bg=COLORS['bg_card'])
        row1.pack(fill='x', pady=4)
        tk.Label(row1, text='格式', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        ttk.Combobox(row1, textvariable=self.conv_fmt, values=list(FMT_MAP.keys()),
                    width=12, state='readonly').pack(side='left', padx=8)
        
        tk.Label(row1, text='质量', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(16, 8))
        scale = tk.Scale(row1, from_=1, to=100, orient='horizontal', variable=self.conv_quality,
                        bg=COLORS['bg_card'], fg=COLORS['text_primary'], highlightthickness=0,
                        troughcolor=COLORS['border'], activebackground=COLORS['primary'])
        scale.pack(side='left', fill='x', expand=True)
        tk.Label(row1, textvariable=self.conv_quality, font=FONTS['body'],
                fg=COLORS['primary'], bg=COLORS['bg_card'], width=4).pack(side='left')
        
        # 选项
        row2 = tk.Frame(body, bg=COLORS['bg_card'])
        row2.pack(fill='x', pady=4)
        tk.Checkbutton(row2, text='同格式也重编码', variable=self.conv_same,
                      font=FONTS['body'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left', padx=4)
        tk.Checkbutton(row2, text='PNG3压缩', variable=self.conv_png3,
                      font=FONTS['body'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left', padx=4)
        
        # ICO选项
        ico_row = tk.Frame(body, bg=COLORS['bg_card'])
        ico_row.pack(fill='x', pady=4)
        tk.Label(ico_row, text='ICO尺寸', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        for s in (16, 32, 48, 64, 128, 256):
            tk.Checkbutton(ico_row, text=str(s), variable=self.conv_ico_sizes[s],
                          font=FONTS['body'], bg=COLORS['bg_card'],
                          selectcolor=COLORS['bg_main']).pack(side='left', padx=3)
        tk.Label(ico_row, text='px', font=FONTS['body_small'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=4)
        
        tk.Entry(ico_row, textvariable=self.conv_ico_custom, width=15,
                font=FONTS['body']).pack(side='left', padx=8)
        tk.Label(ico_row, text='(自定义, 逗号分隔)', font=FONTS['body_small'],
                fg=COLORS['text_secondary'], bg=COLORS['bg_card']).pack(side='left')
        
        # 非方图处理
        sq_row = tk.Frame(body, bg=COLORS['bg_card'])
        sq_row.pack(fill='x', pady=4)
        tk.Label(sq_row, text='非方图', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        for txt, val in [('保持', 'keep'), ('中心裁切', 'center'), ('左上裁切', 'topleft'), ('等比填充', 'fit')]:
            tk.Radiobutton(sq_row, text=txt, variable=self.conv_ico_square, value=val,
                          font=FONTS['body'], bg=COLORS['bg_card'],
                          selectcolor=COLORS['bg_main']).pack(side='left', padx=4)
        
        self._toggle_step(2)
    
    def _build_classify_card(self, parent):
        card = tk.Frame(parent, bg=COLORS['bg_card'], relief='solid',
                       highlightbackground=COLORS['border'], borderwidth=1)
        card.pack(fill='x', padx=24, pady=(0, 16))
        
        self._build_step_header(card, 3, '分类整理', '按比例或形状自动分类', self.step_vars['classify'])
        
        body = tk.Frame(card, bg=COLORS['bg_card'])
        body.pack(fill='x', padx=20, pady=8)
        self.step_frames['classify'] = body
        
        # 比例分类
        ratio_frame = tk.Frame(body, bg=COLORS['bg_card'])
        ratio_frame.pack(fill='x', pady=4)
        
        tk.Checkbutton(ratio_frame, text='比例分类', variable=self.cls_ratio_enabled,
                      font=FONTS['body'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left', padx=4)
        
        tk.Label(ratio_frame, text='容差', font=FONTS['body_small'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(8, 4))
        ttk.Spinbox(ratio_frame, from_=0.0, to=0.2, increment=0.005, format='%.3f',
                   width=6, textvariable=self.cls_ratio_tol).pack(side='left', padx=4)
        
        tk.Entry(ratio_frame, textvariable=self.cls_ratio_custom, width=30,
                font=FONTS['body']).pack(side='left', padx=8, fill='x', expand=True)
        
        tk.Checkbutton(ratio_frame, text='吸附', variable=self.cls_ratio_snap,
                      font=FONTS['body_small'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left', padx=4)
        
        # 形状分类
        shape_frame = tk.Frame(body, bg=COLORS['bg_card'])
        shape_frame.pack(fill='x', pady=4)
        
        tk.Checkbutton(shape_frame, text='形状分类', variable=self.cls_shape_enabled,
                      font=FONTS['body'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left', padx=4)
        
        tk.Label(shape_frame, text='容差', font=FONTS['body_small'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(8, 4))
        ttk.Spinbox(shape_frame, from_=0.01, to=0.5, increment=0.01, format='%.2f',
                   width=6, textvariable=self.cls_shape_tol).pack(side='left', padx=4)
        
        for label, var in [('方形:', self.cls_shape_square), ('横向:', self.cls_shape_horizontal), ('纵向:', self.cls_shape_vertical)]:
            tk.Label(shape_frame, text=label, font=FONTS['body_small'], fg=COLORS['text_secondary'],
                    bg=COLORS['bg_card']).pack(side='left', padx=(4, 2))
            tk.Entry(shape_frame, textvariable=var, width=6, font=FONTS['body']).pack(side='left', padx=2)
        
        self._toggle_step(3)
    
    def _build_rename_card(self, parent):
        card = tk.Frame(parent, bg=COLORS['bg_card'], relief='solid',
                       highlightbackground=COLORS['border'], borderwidth=1)
        card.pack(fill='x', padx=24, pady=(0, 16))
        
        self._build_step_header(card, 4, '批量重命名', '按模板重命名文件', self.step_vars['rename'])
        
        body = tk.Frame(card, bg=COLORS['bg_card'])
        body.pack(fill='x', padx=20, pady=8)
        self.step_frames['rename'] = body
        
        # 模式
        row1 = tk.Frame(body, bg=COLORS['bg_card'])
        row1.pack(fill='x', pady=4)
        tk.Label(row1, text='模式', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        tk.Entry(row1, textvariable=self.rn_pattern, width=40,
                font=('Consolas', 10)).pack(side='left', fill='x', expand=True, padx=8)
        
        # 序号
        row2 = tk.Frame(body, bg=COLORS['bg_card'])
        row2.pack(fill='x', pady=4)
        tk.Label(row2, text='序号', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        
        tk.Label(row2, text='起始', font=FONTS['body_small'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=4)
        ttk.Spinbox(row2, from_=1, to=999999, textvariable=self.rn_start, width=7).pack(side='left', padx=4)
        
        tk.Label(row2, text='步长', font=FONTS['body_small'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=8)
        ttk.Spinbox(row2, from_=1, to=9999, textvariable=self.rn_step, width=5).pack(side='left', padx=4)
        
        tk.Label(row2, text='宽度', font=FONTS['body_small'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=8)
        ttk.Spinbox(row2, from_=0, to=10, textvariable=self.rn_width, width=5).pack(side='left', padx=4)
        
        # 覆盖
        row3 = tk.Frame(body, bg=COLORS['bg_card'])
        row3.pack(fill='x', pady=4)
        tk.Label(row3, text='覆盖', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card'], width=8, anchor='w').pack(side='left')
        ttk.Combobox(row3, textvariable=self.rn_overwrite, values=list(OVERWRITE_MAP.keys()),
                    width=15, state='readonly').pack(side='left', padx=8)
        
        self._toggle_step(4)
    
    def _start(self, write_to_output=True):
        inp = self.app.in_var.get().strip()
        if not inp:
            messagebox.showwarning('提示', '请先在左侧栏选择输入目录或文件')
            return
        if not os.path.exists(inp):
            messagebox.showwarning('提示', '输入路径不存在')
            return
        
        # 检查是否至少启用一个步骤
        if not any(v.get() for v in self.step_vars.values()):
            messagebox.showwarning('提示', '请至少启用一个处理步骤')
            return
        
        self.app.write_to_output = write_to_output
        self.app.processed_source_files.clear()
        self.app.cache_to_original_map.clear()
        self.app._clear_cache()
        self.app._ensure_cache_dir()
        
        self.app.single_file_mode = False
        if os.path.isdir(inp):
            root_dir = inp
            out_dir = self.app.out_var.get().strip() or root_dir
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror('错误', f'输出目录创建失败: {e}')
                return
            from src.core.image_ops import SUPPORTED_EXT
            all_files = []
            for dirpath, dirs, files in os.walk(root_dir):
                for f in files:
                    fp = os.path.join(dirpath, f)
                    if os.path.splitext(f)[1].lower() in SUPPORTED_EXT:
                        all_files.append(fp)
                if not self.app.recursive_var.get():
                    break
            self.app._all_files = all_files
            if not all_files:
                messagebox.showinfo('提示', '未找到图片文件')
                return
        elif os.path.isfile(inp):
            self.app._all_files = [inp]
            self.app.single_file_mode = True
        else:
            messagebox.showwarning('提示', '不支持的文件类型')
            return
        
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')
        
        self.app.progress['value'] = 0
        self.app.progress['maximum'] = len(self.app._all_files)
        self.app.status_var.set('开始...' if write_to_output else '预览模式')
        self.app.stop_flag.clear()
        self.app.last_out_dir = out_dir
        
        self.app.worker = threading.Thread(target=self._pipeline, daemon=True)
        self.app.worker.start()
    
    def _pipeline(self):
        try:
            files = self.app._all_files
            self.app._ensure_cache_dir()
            files = self.app._copy_input_to_cache(files)
            if self.app.stop_flag.is_set():
                return
            
            # 步骤1：去重
            if self.step_vars['dedupe'].get():
                self.app.q.put('STATUS 步骤1/4: 去重检测中...')
                files = self._run_dedupe(files)
                if self.app.stop_flag.is_set():
                    return
            
            # 步骤2：转换
            if self.step_vars['convert'].get():
                self.app.q.put('STATUS 步骤2/4: 格式转换中...')
                files = self._run_convert(files)
                if self.app.stop_flag.is_set():
                    return
            
            # 步骤3：分类
            if self.step_vars['classify'].get():
                if self.cls_ratio_enabled.get():
                    self.app.q.put('STATUS 步骤3/4: 比例分类中...')
                    files = self._run_ratio_classify(files)
                    if self.app.stop_flag.is_set():
                        return
                if self.cls_shape_enabled.get():
                    self.app.q.put('STATUS 步骤3/4: 形状分类中...')
                    files = self._run_shape_classify(files)
                    if self.app.stop_flag.is_set():
                        return
            
            # 步骤4：重命名
            if self.step_vars['rename'].get():
                self.app.q.put('STATUS 步骤4/4: 批量重命名中...')
                self._run_rename(files)
                if self.app.stop_flag.is_set():
                    return
            
            if self.app.write_to_output:
                self.app._finalize_to_output()
            
            self.app.q.put('STATUS 一条龙处理完成')
        except Exception as e:
            import traceback
            self.app.q.put(f'STATUS 失败: {e}')
            print(f"[ERROR] {traceback.format_exc()}")
    
    def _run_dedupe(self, files):
        th = self.dedup_threshold.get()
        keep_mode = KEEP_MAP.get(self.dedup_keep.get(), 'largest')
        action = ACTION_MAP.get(self.dedup_action.get(), 'list')
        move_dir = self.dedup_move_dir.get().strip()
        workers = max(1, self.workers.get())
        
        self.app.q.put(f'STATUS 去重计算哈希 共{len(files)}')
        infos = []
        lock = threading.Lock()
        done = 0
        
        def compute(path):
            nonlocal done
            if self.app.stop_flag.is_set():
                return None
            try:
                from PIL import Image
                with Image.open(path) as im:
                    w, h = im.size
                    ah = ahash(im)
                    dh = dhash(im)
                    st = os.stat(path)
                info = ImgInfo(path, st.st_size, w, h, ah, dh, st.st_mtime)
            except Exception:
                info = None
            with lock:
                done += 1
                self.app.q.put(f'HASH {done} {len(files)}')
            return info
        
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for fut in as_completed([ex.submit(compute, f) for f in files]):
                r = fut.result()
                if r:
                    infos.append(r)
        
        if self.app.stop_flag.is_set():
            return []
        
        groups = []
        for info in infos:
            placed = False
            for g in groups:
                rep = g[0]
                if th == 0:
                    if info.ah == rep.ah and info.dh == rep.dh:
                        g.append(info)
                        placed = True
                        break
                else:
                    if hamming(info.ah, rep.ah) + hamming(info.dh, rep.dh) <= th:
                        g.append(info)
                        placed = True
                        break
            if not placed:
                groups.append([info])
        
        dup = [g for g in groups if len(g) > 1]
        kept = []
        
        for gi, g in enumerate(sorted(dup, key=lambda x: -len(x)), 1):
            if keep_mode == 'largest':
                keep = max(g, key=lambda x: x.res)
            elif keep_mode == 'largest-file':
                keep = max(g, key=lambda x: x.size)
            elif keep_mode == 'newest':
                keep = max(g, key=lambda x: x.mtime)
            elif keep_mode == 'oldest':
                keep = min(g, key=lambda x: x.mtime)
            else:
                keep = g[0]
            
            kept.append(keep.path)
            for o in (x for x in g if x is not keep):
                act = '保留'
                if action == 'delete' and not self.app.stop_flag.is_set():
                    if not self.app.write_to_output:
                        act = '删除(预览)'
                        self.app._simulate_delete(o.path)
                    else:
                        ok, msg = safe_delete(o.path)
                        act = msg if ok else msg
                elif action == 'move' and move_dir and not self.app.stop_flag.is_set():
                    if not self.app.write_to_output:
                        act = '移动(预览)'
                    else:
                        try:
                            os.makedirs(move_dir, exist_ok=True)
                            target = os.path.join(move_dir, os.path.basename(o.path))
                            if os.path.exists(target):
                                from src.core.file_ops import next_non_conflict
                                target = next_non_conflict(target)
                            shutil.move(o.path, target)
                            act = '移动'
                        except Exception as e:
                            act = f'移失败:{e}'
                self.app.q.put(f'LOG\tDEDUP\t{o.path}\t{keep.path}\t{act}')
            self.app.q.put(f'LOG\tDEDUP\t{keep.path}\t组#{gi}\t保留({len(g)})')
        
        dup_paths = {x.path for grp in dup for x in grp}
        for p in files:
            if p not in dup_paths:
                kept.append(p)
        
        return kept
    
    def _run_convert(self, files):
        fmt = FMT_MAP.get(self.conv_fmt.get(), 'png')
        process_same = self.conv_same.get()
        quality = self.conv_quality.get()
        png3 = self.conv_png3.get()
        workers = max(1, self.workers.get())
        
        ico_sizes = None
        if not self.conv_ico_keep.get():
            chosen = []
            for s, var in self.conv_ico_sizes.items():
                if var.get():
                    chosen.append(s)
            custom = self.conv_ico_custom.get().strip()
            if custom:
                for token in custom.replace(',', ' ').replace(';', ' ').split():
                    if token.isdigit():
                        v = int(token)
                        if 1 <= v <= 1024:
                            chosen.append(v)
            if chosen:
                ico_sizes = sorted(set(chosen))[:10]
        
        self.app._ensure_cache_dir()
        out_dir = self.app.cache_final_dir or self.app.cache_dir
        
        results = [None] * len(files)
        lock = threading.Lock()
        done = 0
        total = len(files)
        
        def do_one(i, f):
            nonlocal done
            if self.app.stop_flag.is_set():
                return
            src_ext = norm_ext(f)
            tgt_fmt = fmt
            need_convert = src_ext != fmt or process_same
            
            if not need_convert:
                try:
                    rel_dir = os.path.relpath(os.path.dirname(f), self.app.cache_dir)
                    if rel_dir == '.':
                        rel_dir = ''
                    dst_dir = os.path.join(out_dir, rel_dir)
                    os.makedirs(dst_dir, exist_ok=True)
                    dest = os.path.join(dst_dir, os.path.basename(f))
                    if not os.path.exists(dest):
                        shutil.copy2(f, dest)
                    with lock:
                        results[i] = dest
                        done += 1
                        self.app.q.put(f'PROG {done} {total}')
                except Exception as e:
                    self.app.q.put(f'LOG\tCONVERT\t{f}\t\t复制失败: {e}')
                    with lock:
                        results[i] = f
                        done += 1
                        self.app.q.put(f'PROG {done} {total}')
                return
            
            basename = os.path.splitext(os.path.basename(f))[0]
            out_name = f"{basename}.{tgt_fmt}"
            rel_dir = os.path.relpath(os.path.dirname(f), self.app.cache_dir)
            if rel_dir == '.':
                rel_dir = ''
            dest_dir = os.path.join(out_dir, rel_dir)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, out_name)
            
            ok, msg = convert_one(
                f, dest, tgt_fmt,
                quality if tgt_fmt in ('jpg', 'png', 'webp') else None,
                png3 if tgt_fmt == 'png' else False,
                ico_sizes if tgt_fmt == 'ico' else None,
                self.conv_ico_square.get() if tgt_fmt == 'ico' else None
            )
            
            with lock:
                if ok:
                    self.app.q.put(f'LOG\tCONVERT\t{f}\t{dest}\t转换')
                else:
                    self.app.q.put(f'LOG\tCONVERT\t{f}\t{dest}\t转换失败:{msg}')
                results[i] = dest if ok else f
                done += 1
                self.app.q.put(f'PROG {done} {total}')
        
        if workers > 1 and len(files) > 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(do_one, i, f) for i, f in enumerate(files)]
                for _ in as_completed(futs):
                    if self.app.stop_flag.is_set():
                        break
        else:
            for i, f in enumerate(files):
                do_one(i, f)
        
        return [r for r in results if r]
    
    def _parse_ratios(self):
        text = self.cls_ratio_custom.get().strip()
        if not text:
            text = '16:9,3:2,4:3,1:1,21:9'
        pairs = []
        for token in re.split(r'[;,\s]+', text):
            if not token:
                continue
            token = token.lower().replace('x', ':')
            if ':' not in token:
                continue
            a, b = token.split(':', 1)
            if a.isdigit() and b.isdigit():
                w, h = int(a), int(b)
                if 0 < w <= 10000 and 0 < h <= 10000:
                    pairs.append((w, h, f'{w}x{h}'))
        uniq = {}
        for w, h, label in pairs:
            uniq[(w, h)] = label
        return [(w, h, lbl) for (w, h), lbl in uniq.items()]
    
    def _run_ratio_classify(self, files):
        COMMON = self._parse_ratios()
        if not COMMON:
            return files
        tol = self.cls_ratio_tol.get()
        workers = max(1, self.workers.get())
        out_dir = self.app.cache_final_dir or self.app.cache_dir
        
        result = []
        lock = threading.Lock()
        done = 0
        total = len(files)
        
        def classify_one(p):
            nonlocal done
            if self.app.stop_flag.is_set():
                return None
            if not os.path.isfile(p):
                with lock:
                    done += 1
                return p
            
            is_anim = is_animated_image(p)
            try:
                from PIL import Image
                with Image.open(p) as im:
                    w, h = im.size
            except Exception:
                with lock:
                    done += 1
                return p
            
            if h == 0:
                with lock:
                    done += 1
                return p
            
            ratio = w / h
            ratio_label = 'other'
            for rw, rh, lab in COMMON:
                ideal = rw / rh
                if ideal != 0 and abs(ratio - ideal) / ideal <= tol:
                    ratio_label = lab
                    break
            
            label = f'AM/{ratio_label}' if is_anim else ratio_label
            dir_ratio = os.path.join(out_dir, label)
            if not os.path.isdir(dir_ratio):
                try:
                    os.makedirs(dir_ratio, exist_ok=True)
                except Exception:
                    pass
            
            dest = os.path.join(dir_ratio, os.path.basename(p))
            if os.path.abspath(dest) == os.path.abspath(p):
                with lock:
                    done += 1
                return p
            
            if os.path.exists(dest):
                base_no, ext = os.path.splitext(dest)
                i = 1
                while os.path.exists(dest):
                    dest = f"{base_no}_{i}{ext}"
                    i += 1
            
            try:
                shutil.copy2(p, dest)
                self.app.q.put(f'LOG\tCLASSIFY\t{p}\t{dest}\t比例分类->{label}')
                res_path = dest
            except Exception as e:
                self.app.q.put(f'LOG\tCLASSIFY\t{p}\t{p}\t比例分类失败:{e}')
                res_path = p
            
            with lock:
                done += 1
                self.app.q.put(f'PROG {done} {total}')
            return res_path
        
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for fut in as_completed([ex.submit(classify_one, p) for p in files]):
                    r = fut.result()
                    if r:
                        result.append(r)
        else:
            for p in files:
                r = classify_one(p)
                if r:
                    result.append(r)
        
        return result
    
    def _run_shape_classify(self, files):
        workers = max(1, self.workers.get())
        out_dir = self.app.cache_final_dir or self.app.cache_dir
        
        result = []
        lock = threading.Lock()
        done = 0
        total = len(files)
        
        def classify_one(p):
            nonlocal done
            if self.app.stop_flag.is_set():
                return None
            try:
                from PIL import Image
                with Image.open(p) as im:
                    w, h = im.size
                
                square_tolerance = self.cls_shape_tol.get()
                ratio = w / h if h > 0 else 1
                
                square_name = self.cls_shape_square.get().strip() or 'zfx'
                horizontal_name = self.cls_shape_horizontal.get().strip() or 'hp'
                vertical_name = self.cls_shape_vertical.get().strip() or 'sp'
                
                if abs(ratio - 1) <= square_tolerance:
                    shape_label = square_name
                elif ratio > 1:
                    shape_label = horizontal_name
                else:
                    shape_label = vertical_name
                
                is_anim = is_animated_image(p)
                label = f'AM/{shape_label}' if is_anim else shape_label
                
                dir_shape = os.path.join(out_dir, label)
                if not os.path.isdir(dir_shape):
                    try:
                        os.makedirs(dir_shape, exist_ok=True)
                    except Exception:
                        pass
                
                dest = os.path.join(dir_shape, os.path.basename(p))
                if os.path.abspath(dest) == os.path.abspath(p):
                    with lock:
                        done += 1
                    return p
                
                if os.path.exists(dest):
                    base_no, ext = os.path.splitext(dest)
                    i = 1
                    while os.path.exists(dest):
                        dest = f"{base_no}_{i}{ext}"
                        i += 1
                
                shutil.copy2(p, dest)
                self.app.q.put(f'LOG\tCLASSIFY\t{p}\t{dest}\t形状分类->{label}')
                res_path = dest
            except Exception as e:
                self.app.q.put(f'LOG\tCLASSIFY\t{p}\t{p}\t形状分类失败:{e}')
                res_path = p
            
            with lock:
                done += 1
                self.app.q.put(f'PROG {done} {total}')
            return res_path
        
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                for fut in as_completed([ex.submit(classify_one, p) for p in files]):
                    r = fut.result()
                    if r:
                        result.append(r)
        else:
            for p in files:
                r = classify_one(p)
                if r:
                    result.append(r)
        
        return result
    
    def _run_rename(self, files):
        pattern = self.rn_pattern.get().strip()
        if not pattern:
            return
        start = self.rn_start.get()
        step = self.rn_step.get()
        pad_width = self.rn_width.get()
        overwrite = OVERWRITE_MAP.get(self.rn_overwrite.get(), 'overwrite')
        preview = not self.app.write_to_output
        
        self.app._ensure_cache_dir()
        out_dir = self.app.cache_final_dir or self.app.cache_dir
        class_root = self.app.cache_dir
        
        idx = start
        total = len(files)
        done = 0
        
        for f in files:
            if self.app.stop_flag.is_set():
                break
            if not os.path.isfile(f):
                continue
            
            ext = norm_ext(f)
            stem = os.path.splitext(os.path.basename(f))[0]
            name_raw = pattern
            
            def repl_index(m):
                w = int(m.group(1))
                return str(idx).zfill(w)
            
            name_raw = re.sub(r'\{index:(\d+)\}', repl_index, name_raw)
            if '{index}' in name_raw:
                name_raw = name_raw.replace('{index}', str(idx).zfill(pad_width) if pad_width > 0 else str(idx))
            
            final_name = name_raw.replace('{name}', stem).replace('{ext}', f'.{ext}').replace('{fmt}', ext)
            if '.' not in os.path.basename(final_name):
                final_name += f'.{ext}'
            
            rel_dir = os.path.relpath(os.path.dirname(f), class_root)
            if rel_dir == '.':
                rel_dir = ''
            target_dir = os.path.join(out_dir, rel_dir)
            os.makedirs(target_dir, exist_ok=True)
            dest = os.path.join(target_dir, final_name)
            
            if os.path.abspath(dest) == os.path.abspath(f):
                self.app.q.put(f'LOG\tRENAME\t{f}\t{dest}\t跳过(路径相同)')
                idx += step
                done += 1
                self.app.q.put(f'PROG {done} {total}')
                continue
            
            if os.path.exists(dest):
                if overwrite == 'skip':
                    self.app.q.put(f'LOG\tRENAME\t{f}\t{dest}\t跳过(存在)')
                    idx += step
                    done += 1
                    self.app.q.put(f'PROG {done} {total}')
                    continue
                elif overwrite == 'rename':
                    if not preview:
                        base_no, ext2 = os.path.splitext(dest)
                        i = 1
                        while os.path.exists(dest):
                            dest = f"{base_no}_{i}{ext2}"
                            i += 1
                    else:
                        dest = dest + '(预览改名)'
            
            try:
                shutil.copy2(f, dest)
                self.app.q.put(f'LOG\tRENAME\t{f}\t{dest}\t重命名')
            except Exception as e:
                self.app.q.put(f'LOG\tRENAME\t{f}\t{dest}\t失败:{e}')
            
            idx += step
            done += 1
            self.app.q.put(f'PROG {done} {total}')
