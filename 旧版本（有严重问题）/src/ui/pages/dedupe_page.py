"""重复检测页面"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from src.ui.theme import COLORS, FONTS, SPACING
from src.core.image_ops import KEEP_MAP, ACTION_MAP, ahash, dhash, hamming
from src.core.file_ops import safe_delete, move_file


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


class DedupePage:
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
            color = COLORS['log_dedupe'] if entry.get('stage') == 'DEDUP' else '#FFFFFF'
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
        tk.Label(scrollable, text='重复检测', font=('Microsoft YaHei UI', 18, 'bold'),
                fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(16, 8))
        
        tk.Label(scrollable, text='检测并处理相似图片，支持感知哈希和差值哈希算法',
                font=('Microsoft YaHei UI', 10), fg=COLORS['text_secondary'],
                bg=COLORS['bg_main']).pack(anchor='w', padx=24, pady=(0, 16))
        
        # 检测设置卡片
        card = tk.Frame(scrollable, bg=COLORS['bg_card'], relief='solid',
                       highlightbackground=COLORS['border'], borderwidth=1)
        card.pack(fill='x', padx=24, pady=(0, 16))
        
        # 阈值
        thresh_row = tk.Frame(card, bg=COLORS['bg_card'])
        thresh_row.pack(fill='x', padx=20, pady=(16, 8))
        
        tk.Label(thresh_row, text='相似度阈值', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        thresh_spin = ttk.Spinbox(thresh_row, from_=0, to=32, textvariable=self.app.threshold_var, width=5)
        thresh_spin.pack(side='left')
        
        tk.Label(thresh_row, text='(0=严格匹配, 越大越宽松)', font=FONTS['body_small'],
                fg=COLORS['text_secondary'], bg=COLORS['bg_card']).pack(side='left', padx=(8, 0))
        
        # 保留策略
        keep_row = tk.Frame(card, bg=COLORS['bg_card'])
        keep_row.pack(fill='x', padx=20, pady=8)
        
        tk.Label(keep_row, text='保留策略', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        keep_combo = ttk.Combobox(keep_row, textvariable=self.app.keep_var,
                                  values=list(KEEP_MAP.keys()), width=15, state='readonly')
        keep_combo.pack(side='left')
        keep_combo.set('最大分辨率')
        
        # 动作
        action_row = tk.Frame(card, bg=COLORS['bg_card'])
        action_row.pack(fill='x', padx=20, pady=8)
        
        tk.Label(action_row, text='处理动作', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        action_combo = ttk.Combobox(action_row, textvariable=self.app.dedup_action_var,
                                    values=list(ACTION_MAP.keys()), width=12, state='readonly')
        action_combo.pack(side='left')
        action_combo.set('删除重复')
        
        # 移动目录
        move_row = tk.Frame(card, bg=COLORS['bg_card'])
        move_row.pack(fill='x', padx=20, pady=8)
        
        tk.Label(move_row, text='移动到', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_card']).pack(side='left', padx=(0, 12))
        
        move_entry = tk.Entry(move_row, textvariable=self.app.move_dir_var, width=30,
                             font=FONTS['body'])
        move_entry.pack(side='left', fill='x', expand=True, padx=(0, 8))
        
        move_btn = tk.Button(move_row, text='选择', font=FONTS['body'],
                            bg=COLORS['primary'], fg='white', relief='flat',
                            padx=12, pady=2, cursor='hand2',
                            command=self.app._pick_move_dir)
        move_btn.pack(side='right')
        
        # 底部操作
        action_bar = tk.Frame(scrollable, bg=COLORS['bg_main'])
        action_bar.pack(fill='x', padx=24, pady=(0, 16))
        
        tk.Label(action_bar, text='线程数', font=FONTS['body'], fg=COLORS['text_secondary'],
                bg=COLORS['bg_main']).pack(side='left', padx=(0, 6))
        
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
            from src.core.image_ops import iter_images, SUPPORTED_EXT
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
            
            if not self.app.single_file_mode:
                files = self._dedupe_stage(files)
            if self.app.stop_flag.is_set():
                return
            
            if self.app.write_to_output:
                self.app._finalize_to_output()
            
            self.app.q.put('STATUS 完成')
        except Exception as e:
            import traceback
            self.app.q.put(f'STATUS 失败: {e}')
            print(f"[ERROR] {traceback.format_exc()}")
    
    def _dedupe_stage(self, files):
        th = self.app.threshold_var.get()
        keep_mode = KEEP_MAP.get(self.app.keep_var.get(), 'largest')
        action = ACTION_MAP.get(self.app.dedup_action_var.get(), 'list')
        move_dir = self.app.move_dir_var.get().strip()
        workers = max(1, self.app.workers_var.get())
        
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
                            import shutil
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
