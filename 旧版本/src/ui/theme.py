"""主题配置 - 蓝白配色，干净简洁"""

# 颜色方案
COLORS = {
    'primary': '#2563EB',        # 主蓝色
    'primary_hover': '#1D4ED8',  # 主色悬停
    'primary_light': '#DBEAFE',  # 浅蓝背景
    'bg_main': '#F8FAFC',        # 主背景
    'bg_card': '#FFFFFF',        # 卡片背景
    'bg_sidebar': '#1E293B',     # 侧边栏深色
    'bg_sidebar_hover': '#334155',
    'bg_sidebar_active': '#2563EB',
    'text_primary': '#0F172A',   # 主文字
    'text_secondary': '#64748B', # 次要文字
    'text_sidebar': '#CBD5E1',   # 侧边栏文字
    'text_sidebar_active': '#FFFFFF',
    'border': '#E2E8F0',         # 边框
    'success': '#10B981',        # 成功绿
    'warning': '#F59E0B',        # 警告橙
    'error': '#EF4444',          # 错误红
    'log_dedupe': '#FFF5E6',     # 去重日志背景
    'log_convert': '#DBEAFE',    # 转换日志背景
    'log_rename': '#EDE9FE',     # 重命名日志背景
    'log_classify': '#D1FAE5',   # 分类日志背景
    'log_delete': '#FEE2E2',     # 删除日志背景
}

# 字体配置
FONTS = {
    'title': ('Microsoft YaHei UI', 14, 'bold'),
    'subtitle': ('Microsoft YaHei UI', 11, 'bold'),
    'body': ('Microsoft YaHei UI', 10),
    'body_small': ('Microsoft YaHei UI', 9),
    'log': ('Consolas', 9),
    'sidebar': ('Microsoft YaHei UI', 11),
    'sidebar_active': ('Microsoft YaHei UI', 11, 'bold'),
}

# 间距配置
SPACING = {
    'xs': 4,
    'sm': 8,
    'md': 12,
    'lg': 16,
    'xl': 24,
}

# 圆角配置
RADIUS = {
    'sm': 6,
    'md': 8,
    'lg': 12,
}

# 侧边栏菜单项
SIDEBAR_ITEMS = [
    ('home', '🏠  首页'),
    ('pipeline', '⚡  一条龙模式'),
    ('convert', '🔄  格式转换'),
    ('dedupe', '🔍  重复检测'),
    ('rename', '✏️  批量重命名'),
    ('classify', '📁  分类整理'),
]
