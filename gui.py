# gui.py
# Complete, ready-to-run GUI for vgamepad mapping with:
# - Keys / Mouse tabs
# - Custom inputs per-row with dynamic count (0-20) and working save/load
# - Record buttons with short-press to bind and long-press (>=1s) to clear
# - Hotkeys fully rebindable from the Settings tab (Mouse lock & Emulation toggle)
# - Mouse lock that preserves identical delta behavior locked vs free
# - Separate X/Y sensitivity, deadzone, anti-deadzone, and linearity (gamma) control
# - Immediate application of mouse settings and saving/loading config.json
# - Left stick movement limiter with toggle checkbox and multiplier slider
# - Game executable and visible arguments block
# - GitHub version control with boot-time and manual updates checks
# - Global emulation master toggle (Enable/Disable via UI or Hotkey)
# - Save/Load Config buttons moved exclusively to Settings tab
# - Embedded app.ico support for PyInstaller EXE bundle
# - Controller Passthrough via Pygame integration (Simultaneous KB+M support)
# - Extended mouse mapping (mouse1-5, scroll_up/down)
# - Mouse wheel scroll support added for UI menu/tab navigation
# - RAW INPUT Integration for ultra-low latency mouse tracking & keyboard input
# - Version v2.0.1
#
# Requires: vgamepad, pygame, requests, ViGEmBus driver installed on Windows

import json
import threading
import time
import ctypes
from ctypes import wintypes
import os
import sys
import urllib.request
import webbrowser
from collections import deque
import vgamepad as vg
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pygame

# --- PYINSTALLER EXE / DLL POLUN KORJAUS ---
if getattr(sys, 'frozen', False):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(sys._MEIPASS)

# Määritetään DefWindowProcW:n argumentit ja paluuarvo 64-bittiselle yhteensopivaksi:
user32 = ctypes.windll.user32
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_ssize_t

# --- Sovelluksen nykyinen versio ---
CURRENT_VERSION = "v2.0.1"
GITHUB_REPO = "CheeseJuusto/VGamepad" 

# --- Oletuskonfiguraatio ---
DEFAULT_CONFIG = {
    "profiles_enabled": False,
    "soldier_key": "z",
    "vehicle_key": "x",
    "plane_key": "v",
    "keyboard":   {
        "cross": {"display":"Cross","bind_key":"space","xinput":"A"},
        "circle": {"display":"Circle","bind_key":"e","xinput":"B"},
        "square": {"display":"Square","bind_key":"r","xinput":"X"},
        "triangle": {"display":"Triangle","bind_key":"f","xinput":"Y"},
        "l1": {"display":"L1","bind_key":"mouse2","xinput":"LEFT_SHOULDER"},
        "r1": {"display":"R1","bind_key":"mouse1","xinput":"RIGHT_SHOULDER"},
        "l2": {"display":"L2","bind_key":"g","xinput":"LEFT_TRIGGER"},
        "r2": {"display":"R2","bind_key":"q","xinput":"RIGHT_TRIGGER"},
        "l3": {"display":"L3","bind_key":"shift","xinput":"LEFT_THUMB"},
        "r3": {"display":"R3","bind_key":"c","xinput":"RIGHT_THUMB"},
        "select": {"display":"Select","bind_key":"tab","xinput":"BACK"},
        "start": {"display":"Start","bind_key":"esc","xinput":"START"},
        "dpad_up": {"display":"Dpad Up","bind_key":"c","xinput":"DPAD_UP"},
        "dpad_down":{"display":"Dpad Down","bind_key":"b","xinput":"DPAD_DOWN"}
        },
    "keyboard_vehicle": {},
    "keyboard_plane": {},
    "mouse": {
        "sensitivity_x": 3.0,
        "sensitivity_y": 3.2,
        "deadzone_x": 0.0,
        "deadzone_y": 0.0,
        "anti_deadzone_x": 0.0,
        "anti_deadzone_y": 0.0,
        "linearity": 1.5,
        "invert_y": True,
        "pixel_to_unit": 100.0,
        "smoothing_samples": 1
    },
    "mouse_profiles": {
        "vehicle": {
            "sensitivity_x": 4.0,
            "sensitivity_y": 4.2,
            "deadzone_x": 0.0,
            "deadzone_y": 0.0,
            "anti_deadzone_x": 0.0,
            "anti_deadzone_y": 0.0,
            "linearity": 1.5,
            "invert_y": True
        },
        "plane": {
            "sensitivity_x": 8.0,
            "sensitivity_y": 8.4,
            "deadzone_x": 0.0,
            "deadzone_y": 0.0,
            "anti_deadzone_x": 0.0,
            "anti_deadzone_y": 0.0,
            "linearity": 1.0,
            "invert_y": True
        }
    },
    "update_rate_hz": 120,
    "hotkeys": {
        "toggle_lock": "f5",
        "toggle_emulation": "f6"
    },
    "emulation_enabled": True,
    "custom_count": 4,
    "custom_inputs": [
        {"name":"custom1","target":"cross","bind_key":"","description":""},
        {"name":"custom2","target":"circle","bind_key":"","description":""},
        {"name":"custom3","target":"square","bind_key":"","description":""},
        {"name":"custom4","target":"triangle","bind_key":"","description":""}
    ],
    "left_stick": {"up":"w","down":"s","left":"a","right":"d"},
    "left_stick_limiter": {
        "bind_key": "ctrl_l",
        "is_toggle": True,
        "value": 0.45
    },
    "menu_buttons": {"up":"up","down":"down","left":"left","right":"right","select":"enter","back":"backspace"},
    "game_settings": {
        "executable_path": "",
        "arguments": "--no-gui \"%RPCS3_GAMEID%:NPEB00092\""
    },
    "controller_passthrough": {
        "enabled": False,
        "selected_index": 0
    }
}

# --- POLKUJEN HALLINTA EXE- YMPÄRISTÖSSÄ ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if "mouse" not in loaded:
                loaded["mouse"] = DEFAULT_CONFIG["mouse"].copy()
            if "mouse_profiles" not in loaded:
                loaded["mouse_profiles"] = {}
                
            for key, val in DEFAULT_CONFIG["mouse"].items():
                if key not in loaded["mouse"]:
                    loaded["mouse"][key] = val

            for profile_name in ("vehicle", "plane"):
                if profile_name not in loaded["mouse_profiles"]:
                    loaded["mouse_profiles"][profile_name] = {
                        "sensitivity_x": loaded["mouse"].get("sensitivity_x", 3.0),
                        "sensitivity_y": loaded["mouse"].get("sensitivity_y", 3.2),
                        "deadzone_x": loaded["mouse"].get("deadzone_x", 0.0),
                        "deadzone_y": loaded["mouse"].get("deadzone_y", 0.0),
                        "anti_deadzone_x": loaded["mouse"].get("anti_deadzone_x", 0.0),
                        "anti_deadzone_y": loaded["mouse"].get("anti_deadzone_y", 0.0),
                        "linearity": loaded["mouse"].get("linearity", 1.5),
                        "invert_y": loaded["mouse"].get("invert_y", True)
                    }
                else:
                    for k, v in DEFAULT_CONFIG["mouse"].items():
                        if k not in loaded["mouse_profiles"][profile_name]:
                            loaded["mouse_profiles"][profile_name][k] = v

            if "keyboard_vehicle" not in loaded:
                loaded["keyboard_vehicle"] = {}
            if "keyboard_plane" not in loaded:
                loaded["keyboard_plane"] = {}
            if "left_stick_limiter" not in loaded:
                loaded["left_stick_limiter"] = DEFAULT_CONFIG["left_stick_limiter"].copy()
            if "custom_count" not in loaded:
                loaded["custom_count"] = len(loaded.get("custom_inputs", []))
            if "controller_passthrough" not in loaded:
                loaded["controller_passthrough"] = DEFAULT_CONFIG["controller_passthrough"].copy()
            if "hotkeys" not in loaded:
                loaded["hotkeys"] = DEFAULT_CONFIG["hotkeys"].copy()
            if "toggle_lock" not in loaded["hotkeys"]:
                loaded["hotkeys"]["toggle_lock"] = "f5"
            if "toggle_emulation" not in loaded["hotkeys"]:
                loaded["hotkeys"]["toggle_emulation"] = "f6"
            if "emulation_enabled" not in loaded:
                loaded["emulation_enabled"] = True
            if "profiles_enabled" not in loaded:
                loaded["profiles_enabled"] = DEFAULT_CONFIG["profiles_enabled"]
            if "soldier_key" not in loaded:
                loaded["soldier_key"] = DEFAULT_CONFIG["soldier_key"]
            if "vehicle_key" not in loaded:
                loaded["vehicle_key"] = DEFAULT_CONFIG["vehicle_key"]
            if "plane_key" not in loaded:
                loaded["plane_key"] = DEFAULT_CONFIG["plane_key"]
                
            return loaded
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

cfg = load_config()

# --- Nykyinen aktiivinen profiilitila ---
current_profile_context = "soldier"

ACTION_DESCRIPTIONS = {
    "cross":    {"soldier":"Jump","vehicle":"Change","airplane":"-"},
    "circle":   {"soldier":"Enter/Use Pickup","vehicle":"Exit","airplane":"Exit"},
    "square":   {"soldier":"Reload","vehicle":"-","airplane":"-"},
    "triangle": {"soldier":"Draw Knife","vehicle":"-","airplane":"-"},
    "l1":       {"soldier":"Zoom","vehicle":"Throttle","airplane":"Throttle"},
    "r1":       {"soldier":"Fire","vehicle":"Fire","airplane":"Fire"},
    "l2":       {"soldier":"Throw Grenade","vehicle":"Brake","airplane":"Hold Free Look"},
    "r2":       {"soldier":"Toggle Weapon","vehicle":"Secondary fire","airplane":"Drop bombs"},
    "l3":       {"soldier":"Run","vehicle":"-","airplane":"-"},
    "r3":       {"soldier":"Crouch","vehicle":"-","airplane":"-"},
    "select":   {"soldier":"Command / Score","vehicle":"Command / Score","airplane":"Command / Score"},
    "start":    {"soldier":"In-Game Menu","vehicle":"In-Game Menu","airplane":"In-Game Menu"},
    "dpad_up":  {"soldier":"-","vehicle":"Change Camera","airplane":"Change Camera"},
    "dpad_down":{"soldier":"-","vehicle":"Look back","airplane":"Look back"}
}

gamepad = None

mouse_dx_queue = deque(maxlen=cfg["mouse"].get("smoothing_samples", 1))
mouse_dy_queue = deque(maxlen=cfg["mouse"].get("smoothing_samples", 1))
last_real_pos = None            
last_user_move_time = 0.0
running = True
mouse_locked = True
recording_target = None   
recording_widget = None
current_record_press_time = None
current_record_candidate = None  
buttons_pressed = set()
triggers_pressed = set()
physically_pressed_keys = set()
left_stick_state = {"x": 0.0, "y": 0.0}
limiter_active = False

SetCursorPos = ctypes.windll.user32.SetCursorPos
GetSystemMetrics = ctypes.windll.user32.GetSystemMetrics
ShowCursor = ctypes.windll.user32.ShowCursor

