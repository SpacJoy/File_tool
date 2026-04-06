"""分类整理页面 - 比例分类 + 形状分类"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.ui.theme import COLORS, FONTS, SPACING
from src.core.image_ops import is_animated_image


class ClassifyPage:
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
            info = entry.get('info', '')
            color = COLORS['log_classify'] if entry.get('stage') == 'CLASSIFY' else '#FFFFFF'
            self.log_text.configure(state='normal')
            self.log_text.insert('end', f'[{stage}] {src} - {info}\n', 'entry')
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
        tk.Label(scrollable, text='分类整理', font=('Microsoft YaHei UI', 18, 'bold'),
                fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(16, 8))
        
        tk.Label(scrollable, text='按比例或形状自动分类图片到不同文件夹',
                font=('Microsoft YaHei UI', 10), fg=COLORS['text_secondary'],
                bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(0, 16))
        
        # 比例分类卡片
        ratio_card = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                             highlightbackground=COLORS['border'], borderwidth=1)
        ratio_card.pack(fill='x', padx=24, pady=(0, 16))
        
        tk.Label(ratio_card, text='比例分类', font=FONTS['subtitle'], fg=COLORS['text_primary'],
                bg=COLORS['bg_card']).pack(anchor='w', padx=20, pady=(12, 8))
        
        # 启用
        ratio_enable = tk.Frame(ratio_card, bg=COLORS['bg_card'])
        ratio_enable.pack(fill='x', padx=20, pady=4)
        
        tk.Checkbutton(ratio_enable, text='启用比例分类', variable=self.app.classify_ratio_var,
                      font=FONTS['body'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left')
        
        # 容差
        tol_row = tk.Frame(ratio_card, bg=COLORS['bg_card'])
        tol_row.pack(fill='x', padx=20, pady=4)
        
        tk.Label(tol_row, text='容差', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 8))
        tol_spin = ttk.Spinbox(tol_row, from_=0.0, to=0.2, increment=0.005,
                              format='%.3f', width=6, textvariable=self.app.ratio_tol_var)
        tol_spin.pack(side='left', padx=(0, 16))
        
        tk.Checkbutton(tol_row, text='不匹配吸附最近', variable=self.app.ratio_snap_var,
                      font=FONTS['body'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left')
        
        # 自定义比例
        custom_row = tk.Frame(ratio_card, bg=COLORS['bg_card'])
        custom_row.pack(fill='x', padx=20, pady=8)
        
        tk.Label(custom_row, text='自定义比例', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 8))
        
        custom_entry = tk.Entry(custom_row, textvariable=self.app.ratio_custom_var, width=40,
                               font=FONTS['body'])
        custom_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        
        reset_btn = tk.Button(custom_row, text='恢复默认', font=FONTS['body_small'],
                             bg=COLORS['bg_main'], fg=COLORS['primary'], relief='flat',
                             padx=8, pady=2, cursor='hand2',
                             command=lambda: self.app.ratio_custom_var.set('16:9,3:2,4:3,1:1,21:9'))
        reset_btn.pack(side='right')
        
        # 预设按钮
        preset_frame = tk.Frame(ratio_card, bg=COLORS['bg_card'])
        preset_frame.pack(fill='x', padx=20, pady=(0, 12))
        
        presets = ['16:9', '16:10', '4:3', '3:2', '5:4', '21:9', '1:1']
        for r in presets:
            btn = tk.Button(preset_frame, text=r, font=FONTS['body_small'],
                           bg=COLORS['primary_light'], fg=COLORS['primary'], relief='flat',
                           padx=8, pady=3, cursor='hand2',
                           command=lambda v=r: self._toggle_ratio(v))
            btn.pack(side='left', padx=2)
        
        # 形状分类卡片
        shape_card = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                             highlightbackground=COLORS['border'], borderwidth=1)
        shape_card.pack(fill='x', padx=24, pady=(0, 16))
        
        tk.Label(shape_card, text='形状分类', font=FONTS['subtitle'], fg=COLORS['text_primary'],
                bg=COLORS['bg_card']).pack(anchor='w', padx=20, pady=(12, 8))
        
        # 启用
        shape_enable = tk.Frame(shape_card, bg=COLORS['bg_card'])
        shape_enable.pack(fill='x', padx=20, pady=4)
        
        tk.Checkbutton(shape_enable, text='启用形状分类', variable=self.app.classify_shape_var,
                      font=FONTS['body'], bg=COLORS['bg_card'],
                      selectcolor=COLORS['bg_main']).pack(side='left')
        
        # 容差
        shape_tol_row = tk.Frame(shape_card, bg=COLORS['bg_card'])
        shape_tol_row.pack(fill='x', padx=20, pady=4)
        
        tk.Label(shape_tol_row, text='方形容差', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 8))
        shape_tol_spin = ttk.Spinbox(shape_tol_row, from_=0.01, to=0.5, increment=0.01,
                                    format='%.2f', width=6, textvariable=self.app.shape_tolerance_var)
        shape_tol_spin.pack(side='left')
        
        # 文件夹名称
        folder_row = tk.Frame(shape_card, bg=COLORS['bg_card'])
        folder_row.pack(fill='x', padx=20, pady=8)
        
        names = [
            ('方形', self.app.shape_square_name),
            ('横向', self.app.shape_horizontal_name),
            ('纵向', self.app.shape_vertical_name),
        ]
        for label, var in names:
            lbl = tk.Label(folder_row, text=f'{label}:', font=FONTS['body'],
                          fg=COLORS['text_secondary'], bg=COLORS['bg_card'])
            lbl.pack(side='left', padx=(0, 4))
            entry = tk.Entry(folder_row, textvariable=var, width=8, font=FONTS['body'])
            entry.pack(side='left', padx=(0, 16))
        
        shape_reset = tk.Button(folder_row, text='重置', font=FONTS['body_small'],
                               bg=COLORS['bg_main'], fg=COLORS['primary'], relief='flat',
                               padx=8, pady=2, cursor='hand2',
                               command=lambda: [
                                   self.app.shape_square_name.set('zfx'),
                                   self.app.shape_horizontal_name.set('hp'),
                                   self.app.shape_vertical_name.set('sp'),
                                   self.app.shape_tolerance_var.set(0.15)
                               ])
        shape_reset.pack(side='right')
        
        # 底部操作
        action_bar = tk.Frame(scrollable, bg=COLORS['bg_main'])
        action_bar.pack(fill='x', padx=24, pady=(0, 16))
        
        tk.Checkbutton(action_bar, text='删除源文件', variable=self.app.global_remove_src,
                      font=FONTS['body'], bg=COLORS['bg_main'],
                      selectcolor=COLORS['bg_card']).pack(side='left')
        
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
    
    def _toggle_ratio(self, val):
        cur = self.app.ratio_custom_var.get().replace('；', ';').replace('，', ',').replace(';', ',')
        parts = [p.strip() for p in cur.split(',') if p.strip()]
        lower_map = {p.lower(): p for p in parts}
        key = val.lower()
        if key in lower_map:
            parts = [p for p in parts if p.lower() != key]
        else:
            parts.append(val)
        self.app.ratio_custom_var.set(','.join(parts))
    
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
            
            if not self.app.single_file_mode and self.app.classify_ratio_var.get():
                files = self._ratio_classify(files)
            if self.app.stop_flag.is_set():
                return
            
            if not self.app.single_file_mode and self.app.classify_shape_var.get():
                files = self._shape_classify(files)
            if self.app.stop_flag.is_set():
                return
            
            if self.app.write_to_output:
                self.app._finalize_to_output()
            
            self.app.q.put('STATUS 完成')
        except Exception as e:
            import traceback
            self.app.q.put(f'STATUS 失败: {e}')
            print(f"[ERROR] {traceback.format_exc()}")
    
    def _parse_ratios(self):
        text = self.app.ratio_custom_var.get().strip()
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
    
    def _ratio_classify(self, files):
        COMMON = self._parse_ratios()
        if not COMMON:
            return files
        tol = self.app.ratio_tol_var.get()
        workers = max(1, self.app.workers_var.get())
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
                import shutil
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
    
    def _shape_classify(self, files):
        workers = max(1, self.app.workers_var.get())
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
                
                square_tolerance = self.app.shape_tolerance_var.get()
                ratio = w / h if h > 0 else 1
                
                square_name = self.app.shape_square_name.get().strip() or 'zfx'
                horizontal_name = self.app.shape_horizontal_name.get().strip() or 'hp'
                vertical_name = self.app.shape_vertical_name.get().strip() or 'sp'
                
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
                
                import shutil
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
