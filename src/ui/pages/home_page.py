"""首页 - 欢迎面板"""
import tkinter as tk
from tkinter import ttk
from src.ui.theme import COLORS, FONTS, SPACING


class HomePage:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=COLORS['bg_main'])
        
        self._build()
    
    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
    
    def pack_forget(self):
        self.frame.pack_forget()
    
    def on_show(self):
        pass
    
    def on_log_entry(self, entry):
        pass
    
    def _build(self):
        # 顶部欢迎区域
        welcome = tk.Frame(self.frame, bg=COLORS['bg_card'])
        welcome.pack(fill='x', padx=24, pady=(24, 16))
        
        tk.Label(welcome, text='欢迎使用图片工具', font=('Microsoft YaHei UI', 20, 'bold'),
                fg=COLORS['primary'], bg=COLORS['bg_card']).pack(anchor='w', padx=24, pady=(20, 8))
        
        tk.Label(welcome, text='选择左侧功能开始批量处理图片', font=('Microsoft YaHei UI', 11),
                fg=COLORS['text_secondary'], bg=COLORS['bg_card']).pack(anchor='w', padx=24, pady=(0, 20))
        
        # 一条龙模式 - 推荐卡片
        pipeline_card = tk.Frame(self.frame, bg=COLORS['primary_light'], relief='solid',
                                borderwidth=1, highlightbackground=COLORS['primary'])
        pipeline_card.pack(fill='x', padx=24, pady=(0, 16))
        
        pipeline_inner = tk.Frame(pipeline_card, bg=COLORS['primary_light'])
        pipeline_inner.pack(fill='x', padx=24, pady=16)
        
        tk.Label(pipeline_inner, text='⚡', font=('Segoe UI Emoji', 36),
                bg=COLORS['primary_light']).pack(side='left', padx=(0, 16))
        
        info_frame = tk.Frame(pipeline_inner, bg=COLORS['primary_light'])
        info_frame.pack(side='left', fill='x', expand=True)
        
        tk.Label(info_frame, text='一条龙模式（推荐）', font=('Microsoft YaHei UI', 14, 'bold'),
                fg=COLORS['primary'], bg=COLORS['primary_light']).pack(anchor='w')
        tk.Label(info_frame, text='去重 → 转换 → 分类 → 重命名，一次配置完成所有操作',
                font=('Microsoft YaHei UI', 10), fg=COLORS['text_secondary'],
                bg=COLORS['primary_light']).pack(anchor='w', pady=(4, 0))
        
        btn_pipeline = tk.Button(pipeline_inner, text='立即使用', font=('Microsoft YaHei UI', 10, 'bold'),
                                bg=COLORS['primary'], fg='white', relief='flat',
                                padx=20, pady=6, cursor='hand2',
                                command=lambda: self.app._show_page('pipeline'))
        btn_pipeline.pack(side='right')
        
        # 功能卡片网格
        cards_frame = tk.Frame(self.frame, bg=COLORS['bg_main'])
        cards_frame.pack(fill='both', expand=True, padx=24, pady=(0, 24))
        
        cards = [
            ('convert', '🔄', '格式转换', '批量转换图片格式\n支持 JPG / PNG / WebP / ICO'),
            ('dedupe', '🔍', '重复检测', '智能检测相似图片\n支持感知哈希 + 差值哈希'),
            ('rename', '✏️', '批量重命名', '灵活的重命名模式\n支持自定义模板和序号'),
            ('classify', '📁', '分类整理', '按比例或形状自动分类\n智能创建子目录'),
        ]
        
        for i, (page_id, icon, title, desc) in enumerate(cards):
            row, col = divmod(i, 2)
            card = self._create_card(cards_frame, page_id, icon, title, desc)
            card.grid(row=row, column=col, padx=8, pady=8, sticky='nsew')
        
        for i in range(2):
            cards_frame.columnconfigure(i, weight=1)
        for i in range(2):
            cards_frame.rowconfigure(i, weight=1)
    
    def _create_card(self, parent, page_id, icon, title, desc):
        card = tk.Frame(parent, bg=COLORS['bg_card'], relief='solid', borderwidth=1,
                       highlightbackground=COLORS['border'])
        
        # 图标
        icon_label = tk.Label(card, text=icon, font=('Segoe UI Emoji', 32),
                             bg=COLORS['bg_card'])
        icon_label.pack(pady=(20, 8))
        
        # 标题
        tk.Label(card, text=title, font=('Microsoft YaHei UI', 13, 'bold'),
                fg=COLORS['text_primary'], bg=COLORS['bg_card']).pack(pady=(0, 6))
        
        # 描述
        tk.Label(card, text=desc, font=('Microsoft YaHei UI', 9),
                fg=COLORS['text_secondary'], bg=COLORS['bg_card'],
                justify='center').pack(pady=(0, 16))
        
        # 按钮
        btn = tk.Button(card, text='开始使用', font=('Microsoft YaHei UI', 10, 'bold'),
                       bg=COLORS['primary'], fg='white', relief='flat',
                       padx=24, pady=6, cursor='hand2',
                       command=lambda: self.app._show_page(page_id))
        btn.pack(pady=(0, 20))
        
        # 悬停效果
        def on_enter(e):
            card.configure(highlightbackground=COLORS['primary'])
            btn.configure(bg=COLORS['primary_hover'])
        
        def on_leave(e):
            card.configure(highlightbackground=COLORS['border'])
            btn.configure(bg=COLORS['primary'])
        
        card.bind('<Enter>', on_enter)
        card.bind('<Leave>', on_leave)
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return card