def update_screen_center():
    w = GetSystemMetrics(0); h = GetSystemMetrics(1)
    return (w//2, h//2)

screen_center = update_screen_center()

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

def reset_input_states():
    global left_stick_state
    buttons_pressed.clear()
    triggers_pressed.clear()
    left_stick_state["x"] = 0.0
    left_stick_state["y"] = 0.0

def reevaluate_active_inputs():
    reset_input_states()
    for kname in list(physically_pressed_keys):
        simulate_key_press(kname)

def simulate_key_press(kname):
    for ps_key, entry in cfg.get("keyboard", {}).items():
        actual_bind = entry.get("bind_key")
        if cfg.get("profiles_enabled", False) and current_profile_context == "vehicle":
            actual_bind = cfg.get("keyboard_vehicle", {}).get(ps_key, actual_bind)
            if ps_key == "l1": actual_bind = "w"
            elif ps_key == "l2": actual_bind = "s"
            elif ps_key == "r2": actual_bind = "mouse2"
        elif cfg.get("profiles_enabled", False) and current_profile_context == "plane":
            actual_bind = cfg.get("keyboard_plane", {}).get(ps_key, actual_bind)
            if ps_key == "l1": actual_bind = "w"
            elif ps_key == "l2": actual_bind = "s"
            elif ps_key == "r2": actual_bind = "mouse2"

        if actual_bind == kname:
            xinp = entry.get("xinput", "").upper()
            if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
                triggers_pressed.add(xinp)
            else:
                if xinp: buttons_pressed.add(xinp)
                    
    c_count = int(cfg.get("custom_count", len(cfg.get("custom_inputs", []))))
    for idx, ci in enumerate(cfg.get("custom_inputs", [])):
        if idx >= c_count:
            break
        if ci.get("bind_key") == kname:
            target = ci.get("target")
            xinp = cfg.get("keyboard", {}).get(target, {}).get("xinput", "").upper()
            if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
                triggers_pressed.add(xinp)
            else:
                if xinp: buttons_pressed.add(xinp)
                    
    for dirk, keybind in cfg.get("left_stick", {}).items():
        if keybind == kname:
            if dirk == "up": left_stick_state["y"] = 1.0
            if dirk == "down": left_stick_state["y"] = -1.0
            if dirk == "left": left_stick_state["x"] = -1.0
            if dirk == "right": left_stick_state["x"] = 1.0
    for mkey, keybind in cfg.get("menu_buttons", {}).items():
        if keybind == kname:
            if mkey == "select": buttons_pressed.add("A")
            elif mkey == "back": buttons_pressed.add("B")
            elif mkey == "up": buttons_pressed.add("DPAD_UP")
            elif mkey == "down": buttons_pressed.add("DPAD_DOWN")
            elif mkey == "left": buttons_pressed.add("DPAD_LEFT")
            elif mkey == "right": buttons_pressed.add("DPAD_RIGHT")

def set_profile_context(new_context):
    global current_profile_context
    if current_profile_context != new_context:
        current_profile_context = new_context
        reevaluate_active_inputs()
        try:
            app.mouse_profile_var.set(new_context)
            app.load_mouse_profile_ui()
            app.refresh_keyboard_bindings_ui()
            app.status_var.set(f"Context switched to: {new_context.capitalize()}")
        except Exception:
            pass

raw_input_thread = None

# --- WINDOWS RAW INPUT IMPLEMENTAATIO ---
class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]

class RAWMOUSE(ctypes.Structure):
    class _U1(ctypes.Union):
        class _S1(ctypes.Structure):
            _fields_ = [
                ("usButtonFlags", wintypes.WORD),
                ("usButtonData", wintypes.WORD),
            ]
        _fields_ = [
            ("ulButtons", wintypes.ULONG),
            ("s1", _S1),
        ]
    _fields_ = [
        ("usFlags", wintypes.WORD),
        ("u1", _U1),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.WORD),
        ("Flags", wintypes.WORD),
        ("Reserved", wintypes.WORD),
        ("VKey", wintypes.WORD),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]

class RAWINPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [
            ("mouse", RAWMOUSE),
            ("keyboard", RAWKEYBOARD),
        ]
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("u", _U),
    ]

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]

WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100

RI_MOUSE_LEFT_BUTTON_DOWN   = 0x0001
RI_MOUSE_LEFT_BUTTON_UP     = 0x0002
RI_MOUSE_RIGHT_BUTTON_DOWN  = 0x0004
RI_MOUSE_RIGHT_BUTTON_UP    = 0x0008
RI_MOUSE_MIDDLE_BUTTON_DOWN = 0x0010
RI_MOUSE_MIDDLE_BUTTON_UP   = 0x0020
RI_MOUSE_BUTTON_4_DOWN      = 0x0040
RI_MOUSE_BUTTON_4_UP        = 0x0080
RI_MOUSE_BUTTON_5_DOWN      = 0x0100
RI_MOUSE_BUTTON_5_UP        = 0x0200
RI_MOUSE_WHEEL              = 0x0400

RI_KEY_BREAK = 0x01
RI_KEY_E0    = 0x02

class RawInputWindow:
    def __init__(self):
        self.hwnd = None

    def start(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                dw_size = wintypes.DWORD()
                user32.GetRawInputData(wintypes.HANDLE(lparam), RID_INPUT, None, ctypes.byref(dw_size), ctypes.sizeof(RAWINPUTHEADER))
                if dw_size.value > 0:
                    raw_buf = ctypes.create_string_buffer(dw_size.value)
                    if user32.GetRawInputData(wintypes.HANDLE(lparam), RID_INPUT, raw_buf, ctypes.byref(dw_size), ctypes.sizeof(RAWINPUTHEADER)) == dw_size.value:
                        raw = ctypes.cast(raw_buf, ctypes.POINTER(RAWINPUT)).contents
                        if raw.header.dwType == 0:
                            self.process_raw_mouse(raw.u.mouse)
                        elif raw.header.dwType == 1:
                            self.process_raw_keyboard(raw.u.keyboard)
                return 0
            return user32.DefWindowProcW(
                hwnd, 
                msg, 
                wintypes.WPARAM(wparam), 
                wintypes.LPARAM(lparam)
            )

        self.wnd_proc_cb = WNDPROC(wnd_proc)
        if not hasattr(ctypes.wintypes, 'HCURSOR'):
            ctypes.wintypes.HCURSOR = ctypes.wintypes.HANDLE

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ('style', ctypes.c_uint),
                ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int),
                ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HICON),
                ('hCursor', wintypes.HANDLE),
                ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR)
            ]

        wndclass = WNDCLASSW()
        wndclass.lpszClassName = "RawInputClass"
        wndclass.lpfnWndProc = self.wnd_proc_cb
        wndclass.hInstance = kernel32.GetModuleHandleW(None)

        user32.RegisterClassW(ctypes.byref(wndclass))

        self.hwnd = user32.CreateWindowExW(
            0, "RawInputClass", "RawInputWindow",
            0, 0, 0, 0, 0,
            0, 0, wndclass.hInstance, None
        )

        devices = (RAWINPUTDEVICE * 2)()
        devices[0].usUsagePage = 0x01
        devices[0].usUsage = 0x02
        devices[0].dwFlags = RIDEV_INPUTSINK
        devices[0].hwndTarget = self.hwnd

        devices[1].usUsagePage = 0x01
        devices[1].usUsage = 0x06
        devices[1].dwFlags = RIDEV_INPUTSINK
        devices[1].hwndTarget = self.hwnd

        user32.RegisterRawInputDevices(ctypes.byref(devices), 2, ctypes.sizeof(RAWINPUTDEVICE))

        msg = wintypes.MSG()
        while running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def process_raw_mouse(self, mouse_data):
        if not cfg.get("emulation_enabled", True) and not recording_target:
            return

        dx = mouse_data.lLastX
        dy = mouse_data.lLastY
        if dx != 0 or dy != 0:
            mouse_dx_queue.append(dx)
            mouse_dy_queue.append(dy)

        flags = mouse_data.u1.s1.usButtonFlags
        
        if flags & RI_MOUSE_LEFT_BUTTON_DOWN: on_click(0, 0, "mouse1", True)
        if flags & RI_MOUSE_LEFT_BUTTON_UP: on_click(0, 0, "mouse1", False)
        
        if flags & RI_MOUSE_RIGHT_BUTTON_DOWN: on_click(0, 0, "mouse2", True)
        if flags & RI_MOUSE_RIGHT_BUTTON_UP: on_click(0, 0, "mouse2", False)
        
        if flags & RI_MOUSE_MIDDLE_BUTTON_DOWN: on_click(0, 0, "mouse3", True)
        if flags & RI_MOUSE_MIDDLE_BUTTON_UP: on_click(0, 0, "mouse3", False)
        
        if flags & RI_MOUSE_BUTTON_4_DOWN: on_click(0, 0, "mouse4", True)
        if flags & RI_MOUSE_BUTTON_4_UP: on_click(0, 0, "mouse4", False)
        
        if flags & RI_MOUSE_BUTTON_5_DOWN: on_click(0, 0, "mouse5", True)
        if flags & RI_MOUSE_BUTTON_5_UP: on_click(0, 0, "mouse5", False)

        if flags & RI_MOUSE_WHEEL:
            wheel_delta = ctypes.c_short(mouse_data.u1.s1.usButtonData).value
            if wheel_delta > 0:
                on_scroll(0, 0, 0, 1)
            elif wheel_delta < 0:
                on_scroll(0, 0, 0, -1)

    def process_raw_keyboard(self, kb_data):
        vk = kb_data.VKey
        if vk == 0 or vk == 0xFF:
            return
        
        flags = kb_data.Flags
        is_up = bool(flags & RI_KEY_BREAK)
        is_e0 = bool(flags & RI_KEY_E0)
        
        key_name = normalize_vk_code(vk, is_e0)
        
        if is_up:
            physically_pressed_keys.discard(key_name)
            on_key_release_raw(key_name)
        else:
            physically_pressed_keys.add(key_name)
            on_key_press_raw(key_name)

def clear_binding(target_type, target_key, widget=None):
    if target_type == "keyboard":
        if cfg.get("profiles_enabled", False) and current_profile_context == "vehicle":
            cfg["keyboard_vehicle"][target_key] = ""
        elif cfg.get("profiles_enabled", False) and current_profile_context == "plane":
            cfg["keyboard_plane"][target_key] = ""
        else:
            cfg["keyboard"][target_key]["bind_key"] = ""
    elif target_type == "custom":
        idx = int(target_key)
        if idx < len(cfg["custom_inputs"]):
            cfg["custom_inputs"][idx]["bind_key"] = ""
    elif target_type == "leftstick":
        cfg["left_stick"][target_key] = ""
    elif target_type == "limiter":
        cfg["left_stick_limiter"]["bind_key"] = ""
    elif target_type == "menu":
        cfg["menu_buttons"][target_key] = ""
    elif target_type == "hotkey_lock":
        cfg["hotkeys"]["toggle_lock"] = ""
    elif target_type == "hotkey_emu":
        cfg["hotkeys"]["toggle_emulation"] = ""
    elif target_type in ("soldier_bind", "vehicle_bind", "plane_bind"):
        cfg[target_key] = ""
    save_config(cfg)
    if widget:
        try: widget.config(text="")
        except Exception:
            try: widget.delete(0, tk.END); widget.insert(0, "")
            except Exception: pass

