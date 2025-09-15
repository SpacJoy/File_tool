
# -*- coding: utf-8 -*-
"""
图片工具 - 主入口文件

这个文件是图片工具的主入口点，负责导入和启动UI模块。
主要功能包括：
- 图片格式转换（JPG、PNG、WebP、ICO等）
- 重复图片检测与去重（支持hash算法）
- 批量图片重命名（支持多种命名模式）
- 图片分类整理（按分辨率、格式等）
- 实时预览与处理进度显示

项目结构:
- image_tools_core.py: 核心功能实现（与UI无关）
- image_tools_ui.py: 用户界面实现
- 图片工具.py: 主入口文件

支持多线程处理，具有友好的图形界面和详细的操作日志。
"""

# 尝试导入必要的依赖库
try:
    import sys
    import os
    # 确保当前目录在Python路径中
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    
    # 导入UI模块并启动应用
    from image_tools_ui import launch
    
except ImportError as e:
    # 处理导入错误，给出友好提示
    print(f"导入错误: {e}")
    print("\n请确保已安装所有必要的依赖库。\n")
    print("推荐安装命令:")
    print("pip install pillow send2trash")
    input("按Enter键退出...")
    sys.exit(1)

def main():
    """主函数"""
    try:
        # 启动应用程序
        exit_code = launch()
        sys.exit(exit_code)
    except Exception as e:
        print(f"应用程序异常: {e}")
        import traceback
        traceback.print_exc()
        input("按Enter键退出...")
        sys.exit(2)

if __name__ == '__main__':
    main()
