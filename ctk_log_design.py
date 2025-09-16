"""
CTk 日志/预览区域替代方案设计

当前结构：
- ttk.PanedWindow (垂直分割)
  ├── 上部：ttk.Frame (日志区域)
  │   ├── ttk.Treeview (日志表格)
  │   └── ttk.Scrollbar (滚动条)
  └── 下部：ttk.Frame (预览区域)
      └── ttk.LabelFrame (前后对比)
          ├── 左侧：源图片预览
          └── 右侧：结果图片预览

CTk 替代方案：
- CTkFrame (主容器)
  ├── 上部：CTkFrame (日志区域)
  │   ├── CTkScrollableFrame (可滚动日志容器)
  │   │   └── 自定义日志行组件 (CTkFrame + CTkLabel)
  │   └── 过滤控制栏 (CTkFrame)
  └── 下部：CTkFrame (预览区域)
      ├── 左侧：CTkFrame (源图片)
      └── 右侧：CTkFrame (结果图片)

核心组件设计：
1. CTkLogView - 自定义日志视图组件
2. CTkLogRow - 单行日志显示组件  
3. CTkPreviewFrame - 预览区域组件
4. CTkResizableContainer - 可调整大小的容器
"""

# CTk 日志视图组件设计
class CTkLogView:
    """
    基于 CTkScrollableFrame 的自定义日志视图
    
    功能需求：
    1. 显示多列数据 (阶段、源、目标、信息)
    2. 支持行选择和高亮
    3. 支持颜色标记 (基于阶段类型)
    4. 支持过滤功能
    5. 支持滚动显示
    6. 支持事件绑定 (选择、双击)
    
    实现方案：
    - 使用 CTkScrollableFrame 作为容器
    - 每行使用 CTkFrame + 多个 CTkLabel 实现
    - 自定义选择逻辑和颜色管理
    """
    
    def __init__(self, parent):
        self.parent = parent
        self.selected_row = None
        self.rows = []
        self.row_data = []
        
        # 主容器
        self.main_frame = ctk.CTkFrame(parent)
        
        # 表头
        self.header_frame = ctk.CTkFrame(self.main_frame)
        self.header_frame.pack(fill='x', padx=2, pady=2)
        
        # 列宽定义
        self.columns = [
            ('stage', '阶段', 70),
            ('src', '源', 180), 
            ('dst', '目标/组', 180),
            ('info', '信息', 150)
        ]
        
        # 创建表头
        self._create_header()
        
        # 可滚动内容区域
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame)
        self.scroll_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        # 配置网格权重
        for i, (_, _, width) in enumerate(self.columns):
            self.scroll_frame.grid_columnconfigure(i, weight=1, minsize=width)
    
    def _create_header(self):
        """创建表头"""
        for i, (_, text, width) in enumerate(self.columns):
            label = ctk.CTkLabel(
                self.header_frame, 
                text=text,
                font=ctk.CTkFont(weight="bold"),
                fg_color=("gray90", "gray20")
            )
            label.grid(row=0, column=i, sticky='ew', padx=1, pady=1)
            self.header_frame.grid_columnconfigure(i, weight=1, minsize=width)
    
    def add_row(self, values, tags=None):
        """添加一行数据"""
        row_frame = CTkLogRow(self.scroll_frame, values, tags, self._on_row_select)
        row_frame.grid(row=len(self.rows), column=0, columnspan=len(self.columns), 
                      sticky='ew', padx=1, pady=1)
        
        self.rows.append(row_frame)
        self.row_data.append((values, tags))
        
        return row_frame
    
    def _on_row_select(self, row_frame):
        """处理行选择"""
        # 取消之前的选择
        if self.selected_row:
            self.selected_row.set_selected(False)
        
        # 设置新选择
        self.selected_row = row_frame
        row_frame.set_selected(True)
        
        # 触发选择事件
        if hasattr(self, 'on_select_callback'):
            self.on_select_callback(row_frame)
    
    def clear(self):
        """清空所有行"""
        for row in self.rows:
            row.destroy()
        self.rows.clear()
        self.row_data.clear()
        self.selected_row = None
    
    def filter_rows(self, filter_func):
        """根据过滤函数显示/隐藏行"""
        for i, row in enumerate(self.rows):
            values, tags = self.row_data[i]
            if filter_func(values, tags):
                row.grid()
            else:
                row.grid_remove()


