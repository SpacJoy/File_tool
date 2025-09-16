# -*- coding: utf-8 -*-
"""
文件内容对比工具 - 主入口文件

这个文件是文件内容对比工具的主入口点，负责导入和启动UI模块。
主要功能包括：
- 单文件内容对比（支持PDF、Word、XLSX、PPT、Markdown等多种格式）
- 目录结构和内容对比
- 文件预览功能
- 差异高亮显示
- 对比报告生成

项目结构:
- file_diff_core.py: 核心功能实现（与UI无关）
- file_diff_ui.py: 用户界面实现
- 文件内容对比.py: 主入口文件

具有友好的Win11风格图形界面和详细的操作提示。
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
    from file_diff_ui import launch
    
except ImportError as e:
    # 处理导入错误，给出友好提示
    print(f"导入错误: {e}")
    print("\n请确保已安装所有必要的依赖库。\n")
    print("推荐安装命令:")
    print("pip install pillow pypdf2 python-docx pandas python-pptx markdown")
    input("按Enter键退出...")
    sys.exit(1)

def main():
    """主函数"""
    try:
        # 启动应用程序
        launch()
    except Exception as e:
        print(f"应用程序异常: {e}")
        import traceback
        traceback.print_exc()
        input("按Enter键退出...")
        sys.exit(2)

if __name__ == '__main__':
    main()
    