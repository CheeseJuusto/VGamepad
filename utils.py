import os
import sys
import ctypes
from ctypes import wintypes

# --- PyInstaller EXE / DLL-polkujen hallinta ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(sys._MEIPASS)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# Win32 API -määritykset
user32 = ctypes.windll.user32
user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t

SetCursorPos = user32.SetCursorPos
GetSystemMetrics = user32.GetSystemMetrics
ShowCursor = user32.ShowCursor


def update_screen_center():
    w = GetSystemMetrics(0)
    h = GetSystemMetrics(1)
    return (w // 2, h // 2)


def set_cursor_visible(visible: bool):
    ShowCursor(1 if visible else 0)


def normalize_vk_code(vk, is_e0=False):
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x70 <= vk <= 0x87:
        return f"f{vk - 0x6F}"

    vk_map = {
        0x20: "space",
        0x0D: "enter",
        0x09: "tab",
        0x1B: "esc",
        0x08: "backspace",
        0x10: "shift_r" if is_e0 else "shift",
        0x11: "ctrl_r" if is_e0 else "ctrl_l",
        0x12: "alt_r" if is_e0 else "alt_l",
        0x25: "left",
        0x26: "up",
        0x27: "right",
        0x28: "down",
        0x14: "caps_lock",
        0x2D: "insert",
        0x2E: "delete",
        0x24: "home",
        0x23: "end",
        0x21: "page_up",
        0x22: "page_down"
    }
    return vk_map.get(vk, f"vk_{vk}")


def apply_deadzone_value(v, dz):
    return 0.0 if abs(v) < dz else v


def apply_anti_deadzone(v, adz):
    if v == 0.0:
        return 0.0
    sign = 1.0 if v > 0 else -1.0
    abs_v = abs(v)
    if abs_v < adz:
        return sign * adz
    return v


def apply_linearity(v, gamma):
    sign = 1 if v >= 0 else -1
    return sign * (abs(v) ** (1.0 / gamma if gamma != 0 else 1.0))