#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
图片工具 - 核心功能模块

这个模块包含所有与UI无关的核心功能实现，包括：
- 图片格式转换（JPG、PNG、WebP、ICO等）
- 重复图片检测（hash算法实现）
- 文件操作和工具函数
- 图片信息管理

这些功能可以被UI模块调用，也可以作为独立库使用。
"""

from __future__ import annotations
import os
import sys
import hashlib
import shutil
from dataclasses import dataclass
from typing import List, Iterable, Dict, Tuple, Optional, Any

# 尝试导入PIL库
try:
    from PIL import Image, ImageSequence, ImageFile
except ImportError:
    Image = None
    ImageFile = None

# Windows 回收站支持 (可选)
try:
    from send2trash import send2trash
except ImportError:
    send2trash = None

# 配置和常量
if ImageFile:
    ImageFile.LOAD_TRUNCATED_IMAGES = True  # 更宽容处理截断图片

SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.ico'}

# 显示名称与内部代码映射
KEEP_MAP = {
    '首个': 'first',
    '最大分辨率': 'largest',
    '最大文件': 'largest-file',
    '最新': 'newest',
    '最旧': 'oldest',
}

ACTION_MAP = {
    '仅列出': 'list',
    '删除重复': 'delete',
    '移动重复': 'move',
}

FMT_MAP = {
    'JPG(JPEG)': 'jpg',
    'PNG': 'png',
    'WebP': 'webp',
    'ICO图标': 'ico',
}

OVERWRITE_MAP = {
    '覆盖原有': 'overwrite',
    '跳过已存在': 'skip',
    '自动改名': 'rename',
}

# 动图压缩方法映射
WEBP_COMPRESSION_MAP = {
    '自动选择': 'auto',
    '无损压缩': 'lossless',
    '高质量': 'high_quality', 
    '标准压缩': 'standard',
    '快速压缩': 'fast',
}

# 日志阶段显示映射
STAGE_MAP_DISPLAY = {
    'DEDUP': '去重',
    'CONVERT': '转换',
    'RENAME': '重命名',
    'CLASSIFY': '分类',
}

def _rev_map(mp: dict) -> dict:
    """
    创建字典的反向映射
    
    Args:
        mp: 原始字典，键值对为 {key: value}
        
    Returns:
        dict: 反向映射字典 {value: key}
    """
    return {v: k for k, v in mp.items()}

def get_webp_params(compression_method: str, quality: Optional[int], 
                    original_frames: int, file_size: int, 
                    conservative_mode: bool) -> dict:
    """
    根据压缩方法和文件特征获取WebP压缩参数
    
    Args:
        compression_method (str): 压缩方法 ('auto', 'lossless', 'high_quality', 'standard', 'fast')
        quality (int): 用户设定的质量值
        original_frames (int): 原始帧数
        file_size (int): 文件大小（字节）
        conservative_mode (bool): 是否使用保守模式
        
    Returns:
        dict: WebP压缩参数
    """
    params = {'quality': quality or 80}
    
    if compression_method == 'lossless':
        # 无损压缩
        params.update({
            'lossless': True,
            'method': 6,  # 最佳压缩方法
            'exact': True
        })
    elif compression_method == 'high_quality':
        # 高质量压缩
        params.update({
            'quality': 100,
            'method': 6,
            'lossless': False,
            'exact': True
        })
    elif compression_method == 'fast':
        # 快速压缩
        params.update({
            'quality': max(70, quality or 80),
            'method': 0,  # 最快方法
            'lossless': False
        })
    elif compression_method == 'standard':
        # 标准压缩
        params.update({
            'quality': quality or 80,
            'method': 4,  # 平衡方法
            'lossless': False
        })
    elif compression_method == 'auto':
        # 自动选择（原有逻辑）
        if original_frames > 100 or file_size > 10*1024*1024:
            params.update({
                'lossless': True,
                'method': 6,
                'exact': True
            })
        elif original_frames > 50:
            params.update({
                'quality': 100,
                'method': 6,
                'lossless': False,
                'exact': True
            })
        else:
            params.update({
                'quality': quality or 80,
                'method': 4,
                'lossless': False
            })
    
    # 通用动画参数
    params.update({
        'save_all': True,
        'minimize_size': False  # 确保帧完整性
    })
    
    return params

def iter_images(root: str, recursive: bool, skip_formats: set = None) -> Iterable[str]:
    """
    遍历指定目录中的所有图片文件
    
    使用PIL检测实际文件格式而非仅依赖扩展名，确保准确识别图片文件。
    支持跳过指定格式和递归/非递归遍历。
    
    Args:
        root: 要扫描的根目录路径
        recursive: 是否递归扫描子目录
        skip_formats: 要跳过的图片格式集合，如 {'JPEG', 'PNG'}
        
    Yields:
        str: 有效图片文件的完整路径
    """
    if skip_formats is None:
        skip_formats = set()
    
    for dirpath, dirs, files in os.walk(root):
        for f in files:
            filepath = os.path.join(dirpath, f)
            # 首先检查扩展名是否可能是图片
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXT:
                # 使用PIL检测实际文件格式
                try:
                    with Image.open(filepath) as img:
                        file_format = img.format
                        if file_format and file_format.upper() not in skip_formats:
                            yield filepath
                except (IOError, OSError):
                    # 文件损坏或不是有效图片，跳过
                    continue
            # 如果没有图片扩展名，但启用了格式检测，也尝试用PIL打开
            else:
                try:
                    with Image.open(filepath) as img:
                        file_format = img.format
                        if file_format and file_format.upper() not in skip_formats:
                            yield filepath
                except (IOError, OSError):
                    # 不是图片文件，跳过
                    continue
        if not recursive:
            break

def norm_ext(path: str) -> str:
    """
    标准化文件扩展名
    
    将文件路径的扩展名转换为小写，并将jpeg统一为jpg
    
    Args:
        path: 文件路径
        
    Returns:
        str: 标准化后的扩展名（不含点号）
    """
    e = os.path.splitext(path)[1].lower().lstrip('.')
    return 'jpg' if e == 'jpeg' else e

def next_non_conflict(path: str) -> str:
    """
    生成不冲突的文件路径
    
    如果目标路径已存在文件，自动在文件名后添加数字后缀避免冲突
    
    Args:
        path: 原始文件路径
        
    Returns:
        str: 不冲突的文件路径（如 file_1.jpg, file_2.jpg 等）
    """
    base, ext = os.path.splitext(path); i = 1
    while os.path.exists(path):
        path = f"{base}_{i}{ext}"; i += 1
    return path

def safe_delete(path: str) -> Tuple[bool, str]:
    """
    安全删除文件
    
    优先尝试将文件移动到系统回收站，如果失败则直接删除。
    提供详细的操作结果反馈。
    
    Args:
        path: 要删除的文件路径
        
    Returns:
        tuple: (成功标志, 操作描述)
            - (True, "删除->回收站") - 成功移动到回收站
            - (True, "删除") - 直接删除成功
            - (False, "删除失败: 权限不足") - 权限不足
            - (False, "删失败: 错误详情") - 其他错误
    """
    if send2trash is not None:
        try:
            send2trash(path)
            return True, '删除->回收站'
        except Exception as e:
            # 回退到直接删除
            try:
                os.remove(path)
                return True, f'删除(回收站失败:{e})'
            except PermissionError as e2:
                return False, f'删除失败: 权限不足'
            except Exception as e2:
                return False, f'删失败:{e2}'
    try:
        os.remove(path); return True, '删除'
    except PermissionError as e:
        return False, f'删除失败: 权限不足'
    except Exception as e:
        return False, f'删失败:{e}'

def ahash(im) -> int:
    """
    计算图片的平均哈希值（Average Hash）
    
    平均哈希算法：将图片缩放为8x8灰度图，计算像素均值，
    根据每个像素是否大于均值生成64位哈希值。
    适用于检测相似图片，对轻微的颜色和亮度变化不敏感。
    
    Args:
        im: PIL Image对象
        
    Returns:
        int: 64位哈希值
    """
    im = im.convert('L').resize((8, 8))
    avg = sum(im.getdata()) / 64.0
    bits = 0
    for i, p in enumerate(im.getdata()):
        if p >= avg: bits |= 1 << i
    return bits

def dhash(im) -> int:
    """
    计算图片的差分哈希值（Difference Hash）
    
    差分哈希算法：将图片缩放为9x8灰度图，比较相邻像素的亮度差异，
    生成64位哈希值。相比平均哈希对图片的裁剪和缩放更敏感，
    但对渐变和纹理变化的检测效果更好。
    
    Args:
        im: PIL Image对象
        
    Returns:
        int: 64位哈希值
    """
    im = im.convert('L').resize((9, 8))
    pixels = list(im.getdata())
    bits = 0; idx = 0
    for r in range(8):
        row = pixels[r*9:(r+1)*9]
        for c in range(8):
            if row[c] > row[c+1]: bits |= 1 << idx
            idx += 1
    return bits

def hamming(a: int, b: int) -> int:
    """
    计算两个整数的汉明距离（Hamming Distance）
    
    汉明距离表示两个二进制数不同位的数量。
    在图片相似度检测中，汉明距离越小表示图片越相似。
    
    Args:
        a: 第一个整数（通常是图片哈希值）
        b: 第二个整数（通常是图片哈希值）
        
    Returns:
        int: 汉明距离（0-64，哈希值为64位时）
    """
    return (a ^ b).bit_count()

def _fmt_size(n: int) -> str:
    """
    将字节数格式化为人类可读的文件大小
    
    自动选择合适的单位（B、KB、MB、GB、TB）并保留适当的小数位数。
    
    Args:
        n: 文件大小（字节）
        
    Returns:
        str: 格式化的文件大小字符串，如 "1.5MB"、"234KB"
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    f = float(n); i = 0
    while f >= 1024 and i < len(units) - 1:
        f /= 1024; i += 1
    return (f'{f:.2f}{units[i]}' if i > 0 else f'{int(f)}{units[i]}')