def bind_and_save(target_type, target_key, bind_name, widget=None):
    if target_type == "keyboard":
        if cfg.get("profiles_enabled", False) and current_profile_context == "vehicle":
            cfg["keyboard_vehicle"][target_key] = bind_name
        elif cfg.get("profiles_enabled", False) and current_profile_context == "plane":
            cfg["keyboard_plane"][target_key] = bind_name
        else:
            cfg["keyboard"][target_key]["bind_key"] = bind_name
    elif target_type == "custom":
        idx = int(target_key)
        while len(cfg["custom_inputs"]) <= idx:
            cfg["custom_inputs"].append({"name": f"custom{len(cfg['custom_inputs'])+1}", "target": "cross", "bind_key": "", "description": ""})
        cfg["custom_inputs"][idx]["bind_key"] = bind_name
    elif target_type == "leftstick":
        cfg["left_stick"][target_key] = bind_name
    elif target_type == "limiter":
        cfg["left_stick_limiter"]["bind_key"] = bind_name
    elif target_type == "menu":
        cfg["menu_buttons"][target_key] = bind_name
    elif target_type == "hotkey_lock":
        cfg["hotkeys"]["toggle_lock"] = bind_name
    elif target_type == "hotkey_emu":
        cfg["hotkeys"]["toggle_emulation"] = bind_name
    elif target_type in ("soldier_bind", "vehicle_bind", "plane_bind"):
        cfg[target_key] = bind_name
    save_config(cfg)
    if widget:
        try: widget.config(text=bind_name)
        except Exception:
            try:
                widget.delete(0, tk.END)
                widget.insert(0, bind_name)
            except Exception: pass

def record_button_press(ttype, tkey, widget):
    global current_record_press_time, current_record_candidate
    current_record_press_time = time.time()
    current_record_candidate = (ttype, tkey, widget)

def record_button_release(event=None):
    global current_record_press_time, current_record_candidate, recording_target, recording_widget
    if current_record_candidate is None:
        return
    held = time.time() - (current_record_press_time or 0)
    ttype, tkey, widget = current_record_candidate
    current_record_press_time = None
    current_record_candidate = None
    
    if held >= 1.0:
        clear_binding(ttype, tkey, widget)
        try: app.status_var.set(f"Cleared binding for {ttype} {tkey}")
        except Exception: pass
        return
    recording_target = (ttype, tkey)
    recording_widget = widget
    try: widget.config(text="(press key...)")
    except Exception:
        try: widget.delete(0, tk.END); widget.insert(0, "(press key...)")
        except Exception: pass
    try: app.status_var.set(f"Recording {ttype} {tkey} — press a key or mouse button")
    except Exception: pass

def on_key_press_raw(kname):
    global recording_target, left_stick_state, limiter_active
    if recording_target:
        ttype, tkey = recording_target
        bind_and_save(ttype, tkey, kname, recording_widget)
        recording_target = None
        try: app.status_var.set(f"Bound {kname}")
        except Exception: pass
        return

    emu_hk = cfg.get("hotkeys", {}).get("toggle_emulation", "f6").lower()
    if kname == emu_hk and emu_hk != "":
        toggle_master_emulation()
        return

    if not cfg.get("emulation_enabled", True):
        return

    hk = cfg.get("hotkeys", {}).get("toggle_lock", "f5").lower()
    if kname == hk and hk != "":
        toggle_mouse_lock()
        return

    if cfg.get("profiles_enabled", False):
        c_count = int(cfg.get("custom_count", len(cfg.get("custom_inputs", []))))
        for idx, ci in enumerate(cfg.get("custom_inputs", [])):
            if idx >= c_count: break
            if ci.get("bind_key") == kname:
                if ci.get("target") == "soldier_profile":
                    set_profile_context("soldier")
                elif ci.get("target") == "vehicle_profile":
                    set_profile_context("vehicle")
                elif ci.get("target") == "plane_profile":
                    set_profile_context("plane")

        if kname == cfg.get("soldier_key", "e"):
            set_profile_context("soldier")
            return
        elif kname == cfg.get("vehicle_key", "t"):
            set_profile_context("vehicle")
            return
        elif kname == cfg.get("plane_key", "y"):
            set_profile_context("plane")
            return

    lk = cfg.get("left_stick_limiter", {}).get("bind_key", "ctrl_l").lower()
    if kname == lk and lk != "":
        if cfg.get("left_stick_limiter", {}).get("is_toggle", False):
            limiter_active = not limiter_active
        else:
            limiter_active = True
        return

    simulate_key_press(kname)

def on_key_release_raw(kname):
    global limiter_active
    if not cfg.get("emulation_enabled", True):
        return
    
    lk = cfg.get("left_stick_limiter", {}).get("bind_key", "ctrl_l").lower()
    if kname == lk and lk != "":
        if not cfg.get("left_stick_limiter", {}).get("is_toggle", False):
            limiter_active = False
        return

    for ps_key, entry in cfg.get("keyboard", {}).items():
        actual_bind = entry.get("bind_key")
        if cfg.get("profiles_enabled", False) and current_profile_context == "vehicle":
            actual_bind = cfg.get("keyboard_vehicle", {}).get(ps_key, actual_bind)
            if ps_key == "l1": actual_bind = "w"
            elif ps_key == "l2": actual_bind = "s"
            elif ps_key == "r2": actual_bind = "mouse2"
        elif cfg.get("profiles_enabled", False) and current_profile_context == "plane":
            actual_bind = cfg.get("keyboard_plane", {}).get(ps_key, actual_bind)
            if ps_key == "l1": actual_bind = "w"
            elif ps_key == "l2": actual_bind = "s"
            elif ps_key == "r2": actual_bind = "mouse2"

        if actual_bind == kname:
            xinp = entry.get("xinput", "").upper()
            if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
                if xinp in triggers_pressed: triggers_pressed.discard(xinp)
            else:
                if xinp and xinp in buttons_pressed:
                    buttons_pressed.discard(xinp)
                    
    c_count = int(cfg.get("custom_count", len(cfg.get("custom_inputs", []))))
    for idx, ci in enumerate(cfg.get("custom_inputs", [])):
        if idx >= c_count:
            break
        if ci.get("bind_key") == kname:
            target = ci.get("target")
            xinp = cfg.get("keyboard", {}).get(target, {}).get("xinput", "").upper()
            if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
                if xinp in triggers_pressed: triggers_pressed.discard(xinp)
            else:
                if xinp and xinp in buttons_pressed:
                    buttons_pressed.discard(xinp)
                    
    for dirk, keybind in cfg.get("left_stick", {}).items():
        if keybind == kname:
            if dirk == "up" and left_stick_state["y"] > 0: left_stick_state["y"] = 0.0
            if dirk == "down" and left_stick_state["y"] < 0: left_stick_state["y"] = 0.0
            if dirk == "left" and left_stick_state["x"] < 0: left_stick_state["x"] = 0.0
            if dirk == "right" and left_stick_state["x"] > 0: left_stick_state["x"] = 0.0
    for mkey, keybind in cfg.get("menu_buttons", {}).items():
        if keybind == kname:
            if mkey == "select" and "A" in buttons_pressed: buttons_pressed.discard("A")
            if mkey == "back" and "B" in buttons_pressed: buttons_pressed.discard("B")
            if mkey == "up" and "DPAD_UP" in buttons_pressed: buttons_pressed.discard("DPAD_UP")
            if mkey == "down" and "DPAD_DOWN" in buttons_pressed: buttons_pressed.discard("DPAD_DOWN")
            if mkey == "left" and "DPAD_LEFT" in buttons_pressed: buttons_pressed.discard("DPAD_LEFT")
            if mkey == "right" and "DPAD_RIGHT" in buttons_pressed: buttons_pressed.discard("DPAD_RIGHT")

def on_click(x, y, keyname, pressed):
    global recording_target, recording_widget
    
    if pressed:
        physically_pressed_keys.add(keyname)
    else:
        physically_pressed_keys.discard(keyname)

    if not cfg.get("emulation_enabled", True) and not recording_target:
        return

    if recording_target:
        if pressed:
            ttype, tkey = recording_target
            bind_and_save(ttype, tkey, keyname, recording_widget)
            recording_target = None
            try: app.status_var.set(f"Bound {keyname}")
            except Exception: pass
        return

    for ps_key, entry in cfg.get("keyboard", {}).items():
        actual_bind = entry.get("bind_key")
        if cfg.get("profiles_enabled", False) and current_profile_context == "vehicle":
            actual_bind = cfg.get("keyboard_vehicle", {}).get(ps_key, actual_bind)
            if ps_key == "l1": actual_bind = "w"
            elif ps_key == "l2": actual_bind = "s"
            elif ps_key == "r2": actual_bind = "mouse2"
        elif cfg.get("profiles_enabled", False) and current_profile_context == "plane":
            actual_bind = cfg.get("keyboard_plane", {}).get(ps_key, actual_bind)
            if ps_key == "l1": actual_bind = "w"
            elif ps_key == "l2": actual_bind = "s"
            elif ps_key == "r2": actual_bind = "mouse2"

        if actual_bind == keyname:
            xinp = entry.get("xinput", "").upper()
            if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
                if pressed: triggers_pressed.add(xinp)
                else: triggers_pressed.discard(xinp)
            else:
                if pressed: buttons_pressed.add(xinp)
                else: buttons_pressed.discard(xinp)
                    
    c_count = int(cfg.get("custom_count", len(cfg.get("custom_inputs", []))))
    for idx, ci in enumerate(cfg.get("custom_inputs", [])):
        if idx >= c_count:
            break
        if ci.get("bind_key") == keyname:
            target = ci.get("target")
            xinp = cfg.get("keyboard", {}).get(target, {}).get("xinput", "").upper()
            if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
                if pressed: triggers_pressed.add(xinp)
                else: triggers_pressed.discard(xinp)
            else:
                if pressed: buttons_pressed.add(xinp)
                else: buttons_pressed.discard(xinp)
                    
    for dirk, keybind in cfg.get("left_stick", {}).items():
        if keybind == keyname:
            axis = "y" if dirk in ("up","down") else "x"
            val = 1.0 if dirk in ("up","right") else -1.0
            if pressed: left_stick_state[axis] = val
            else: left_stick_state[axis] = 0.0

    for mkey, keybind in cfg.get("menu_buttons", {}).items():
        if keybind == keyname:
            if pressed:
                if mkey == "select": buttons_pressed.add("A")
                elif mkey == "back": buttons_pressed.add("B")
                elif mkey == "up": buttons_pressed.add("DPAD_UP")
                elif mkey == "down": buttons_pressed.add("DPAD_DOWN")
                elif mkey == "left": buttons_pressed.add("DPAD_LEFT")
                elif mkey == "right": buttons_pressed.add("DPAD_RIGHT")
            else:
                if mkey == "select" and "A" in buttons_pressed: buttons_pressed.discard("A")
                if mkey == "back" and "B" in buttons_pressed: buttons_pressed.discard("B")
                if mkey == "up" and "DPAD_UP" in buttons_pressed: buttons_pressed.discard("DPAD_UP")
                if mkey == "down" and "DPAD_DOWN" in buttons_pressed: buttons_pressed.discard("DPAD_DOWN")
                if mkey == "left" and "DPAD_LEFT" in buttons_pressed: buttons_pressed.discard("DPAD_LEFT")
                if mkey == "right" and "DPAD_RIGHT" in buttons_pressed: buttons_pressed.discard("DPAD_RIGHT")

