"""图片工具 - 核心文件操作模块"""
import os
import shutil

try:
    from send2trash import send2trash
except Exception:
    send2trash = None


def safe_delete(path: str):
    if send2trash is not None:
        try:
            send2trash(path)
            return True, '删除->回收站'
        except Exception as e:
            try:
                os.remove(path)
                return True, f'删除(回收站失败:{e})'
            except PermissionError:
                return False, '删除失败: 权限不足'
            except Exception as e2:
                return False, f'删失败:{e2}'
    try:
        os.remove(path)
        return True, '删除'
    except PermissionError:
        return False, '删除失败: 权限不足'
    except Exception as e:
        return False, f'删失败:{e}'


def next_non_conflict(path: str) -> str:
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(path):
        path = f"{base}_{i}{ext}"
        i += 1
    return path


def copy_file(src: str, dst: str) -> tuple:
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return True, '复制'
    except PermissionError:
        return False, '复制失败: 权限不足'
    except Exception as e:
        return False, f'复制失败:{e}'


def move_file(src: str, dst: str) -> tuple:
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            dst = next_non_conflict(dst)
        shutil.move(src, dst)
        return True, '移动'
    except Exception as e:
        return False, f'移失败:{e}'