def convert_one(src: str, dst: str, fmt: str, quality: Optional[int] = None, 
                png3: bool = False, ico_sizes: Optional[List[int]] = None, 
                square_mode: Optional[str] = None, 
                webp_compression: str = 'auto') -> Tuple[bool, str, Optional[str]]:
    """
    转换单个图片文件格式
    
    支持多种图片格式转换，包括特殊处理逻辑：
    - JPG转换时自动处理透明通道（转为白色背景）
    - ICO转换时支持多种尺寸和方形处理模式
    - GIF保持动画帧、持续时间和循环信息
    - WebP支持动画帧、质量控制和循环信息（自动检测动画图片）
    - PNG支持调色板模式和APNG动画格式（保持动画帧和时间信息）
    
    Args:
        src (str): 源文件路径
        dst (str): 目标文件路径
        fmt (str): 目标格式 ('jpg', 'png', 'webp', 'ico', 'gif')
        quality (int, optional): 压缩质量 (1-100)，适用于JPG和WebP
        png3 (bool): 是否使用PNG3.0规范进行优化（应用特殊的调色板和压缩参数，支持静态和动画图片）
        ico_sizes (list, optional): ICO图标尺寸列表，如 [16, 32, 48]
        square_mode (str, optional): ICO方形处理模式
            - 'center': 居中裁剪为方形
            - 'topleft': 左上角裁剪为方形  
            - 'fit': 填充为方形（保持原图完整）
            - 'keep': 保持原始比例
        webp_compression (str): WebP压缩方法
            - 'auto': 自动选择（默认）
            - 'lossless': 无损压缩
            - 'high_quality': 高质量压缩
            - 'standard': 标准压缩
            - 'fast': 快速压缩
            
    Returns:
        tuple: (是否成功, 结果描述, 实际使用的压缩方法)
            - (True, 'OK', method) - 转换成功
            - (False, 错误信息, None) - 转换失败，包含详细错误信息
            
    Note:
        支持的动画格式互转：GIF ↔ WebP ↔ APNG
        动画转换时会尝试保持原始的帧数、持续时间和循环设置
        针对大文件和高帧数动画进行了优化，包含帧数验证机制
        当帧数不一致时会自动尝试其他压缩方法
        返回值增加了实际使用的压缩方法信息，用于日志记录
    """
    import psutil
    
    try:
        # 检查文件大小
        file_size = os.path.getsize(src)
        
        # 检查可用内存
        available_memory = psutil.virtual_memory().available
        
        # 对于大文件（>50MB）或内存不足的情况，启用保守模式
        conservative_mode = file_size > 50 * 1024 * 1024 or available_memory < 500 * 1024 * 1024
        
        with Image.open(src) as im:
            # 检测动画信息
            is_animated = hasattr(im, 'is_animated') and im.is_animated
            original_frames = getattr(im, 'n_frames', 1) if is_animated else 1
            
            # 对于高帧数动画，记录详细信息用于验证
            if is_animated and original_frames > 100:
                print(f"处理高帧数动画: {original_frames}帧, 文件大小: {file_size/1024/1024:.1f}MB")
            
            if fmt == 'ico':
                w, h = im.size
                if w != h and square_mode and square_mode != 'keep':
                    if square_mode == 'center':
                        side = min(w, h); left = (w-side)//2; top = (h-side)//2
                        im = im.crop((left, top, left+side, top+side))
                    elif square_mode == 'topleft':
                        side = min(w, h); im = im.crop((0, 0, side, side))
                    elif square_mode == 'fit':  # 填充
                        side = max(w, h)
                        canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
                        x = (side-w)//2; y = (side-h)//2
                        canvas.paste(im, (x, y))
                        im = canvas
            
            if fmt == 'gif':
                # GIF格式：保持动画和循环信息
                save_params = {}
                if is_animated:
                    save_params['save_all'] = True
                    save_params['optimize'] = False  # 对于大文件禁用优化以确保帧完整性
                    
                    # 保留原始动画的持续时间和循环信息
                    try:
                        if hasattr(im, 'info'):
                            if 'duration' in im.info:
                                save_params['duration'] = im.info['duration']
                            if 'loop' in im.info:
                                save_params['loop'] = im.info['loop']
                    except Exception:
                        pass
                        
                    # 对于高帧数动画，使用更保守的参数
                    if original_frames > 200 or conservative_mode:
                        save_params['optimize'] = False
                        save_params['disposal'] = 2  # 恢复到背景颜色
                
                im.save(dst, **save_params)
                
            elif fmt == 'ico':
                im.save(dst, sizes=[(s, s) for s in (ico_sizes or [256])])
                
            else:
                params = {}
                if fmt == 'jpg':
                    params['quality'] = quality or 100
                    if im.mode in ('RGBA', 'LA'):
                        bg = Image.new('RGB', im.size, (255, 255, 255))
                        bg.paste(im, mask=im.split()[-1])
                        im = bg
                    else:
                        im = im.convert('RGB')
                        
                elif fmt == 'png':
                    # PNG格式：支持APNG（动画PNG）
                    if is_animated:
                        params['save_all'] = True
                        
                        # 保留动画信息
                        try:
                            if hasattr(im, 'info'):
                                if 'duration' in im.info:
                                    params['duration'] = im.info['duration']
                                if 'loop' in im.info:
                                    params['loop'] = im.info['loop']
                        except Exception:
                            pass
                                 
                        # 对于高帧数APNG，使用特殊设置
                        if original_frames > 100 or conservative_mode:
                            params['compress_level'] = 1  # 低压缩级别，保证速度和稳定性
                        
                        # 使用PNG3.0规范进行优化处理（支持动图）
                        if png3:
                            # 动画PNG使用适中的压缩参数，保证质量和速度平衡
                            params['optimize'] = True
                            params['compress_level'] = 4  # 动图使用较低压缩级别以保证稳定性
                    
                    elif png3:
                        # 静态图片使用PNG3.0规范进行优化处理
                        # 转换为P模式并使用自适应调色板
                        im = im.convert('P', palette=Image.ADAPTIVE, colors=256)
                        # 添加PNG3.0特定的压缩优化参数
                        params['optimize'] = True
                        params['compress_level'] = 6  # PNG3.0推荐的压缩级别
                        # 确保保留透明度信息
                        if 'transparency' in im.info:
                            params['transparency'] = im.info['transparency']
                        
                elif fmt == 'webp':
                    # WebP格式：支持动画和多种压缩方法
                    used_method = webp_compression  # 记录实际使用的方法
                    
                    if is_animated:
                        # 定义备用压缩方法顺序（按安全性和效果排序）
                        fallback_methods = ['lossless', 'high_quality', 'standard', 'fast']
                        
                        # 如果用户选择了具体方法，先尝试该方法
                        if webp_compression != 'auto' and webp_compression in fallback_methods:
                            methods_to_try = [webp_compression] + [m for m in fallback_methods if m != webp_compression]
                        else:
                            # 自动模式或无效方法，使用默认顺序
                            methods_to_try = ['auto'] + fallback_methods
                            
                        success = False
                        last_error = None
                        tried_methods = []  # 记录尝试过的方法
                        
                        for method in methods_to_try:
                            tried_methods.append(method)
                            try:
                                params = get_webp_params(method, quality, original_frames, file_size, conservative_mode)
                                
                                # 保留动画的时间间隔和循环信息
                                try:
                                    if hasattr(im, 'info'):
                                        if 'duration' in im.info:
                                            duration = im.info['duration']
                                            if isinstance(duration, (list, tuple)):
                                                params['duration'] = duration
                                            else:
                                                params['duration'] = max(1, int(duration))
                                        if 'loop' in im.info:
                                            params['loop'] = im.info['loop']
                                except Exception:
                                    pass
                                
                                # 尝试保存
                                im.save(dst, 'WEBP', **params)
                                
                                # 验证帧数
                                with Image.open(dst) as result_im:
                                    result_frames = getattr(result_im, 'n_frames', 1) if getattr(result_im, 'is_animated', False) else 1
                                    
                                    if result_frames == original_frames:
                                        method_name = {
                                            'auto': '自动选择',
                                            'lossless': '无损压缩', 
                                            'high_quality': '高质量',
                                            'standard': '标准压缩',
                                            'fast': '快速压缩'
                                        }.get(method, method)
                                        
                                        used_method = method  # 记录成功的方法
                                        print(f"WebP转换成功: 使用{method_name}方法，保持{original_frames}帧")
                                        success = True
                                        break
                                    else:
                                        method_name = {
                                            'auto': '自动选择',
                                            'lossless': '无损压缩', 
                                            'high_quality': '高质量',
                                            'standard': '标准压缩',
                                            'fast': '快速压缩'
                                        }.get(method, method)
                                        print(f"WebP {method_name}方法帧数不一致: {original_frames} -> {result_frames}，尝试下一种方法")
                                        last_error = f"帧数不一致: 原始{original_frames}帧 -> 结果{result_frames}帧"
                                        
                            except Exception as e:
                                method_name = {
                                    'auto': '自动选择',
                                    'lossless': '无损压缩', 
                                    'high_quality': '高质量',
                                    'standard': '标准压缩',
                                    'fast': '快速压缩'
                                }.get(method, method)
                                print(f"WebP {method_name}方法失败: {e}，尝试下一种方法")
                                last_error = str(e)
                                continue
                            
                        if not success:
                            # 所有WebP方法都失败，尝试手动帧处理作为最后的努力
                            print(f"WebP方法都失败，尝试手动帧处理...")
                            try:
                                # 手动收集所有帧
                                frames = []
                                durations = []
                                
                                for frame in ImageSequence.Iterator(im):
                                    # 转换为RGB避免模式问题
                                    if frame.mode != 'RGB':
                                        frame_rgb = frame.convert('RGB')
                                    else:
                                        frame_rgb = frame.copy()
                                    frames.append(frame_rgb)
                                    
                                    # 修复持续时间
                                    duration = frame.info.get('duration', 100)
                                    durations.append(max(duration, 1))
                                
                                # 如果收集的帧数正确，尝试手动保存
                                if len(frames) == original_frames:
                                    frames[0].save(
                                        dst,
                                        'WEBP',
                                        save_all=True,
                                        append_images=frames[1:],
                                        duration=100,  # 使用固定持续时间
                                        loop=0,
                                        lossless=True,
                                        method=6
                                    )
                                    
                                    # 再次验证
                                    with Image.open(dst) as result_im:
                                        result_frames = getattr(result_im, 'n_frames', 1)
                                        if result_frames == original_frames:
                                            print(f"手动帧处理成功: {original_frames}帧")
                                            used_method = 'manual_frame_processing'
                                            success = True
                                        else:
                                            print(f"手动帧处理仍有问题: {original_frames} -> {result_frames}")
                                
                            except Exception as manual_error:
                                print(f"手动帧处理失败: {manual_error}")
                            
                            if not success:
                                # 记录尝试过的所有方法
                                tried_methods_str = ', '.join([{
                                    'auto': '自动选择',
                                    'lossless': '无损压缩', 
                                    'high_quality': '高质量',
                                    'standard': '标准压缩',
                                    'fast': '快速压缩'
                                }.get(m, m) for m in tried_methods])
                                
                                # 最终备用方案：提示用户WebP可能不适合此文件
                                return False, f"WebP转换失败(已尝试: {tried_methods_str}): {last_error}。建议改用PNG(APNG)或GIF格式", None
                            
                    else:
                        # 静态图片
                        params = {'quality': quality or 80}
                        im.save(dst, 'WEBP', **params)
                
                # 修复Pillow格式名称映射并保存（非WebP动画）
                if not (fmt == 'webp' and is_animated):
                    pillow_fmt = fmt.upper()
                    if pillow_fmt == 'JPG':
                        pillow_fmt = 'JPEG'
                    im.save(dst, pillow_fmt, **params)
            
        # 验证转换结果的帧数（仅对动画）
        if is_animated and original_frames > 1:
            try:
                with Image.open(dst) as result_im:
                    result_frames = getattr(result_im, 'n_frames', 1) if getattr(result_im, 'is_animated', False) else 1
                    
                    if result_frames != original_frames:
                        return False, f"帧数不一致: 原始{original_frames}帧 -> 结果{result_frames}帧", None
                    elif original_frames > 100:
                        # 对于高帧数动画，返回详细信息
                        return True, f"OK ({original_frames}帧)", used_method
            except Exception as e:
                # 如果验证失败，记录但不影响主流程
                print(f"帧数验证失败: {e}")
            
        return True, 'OK', used_method
        
    except MemoryError as e:
        return False, f"内存不足，文件过大: {str(e)}", None
    except PermissionError as e:
        return False, f"权限不足: {str(e)}", None
    except Exception as e:
        import traceback
        # 返回详细的错误信息，包含异常类型和堆栈
        error_detail = f"{type(e).__name__}: {str(e)}"
        # 添加关键的堆栈信息（最后几行）
        tb_lines = traceback.format_exc().strip().split('\n')
        if len(tb_lines) > 2:
            # 取最后的错误行
            error_detail += f" | {tb_lines[-2].strip()}"
        return False, error_detail, None

