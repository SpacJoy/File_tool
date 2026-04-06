"""格式转换页面"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.ui.theme import COLORS, FONTS, SPACING
from src.core.image_ops import FMT_MAP, norm_ext, convert_one, is_animated_image
from src.core.file_ops import copy_file


class ConvertPage:
    def __init__(self, parent, app):
        self.app = app
        self.frame = tk.Frame(parent, bg=COLORS['bg_main'])
        self.log_frame = None
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
            info = entry.get('info', '')
            color = COLORS['log_convert'] if entry.get('stage') == 'CONVERT' else '#FFFFFF'
            self.log_text.configure(state='normal')
            self.log_text.insert('end', f'[{stage}] {src} - {info}\n', 'entry')
            self.log_text.tag_configure('entry', background=color)
            self.log_text.see('end')
            self.log_text.configure(state='disabled')
    
    def _build(self):
        # 滚动区域
        canvas = tk.Canvas(self.frame, bg=COLORS['bg_main'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame, orient='vertical', command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=COLORS['bg_main'])
        
        scrollable.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scrollable, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 标题
        tk.Label(scrollable, text='格式转换', font=('Microsoft YaHei UI', 18, 'bold'),
                fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(16, 8))
        
        tk.Label(scrollable, text='将图片批量转换为目标格式，支持质量调节和特殊选项',
                font=('Microsoft YaHei UI', 10), fg=COLORS['text_secondary'],
                bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(0, 16))
        
        # 主设置卡片
        card = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                       highlightbackground=COLORS['border'], borderwidth=1)
        card.pack(fill='x', padx=24, pady=(0, 16))
        
        # 格式选择
        fmt_row = tk.Frame(card, bg=COLORS['bg_card'])
        fmt_row.pack(fill='x', padx=20, pady=(16, 8))
        
        tk.Label(fmt_row, text='目标格式', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        self.fmt_combo = ttk.Combobox(fmt_row, textvariable=self.app.fmt_var,
                                      values=list(FMT_MAP.keys()), width=15, state='readonly')
        self.fmt_combo.pack(side='left')
        self.fmt_combo.set('WebP')
        
        # 质量设置
        quality_row = tk.Frame(card, bg=COLORS['bg_card'])
        quality_row.pack(fill='x', padx=20, pady=8)
        
        tk.Label(quality_row, text='质量', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        quality_scale = tk.Scale(quality_row, from_=1, to=100, orient='horizontal',
                                variable=self.app.quality_var, bg=COLORS['bg_card'],
                                fg=COLORS['text_primary'], highlightthickness=0,
                                troughcolor=COLORS['border'], activebackground=COLORS['primary'])
        quality_scale.pack(side='left', fill='x', expand=True)
        
        tk.Label(quality_row, textvariable=self.app.quality_var, font=FONTS['body'],
                fg=COLORS['primary'], bg=COLORS['bg_card'], width=4).pack(side='left', padx=(8, 0))
        
        # 选项行
        options_row = tk.Frame(card, bg=COLORS['bg_card'])
        options_row.pack(fill='x', padx=20, pady=8)
        
        self._create_checkbox(options_row, '同格式也重编码', self.app.process_same_var)
        self._create_checkbox(options_row, 'PNG3压缩', self.app.png3_var)
        
        # ICO选项
        ico_card = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                           highlightbackground=COLORS['border'], borderwidth=1)
        ico_card.pack(fill='x', padx=24, pady=(0, 16))
        
        tk.Label(ico_card, text='ICO 选项', font=FONTS['subtitle'], fg=COLORS['text_primary'],
                bg=COLORS['bg_card']).pack(anchor='w', padx=20, pady=(12, 8))
        
        ico_sizes_row = tk.Frame(ico_card, bg=COLORS['bg_card'])
        ico_sizes_row.pack(fill='x', padx=20, pady=4)
        
        tk.Label(ico_sizes_row, text='尺寸', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        for s in (16, 32, 48, 64, 128, 256):
            cb = tk.Checkbutton(ico_sizes_row, text=str(s), variable=self.app.ico_size_vars[s],
                               font=FONTS['body'], bg=COLORS['bg_card'],
                               selectcolor=COLORS['bg_main'])
            cb.pack(side='left', padx=6)
        
        tk.Label(ico_sizes_row, text='px', font=FONTS['body_small'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left')
        
        # 非方图处理
        sq_row = tk.Frame(ico_card, bg=COLORS['bg_card'])
        sq_row.pack(fill='x', padx=20, pady=8)
        
        tk.Label(sq_row, text='非方图', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        for txt, val in [('保持', 'keep'), ('中心裁切', 'center'), ('左上裁切', 'topleft'), ('等比填充', 'fit')]:
            rb = tk.Radiobutton(sq_row, text=txt, variable=self.app.ico_square_mode, value=val,
                               font=FONTS['body'], bg=COLORS['bg_card'],
                               selectcolor=COLORS['bg_main'])
            rb.pack(side='left', padx=6)
        
        # 底部操作栏
        action_bar = tk.Frame(scrollable, bg=COLORS['bg_main'])
        action_bar.pack(fill='x', padx=24, pady=(0, 16))
        
        self._create_checkbox(action_bar, '删除源文件', self.app.global_remove_src)
        
        tk.Label(action_bar, text='线程数', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_main']).pack(side='left', padx=(20, 6))
        
        thread_spin = ttk.Spinbox(action_bar, from_=1, to=64, textvariable=self.app.workers_var, width=5)
        thread_spin.pack(side='left')
        
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
        
        # 日志区域
        self.log_frame = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                                 highlightbackground=COLORS['border'], borderwidth=1)
        self.log_frame.pack(fill='both', expand=True, padx=24, pady=(0, 24))
        
        tk.Label(self.log_frame, text='处理日志', font=FONTS['subtitle'], fg=COLORS['text_primary'],
                bg=COLORS['bg_card']).pack(anchor='w', padx=16, pady=(10, 4))
        
        self.log_text = tk.Text(self.log_frame, height=8, font=('Consolas', 9),
                               bg=COLORS['bg_main'], fg=COLORS['text_primary'],
                               relief='flat', state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=12, pady=(0, 12))
    
    def _create_checkbox(self, parent, text, var):
        cb = tk.Checkbutton(parent, text=text, variable=var, font=FONTS['body'],
                           bg=COLORS['bg_card'] if 'card' in str(parent.cget('bg')) else COLORS['bg_main'],
                           selectcolor=COLORS['bg_main'])
        cb.pack(side='left', padx=6)
        return cb
    
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
            try:
                all_files, _ = self._scan_files(root_dir, self.app.recursive_var.get())
                self.app._all_files = all_files
            except PermissionError:
                messagebox.showerror('错误', '输入文件夹无读取权限')
                return
            except Exception as e:
                messagebox.showerror('错误', f'读取失败: {e}')
                return
            if not all_files:
                messagebox.showinfo('提示', '未找到图片文件')
                return
        elif os.path.isfile(inp):
            root_dir = os.path.dirname(inp) or os.getcwd()
            out_dir = self.app.out_var.get().strip() or root_dir
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror('错误', f'输出目录创建失败: {e}')
                return
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
    
    def _scan_files(self, root_dir, recursive):
        from src.core.image_ops import iter_images, SUPPORTED_EXT
        files = []
        for dirpath, dirs, filenames in os.walk(root_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXT:
                    files.append(fp)
            if not recursive:
                break
        return files, []
    
    def _pipeline(self):
        try:
            files = self.app._all_files
            self.app._ensure_cache_dir()
            files = self.app._copy_input_to_cache(files)
            if self.app.stop_flag.is_set():
                return
            
            files = self._convert_stage(files)
            if self.app.stop_flag.is_set():
                return
            
            if self.app.write_to_output:
                self.app._finalize_to_output()
            
            self.app.q.put('STATUS 完成')
        except Exception as e:
            import traceback
            self.app.q.put(f'STATUS 失败: {e}')
            print(f"[ERROR] {traceback.format_exc()}")
    
    def _convert_stage(self, files):
        fmt = FMT_MAP.get(self.app.fmt_var.get(), 'png')
        process_same = self.app.process_same_var.get()
        quality = self.app.quality_var.get()
        png3 = self.app.png3_var.get()
        workers = max(1, self.app.workers_var.get())
        
        ico_sizes = None
        if not self.app.ico_keep_orig.get():
            chosen = []
            for s, var in self.app.ico_size_vars.items():
                if var.get():
                    chosen.append(s)
            custom = self.app.ico_sizes_var.get().strip()
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
                        import shutil
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
                self.app.ico_square_mode.get() if tgt_fmt == 'ico' else None
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