def on_scroll(x, y, dx, dy):
    global recording_target, recording_widget

    if not cfg.get("emulation_enabled", True) and not recording_target:
        return

    keyname = "scroll_up" if dy > 0 else "scroll_down"

    if recording_target:
        ttype, tkey = recording_target
        bind_and_save(ttype, tkey, keyname, recording_widget)
        recording_target = None
        try:
            app.status_var.set(f"Bound {keyname}")
        except Exception:
            pass
        return

    def pulse_button(xinp):
        if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
            triggers_pressed.add(xinp)
            threading.Thread(
                target=lambda: (
                    time.sleep(0.08),
                    triggers_pressed.discard(xinp)
                ),
                daemon=True
            ).start()
        else:
            buttons_pressed.add(xinp)
            threading.Thread(
                target=lambda: (
                    time.sleep(0.08),
                    buttons_pressed.discard(xinp)
                ),
                daemon=True
            ).start()

    for ps_key, entry in cfg.get("keyboard", {}).items():
        actual_bind = entry.get("bind_key")

        if cfg.get("profiles_enabled", False):
            if current_profile_context == "vehicle":
                actual_bind = cfg.get("keyboard_vehicle", {}).get(ps_key, actual_bind)
            elif current_profile_context == "plane":
                actual_bind = cfg.get("keyboard_plane", {}).get(ps_key, actual_bind)

        if actual_bind == keyname:
            pulse_button(entry.get("xinput", "").upper())

    c_count = int(cfg.get("custom_count", len(cfg.get("custom_inputs", []))))
    for idx, ci in enumerate(cfg.get("custom_inputs", [])):
        if idx >= c_count:
            break

        if ci.get("bind_key") == keyname:
            target = ci.get("target")
            xinp = cfg.get("keyboard", {}).get(target, {}).get("xinput", "").upper()
            if xinp:
                pulse_button(xinp)

    for mkey, bind in cfg.get("menu_buttons", {}).items():
        if bind != keyname:
            continue

        mapping = {
            "select": "A",
            "back": "B",
            "up": "DPAD_UP",
            "down": "DPAD_DOWN",
            "left": "DPAD_LEFT",
            "right": "DPAD_RIGHT",
        }

        if mkey in mapping:
            pulse_button(mapping[mkey])

def update_loop():
    global last_user_move_time, mouse_locked, screen_center, last_real_pos, limiter_active, current_profile_context, gamepad
    
    pygame.init()
    pygame.joystick.init()
    
    while running:
        start_time = time.perf_counter()

        update_rate = int(cfg.get("mouse", {}).get("update_rate_hz", cfg.get("update_rate_hz", 60)))
        period = 1.0 / max(1, update_rate)

        if not cfg.get("emulation_enabled", True):
            if gamepad:
                try:
                    gamepad.reset()
                    gamepad.update()
                except Exception: pass
            
            elapsed = time.perf_counter() - start_time
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            continue

        pixel_to_unit = float(cfg.get("mouse", {}).get("pixel_to_unit", 100.0))
        
        if cfg.get("profiles_enabled", False) and current_profile_context in ("vehicle", "plane"):
            p_data = cfg.get("mouse_profiles", {}).get(current_profile_context, {})
            sens_x = float(p_data.get("sensitivity_x", 3.0))
            sens_y = float(p_data.get("sensitivity_y", 3.2))
            dead_x = float(p_data.get("deadzone_x", 0.0))
            dead_y = float(p_data.get("deadzone_y", 0.0))
            adz_x = float(p_data.get("anti_deadzone_x", 0.0))
            adz_y = float(p_data.get("anti_deadzone_y", 0.0))
            gamma = float(p_data.get("linearity", 1.5))
            invert_y = bool(p_data.get("invert_y", True))
        else:
            sens_x = float(cfg.get("mouse", {}).get("sensitivity_x", 3.0))
            sens_y = float(cfg.get("mouse", {}).get("sensitivity_y", 3.2))
            dead_x = float(cfg.get("mouse", {}).get("deadzone_x", 0.0))
            dead_y = float(cfg.get("mouse", {}).get("deadzone_y", 0.0))
            adz_x = float(cfg.get("mouse", {}).get("anti_deadzone_x", 0.0))
            adz_y = float(cfg.get("mouse", {}).get("anti_deadzone_y", 0.0))
            gamma = float(cfg.get("mouse", {}).get("linearity", 1.5))
            invert_y = bool(cfg.get("mouse", {}).get("invert_y", True))

        passthrough_active = False
        target_lx, target_ly = 0.0, 0.0
        target_rx, target_ry = 0.0, 0.0
        target_lt, target_rt = 0, 0
        active_buttons = set(buttons_pressed)

        pt_config = cfg.get("controller_passthrough", {"enabled": False, "selected_index": 0})
        
        if pt_config.get("enabled", False):
            pygame.event.pump()
            j_count = pygame.joystick.get_count()
            target_idx = pt_config.get("selected_index", 0)
            
            if target_idx < j_count:
                try:
                    js = pygame.joystick.Joystick(target_idx)
                    if not js.get_init(): js.init()
                    
                    passthrough_active = True
                    js_lx = js.get_axis(0)
                    js_ly = -js.get_axis(1)
                    js_rx = js.get_axis(2)
                    js_ry = -js.get_axis(3)
                    
                    if abs(js_lx) > 0.15 or abs(js_ly) > 0.15: target_lx, target_ly = js_lx, js_ly
                    if abs(js_rx) > 0.15 or abs(js_ry) > 0.15: target_rx, target_ry = js_rx, js_ry
                    
                    num_axes = js.get_numaxes()
                    if num_axes >= 6:
                        js_lt = int(((js.get_axis(4) + 1.0) / 2.0) * 255) if js.get_axis(4) != 0 else 0
                        js_rt = int(((js.get_axis(5) + 1.0) / 2.0) * 255) if js.get_axis(5) != 0 else 0
                        if js_lt > 20: target_lt = js_lt
                        if js_rt > 20: target_rt = js_rt
                    elif num_axes >= 3:
                        js_trig = js.get_axis(2)
                        if js_trig > 0.15: target_rt = int(js_trig * 255)
                        elif js_trig < -0.15: target_lt = int(abs(js_trig) * 255)
                    
                    num_buttons = js.get_numbuttons()
                    mapping_names = ["A", "B", "X", "Y", "LEFT_SHOULDER", "RIGHT_SHOULDER", "BACK", "START", "LEFT_THUMB", "RIGHT_THUMB"]
                    for btn_idx, name in enumerate(mapping_names):
                        if btn_idx < num_buttons and js.get_button(btn_idx): active_buttons.add(name)
                            
                    if js.get_numhats() > 0:
                        hat = js.get_hat(0)
                        if hat[1] == 1: active_buttons.add("DPAD_UP")
                        if hat[1] == -1: active_buttons.add("DPAD_DOWN")
                        if hat[0] == -1: active_buttons.add("DPAD_LEFT")
                        if hat[0] == 1: active_buttons.add("DPAD_RIGHT")
                except Exception:
                    passthrough_active = False

        if target_rx == 0.0 and target_ry == 0.0:
            if mouse_dx_queue:
                sum_dx = sum(mouse_dx_queue)
                sum_dy = sum(mouse_dy_queue)
                mouse_dx_queue.clear()
                mouse_dy_queue.clear()
            else:
                sum_dx = 0.0
                sum_dy = 0.0

            raw_x = (sum_dx / pixel_to_unit) * sens_x
            raw_y = (sum_dy / pixel_to_unit) * sens_y

            vx = apply_deadzone_value(raw_x, dead_x)
            vy = apply_deadzone_value(raw_y, dead_y)

            vx = apply_anti_deadzone(vx, adz_x)
            vy = apply_anti_deadzone(vy, adz_y)

            if gamma != 1.0 and (vx != 0 or vy != 0):
                vx = apply_linearity(vx, gamma)
                vy = apply_linearity(vy, gamma)

            vx = max(-1.0, min(1.0, vx))
            vy = max(-1.0, min(1.0, vy))

            if invert_y:
                vy = -vy
            target_rx, target_ry = vx, vy

        if target_lx == 0.0 and target_ly == 0.0:
            lx = max(-1.0, min(1.0, left_stick_state["x"]))
            ly = max(-1.0, min(1.0, left_stick_state["y"]))
            if limiter_active:
                mod = float(cfg.get("left_stick_limiter", {}).get("value", 0.5))
                lx *= mod; ly *= mod
            target_lx, target_ly = lx, ly

        if "LEFT_TRIGGER" in triggers_pressed: target_lt = 255
        if "RIGHT_TRIGGER" in triggers_pressed: target_rt = 255

        if gamepad:
            try:
                gamepad.left_joystick_float(target_lx, target_ly)
                gamepad.right_joystick_float(target_rx, target_ry)
                gamepad.left_trigger(target_lt)
                gamepad.right_trigger(target_rt)
                
                mapping = {
                    "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A, "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
                    "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X, "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
                    "LEFT_SHOULDER": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER, "RIGHT_SHOULDER": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
                    "DPAD_UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, "DPAD_DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
                    "DPAD_LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT, "DPAD_RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
                    "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START, "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
                    "LEFT_THUMB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB, "RIGHT_THUMB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB
                }
                for name, enum in mapping.items():
                    if name in active_buttons: gamepad.press_button(button=enum)
                    else: gamepad.release_button(button=enum)
                gamepad.update()
            except Exception: pass

        if mouse_locked:
            cx, cy = screen_center
            SetCursorPos(cx, cy)

        elapsed = time.perf_counter() - start_time
        sleep_time = period - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

def toggle_mouse_lock():
    global mouse_locked, last_real_pos
    if not cfg.get("emulation_enabled", True):
        return
    mouse_locked = not mouse_locked
    if mouse_locked:
        cx, cy = screen_center
        SetCursorPos(cx, cy)
        set_cursor_visible(False)
        try: app.status_var.set("Target state synchronized: Mouse locked inside emulator.")
        except Exception: pass
    else:
        set_cursor_visible(True)
        try: app.status_var.set("Target state synchronized: Mouse tracking context released.")
        except Exception: pass