@dataclass
class ImgInfo:
    """
    图片信息数据类
    
    存储图片的基本信息和哈希值，用于去重检测和文件管理。
    
    Attributes:
        path (str): 图片文件的完整路径
        size (int): 文件大小（字节）
        w (int): 图片宽度（像素）
        h (int): 图片高度（像素）
        ah (int): 平均哈希值（Average Hash）
        dh (int): 差分哈希值（Difference Hash）
        mtime (float): 文件修改时间戳
    """
    path: str; size: int; w: int; h: int; ah: int; dh: int; mtime: float
    
    @property
    def res(self) -> int:
        """
        计算图片分辨率（总像素数）
        
        Returns:
            int: 宽度 × 高度的像素总数
        """
        return self.w * self.h

def is_animated_image(path: str) -> bool:
    """
    检测图片是否为动图 (GIF, WebP, APNG)
    
    Args:
        path: 图片文件路径
        
    Returns:
        bool: 是否为动图
    """
    try:
        with Image.open(path) as im:
            # 检查是否有多帧
            if hasattr(im, 'is_animated') and im.is_animated:
                return True
            
            # 对于一些较老版本的PIL，手动检查帧数
            if im.format in ('GIF', 'WEBP'):
                try:
                    im.seek(1)  # 尝试移动到第二帧
                    return True
                except (AttributeError, EOFError):
                    pass
            
            # 检查PNG是否为APNG (动态PNG)
            if im.format == 'PNG':
                # APNG会有特殊的chunk标识
                if hasattr(im, 'info') and 'transparency' in im.info:
                    # 简单检查，更完整的检查需要解析PNG chunk
                    try:
                        frames = list(ImageSequence.Iterator(im))
                        return len(frames) > 1
                    except:
                        pass
            
        return False
    except Exception:
        return False

