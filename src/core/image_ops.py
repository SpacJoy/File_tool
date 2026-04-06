"""图片工具 - 核心图片操作模块"""
import os
from PIL import Image, ImageSequence, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.ico'}

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

STAGE_MAP_DISPLAY = {
    'DEDUP': '去重',
    'CONVERT': '转换',
    'RENAME': '重命名',
    'CLASSIFY': '分类',
}


def iter_images(root: str, recursive: bool, skip_formats: set = None):
    if skip_formats is None:
        skip_formats = set()
    for dirpath, dirs, files in os.walk(root):
        for f in files:
            filepath = os.path.join(dirpath, f)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXT:
                try:
                    with Image.open(filepath) as img:
                        file_format = img.format
                        if file_format and file_format.upper() not in skip_formats:
                            yield filepath
                except (IOError, OSError):
                    continue
            else:
                try:
                    with Image.open(filepath) as img:
                        file_format = img.format
                        if file_format and file_format.upper() not in skip_formats:
                            yield filepath
                except (IOError, OSError):
                    continue
        if not recursive:
            break


def norm_ext(path: str) -> str:
    e = os.path.splitext(path)[1].lower().lstrip('.')
    return 'jpg' if e == 'jpeg' else e


def ahash(im):
    im = im.convert('L').resize((8, 8))
    avg = sum(im.getdata()) / 64.0
    bits = 0
    for i, p in enumerate(im.getdata()):
        if p >= avg:
            bits |= 1 << i
    return bits


def dhash(im):
    im = im.convert('L').resize((9, 8))
    pixels = list(im.getdata())
    bits = 0
    idx = 0
    for r in range(8):
        row = pixels[r * 9:(r + 1) * 9]
        for c in range(8):
            if row[c] > row[c + 1]:
                bits |= 1 << idx
            idx += 1
    return bits


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def is_animated_image(path: str) -> bool:
    try:
        with Image.open(path) as im:
            if hasattr(im, 'is_animated') and im.is_animated:
                return True
            if im.format in ('GIF', 'WEBP'):
                try:
                    im.seek(1)
                    return True
                except (AttributeError, EOFError):
                    pass
            if im.format == 'PNG':
                try:
                    frames = list(ImageSequence.Iterator(im))
                    return len(frames) > 1
                except Exception:
                    pass
        return False
    except Exception:
        return False


def convert_one(src, dst, fmt, quality=None, png3=False, ico_sizes=None, square_mode=None):
    try:
        with Image.open(src) as im:
            if fmt == 'ico':
                w, h = im.size
                if w != h and square_mode and square_mode != 'keep':
                    if square_mode == 'center':
                        side = min(w, h)
                        left = (w - side) // 2
                        top = (h - side) // 2
                        im = im.crop((left, top, left + side, top + side))
                    elif square_mode == 'topleft':
                        side = min(w, h)
                        im = im.crop((0, 0, side, side))
                    elif square_mode == 'fit':
                        side = max(w, h)
                        canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
                        x = (side - w) // 2
                        y = (side - h) // 2
                        canvas.paste(im, (x, y))
                        im = canvas
            if fmt == 'gif':
                im.save(dst, save_all=True)
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
                    if png3:
                        im = im.convert('P', palette=Image.ADAPTIVE, colors=256)
                elif fmt == 'webp':
                    params['quality'] = quality or 80
                im.save(dst, fmt.upper(), **params)
        return True, 'OK'
    except PermissionError as e:
        return False, f"权限不足: {str(e)}"
    except Exception as e:
        import traceback
        error_detail = f"{type(e).__name__}: {str(e)}"
        tb_lines = traceback.format_exc().strip().split('\n')
        if len(tb_lines) > 2:
            error_detail += f" | {tb_lines[-2].strip()}"
        return False, error_detail


def scan_directory_files(root_dir, recursive=True, skip_formats=None):
    if skip_formats is None:
        skip_formats = set()
    image_files = []
    non_image_files = []
    try:
        for img_path in iter_images(root_dir, recursive, skip_formats):
            image_files.append(img_path)
        for dirpath, dirs, files in os.walk(root_dir):
            for f in files:
                full_path = os.path.join(dirpath, f)
                ext = os.path.splitext(f)[1].lower()
                if ext not in SUPPORTED_EXT:
                    try:
                        with Image.open(full_path) as img:
                            pass
                    except (IOError, OSError):
                        non_image_files.append(f)
                elif ext in SUPPORTED_EXT:
                    try:
                        with Image.open(full_path) as img:
                            file_format = img.format
                            if file_format and file_format.upper() in skip_formats:
                                non_image_files.append(f + f" (跳过{file_format}格式)")
                    except (IOError, OSError):
                        non_image_files.append(f + " (损坏)")
            if not recursive:
                break
    except PermissionError:
        raise PermissionError("扫描目录时权限不足")
    except Exception as e:
        print(f"扫描目录时出错：{e}")
    return image_files, non_image_files
