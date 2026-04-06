"""图片工具 - 新版入口"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
except Exception:
    tk = None

try:
    from PIL import Image
except Exception:
    Image = None


def launch():
    if tk is None or Image is None:
        print('缺少 Tkinter 或 Pillow，请先安装依赖: pip install pillow')
        return 2
    
    from src.ui.main_window import MainWindow
    app = MainWindow()
    app.run()
    return 0


if __name__ == '__main__':
    launch()