# 确保PIL库可用的检查函数
def check_dependencies() -> Tuple[bool, str]:
    """
    检查必要的依赖库是否可用
    
    Returns:
        tuple: (是否成功, 错误信息)
    """
    errors = []
    
    if Image is None:
        errors.append("缺少PIL/Pillow库")
    
    if errors:
        return False, ", ".join(errors)
    
    return True, "依赖库检查通过"

# 添加这个函数以便在模块导入时进行基本验证
_dependency_check_passed, _dependency_check_message = check_dependencies()

if __name__ == '__main__':
    # 简单的测试函数
    if not _dependency_check_passed:
        print(f"错误: {_dependency_check_message}")
        print("请使用 pip install pillow send2trash 安装依赖库")
        sys.exit(1)
    
    print("图片工具核心功能模块已加载成功！")
    # 可以添加简单的命令行功能测试
    import argparse
    parser = argparse.ArgumentParser(description='图片工具核心功能测试')
    parser.add_argument('--test-hash', type=str, help='测试图片哈希计算')
    
    args = parser.parse_args()
    
    if args.test_hash:
        try:
            with Image.open(args.test_hash) as img:
                a_hash = ahash(img)
                d_hash = dhash(img)
                print(f"图片: {args.test_hash}")
                print(f"平均哈希 (ahash): {a_hash:016x}")
                print(f"差分哈希 (dhash): {d_hash:016x}")
        except Exception as e:
            print(f"哈希计算失败: {e}")