def toggle_master_emulation():
    state = not cfg.get("emulation_enabled", True)
    cfg["emulation_enabled"] = state
    save_config(cfg)
    try:
        app.emulation_enabled_var.set(state)
        status = "ENABLED" if state else "DISABLED"
        app.status_var.set(f"Remap hooks state shifted via Hotkey: {status}")
    except Exception: pass
    global mouse_locked
    if not state and mouse_locked: toggle_mouse_lock()

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, width=860, height=700, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, width=width, height=height, bg="#f8f9fa")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style="TFrame")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._bind_mouse_wheel(self)

    def _bind_mouse_wheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mouse_wheel)
        widget.bind("<Button-4>", self._on_mouse_wheel)
        widget.bind("<Button-5>", self._on_mouse_wheel)
        for child in widget.winfo_children(): self._bind_mouse_wheel(child)

    def _on_mouse_wheel(self, event):
        if event.num == 4 or event.delta > 0: self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0: self.canvas.yview_scroll(1, "units")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("vgamepad Mapping Toolkit")
        self.geometry("1040x880")
        self.configure(bg="#f8f9fa")
        
        self.style = ttk.Style()
        self.style.theme_use('clam')    
        self.style.configure(".", font=("Segoe UI", 10), background="#f8f9fa", foreground="#212529")
        self.style.configure("TFrame", background="#f8f9fa")
        self.style.configure("TNotebook", background="#f8f9fa", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[20, 8], background="#e9ecef", foreground="#495057")
        self.style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#007bff")])
        
        self.style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), foreground="#111111", padding=5)
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 10, "bold"), foreground="#495057")
        self.style.configure("KeyBind.TLabel", font=("Consolas", 10), background="#ffffff", relief="solid", borderwidth=1, anchor="center")
        
        self.style.configure("TButton", font=("Segoe UI", 10), padding=[12, 4], background="#e9ecef", foreground="#212529", borderwidth=1)
        self.style.map("TButton", background=[("active", "#dee2e6")])
        self.style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), background="#007bff", foreground="#ffffff")
        self.style.map("Action.TButton", background=[("active", "#0056b3")])

        # KUVAKKEEN LATAUS EXE- JOTKA SOVELTUVAT PYINSTALLER-YMPÄRISTÖÖN
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, "app.ico")
            else:
                icon_path = os.path.join(BASE_DIR, "app.ico")
            
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            elif os.path.exists(os.path.join(BASE_DIR, "app.ico")):
                self.iconbitmap(os.path.join(BASE_DIR, "app.ico"))
        except Exception: 
            pass
            
        self.custom_widgets = []
        self.custom_rows_pool = []
        
        self.mouse_profile_var = tk.StringVar(value="soldier")
        
        self.create_widgets()
        self.rebuild_custom_inputs_ui()
        threading.Thread(target=lambda: self.check_update(silent=True), daemon=True).start()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg="#ffffff", height=60, bd=0, highlightthickness=1, highlightbackground="#dee2e6")
        top_bar.pack(side="top", fill="x")
        top_bar.pack_propagate(False)
        
        title_lbl = tk.Label(top_bar, text="vgamepad Remapper Toolkit", font=("Segoe UI", 14, "bold"), bg="#ffffff", fg="#212529")
        title_lbl.pack(side="left", padx=20)
        
        start_btn = ttk.Button(top_bar, text="▶ Start Game", style="Action.TButton", command=self.start_game)
        start_btn.pack(side="right", padx=20)
        
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=15)
        
        sf_keys = ScrollableFrame(nb, width=980, height=720)
        sf_mouse = ScrollableFrame(nb, width=980, height=720)
        sf_settings = ScrollableFrame(nb, width=980, height=720)
        
        nb.add(sf_keys, text="⌨️Keyboard Mapping")
        nb.add(sf_mouse, text="🖱️Mouse Input Tuning")
        nb.add(sf_settings, text="⚙️Application Settings")
        
        self.keys_frame = sf_keys.scrollable_frame
        mouse_frame = sf_mouse.scrollable_frame
        settings_frame = sf_settings.scrollable_frame
        
        # === KEYBOARD TAB MOUSE PROFILE SELECTOR ===
        self.keys_profile_frame = ttk.LabelFrame(self.keys_frame, text="Active Context Profile", padding=10)
        self.keys_profile_frame.grid(column=0, row=0, columnspan=6, sticky=tk.W, padx=20, pady=(15, 5))
        
        self.rb_k_soldier = ttk.Radiobutton(self.keys_profile_frame, text="Soldier", variable=self.mouse_profile_var, value="soldier", command=self.on_mouse_profile_tab_changed)
        self.rb_k_soldier.pack(side="left", padx=5)
        self.rb_k_vehicle = ttk.Radiobutton(self.keys_profile_frame, text="Vehicle", variable=self.mouse_profile_var, value="vehicle", command=self.on_mouse_profile_tab_changed)
        self.rb_k_vehicle.pack(side="left", padx=5)
        self.rb_k_plane = ttk.Radiobutton(self.keys_profile_frame, text="Plane", variable=self.mouse_profile_var, value="plane", command=self.on_mouse_profile_tab_changed)
        self.rb_k_plane.pack(side="left", padx=5)
        
        main_desc = ttk.Label(self.keys_frame, text="Configure keyboard inputs to emulate controller actions. Press 'Record' to bind a key.", style="SubHeader.TLabel")
        main_desc.grid(column=0, row=1, columnspan=6, sticky=tk.W, pady=(10,15), padx=20)
        
        headers = ["Gamepad Target", "Current Binding", "Action", "Soldier Context", "Vehicle Context", "Aircraft Context"]
        for i, h in enumerate(headers):
            lbl_h = ttk.Label(self.keys_frame, text=h, font=("Segoe UI", 9, "bold"), foreground="#6c757d")
            lbl_h.grid(column=i, row=2, padx=10, pady=8, sticky=tk.W if i != 1 else tk.EW)
            
        self.bind_widgets = {}
        row = 3
        for ps_key, entry in cfg.get("keyboard", {}).items():
            display = entry.get("display", ps_key)
            ttk.Label(self.keys_frame, text=display, font=("Segoe UI", 10, "bold"), width=15).grid(column=0, row=row, padx=10, pady=6, sticky=tk.W)
            
            lbl = ttk.Label(self.keys_frame, text=entry.get("bind_key",""), width=16, style="KeyBind.TLabel", padding=4)
            lbl.grid(column=1, row=row, padx=10, pady=6, sticky=tk.EW)
            
            btn = ttk.Button(self.keys_frame, text="Record", width=9)
            btn.grid(column=2, row=row, padx=10, pady=6)
            btn.bind("<ButtonPress-1>", lambda e, t="keyboard", k=ps_key, w=lbl: record_button_press(t, k, w))
            btn.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
            
            desc = ACTION_DESCRIPTIONS.get(ps_key, {"soldier":"-","vehicle":"-","airplane":"-"})
            ttk.Label(self.keys_frame, text=desc["soldier"], foreground="#495057").grid(column=3, row=row, padx=10, pady=6, sticky=tk.W)
            ttk.Label(self.keys_frame, text=desc["vehicle"], foreground="#495057").grid(column=4, row=row, padx=10, pady=6, sticky=tk.W)
            ttk.Label(self.keys_frame, text=desc["airplane"], foreground="#495057").grid(column=5, row=row, padx=10, pady=6, sticky=tk.W)
            
            self.bind_widgets[ps_key] = lbl
            row += 1
            
        row = self.create_section_divider(self.keys_frame, row, "Left Analog Stick Emulation")
        
        self.leftstick_labels = {}
        for dirk in ("up","down","left","right"):
            ttk.Label(self.keys_frame, text=f"Stick {dirk.capitalize()}", font=("Segoe UI", 10), width=15).grid(column=0, row=row, padx=10, pady=5, sticky=tk.W)
            lbl = ttk.Label(self.keys_frame, text=cfg.get("left_stick", {}).get(dirk,""), width=16, style="KeyBind.TLabel", padding=4)
            lbl.grid(column=1, row=row, padx=10, pady=5, sticky=tk.EW)
            
            btn = ttk.Button(self.keys_frame, text="Record", width=9)
            btn.grid(column=2, row=row, padx=10, pady=5)
            btn.bind("<ButtonPress-1>", lambda e, t="leftstick", k=dirk, w=lbl: record_button_press(t, k, w))
            btn.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
            self.leftstick_labels[dirk] = lbl
            row += 1
            
        ttk.Label(self.keys_frame, text="Stick Limiter(Walk)", font=("Segoe UI", 10), width=15).grid(column=0, row=row, padx=10, pady=8, sticky=tk.W)
        self.limiter_lbl = ttk.Label(self.keys_frame, text=cfg.get("left_stick_limiter", {}).get("bind_key","ctrl_l"), width=16, style="KeyBind.TLabel", padding=4)
        self.limiter_lbl.grid(column=1, row=row, padx=10, pady=8, sticky=tk.EW)
        
        btn_lim = ttk.Button(self.keys_frame, text="Record", width=9)
        btn_lim.grid(column=2, row=row, padx=10, pady=8)
        btn_lim.bind("<ButtonPress-1>", lambda e, t="limiter", k="bind_key", w=self.limiter_lbl: record_button_press(t, k, w))
        btn_lim.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
        
        self.limiter_toggle_var = tk.BooleanVar(value=cfg.get("left_stick_limiter", {}).get("is_toggle", False))
        chk_lim = ttk.Checkbutton(self.keys_frame, text="Toggle Mode", variable=self.limiter_toggle_var, command=self.on_limiter_toggle_changed)
        chk_lim.grid(column=3, row=row, sticky=tk.W, padx=10, pady=8)
        
        slider_frame = ttk.Frame(self.keys_frame)
        slider_frame.grid(column=4, row=row, columnspan=2, sticky=tk.W, padx=10, pady=8)
        ttk.Label(slider_frame, text="Rate: ", foreground="#6c757d").pack(side="left")
        
        self.limiter_val_var = tk.DoubleVar(value=cfg.get("left_stick_limiter", {}).get("value", 0.5))
        sld_lim = ttk.Scale(slider_frame, from_=0.1, to=1.0, variable=self.limiter_val_var, orient=tk.HORIZONTAL, length=120, command=lambda e: self.on_limiter_val_changed())
        sld_lim.pack(side="left", padx=5)
        row += 1

        btn_reset_kb = ttk.Button(self.keys_frame, text="Reset Keyboard Defaults", command=self.reset_keyboard_defaults)
        btn_reset_kb.grid(column=0, row=row, columnspan=2, padx=10, pady=15, sticky=tk.W)
        row += 1
        
        self.custom_sep = ttk.Separator(self.keys_frame, orient=tk.HORIZONTAL)
        self.custom_title_lbl = ttk.Label(self.keys_frame, text="Custom Auxiliary Macros / Triggers", style="Header.TLabel")
        self.custom_start_row = row + 2
        
        self.menu_sep = ttk.Separator(self.keys_frame, orient=tk.HORIZONTAL)
        self.menu_title_lbl = ttk.Label(self.keys_frame, text="Menu Navigation Shortcuts (Maps Select->A, Back->B Directly)", style="Header.TLabel")
        
        self.menu_labels = {}
        self.menu_ui_elements = []
        
        # === MOUSE TAB ===
        ttk.Label(mouse_frame, text="Fine-tune Emulated Right Stick Sensitivity and Curves", style="SubHeader.TLabel").grid(column=0, row=0, columnspan=3, sticky=tk.W, pady=(15,15), padx=20)
        
        self.mouse_profile_frame = ttk.LabelFrame(mouse_frame, text="Mouse Profiles", padding=10)
        self.mouse_profile_frame.grid(column=0, row=1, columnspan=3, sticky=tk.W, padx=20, pady=5)
        
        self.rb_m_soldier = ttk.Radiobutton(self.mouse_profile_frame, text="Soldier", variable=self.mouse_profile_var, value="soldier", command=self.on_mouse_profile_tab_changed)
        self.rb_m_soldier.pack(side="left", padx=5)
        self.rb_m_vehicle = ttk.Radiobutton(self.mouse_profile_frame, text="Vehicle", variable=self.mouse_profile_var, value="vehicle", command=self.on_mouse_profile_tab_changed)
        self.rb_m_vehicle.pack(side="left", padx=5)
        self.rb_m_plane = ttk.Radiobutton(self.mouse_profile_frame, text="Plane", variable=self.mouse_profile_var, value="plane", command=self.on_mouse_profile_tab_changed)
        self.rb_m_plane.pack(side="left", padx=5)
        
        if not cfg.get("profiles_enabled", False):
            self.rb_m_vehicle.state(["disabled"])
            self.rb_m_plane.state(["disabled"])
            self.rb_k_vehicle.state(["disabled"])
            self.rb_k_plane.state(["disabled"])

        ttk.Label(mouse_frame, text="Sensitivity X:").grid(column=0, row=2, padx=20, pady=8, sticky=tk.W)
        self.sens_x_var = tk.DoubleVar(value=cfg["mouse"]["sensitivity_x"])
        self.sens_x_scale = ttk.Scale(mouse_frame, from_=0.1, to=10.0, variable=self.sens_x_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.sens_x_scale.grid(column=1, row=2, padx=10, pady=8, sticky=tk.W)
        self.sens_x_lbl = ttk.Label(mouse_frame, text=f"{self.sens_x_var.get():.2f}")
        self.sens_x_lbl.grid(column=2, row=2, padx=10, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Sensitivity Y:").grid(column=0, row=3, padx=20, pady=8, sticky=tk.W)
        self.sens_y_var = tk.DoubleVar(value=cfg["mouse"]["sensitivity_y"])
        self.sens_y_scale = ttk.Scale(mouse_frame, from_=0.1, to=10.0, variable=self.sens_y_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.sens_y_scale.grid(column=1, row=3, padx=10, pady=8, sticky=tk.W)
        self.sens_y_lbl = ttk.Label(mouse_frame, text=f"{self.sens_y_var.get():.2f}")
        self.sens_y_lbl.grid(column=2, row=3, padx=10, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Deadzone X:").grid(column=0, row=4, padx=20, pady=8, sticky=tk.W)
        self.dead_x_var = tk.DoubleVar(value=cfg["mouse"]["deadzone_x"])
        self.dead_x_scale = ttk.Scale(mouse_frame, from_=0.0, to=0.5, variable=self.dead_x_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.dead_x_scale.grid(column=1, row=4, padx=10, pady=8, sticky=tk.W)
        self.dead_x_lbl = ttk.Label(mouse_frame, text=f"{self.dead_x_var.get():.2f}")
        self.dead_x_lbl.grid(column=2, row=4, padx=10, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Deadzone Y:").grid(column=0, row=5, padx=20, pady=8, sticky=tk.W)
        self.dead_y_var = tk.DoubleVar(value=cfg["mouse"]["deadzone_y"])
        self.dead_y_scale = ttk.Scale(mouse_frame, from_=0.0, to=0.5, variable=self.dead_y_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.dead_y_scale.grid(column=1, row=5, padx=10, pady=8, sticky=tk.W)
        self.dead_y_lbl = ttk.Label(mouse_frame, text=f"{self.dead_y_var.get():.2f}")
        self.dead_y_lbl.grid(column=2, row=5, padx=10, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Anti-Deadzone X:").grid(column=0, row=6, padx=20, pady=8, sticky=tk.W)
        self.adz_x_var = tk.DoubleVar(value=cfg["mouse"].get("anti_deadzone_x", 0.0))
        self.adz_x_scale = ttk.Scale(mouse_frame, from_=0.0, to=0.2, variable=self.adz_x_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.adz_x_scale.grid(column=1, row=6, padx=10, pady=8, sticky=tk.W)
        self.adz_x_lbl = ttk.Label(mouse_frame, text=f"{self.adz_x_var.get():.3f}")
        self.adz_x_lbl.grid(column=2, row=6, padx=10, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Anti-Deadzone Y:").grid(column=0, row=7, padx=20, pady=8, sticky=tk.W)
        self.adz_y_var = tk.DoubleVar(value=cfg["mouse"].get("anti_deadzone_y", 0.0))
        self.adz_y_scale = ttk.Scale(mouse_frame, from_=0.0, to=0.2, variable=self.adz_y_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.adz_y_scale.grid(column=1, row=7, padx=10, pady=8, sticky=tk.W)
        self.adz_y_lbl = ttk.Label(mouse_frame, text=f"{self.adz_y_var.get():.3f}")
        self.adz_y_lbl.grid(column=2, row=7, padx=10, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Linearity (Gamma):").grid(column=0, row=8, padx=20, pady=8, sticky=tk.W)
        self.gamma_var = tk.DoubleVar(value=cfg["mouse"]["linearity"])
        self.gamma_scale = ttk.Scale(mouse_frame, from_=0.1, to=2.0, variable=self.gamma_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.gamma_scale.grid(column=1, row=8, padx=10, pady=8, sticky=tk.W)
        self.gamma_lbl = ttk.Label(mouse_frame, text=f"{self.gamma_var.get():.2f}")
        self.gamma_lbl.grid(column=2, row=8, padx=10, pady=8, sticky=tk.W)

        self.invert_y_var = tk.BooleanVar(value=cfg["mouse"]["invert_y"])
        self.invert_y_chk = ttk.Checkbutton(mouse_frame, text="Invert Y Axis", variable=self.invert_y_var, command=self.update_mouse_config)
        self.invert_y_chk.grid(column=0, row=9, columnspan=2, padx=20, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Pixel to Unit Factor:").grid(column=0, row=10, padx=20, pady=8, sticky=tk.W)
        self.pt_unit_var = tk.DoubleVar(value=cfg["mouse"].get("pixel_to_unit", 100.0))
        self.pt_unit_scale = ttk.Scale(mouse_frame, from_=5.0, to=100.0, variable=self.pt_unit_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.pt_unit_scale.grid(column=1, row=10, padx=10, pady=8, sticky=tk.W)
        self.pt_unit_lbl = ttk.Label(mouse_frame, text=f"{self.pt_unit_var.get():.1f}")
        self.pt_unit_lbl.grid(column=2, row=10, padx=10, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Smoothing Samples:").grid(column=0, row=11, padx=20, pady=8, sticky=tk.W)
        self.smooth_var = tk.IntVar(value=cfg["mouse"].get("smoothing_samples", 1))
        smooth_spin = tk.Spinbox(mouse_frame, from_=1, to=10, textvariable=self.smooth_var, width=5, command=self.update_mouse_config)
        smooth_spin.grid(column=1, row=11, padx=10, pady=8, sticky=tk.W)
        smooth_spin.bind("<KeyRelease>", lambda e: self.update_mouse_config())

        ttk.Label(mouse_frame, text="Update Rate (Hz):").grid(row=12, column=0, sticky="w", padx=20, pady=8)

        hz_var = tk.IntVar(value=cfg.get("update_rate_hz", 120))
        hz_dropdown = ttk.Combobox(mouse_frame, textvariable=hz_var, values=[30, 60, 100, 120], width=10, state="readonly")
        hz_dropdown.grid(row=12, column=1, sticky="w", padx=10, pady=8)

        def on_hz_change(event):
            cfg["update_rate_hz"] = int(hz_var.get())
            save_config(cfg)

        hz_dropdown.bind("<<ComboboxSelected>>", on_hz_change)

        btn_reset_mouse = ttk.Button(mouse_frame, text="Reset Mouse Defaults", command=self.reset_mouse_defaults)
        btn_reset_mouse.grid(column=0, row=13, columnspan=2, padx=20, pady=15, sticky=tk.W)
        
        # --- APPLICATION SETTINGS TAB ---
        ttk.Label(settings_frame, text="System Hotkeys & Global Emulation State", style="SubHeader.TLabel").grid(column=0, row=0, columnspan=3, sticky=tk.W, pady=(15,10), padx=20)
        
        self.emulation_enabled_var = tk.BooleanVar(value=cfg.get("emulation_enabled", True))
        chk_master = ttk.Checkbutton(settings_frame, text="Master Emulation Active (Uncheck to suspend all background inputs completely)", variable=self.emulation_enabled_var, command=self.on_master_toggle_changed)
        chk_master.grid(column=0, row=1, columnspan=3, padx=20, pady=5, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Toggle Mouse Lock Hotkey:").grid(column=0, row=2, padx=20, pady=6, sticky=tk.W)
        self.hk_lock_lbl = ttk.Label(settings_frame, text=cfg.get("hotkeys",{}).get("toggle_lock","f5"), width=12, style="KeyBind.TLabel", padding=4)
        self.hk_lock_lbl.grid(column=1, row=2, padx=10, pady=6, sticky=tk.W)
        btn_hl = ttk.Button(settings_frame, text="Record", width=8)
        btn_hl.grid(column=2, row=2, padx=5, pady=6, sticky=tk.W)
        btn_hl.bind("<ButtonPress-1>", lambda e, t="hotkey_lock", k="toggle_lock", w=self.hk_lock_lbl: record_button_press(t, k, w))
        btn_hl.bind("<ButtonRelease-1>", lambda e: record_button_release(e))

        ttk.Label(settings_frame, text="Toggle Emulation Hotkey:").grid(column=0, row=3, padx=20, pady=6, sticky=tk.W)
        self.hk_emu_lbl = ttk.Label(settings_frame, text=cfg.get("hotkeys",{}).get("toggle_emulation","f6"), width=12, style="KeyBind.TLabel", padding=4)
        self.hk_emu_lbl.grid(column=1, row=3, padx=10, pady=6, sticky=tk.W)
        btn_he = ttk.Button(settings_frame, text="Record", width=8)
        btn_he.grid(column=2, row=3, padx=5, pady=6, sticky=tk.W)
        btn_he.bind("<ButtonPress-1>", lambda e, t="hotkey_emu", k="toggle_emulation", w=self.hk_emu_lbl: record_button_press(t, k, w))
        btn_he.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
        
        ttk.Label(settings_frame, text="Custom Macro Row Allocation Count (0-20):").grid(column=0, row=4, padx=20, pady=12, sticky=tk.W)
        self.custom_count_var = tk.IntVar(value=cfg.get("custom_count", 4))
        sp_cc = tk.Spinbox(settings_frame, from_=0, to=20, textvariable=self.custom_count_var, width=6, command=self.on_custom_count_changed)
        sp_cc.grid(column=1, row=4, padx=10, pady=12, sticky=tk.W)
        sp_cc.bind("<KeyRelease>", lambda e: self.on_custom_count_changed())
        
        ttk.Label(settings_frame, text="Hardware Controller Mixed Passthrough (Direct input injection coexistence)", style="SubHeader.TLabel").grid(column=0, row=5, columnspan=3, sticky=tk.W, pady=(15,10), padx=20)
        self.pt_enabled_var = tk.BooleanVar(value=cfg.get("controller_passthrough", {}).get("enabled", False))
        chk_pt = ttk.Checkbutton(settings_frame, text="Enable Controller Passthrough Modality", variable=self.pt_enabled_var, command=self.on_passthrough_toggled)
        chk_pt.grid(column=0, row=6, columnspan=3, padx=20, pady=5, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Select Passthrough Joystick Index:").grid(column=0, row=7, padx=20, pady=6, sticky=tk.W)
        self.pt_index_var = tk.IntVar(value=cfg.get("controller_passthrough", {}).get("selected_index", 0))
        sp_pt = ttk.Spinbox(settings_frame, from_=0, to=8, textvariable=self.pt_index_var, width=6, command=self.on_passthrough_index_changed)
        sp_pt.grid(column=1, row=7, padx=10, pady=6, sticky=tk.W)
        sp_pt.bind("<KeyRelease>", lambda e: self.on_passthrough_index_changed())
        
        ttk.Label(settings_frame, text="Target Software / Environment Settings", style="SubHeader.TLabel").grid(column=0, row=8, columnspan=3, sticky=tk.W, pady=(20,10), padx=20)
        
        ttk.Label(settings_frame, text="Game Executable Path:").grid(column=0, row=9, padx=20, pady=6, sticky=tk.W)
        self.exec_path_var = tk.StringVar(value=cfg.get("game_settings", {}).get("executable_path", ""))
        exec_entry = ttk.Entry(settings_frame, textvariable=self.exec_path_var, width=45)
        exec_entry.grid(column=1, row=9, padx=10, pady=6, sticky=tk.W)
        exec_entry.bind("<KeyRelease>", lambda e: self.save_game_settings())
        
        btn_browse = ttk.Button(settings_frame, text="Browse...", command=self.browse_executable)
        btn_browse.grid(column=2, row=9, padx=5, pady=6, sticky=tk.W)
        
        ttk.Label(settings_frame, text="Launch Arguments:").grid(column=0, row=10, padx=20, pady=6, sticky=tk.W)
        self.exec_args_var = tk.StringVar(value=cfg.get("game_settings", {}).get("arguments", ""))
        args_entry = ttk.Entry(settings_frame, textvariable=self.exec_args_var, width=45)
        args_entry.grid(column=1, row=10, padx=10, pady=6, sticky=tk.W)
        args_entry.bind("<KeyRelease>", lambda e: self.save_game_settings())
        
        ttk.Label(settings_frame, text="Profile Management", style="SubHeader.TLabel").grid(column=0, row=11, columnspan=3, sticky=tk.W, pady=(20,10), padx=20)
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.grid(column=0, row=12, columnspan=3, padx=20, pady=5, sticky=tk.W)
        
        btn_save_c = ttk.Button(btn_frame, text="Save Current Config To File", command=self.manual_save_config)
        btn_save_c.pack(side="left", padx=5)
        btn_load_c = ttk.Button(btn_frame, text="Reload Config From File", command=self.manual_load_config)
        btn_load_c.pack(side="left", padx=5)
        
        ttk.Label(settings_frame, text="GitHub Repository Updates Pipeline", style="SubHeader.TLabel").grid(column=0, row=13, columnspan=3, sticky=tk.W, pady=(20,10), padx=20)
        up_frame = ttk.Frame(settings_frame)
        up_frame.grid(column=0, row=14, columnspan=3, padx=20, pady=5, sticky=tk.W)
        
        btn_check_u = ttk.Button(up_frame, text="Check for Updates Manually", command=lambda: self.check_update(silent=False))
        btn_check_u.pack(side="left", padx=5)
        
        self.version_lbl = ttk.Label(settings_frame, text=f"Active Local Software Version: {CURRENT_VERSION}", foreground="#6c757d")
        self.version_lbl.grid(column=0, row=15, columnspan=3, padx=20, pady=(15,5), sticky=tk.W)

        self.status_var = tk.StringVar(value="System initialized. Remapper loop operational.")
        status_bar = tk.Label(self, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W, font=("Segoe UI", 9), bg="#e9ecef", fg="#495057", padx=4, pady=4)
        status_bar.pack(side="bottom", fill="x")

    def reset_keyboard_defaults(self):
        if messagebox.askyesno("Reset Defaults", "Are you sure you want to reset all keyboard mappings to default values?"):
            cfg["keyboard"] = DEFAULT_CONFIG["keyboard"].copy()
            cfg["keyboard_vehicle"] = {}
            cfg["keyboard_plane"] = {}
            cfg["left_stick"] = DEFAULT_CONFIG["left_stick"].copy()
            cfg["menu_buttons"] = DEFAULT_CONFIG["menu_buttons"].copy()
            save_config(cfg)
            self.refresh_keyboard_bindings_ui()
            for k, lbl in self.leftstick_labels.items():
                lbl.config(text=cfg.get("left_stick", {}).get(k, ""))
            for mkey, lbl in self.menu_labels.items():
                lbl.config(text=cfg.get("menu_buttons", {}).get(mkey, ""))
            self.status_var.set("Keyboard mappings reset to defaults.")

    def reset_mouse_defaults(self):
        if messagebox.askyesno("Reset Defaults", "Are you sure you want to reset all mouse tuning parameters to default values?"):
            cfg["mouse"] = DEFAULT_CONFIG["mouse"].copy()
            cfg["mouse_profiles"] = DEFAULT_CONFIG["mouse_profiles"].copy()
            save_config(cfg)
            self.load_mouse_profile_ui()
            self.smooth_var.set(cfg["mouse"].get("smoothing_samples", 1))
            self.pt_unit_var.set(cfg["mouse"].get("pixel_to_unit", 100.0))
            self.status_var.set("Mouse tuning parameters reset to defaults.")

    def create_section_divider(self, frame, row, title):
        sep = ttk.Separator(frame, orient=tk.HORIZONTAL)
        sep.grid(column=0, row=row, columnspan=6, sticky=tk.EW, pady=(20, 10))
        lbl = ttk.Label(frame, text=title, style="Header.TLabel")
        lbl.grid(column=0, row=row+1, columnspan=6, sticky=tk.W, padx=10, pady=(0, 10))
        return row + 2

    def build_custom_inputs_ui(self):
        for elem in self.menu_ui_elements: elem.destroy()
        self.menu_ui_elements.clear()
        
        row = self.custom_start_row
        c_count = self.custom_count_var.get()
        
        if c_count > 0:
            self.custom_sep.grid(column=0, row=row, columnspan=6, sticky=tk.EW, pady=(20, 10))
            self.custom_title_lbl.grid(column=0, row=row+1, columnspan=6, sticky=tk.W, padx=10, pady=(0, 10))
            row += 2
            
            headers = ["Macro Name", "Gamepad Target", "Current Binding", "", "", ""]
            for i, h in enumerate(headers):
                if h:
                    lbl_h = ttk.Label(self.keys_frame, text=h, font=("Segoe UI", 9, "bold"), foreground="#6c757d")
                    lbl_h.grid(column=i, row=row, padx=10, pady=5, sticky=tk.W)
                    self.menu_ui_elements.append(lbl_h)
            row += 1
            
            self.custom_widgets.clear()
            available_targets = list(cfg.get("keyboard", {}).keys())
            
            for idx in range(c_count):
                while len(cfg["custom_inputs"]) <= idx:
                    cfg["custom_inputs"].append({"name": f"custom{idx+1}", "target": "cross", "bind_key": "", "description": ""})
                ci = cfg["custom_inputs"][idx]
                
                var_name = tk.StringVar(value=ci.get("name", f"custom{idx+1}"))
                ent_name = ttk.Entry(self.keys_frame, textvariable=var_name, width=14)
                ent_name.grid(column=0, row=row, padx=10, pady=4, sticky=tk.W)
                
                var_target = tk.StringVar(value=ci.get("target", "cross"))
                cb_target = ttk.Combobox(self.keys_frame, textvariable=var_target, values=available_targets, state="readonly", width=14)
                cb_target.grid(column=1, row=row, padx=10, pady=4, sticky=tk.W)
                
                lbl_bind = ttk.Label(self.keys_frame, text=ci.get("bind_key",""), width=16, style="KeyBind.TLabel", padding=4)
                lbl_bind.grid(column=2, row=row, padx=10, pady=4, sticky=tk.EW)
                
                btn_rec = ttk.Button(self.keys_frame, text="Record", width=9)
                btn_rec.grid(column=3, row=row, padx=10, pady=4, sticky=tk.W)
                btn_rec.bind("<ButtonPress-1>", lambda e, t="custom", k=str(idx), w=lbl_bind: record_button_press(t, k, w))
                btn_rec.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
                
                def make_save_callback(index, vname, vtarget):
                    return lambda *args: self.update_custom_input_fields(index, vname.get(), vtarget.get())
                
                var_name.trace_add("write", make_save_callback(idx, var_name, var_target))
                var_target.trace_add("write", make_save_callback(idx, var_name, var_target))
                
                self.menu_ui_elements.extend([ent_name, cb_target, lbl_bind, btn_rec])
                row += 1

        self.menu_sep.grid(column=0, row=row, columnspan=6, sticky=tk.EW, pady=(20, 10))
        self.menu_title_lbl.grid(column=0, row=row+1, columnspan=6, sticky=tk.W, padx=10, pady=(0, 10))
        row += 2
        
        left_menu_frame = ttk.Frame(self.keys_frame)
        left_menu_frame.grid(column=0, row=row, columnspan=3, sticky=tk.NW, padx=10, pady=5)
        self.menu_ui_elements.append(left_menu_frame)
        
        right_profile_frame = ttk.Frame(self.keys_frame)
        right_profile_frame.grid(column=3, row=row, columnspan=3, sticky=tk.NW, padx=20, pady=5)
        self.menu_ui_elements.append(right_profile_frame)
        
        m_row = 0
        for mkey, keybind in cfg.get("menu_buttons", {}).items():
            ttk.Label(left_menu_frame, text=f"Menu {mkey.capitalize()}", font=("Segoe UI", 10), width=15).grid(column=0, row=m_row, padx=5, pady=4, sticky=tk.W)
            lbl = ttk.Label(left_menu_frame, text=keybind, width=14, style="KeyBind.TLabel", padding=4)
            lbl.grid(column=1, row=m_row, padx=5, pady=4, sticky=tk.W)
            
            btn = ttk.Button(left_menu_frame, text="Record", width=8)
            btn.grid(column=2, row=m_row, padx=5, pady=4, sticky=tk.W)
            btn.bind("<ButtonPress-1>", lambda e, t="menu", k=mkey, w=lbl: record_button_press(t, k, w))
            btn.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
            self.menu_labels[mkey] = lbl
            m_row += 1

        ttk.Label(right_profile_frame, text="Vehicle/Plane profile", font=("Segoe UI", 11, "bold")).grid(column=0, row=0, columnspan=3, sticky=tk.W, pady=(0,5))
        
        self.profiles_active_var = tk.BooleanVar(value=cfg.get("profiles_enabled", False))
        chk_p_active = ttk.Checkbutton(right_profile_frame, text="activate", variable=self.profiles_active_var, command=self.on_profiles_active_toggle)
        chk_p_active.grid(column=0, row=1, columnspan=3, sticky=tk.W, pady=2)
        
        ttk.Label(right_profile_frame, text="Soldier Context Key:").grid(column=0, row=2, sticky=tk.W, pady=4, padx=(0,5))
        self.lbl_soldier_b = ttk.Label(right_profile_frame, text=cfg.get("soldier_key", "e"), width=12, style="KeyBind.TLabel", padding=3)
        self.lbl_soldier_b.grid(column=1, row=2, pady=4, padx=5)
        btn_sb = ttk.Button(right_profile_frame, text="Record", width=8)
        btn_sb.grid(column=2, row=2, pady=4, padx=5)
        btn_sb.bind("<ButtonPress-1>", lambda e, t="soldier_bind", k="soldier_key", w=self.lbl_soldier_b: record_button_press(t, k, w))
        btn_sb.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
        
        ttk.Label(right_profile_frame, text="Vehicle Context Key:").grid(column=0, row=3, sticky=tk.W, pady=4, padx=(0,5))
        self.lbl_vehicle_b = ttk.Label(right_profile_frame, text=cfg.get("vehicle_key", "t"), width=12, style="KeyBind.TLabel", padding=3)
        self.lbl_vehicle_b.grid(column=1, row=3, pady=4, padx=5)
        btn_vb = ttk.Button(right_profile_frame, text="Record", width=8)
        btn_vb.grid(column=2, row=3, pady=4, padx=5)
        btn_vb.bind("<ButtonPress-1>", lambda e, t="vehicle_bind", k="vehicle_key", w=self.lbl_vehicle_b: record_button_press(t, k, w))
        btn_vb.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
        
        ttk.Label(right_profile_frame, text="Plane Context Key:").grid(column=0, row=4, sticky=tk.W, pady=4, padx=(0,5))
        self.lbl_plane_b = ttk.Label(right_profile_frame, text=cfg.get("plane_key", "y"), width=12, style="KeyBind.TLabel", padding=3)
        self.lbl_plane_b.grid(column=1, row=4, pady=4, padx=5)
        btn_pb = ttk.Button(right_profile_frame, text="Record", width=8)
        btn_pb.grid(column=2, row=4, pady=4, padx=5)
        btn_pb.bind("<ButtonPress-1>", lambda e, t="plane_bind", k="plane_key", w=self.lbl_plane_b: record_button_press(t, k, w))
        btn_pb.bind("<ButtonRelease-1>", lambda e: record_button_release(e))

    def rebuild_custom_inputs_ui(self):
        self.build_custom_inputs_ui()

    def on_profiles_active_toggle(self):
        state = self.profiles_active_var.get()
        cfg["profiles_enabled"] = state
        save_config(cfg)
        
        if state:
            self.rb_m_vehicle.state(["!disabled"])
            self.rb_m_plane.state(["!disabled"])
            self.rb_k_vehicle.state(["!disabled"])
            self.rb_k_plane.state(["!disabled"])
        else:
            self.rb_m_vehicle.state(["disabled"])
            self.rb_m_plane.state(["disabled"])
            self.rb_k_vehicle.state(["disabled"])
            self.rb_k_plane.state(["disabled"])
            set_profile_context("soldier")

    def on_mouse_profile_tab_changed(self):
        p = self.mouse_profile_var.get()
        if cfg.get("profiles_enabled", False):
            set_profile_context(p)
        else:
            self.load_mouse_profile_ui()

    def refresh_keyboard_bindings_ui(self):
        for ps_key, lbl in self.bind_widgets.items():
            entry = cfg.get("keyboard", {}).get(ps_key, {})
            actual_bind = entry.get("bind_key", "")
            
            if cfg.get("profiles_enabled", False) and current_profile_context == "vehicle":
                actual_bind = cfg.get("keyboard_vehicle", {}).get(ps_key, actual_bind)
                if ps_key == "l1": actual_bind = "w"
                elif ps_key == "l2": actual_bind = "s"
                elif ps_key == "r2": actual_bind = "mouse2"
            elif cfg.get("profiles_enabled", False) and current_profile_context == "plane":
                actual_bind = cfg.get("keyboard_plane", {}).get(ps_key, actual_bind)
                if ps_key == "l1": actual_bind = "w"
                elif ps_key == "l2": actual_bind = "s"
                elif ps_key == "r2": actual_bind = "mouse2"
                
            lbl.config(text=actual_bind)

    def load_mouse_profile_ui(self):
        p = self.mouse_profile_var.get()
        if p == "soldier": m_cfg = cfg["mouse"]
        else: m_cfg = cfg.get("mouse_profiles", {}).get(p, {})
            
        self.sens_x_var.set(m_cfg.get("sensitivity_x", 3.0))
        self.sens_y_var.set(m_cfg.get("sensitivity_y", 3.2))
        self.dead_x_var.set(m_cfg.get("deadzone_x", 0.0))
        self.dead_y_var.set(m_cfg.get("deadzone_y", 0.0))
        self.adz_x_var.set(m_cfg.get("anti_deadzone_x", 0.0))
        self.adz_y_var.set(m_cfg.get("anti_deadzone_y", 0.0))
        self.gamma_var.set(m_cfg.get("linearity", 1.5))
        self.invert_y_var.set(m_cfg.get("invert_y", True))
        
        self.sens_x_lbl.config(text=f"{self.sens_x_var.get():.2f}")
        self.sens_y_lbl.config(text=f"{self.sens_y_var.get():.2f}")
        self.dead_x_lbl.config(text=f"{self.dead_x_var.get():.2f}")
        self.dead_y_lbl.config(text=f"{self.dead_y_var.get():.2f}")
        self.adz_x_lbl.config(text=f"{self.adz_x_var.get():.3f}")
        self.adz_y_lbl.config(text=f"{self.adz_y_var.get():.3f}")
        self.gamma_lbl.config(text=f"{self.gamma_var.get():.2f}")

    def update_mouse_config(self):
        p = self.mouse_profile_var.get()
        if p == "soldier":
            cfg["mouse"]["sensitivity_x"] = self.sens_x_var.get()
            cfg["mouse"]["sensitivity_y"] = self.sens_y_var.get()
            cfg["mouse"]["deadzone_x"] = self.dead_x_var.get()
            cfg["mouse"]["deadzone_y"] = self.dead_y_var.get()
            cfg["mouse"]["anti_deadzone_x"] = self.adz_x_var.get()
            cfg["mouse"]["anti_deadzone_y"] = self.adz_y_var.get()
            cfg["mouse"]["linearity"] = self.gamma_var.get()
            cfg["mouse"]["invert_y"] = self.invert_y_var.get()
            cfg["mouse"]["pixel_to_unit"] = self.pt_unit_var.get()
            cfg["mouse"]["smoothing_samples"] = self.smooth_var.get()
        else:
            if "mouse_profiles" not in cfg: cfg["mouse_profiles"] = {}
            if p not in cfg["mouse_profiles"]: cfg["mouse_profiles"][p] = {}
            cfg["mouse_profiles"][p]["sensitivity_x"] = self.sens_x_var.get()
            cfg["mouse_profiles"][p]["sensitivity_y"] = self.sens_y_var.get()
            cfg["mouse_profiles"][p]["deadzone_x"] = self.dead_x_var.get()
            cfg["mouse_profiles"][p]["deadzone_y"] = self.dead_y_var.get()
            cfg["mouse_profiles"][p]["anti_deadzone_x"] = self.adz_x_var.get()
            cfg["mouse_profiles"][p]["anti_deadzone_y"] = self.adz_y_var.get()
            cfg["mouse_profiles"][p]["linearity"] = self.gamma_var.get()
            cfg["mouse_profiles"][p]["invert_y"] = self.invert_y_var.get()
            
        save_config(cfg)
        self.sens_x_lbl.config(text=f"{self.sens_x_var.get():.2f}")
        self.sens_y_lbl.config(text=f"{self.sens_y_var.get():.2f}")
        self.dead_x_lbl.config(text=f"{self.dead_x_var.get():.2f}")
        self.dead_y_lbl.config(text=f"{self.dead_y_var.get():.2f}")
        self.adz_x_lbl.config(text=f"{self.adz_x_var.get():.3f}")
        self.adz_y_lbl.config(text=f"{self.adz_y_var.get():.3f}")
        self.gamma_lbl.config(text=f"{self.gamma_var.get():.2f}")
        self.pt_unit_lbl.config(text=f"{self.pt_unit_var.get():.1f}")

    def update_custom_input_fields(self, index, name, target):
        while len(cfg["custom_inputs"]) <= index:
            cfg["custom_inputs"].append({"name": f"custom{index+1}", "target": "cross", "bind_key": "", "description": ""})
        cfg["custom_inputs"][index]["name"] = name
        cfg["custom_inputs"][index]["target"] = target
        save_config(cfg)

    def on_custom_count_changed(self):
        try:
            val = self.custom_count_var.get()
            if 0 <= val <= 20:
                cfg["custom_count"] = val
                save_config(cfg)
                self.rebuild_custom_inputs_ui()
        except Exception: pass

    def on_limiter_toggle_changed(self):
        cfg["left_stick_limiter"]["is_toggle"] = self.limiter_toggle_var.get()
        save_config(cfg)

    def on_limiter_val_changed(self):
        cfg["left_stick_limiter"]["value"] = self.limiter_val_var.get()
        save_config(cfg)

    def on_master_toggle_changed(self):
        state = self.emulation_enabled_var.get()
        cfg["emulation_enabled"] = state
        save_config(cfg)
        if not state and mouse_locked: toggle_mouse_lock()

    def on_passthrough_toggled(self):
        if "controller_passthrough" not in cfg: cfg["controller_passthrough"] = {}
        cfg["controller_passthrough"]["enabled"] = self.pt_enabled_var.get()
        save_config(cfg)

    def on_passthrough_index_changed(self):
        if "controller_passthrough" not in cfg: cfg["controller_passthrough"] = {}
        try:
            cfg["controller_passthrough"]["selected_index"] = self.pt_index_var.get()
            save_config(cfg)
        except Exception: pass

    def save_game_settings(self):
        if "game_settings" not in cfg: cfg["game_settings"] = {}
        cfg["game_settings"]["executable_path"] = self.exec_path_var.get()
        cfg["game_settings"]["arguments"] = self.exec_args_var.get()
        save_config(cfg)

    def browse_executable(self):
        path = filedialog.askopenfilename(filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")])
        if path:
            self.exec_path_var.set(path)
            self.save_game_settings()

    def start_game(self):
            exe = self.exec_path_var.get()
            args = self.exec_args_var.get()
            if not exe:
                messagebox.showwarning("Execution Pipeline", "No binary context path declared inside environment.")
                return
            
            import subprocess
            import os
            import time
            try:
                exe_clean = os.path.normpath(exe.strip('"'))
                game_folder = os.path.dirname(exe_clean)
                bat_args = args.replace('%', '%%')
                
                bat_path = os.path.abspath("launch_game.bat")
                
                with open(bat_path, "w", encoding="utf-8") as bat_file:
                    bat_file.write("@echo off\n")
                    bat_file.write(f'cd /d "{game_folder}"\n')
                    if bat_args:
                        bat_file.write(f'start "" "{exe_clean}" {bat_args}\n')
                    else:
                        bat_file.write(f'start "" "{exe_clean}"\n')
                
                cmd = f'explorer "{bat_path}"'
                subprocess.Popen(cmd, shell=True)
                
                def cleanup_bat():
                    time.sleep(1.5)
                    try:
                        if os.path.exists(bat_path):
                            os.remove(bat_path)
                    except Exception:
                        pass
    
                threading.Thread(target=cleanup_bat, daemon=True).start()
                
                self.status_var.set("Target game execution environment spawned via script wrapper.")
            except Exception as e:
                messagebox.showerror("Execution Pipeline Critical", f"Failed to instantiate target process tree:\n{e}")
                
                def cleanup_bat():
                    time.sleep(1.5) # Odotetaan hetki että peli ehtii käynnistyä
                    try:
                        if os.path.exists(bat_path):
                            os.remove(bat_path)
                    except Exception:
                        pass # Jos tiedosto on vielä lukittu, jätetään se rauhaan
    
                threading.Thread(target=cleanup_bat, daemon=True).start()
                
                self.status_var.set("Target game execution environment spawned via script wrapper.")
            except Exception as e:
                messagebox.showerror("Execution Pipeline Critical", f"Failed to instantiate target process tree:\n{e}")

    def manual_save_config(self):
        save_config(cfg)
        messagebox.showinfo("Config", f"Configuration successfully saved to {CONFIG_FILE}")

    def manual_load_config(self):
        global cfg
        cfg = load_config()
        self.refresh_keyboard_bindings_ui()
        self.load_mouse_profile_ui()
        self.status_var.set("Configuration reloaded from file.")

    def check_update(self, silent=True):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                latest = data.get("tag_name", "")
                if latest and latest != CURRENT_VERSION:
                    if messagebox.askyesno("Update Available", f"A new version ({latest}) is available! Open GitHub download page?"):
                        webbrowser.open(data.get("html_url", f"https://github.com/{GITHUB_REPO}"))
                elif not silent:
                    messagebox.showinfo("Up to Date", f"You are running the latest version ({CURRENT_VERSION}).")
        except Exception as e:
            if not silent:
                messagebox.showerror("Update Error", f"Failed to check for updates:\n{e}")

if __name__ == "__main__":
    try:
        gamepad = vg.VX360Gamepad()
    except Exception as e:
        print(f"Failed to initialize vgamepad Xbox controller: {e}")

    raw_window = RawInputWindow()
    raw_input_thread = threading.Thread(target=raw_window.start, daemon=True)
    raw_input_thread.start()

    update_thread = threading.Thread(target=update_loop, daemon=True)
    update_thread.start()

    app = App()
    
    def on_closing():
        global running
        running = False
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()