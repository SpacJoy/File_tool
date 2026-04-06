"""主窗口 - 带侧边栏导航"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import threading
import queue

from src.ui.theme import COLORS, FONTS, SPACING, SIDEBAR_ITEMS
from src.ui.pages.home_page import HomePage
from src.ui.pages.pipeline_page import PipelinePage
from src.ui.pages.convert_page import ConvertPage
from src.ui.pages.dedupe_page import DedupePage
from src.ui.pages.rename_page import RenamePage
from src.ui.pages.classify_page import ClassifyPage


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('图片工具')
        self.root.geometry('1100x700')
        self.root.minsize(900, 600)
        
        # 设置背景色
        self.root.configure(background=COLORS['bg_main'])
        
        # 全局状态
        self.q = queue.Queue()
        self.worker = None
        self.stop_flag = threading.Event()
        self._all_files = []
        self.single_file_mode = False
        self.write_to_output = True
        self.last_out_dir = None
        self.cache_dir = None
        self.cache_final_dir = None
        self.cache_trash_dir = None
        self.processed_source_files = set()
        self.cache_to_original_map = {}
        self._raw_logs = []
        
        # 输入输出变量
        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=False)
        self.global_remove_src = tk.BooleanVar(value=False)
        self.workers_var = tk.IntVar(value=16)
        
        # 功能开关
        self.enable_convert = tk.BooleanVar(value=False)
        self.enable_dedupe = tk.BooleanVar(value=False)
        self.enable_rename = tk.BooleanVar(value=False)
        self.classify_ratio_var = tk.BooleanVar(value=False)
        self.classify_shape_var = tk.BooleanVar(value=False)
        
        # 格式转换配置
        self.fmt_var = tk.StringVar(value='WebP')
        self.quality_var = tk.IntVar(value=100)
        self.process_same_var = tk.BooleanVar(value=False)
        self.png3_var = tk.BooleanVar(value=False)
        self.ico_sizes_var = tk.StringVar(value='')
        self.ico_keep_orig = tk.BooleanVar(value=False)
        self.ico_square_mode = tk.StringVar(value='fit')
        self.ico_size_vars = {s: tk.BooleanVar(value=(s in (16, 32, 48, 64))) for s in (16, 32, 48, 64, 128, 256)}
        
        # 去重配置
        self.threshold_var = tk.IntVar(value=3)
        self.keep_var = tk.StringVar(value='最大分辨率')
        self.dedup_action_var = tk.StringVar(value='删除重复')
        self.move_dir_var = tk.StringVar()
        
        # 重命名配置
        self.pattern_var = tk.StringVar(value='{name}_{index}.{fmt}')
        self.start_var = tk.IntVar(value=1)
        self.step_var = tk.IntVar(value=1)
        self.index_width_var = tk.IntVar(value=3)
        self.overwrite_var = tk.StringVar(value='覆盖原有')
        
        # 比例分类配置
        self.ratio_tol_var = tk.DoubleVar(value=0.15)
        self.ratio_custom_var = tk.StringVar(value='16:9,3:2,4:3,1:1,21:9')
        self.ratio_snap_var = tk.BooleanVar(value=False)
        
        # 形状分类配置
        self.shape_tolerance_var = tk.DoubleVar(value=0.15)
        self.shape_square_name = tk.StringVar(value='zfx')
        self.shape_horizontal_name = tk.StringVar(value='hp')
        self.shape_vertical_name = tk.StringVar(value='sp')
        
        # 跳过格式配置
        self.skip_formats_enabled = tk.BooleanVar()
        self.skip_convert_only = tk.BooleanVar()
        self.skip_jpeg = tk.BooleanVar()
        self.skip_png = tk.BooleanVar()
        self.skip_webp = tk.BooleanVar()
        self.skip_gif = tk.BooleanVar()
        self.skip_bmp = tk.BooleanVar()
        self.skip_tiff = tk.BooleanVar()
        self.skip_ico = tk.BooleanVar()
        self.skip_custom_var = tk.StringVar()
        
        # 当前页面
        self.current_page = None
        self.pages = {}
        
        self._build_ui()
        self.root.after(200, self._drain)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _build_ui(self):
        # 主容器
        main_container = tk.Frame(self.root, bg=COLORS['bg_main'])
        main_container.pack(fill='both', expand=True)
        
        # 侧边栏
        self._build_sidebar(main_container)
        
        # 内容区
        self.content_area = tk.Frame(main_container, bg=COLORS['bg_main'])
        self.content_area.pack(side='right', fill='both', expand=True)
        
        # 底部状态栏
        self._build_status_bar(main_container)
        
        # 初始化页面
        self._init_pages()
        self._show_page('home')
    
    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=COLORS['bg_sidebar'], width=180)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        
        # Logo区域
        logo_frame = tk.Frame(sidebar, bg=COLORS['bg_sidebar'])
        logo_frame.pack(fill='x', pady=(20, 10), padx=16)
        
        logo_label = tk.Label(logo_frame, text='图片工具', font=('Microsoft YaHei UI', 16, 'bold'),
                             fg=COLORS['text_sidebar_active'], bg=COLORS['bg_sidebar'])
        logo_label.pack(anchor='w')
        
        subtitle = tk.Label(logo_frame, text='批量处理 · 高效简洁', font=('Microsoft YaHei UI', 8),
                           fg=COLORS['text_sidebar'], bg=COLORS['bg_sidebar'])
        subtitle.pack(anchor='w', pady=(2, 0))
        
        ttk.Separator(sidebar, orient='horizontal').pack(fill='x', padx=16, pady=10)
        
        # 菜单项
        self.sidebar_buttons = {}
        for page_id, label in SIDEBAR_ITEMS:
            btn = self._create_sidebar_button(sidebar, page_id, label)
            self.sidebar_buttons[page_id] = btn
            btn.pack(fill='x', padx=8, pady=2)
        
        # 底部输入/输出区域
        ttk.Separator(sidebar, orient='horizontal').pack(fill='x', padx=16, pady=(20, 10))
        
        io_frame = tk.Frame(sidebar, bg=COLORS['bg_sidebar'])
        io_frame.pack(fill='x', padx=12, pady=(0, 10))
        
        # 输入
        tk.Label(io_frame, text='输入路径', font=('Microsoft YaHei UI', 9),
                fg=COLORS['text_sidebar'], bg=COLORS['bg_sidebar']).pack(anchor='w', pady=(0, 4))
        in_frame = tk.Frame(io_frame, bg=COLORS['bg_sidebar'])
        in_frame.pack(fill='x', pady=(0, 10))
        in_entry = tk.Entry(in_frame, textvariable=self.in_var, font=('Microsoft YaHei UI', 8),
                           bg=COLORS['bg_sidebar_hover'], fg='white', relief='flat', insertbackground='white')
        in_entry.pack(side='left', fill='x', expand=True, padx=(0, 4))
        in_entry.configure(width=12)
        btn_in = tk.Button(in_frame, text='...', font=('Microsoft YaHei UI', 8),
                          bg=COLORS['primary'], fg='white', relief='flat',
                          command=self._pick_in, cursor='hand2')
        btn_in.pack(side='right')
        
        # 输出
        tk.Label(io_frame, text='输出路径', font=('Microsoft YaHei UI', 9),
                fg=COLORS['text_sidebar'], bg=COLORS['bg_sidebar']).pack(anchor='w', pady=(0, 4))
        out_frame = tk.Frame(io_frame, bg=COLORS['bg_sidebar'])
        out_frame.pack(fill='x')
        out_entry = tk.Entry(out_frame, textvariable=self.out_var, font=('Microsoft YaHei UI', 8),
                            bg=COLORS['bg_sidebar_hover'], fg='white', relief='flat', insertbackground='white')
        out_entry.pack(side='left', fill='x', expand=True, padx=(0, 4))
        out_entry.configure(width=12)
        btn_out = tk.Button(out_frame, text='...', font=('Microsoft YaHei UI', 8),
                           bg=COLORS['primary'], fg='white', relief='flat',
                           command=self._pick_out, cursor='hand2')
        btn_out.pack(side='right')
        
        # 递归选项
        cb_rec = tk.Checkbutton(io_frame, text='递归子目录', variable=self.recursive_var,
                               font=('Microsoft YaHei UI', 8), fg=COLORS['text_sidebar'],
                               bg=COLORS['bg_sidebar'], selectcolor=COLORS['bg_sidebar_hover'],
                               activebackground=COLORS['bg_sidebar'], activeforeground=COLORS['text_sidebar'])
        cb_rec.pack(anchor='w', pady=(8, 0))
    
    def _create_sidebar_button(self, parent, page_id, label):
        btn = tk.Button(parent, text=label, font=FONTS['sidebar'],
                       bg=COLORS['bg_sidebar'], fg=COLORS['text_sidebar'],
                       relief='flat', anchor='w', padx=12, pady=10,
                       cursor='hand2')
        btn.bind('<Enter>', lambda e, b=btn: b.configure(bg=COLORS['bg_sidebar_hover']))
        btn.bind('<Leave>', lambda e, b=btn, p=page_id: b.configure(
            bg=COLORS['bg_sidebar_active'] if self.current_page == p else COLORS['bg_sidebar']))
        btn.configure(command=lambda p=page_id: self._show_page(p))
        return btn
    
    def _update_sidebar_active(self):
        for page_id, btn in self.sidebar_buttons.items():
            if page_id == self.current_page:
                btn.configure(bg=COLORS['bg_sidebar_active'], fg=COLORS['text_sidebar_active'],
                             font=FONTS['sidebar_active'])
            else:
                btn.configure(bg=COLORS['bg_sidebar'], fg=COLORS['text_sidebar'],
                             font=FONTS['sidebar'])
    
    def _build_status_bar(self, parent):
        status_frame = tk.Frame(parent, bg=COLORS['bg_card'], height=36)
        status_frame.pack(side='bottom', fill='x')
        status_frame.pack_propagate(False)
        
        ttk.Separator(parent, orient='horizontal').pack(side='bottom', fill='x')
        
        self.progress = ttk.Progressbar(status_frame, maximum=100)
        self.progress.pack(side='left', fill='x', expand=True, padx=(12, 8), pady=8)
        
        self.status_var = tk.StringVar(value='就绪')
        status_label = tk.Label(status_frame, textvariable=self.status_var, font=FONTS['body_small'],
                               fg=COLORS['primary'], bg=COLORS['bg_card'])
        status_label.pack(side='right', padx=(0, 12))
    
    def _init_pages(self):
        page_configs = {
            'home': HomePage,
            'pipeline': PipelinePage,
            'convert': ConvertPage,
            'dedupe': DedupePage,
            'rename': RenamePage,
            'classify': ClassifyPage,
        }
        for page_id, page_class in page_configs.items():
            self.pages[page_id] = page_class(self.content_area, self)
    
    def _show_page(self, page_id):
        if self.current_page and self.current_page in self.pages:
            self.pages[self.current_page].pack_forget()
        
        self.current_page = page_id
        self._update_sidebar_active()
        
        if page_id in self.pages:
            self.pages[page_id].pack(fill='both', expand=True)
            self.pages[page_id].on_show()
    
    def _pick_in(self):
        d = filedialog.askdirectory()
        if d:
            self.in_var.set(d)
    
    def _pick_in_file(self):
        f = filedialog.askopenfilename(
            filetypes=[('图片', '*.jpg;*.jpeg;*.png;*.webp;*.gif;*.bmp;*.tiff;*.ico')])
        if f:
            self.in_var.set(f)
    
    def _pick_out(self):
        d = filedialog.askdirectory()
        if d:
            self.out_var.set(d)
    
    def _pick_move_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.move_dir_var.set(d)
    
    def _on_close(self):
        self._clear_cache()
        self.root.destroy()
    
    def _clear_cache(self):
        if self.cache_dir and os.path.exists(self.cache_dir):
            try:
                import shutil
                shutil.rmtree(self.cache_dir)
                self.cache_dir = None
                self.cache_trash_dir = None
                self.cache_final_dir = None
            except Exception:
                pass
    
    def _cancel(self):
        self.stop_flag.set()
        self.status_var.set('请求取消...')
    
    def _ensure_cache_dir(self):
        if self.cache_dir and os.path.exists(self.cache_dir):
            return
        out_dir = self.out_var.get().strip() or os.getcwd()
        self.cache_dir = os.path.join(out_dir, '.preview_cache')
        if os.path.basename(self.cache_dir) == '_final':
            self.cache_dir = os.path.dirname(self.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_trash_dir = os.path.join(self.cache_dir, '_trash')
        os.makedirs(self.cache_trash_dir, exist_ok=True)
        candidate_final = os.path.join(self.cache_dir, '_final')
        if os.path.basename(self.cache_dir) == '_final':
            self.cache_final_dir = self.cache_dir
        else:
            self.cache_final_dir = candidate_final
        if not os.path.exists(self.cache_final_dir):
            os.makedirs(self.cache_final_dir, exist_ok=True)
    
    def _copy_input_to_cache(self, files):
        try:
            cache_input_dir = os.path.join(self.cache_dir, 'input')
            os.makedirs(cache_input_dir, exist_ok=True)
            input_dir = self.in_var.get().strip()
            copied_files = []
            self.cache_to_original_map = {}
            for file_path in files:
                if self.stop_flag.is_set():
                    break
                if self.single_file_mode:
                    relative_path = os.path.basename(file_path)
                else:
                    relative_path = os.path.relpath(file_path, input_dir)
                cache_file_path = os.path.join(cache_input_dir, relative_path)
                os.makedirs(os.path.dirname(cache_file_path), exist_ok=True)
                try:
                    import shutil
                    shutil.copy2(file_path, cache_file_path)
                    copied_files.append(cache_file_path)
                    self.cache_to_original_map[cache_file_path] = file_path
                except Exception as e:
                    self.q.put(f'LOG\tCOPY_INPUT\t{relative_path}\t\t复制失败: {e}')
            if copied_files:
                self.q.put(f'STATUS 已准备 {len(copied_files)} 个文件进行处理')
            return copied_files
        except Exception as e:
            self.q.put(f'LOG\tCOPY_INPUT\t\t\t失败: {e}')
            return files
    
    def _finalize_to_output(self):
        try:
            real_out = self.out_var.get().strip() or self.in_var.get().strip()
            if not real_out or not os.path.exists(self.cache_dir):
                return
            os.makedirs(real_out, exist_ok=True)
            if os.path.exists(real_out):
                for item in os.listdir(real_out):
                    item_path = os.path.join(real_out, item)
                    if item == '.preview_cache':
                        continue
                    try:
                        if os.path.isdir(item_path):
                            import shutil
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except Exception:
                        pass
            source_dir = self.cache_final_dir or self.cache_dir
            file_count = 0
            for root, dirs, files in os.walk(source_dir):
                if '_trash' in root:
                    continue
                for file in files:
                    if self.stop_flag.is_set():
                        break
                    src_path = os.path.join(root, file)
                    if not os.path.isfile(src_path):
                        continue
                    rel_path = os.path.relpath(src_path, source_dir)
                    dest_path = os.path.join(real_out, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    try:
                        import shutil
                        shutil.copy2(src_path, dest_path)
                        file_count += 1
                    except Exception:
                        pass
            remove_info = ""
            if self.global_remove_src.get():
                deleted_count, failed_count = self._remove_source_files()
                if deleted_count > 0 or failed_count > 0:
                    remove_info = f"，删源：删除 {deleted_count} 个，失败 {failed_count} 个"
            return remove_info
        except Exception as e:
            self.q.put(f'LOG\tFINALIZE\t\t\t失败: {e}')
    
    def _remove_source_files(self):
        try:
            input_dir = self.in_var.get().strip()
            if not input_dir or not os.path.exists(input_dir):
                return 0, 0
            original_files = set(self.cache_to_original_map.values())
            deleted_count = 0
            failed_count = 0
            for source_file in original_files:
                if self.stop_flag.is_set():
                    break
                if not os.path.exists(source_file):
                    continue
                try:
                    rel_path = os.path.relpath(source_file, input_dir)
                    if rel_path.startswith('..'):
                        continue
                except ValueError:
                    continue
                try:
                    from src.core.file_ops import safe_delete
                    safe_delete(source_file)
                    deleted_count += 1
                except Exception:
                    failed_count += 1
            return deleted_count, failed_count
        except Exception:
            return 0, 0
    
    def _simulate_delete(self, path):
        try:
            self._ensure_cache_dir()
            if not self.cache_trash_dir:
                return
            os.makedirs(self.cache_trash_dir, exist_ok=True)
            base = os.path.basename(path)
            target = os.path.join(self.cache_trash_dir, base)
            if os.path.exists(target):
                base_no, ext = os.path.splitext(base)
                i = 1
                while os.path.exists(target):
                    target = os.path.join(self.cache_trash_dir, f"{base_no}_{i}{ext}")
                    i += 1
            import shutil
            shutil.move(path, target)
        except Exception:
            pass
    
    def _drain(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m.startswith('HASH '):
                    _, d, total = m.split()
                    d, total = int(d), int(total)
                    self.progress['maximum'] = total
                    self.progress['value'] = d
                    pct = int(d / total * 100) if total else 0
                    self.status_var.set(f'去重哈希 {pct}% ({d}/{total})')
                elif m.startswith('PROG '):
                    _, d, total = m.split()
                    d, total = int(d), int(total)
                    self.progress['maximum'] = total
                    self.progress['value'] = d
                    pct = int(d / total * 100) if total else 0
                    self.status_var.set(f'处理 {pct}% ({d}/{total})')
                elif m.startswith('STATUS '):
                    self.status_var.set(m[7:])
                elif m.startswith('LOG\t'):
                    try:
                        parts = m.split('\t', 4)
                        if len(parts) >= 5:
                            _tag, stage, src, dst, info = parts
                            from src.core.image_ops import STAGE_MAP_DISPLAY
                            stage_disp = STAGE_MAP_DISPLAY.get(stage, stage)
                            log_entry = {
                                'stage': stage,
                                'stage_disp': stage_disp,
                                'src': src,
                                'dst': dst,
                                'info': info,
                            }
                            self._raw_logs.append(log_entry)
                            # 通知当前页面更新日志
                            if self.current_page in self.pages:
                                self.pages[self.current_page].on_log_entry(log_entry)
                    except Exception:
                        pass
        except queue.Empty:
            pass
        finally:
            self.root.after(150, self._drain)
    
    def run(self):
        self.root.mainloop()
