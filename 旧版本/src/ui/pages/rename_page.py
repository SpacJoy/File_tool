"""批量重命名页面"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import threading

from src.ui.theme import COLORS, FONTS, SPACING
from src.core.image_ops import OVERWRITE_MAP, norm_ext


class RenamePage:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=COLORS['bg_main'])
        self.log_text = None
        
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
            color = COLORS['log_rename'] if entry.get('stage') == 'RENAME' else '#FFFFFF'
            self.log_text.configure(state='normal')
            self.log_text.insert('end', f'[{stage}] {src} -> {dst} - {info}\n', 'entry')
            self.log_text.tag_configure('entry', background=color)
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
    
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
        tk.Label(scrollable, text='批量重命名', font=('Microsoft YaHei UI', 18, 'bold'),
                fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(16, 8))
        
        tk.Label(scrollable, text='使用自定义模板批量重命名图片文件',
                font=('Microsoft YaHei UI', 10), fg=COLORS['text_secondary'],
                bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(0, 16))
        
        # 重命名设置卡片
        card = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                       highlightbackground=COLORS['border'], borderwidth=1)
        card.pack(fill='x', padx=24, pady=(0, 16))
        
        # 命名模式
        pattern_row = tk.Frame(card, bg=COLORS['bg_card'])
        pattern_row.pack(fill='x', padx=20, pady=(16, 8))
        
        tk.Label(pattern_row, text='命名模式', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        pattern_entry = tk.Entry(pattern_row, textvariable=self.app.pattern_var, width=40,
                                font=('Consolas', 10))
        pattern_entry.pack(side='left', fill='x', expand=True)
        
        # 变量说明
        help_text = tk.Label(scrollable, text='可用变量: {name} 原文件名 | {ext} 扩展名 | {fmt} 格式 | {index} 序号 | {index:03} 补零序号',
                            font=FONTS['body_small'], fg=COLORS['text_secondary'],
                            bg=COLORS['bg_main'], justify='left')
        help_text.pack(anchor='w', padx=24, pady=(0, 8))
        
        # 序号设置
        seq_card = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                           highlightbackground=COLORS['border'], borderwidth=1)
        seq_card.pack(fill='x', padx=24, pady=(0, 16))
        
        seq_row = tk.Frame(seq_card, bg=COLORS['bg_card'])
        seq_row.pack(fill='x', padx=20, pady=12)
        
        tk.Label(seq_row, text='起始序号', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 8))
        start_spin = ttk.Spinbox(seq_row, from_=1, to=999999, textvariable=self.app.start_var, width=8)
        start_spin.pack(side='left', padx=(0, 20))
        
        tk.Label(seq_row, text='步长', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 8))
        step_spin = ttk.Spinbox(seq_row, from_=1, to=9999, textvariable=self.app.step_var, width=5)
        step_spin.pack(side='left', padx=(0, 20))
        
        tk.Label(seq_row, text='序号宽度', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 8))
        width_spin = ttk.Spinbox(seq_row, from_=0, to=10, textvariable=self.app.index_width_var, width=5)
        width_spin.pack(side='left')
        
        # 覆盖策略
        overwrite_row = tk.Frame(seq_card, bg=COLORS['bg_card'])
        overwrite_row.pack(fill='x', padx=20, pady=(0, 12))
        
        tk.Label(overwrite_row, text='覆盖策略', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        overwrite_combo = ttk.Combobox(overwrite_row, textvariable=self.app.overwrite_var,
                                       values=list(OVERWRITE_MAP.keys()), width=15, state='readonly')
        overwrite_combo.pack(side='left')
        overwrite_combo.set('覆盖原有')
        
        # 按钮
        btn_frame = tk.Frame(scrollable, bg=COLORS['bg_main'])
        btn_frame.pack(fill='x', padx=24, pady=(0, 24))
        
        self.btn_preview = tk.Button(btn_frame, text='预览', font=('Microsoft YaHei UI', 10),
                                     bg=COLORS['bg_card'], fg=COLORS['primary'], relief='solid',
                                     borderwidth=1, padx=24, pady=6, cursor='hand2',
                                     command=lambda: self._start(write_to_output=False))
        self.btn_preview.pack(side='right', padx=6)
        
        self.btn_start = tk.Button(btn_frame, text='开始执行', font=('Microsoft YaHei UI', 10, 'bold'),
                                   bg=COLORS['primary'], fg='white', relief='flat',
                                   padx=24, pady=6, cursor='hand2',
                                   command=lambda: self._start(write_to_output=True))
        self.btn_start.pack(side='right', padx=6)
        
        self.btn_cancel = tk.Button(btn_frame, text='取消', font=('Microsoft YaHei UI', 10),
                                    bg=COLORS['error'], fg='white', relief='flat',
                                    padx=24, pady=6, cursor='hand2',
                                    command=self.app._cancel)
        self.btn_cancel.pack(side='right', padx=6)
        
        # 日志
        self.log_frame = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                                 highlightbackground=COLORS['border'], borderwidth=1)
        self.log_frame.pack(fill='both', expand=True, padx=24, pady=(0, 24))
        
        tk.Label(self.log_frame, text='处理日志', font=FONTS['subtitle'], fg=COLORS['text_primary'],
                bg=COLORS['bg_card']).pack(anchor='w', padx=16, pady=(10, 4))
        
        self.log_text = tk.Text(self.log_frame, height=8, font=('Consolas', 9),
                               bg=COLORS['bg_main'], fg=COLORS['text_primary'],
                               relief='flat', state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=12, pady=(0, 12))
    
    def _start(self, write_to_output=True):
        inp = self.app.in_var.get().strip()
        if not inp:
            messagebox.showwarning('提示', '请先选择输入目录或文件')
            return
        if not os.path.exists(inp):
            messagebox.showwarning('提示', '输入路径不存在')
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
            
            self._rename_stage(files)
            if self.app.stop_flag.is_set():
                return
            
            if self.app.write_to_output:
                self.app._finalize_to_output()
            
            self.app.q.put('STATUS 完成')
        except Exception as e:
            import traceback
            self.app.q.put(f'STATUS 失败: {e}')
            print(f"[ERROR] {traceback.format_exc()}")
    
    def _rename_stage(self, files):
        pattern = self.app.pattern_var.get().strip()
        if not pattern:
            return
        start = self.app.start_var.get()
        step = self.app.step_var.get()
        pad_width = self.app.index_width_var.get()
        overwrite = OVERWRITE_MAP.get(self.app.overwrite_var.get(), 'overwrite')
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
                import shutil
                shutil.copy2(f, dest)
                self.app.q.put(f'LOG\tRENAME\t{f}\t{dest}\t重命名')
            except Exception as e:
                self.app.q.put(f'LOG\tRENAME\t{f}\t{dest}\t失败:{e}')
            
            idx += step
            done += 1
            self.app.q.put(f'PROG {done} {total}')