class CTkLogRow:
    """单行日志显示组件"""
    
    def __init__(self, parent, values, tags, select_callback):
        self.parent = parent
        self.values = values
        self.tags = tags
        self.select_callback = select_callback
        self.selected = False
        
        # 行容器
        self.frame = ctk.CTkFrame(parent, height=25)
        
        # 根据标签设置颜色
        self._set_colors()
        
        # 创建列标签
        self.labels = []
        for i, value in enumerate(values):
            label = ctk.CTkLabel(
                self.frame,
                text=str(value),
                anchor='w',
                height=20
            )
            label.grid(row=0, column=i, sticky='ew', padx=2)
            self.labels.append(label)
            
            # 绑定点击事件
            label.bind("<Button-1>", self._on_click)
        
        # 绑定框架点击事件
        self.frame.bind("<Button-1>", self._on_click)
    
    def _set_colors(self):
        """根据标签设置颜色"""
        stage_colors = {
            'STAGE_DEDUPE': ("#FFF5E6", "#4A3700"),      # 淡橙
            'STAGE_CONVERT': ("#E6F5FF", "#003A4A"),     # 淡蓝
            'STAGE_RENAME': ("#F0E6FF", "#3D0047"),      # 淡紫
            'STAGE_CLASSIFY': ("#E6FFE6", "#004700"),    # 淡绿
            'STAGE_DELETE': ("#FFE6E6", "#4A0000"),      # 淡红
            'STAGE_MOVE': ("#E6FFE6", "#004700"),        # 淡绿
            'STAGE_KEEP': ("#F5F5F5", "#2A2A2A"),        # 灰白
            'STAGE_INFO': ("#EEEEEE", "#2A2A2A"),        # 信息行
        }
        
        if self.tags and len(self.tags) >= 3:
            stage_tag = self.tags[2]
            if stage_tag in stage_colors:
                bg_color, text_color = stage_colors[stage_tag]
                self.frame.configure(fg_color=bg_color)
    
    def _on_click(self, event=None):
        """处理点击事件"""
        self.select_callback(self)
    
    def set_selected(self, selected):
        """设置选择状态"""
        self.selected = selected
        if selected:
            self.frame.configure(border_width=2, border_color="#1f6aa5")
        else:
            self.frame.configure(border_width=0)
    
    def grid(self, **kwargs):
        """显示行"""
        self.frame.grid(**kwargs)
    
    def grid_remove(self):
        """隐藏行"""
        self.frame.grid_remove()
    
    def destroy(self):
        """销毁行"""
        self.frame.destroy()


# 使用示例和测试代码
if __name__ == "__main__":
    import customtkinter as ctk
    
    ctk.set_appearance_mode("light")
    
    root = ctk.CTk()
    root.title("CTk日志视图测试")
    root.geometry("800x600")
    
    # 创建日志视图
    log_view = CTkLogView(root)
    log_view.main_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
    # 添加测试数据
    test_data = [
        (("转换", "image1.jpg", "image1.png", "成功"), ("src1", "dst1", "STAGE_CONVERT")),
        (("重命名", "image2.jpg", "IMG_001.jpg", "完成"), ("src2", "dst2", "STAGE_RENAME")),
        (("去重", "duplicate.jpg", "组1", "删除"), ("src3", "dst3", "STAGE_DEDUPE")),
        (("分类", "photo.jpg", "横向", "移动"), ("src4", "dst4", "STAGE_CLASSIFY")),
    ]
    
    for values, tags in test_data:
        log_view.add_row(values, tags)
    
    root.mainloop()