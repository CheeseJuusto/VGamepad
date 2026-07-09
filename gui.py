# gui.py
# Complete, ready-to-run GUI for vgamepad mapping with:
# - Keys / Mouse tabs
# - Custom inputs per-row with dynamic count (0-20) and working save/load
# - Record buttons with short-press to bind and long-press (>=1s) to clear
# - Hotkeys fully rebindable from the Settings tab (Mouse lock & Emulation toggle)
# - Mouse lock that preserves identical delta behavior locked vs free
# - Separate X/Y sensitivity and deadzone, and linearity (gamma) control
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
# - Version v1.0
#
# Requires: vgamepad, pynput, pygame, requests, ViGEmBus driver installed on Windows

import json
import threading
import time
import ctypes
import os
import sys
import urllib.request
import webbrowser
from collections import deque
import vgamepad as vg
from pynput import keyboard, mouse
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pygame

# --- Sovelluksen nykyinen versio ---
CURRENT_VERSION = "v1.0"
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
        "linearity": 0.58,
        "invert_y": True,
        "pixel_to_unit": 17.0,
        "smoothing_samples": 5
    },
    "mouse_profiles": {
        "vehicle": {
            "sensitivity_x": 3.0,
            "sensitivity_y": 3.2,
            "deadzone_x": 0.0,
            "deadzone_y": 0.0,
            "linearity": 0.58,
            "invert_y": True
        },
        "plane": {
            "sensitivity_x": 6.0,
            "sensitivity_y": 6.4,
            "deadzone_x": 0.0,
            "deadzone_y": 0.0,
            "linearity": 0.58,
            "invert_y": True
        }
    },
    "update_rate_hz": 60,
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
        "executable_path": "WORK IN PROGRESS!!",
        "arguments": "--no-gui \"%RPCS3_GAMEID%:NPEB00092\""
    },
    "controller_passthrough": {
        "enabled": False,
        "selected_index": 0
    }
}

CONFIG_FILE = "config.json"

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
                        "linearity": loaded["mouse"].get("linearity", 0.58),
                        "invert_y": loaded["mouse"].get("invert_y", True)
                    }

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

# Alustetaan ohjain tyhjäksi, luodaan se start_listeners_and_loopissa
gamepad = None

mouse_dx_queue = deque(maxlen=cfg["mouse"].get("smoothing_samples", 1))
mouse_dy_queue = deque(maxlen=cfg["mouse"].get("smoothing_samples", 1))
last_real_pos = None            
last_user_move_time = 0.0
running = True
mouse_locked = False
recording_target = None   
recording_widget = None
current_record_press_time = None
current_record_candidate = None  
buttons_pressed = set()
triggers_pressed = set()
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

def normalize_key_name(key):
    try:
        if key.char is not None:
            if 1 <= ord(key.char) <= 26:
                return chr(ord(key.char) + 96)
            return key.char.lower()
    except AttributeError:
        pass
    return str(key).split('.')[-1].lower()

def apply_deadzone_value(v, dz):
    return 0.0 if abs(v) < dz else v

def apply_linearity(v, gamma):
    sign = 1 if v >= 0 else -1
    return sign * (abs(v) ** gamma)

kb_listener = None
ms_listener = None

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

def on_key_press(key):
    global recording_target, left_stick_state, limiter_active, current_profile_context
    kname = normalize_key_name(key)
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
                    current_profile_context = "soldier"
                    app.mouse_profile_var.set("soldier")
                    app.load_mouse_profile_ui()
                    app.refresh_keyboard_bindings_ui()
                elif ci.get("target") == "vehicle_profile":
                    current_profile_context = "vehicle"
                    app.mouse_profile_var.set("vehicle")
                    app.load_mouse_profile_ui()
                    app.refresh_keyboard_bindings_ui()
                elif ci.get("target") == "plane_profile":
                    current_profile_context = "plane"
                    app.mouse_profile_var.set("plane")
                    app.load_mouse_profile_ui()
                    app.refresh_keyboard_bindings_ui()

        if kname == cfg.get("soldier_key", "e"):
            current_profile_context = "soldier"
            try:
                app.mouse_profile_var.set("soldier")
                app.load_mouse_profile_ui()
                app.refresh_keyboard_bindings_ui()
                app.status_var.set("Context switched to: Soldier")
            except Exception: pass
            return
        elif kname == cfg.get("vehicle_key", "t"):
            current_profile_context = "vehicle"
            try:
                app.mouse_profile_var.set("vehicle")
                app.load_mouse_profile_ui()
                app.refresh_keyboard_bindings_ui()
                app.status_var.set("Context switched to: Vehicle")
            except Exception: pass
            return
        elif kname == cfg.get("plane_key", "y"):
            current_profile_context = "plane"
            try:
                app.mouse_profile_var.set("plane")
                app.load_mouse_profile_ui()
                app.refresh_keyboard_bindings_ui()
                app.status_var.set("Context switched to: Plane")
            except Exception: pass
            return

    lk = cfg.get("left_stick_limiter", {}).get("bind_key", "ctrl_l").lower()
    if kname == lk and lk != "":
        if cfg.get("left_stick_limiter", {}).get("is_toggle", False):
            limiter_active = not limiter_active
        else:
            limiter_active = True
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

def on_key_release(key):
    global limiter_active
    if not cfg.get("emulation_enabled", True):
        return
        
    kname = normalize_key_name(key)
    
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

def on_move(x, y):
    global last_real_pos, last_user_move_time, mouse_locked, screen_center
    if not cfg.get("emulation_enabled", True):
        return
        
    now = time.time()
    if last_real_pos is None:
        last_real_pos = (x, y)
        last_user_move_time = now
        return
    dx = x - last_real_pos[0]
    dy = y - last_real_pos[1]
    last_real_pos = (x, y)
    last_user_move_time = now
    if mouse_locked:
        cx, cy = screen_center
        if x == cx and y == cy:
            return
    mouse_dx_queue.append(dx)
    mouse_dy_queue.append(dy)

def on_click(x, y, button, pressed):
    global recording_target, recording_widget
    
    if not cfg.get("emulation_enabled", True) and not recording_target:
        return
        
    bname = str(button).split('.')[-1].lower()
    
    if bname == "left": keyname = "mouse1"
    elif bname == "right": keyname = "mouse2"
    elif bname == "middle": keyname = "mouse3"
    elif bname == "x1": keyname = "mouse4"
    elif bname == "x2": keyname = "mouse5"
    else: keyname = f"mouse_{bname}"

    if recording_target:
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
            if xinp:
                if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
                    triggers_pressed.add(xinp)
                    threading.Thread(target=lambda: [time.sleep(0.1), triggers_pressed.discard(xinp)]).start()
                else:
                    buttons_pressed.add(xinp)
                    threading.Thread(target=lambda: [time.sleep(0.1), buttons_pressed.discard(xinp)]).start()

def update_loop():
    update_rate = int(cfg.get("update_rate_hz", 60))
    period = 1.0 / update_rate
    global last_user_move_time, mouse_locked, screen_center, last_real_pos, limiter_active, current_profile_context, gamepad
    
    pygame.init()
    pygame.joystick.init()
    
    while running:
        if not cfg.get("emulation_enabled", True):
            if gamepad:
                try:
                    gamepad.reset()
                    gamepad.update()
                except Exception: pass
            time.sleep(period)
            continue

        pixel_to_unit = float(cfg.get("mouse", {}).get("pixel_to_unit", 20.0))
        
        if cfg.get("profiles_enabled", False) and current_profile_context in ("vehicle", "plane"):
            p_data = cfg.get("mouse_profiles", {}).get(current_profile_context, {})
            sens_x = float(p_data.get("sensitivity_x", 3.0))
            sens_y = float(p_data.get("sensitivity_y", 3.2))
            dead_x = float(p_data.get("deadzone_x", 0.0))
            dead_y = float(p_data.get("deadzone_y", 0.0))
            gamma = float(p_data.get("linearity", 0.58))
            invert_y = bool(p_data.get("invert_y", True))
        else:
            sens_x = float(cfg.get("mouse", {}).get("sensitivity_x", 3.0))
            sens_y = float(cfg.get("mouse", {}).get("sensitivity_y", 3.2))
            dead_x = float(cfg.get("mouse", {}).get("deadzone_x", 0.0))
            dead_y = float(cfg.get("mouse", {}).get("deadzone_y", 0.0))
            gamma = float(cfg.get("mouse", {}).get("linearity", 0.58))
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
                avg_dx = sum(mouse_dx_queue) / len(mouse_dx_queue)
                avg_dy = sum(mouse_dy_queue) / len(mouse_dy_queue)
                mouse_dx_queue.clear(); mouse_dy_queue.clear()
            else:
                avg_dx = 0.0; avg_dy = 0.0

            raw_x = (avg_dx / pixel_to_unit) * sens_x
            raw_y = (avg_dy / pixel_to_unit) * sens_y
            vx = max(-1.0, min(1.0, apply_deadzone_value(raw_x, dead_x)))
            vy = max(-1.0, min(1.0, apply_deadzone_value(raw_y, dead_y)))
            vx = max(-1.0, min(1.0, apply_linearity(vx, gamma)))
            vy = max(-1.0, min(1.0, apply_linearity(vy, gamma)))

            if invert_y: vy = -vy
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
            last_real_pos = (cx, cy)
            SetCursorPos(cx, cy)
        time.sleep(period)

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

        try:
            if hasattr(sys, '_MEIPASS'): icon_path = os.path.join(sys._MEIPASS, "app.ico")
            else: icon_path = os.path.join(os.path.dirname(__file__), "app.ico")
            if os.path.exists(icon_path): self.iconbitmap(icon_path)
        except Exception: pass
            
        self.custom_widgets = []
        self.custom_rows_pool = []
        
        # Alustetaan yhteinen profiilimuuttuja ennen widgettien luontia
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
        
        nb.add(sf_keys, text="Keyboard Mapping")
        nb.add(sf_mouse, text="Mouse Input Tuning")
        nb.add(sf_settings, text="Application Settings")
        
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

        ttk.Label(mouse_frame, text="Linearity (Gamma):").grid(column=0, row=6, padx=20, pady=8, sticky=tk.W)
        self.gamma_var = tk.DoubleVar(value=cfg["mouse"]["linearity"])
        self.gamma_scale = ttk.Scale(mouse_frame, from_=0.1, to=2.0, variable=self.gamma_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.gamma_scale.grid(column=1, row=6, padx=10, pady=8, sticky=tk.W)
        self.gamma_lbl = ttk.Label(mouse_frame, text=f"{self.gamma_var.get():.2f}")
        self.gamma_lbl.grid(column=2, row=6, padx=10, pady=8, sticky=tk.W)

        self.invert_y_var = tk.BooleanVar(value=cfg["mouse"]["invert_y"])
        self.invert_y_chk = ttk.Checkbutton(mouse_frame, text="Invert Y Axis", variable=self.invert_y_var, command=self.update_mouse_config)
        self.invert_y_chk.grid(column=0, row=7, columnspan=2, padx=20, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Pixel to Unit Factor:").grid(column=0, row=8, padx=20, pady=8, sticky=tk.W)
        self.pt_unit_var = tk.DoubleVar(value=cfg["mouse"].get("pixel_to_unit", 20.0))
        self.pt_unit_scale = ttk.Scale(mouse_frame, from_=5.0, to=100.0, variable=self.pt_unit_var, orient=tk.HORIZONTAL, length=200, command=lambda e: self.update_mouse_config())
        self.pt_unit_scale.grid(column=1, row=8, padx=10, pady=8, sticky=tk.W)
        self.pt_unit_lbl = ttk.Label(mouse_frame, text=f"{self.pt_unit_var.get():.1f}")
        self.pt_unit_lbl.grid(column=2, row=8, padx=10, pady=8, sticky=tk.W)

        ttk.Label(mouse_frame, text="Smoothing Samples:").grid(column=0, row=9, padx=20, pady=8, sticky=tk.W)
        self.smooth_var = tk.IntVar(value=cfg["mouse"].get("smoothing_samples", 1))
        smooth_spin = tk.Spinbox(mouse_frame, from_=1, to=10, textvariable=self.smooth_var, width=5, command=self.update_mouse_config)
        smooth_spin.grid(column=1, row=9, padx=10, pady=8, sticky=tk.W)
        smooth_spin.bind("<KeyRelease>", lambda e: self.update_mouse_config())
        
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
        sp_pt = tk.Spinbox(settings_frame, from_=0, to=8, textvariable=self.pt_index_var, width=6, command=self.on_passthrough_index_changed)
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
        
        ttk.Label(settings_frame, text="Profile Profile Management", style="SubHeader.TLabel").grid(column=0, row=11, columnspan=3, sticky=tk.W, pady=(20,10), padx=20)
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
            self.mouse_profile_var.set("soldier")
            global current_profile_context
            current_profile_context = "soldier"
            self.load_mouse_profile_ui()
            self.refresh_keyboard_bindings_ui()

    def on_mouse_profile_tab_changed(self):
        global current_profile_context
        p = self.mouse_profile_var.get()
        if cfg.get("profiles_enabled", False):
            current_profile_context = p
            self.refresh_keyboard_bindings_ui()
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
        self.gamma_var.set(m_cfg.get("linearity", 0.58))
        self.invert_y_var.set(m_cfg.get("invert_y", True))
        
        self.sens_x_lbl.config(text=f"{self.sens_x_var.get():.2f}")
        self.sens_y_lbl.config(text=f"{self.sens_y_var.get():.2f}")
        self.dead_x_lbl.config(text=f"{self.dead_x_var.get():.2f}")
        self.dead_y_lbl.config(text=f"{self.dead_y_var.get():.2f}")
        self.gamma_lbl.config(text=f"{self.gamma_var.get():.2f}")

    def update_mouse_config(self):
        p = self.mouse_profile_var.get()
        if p == "soldier":
            cfg["mouse"]["sensitivity_x"] = self.sens_x_var.get()
            cfg["mouse"]["sensitivity_y"] = self.sens_y_var.get()
            cfg["mouse"]["deadzone_x"] = self.dead_x_var.get()
            cfg["mouse"]["deadzone_y"] = self.dead_y_var.get()
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
            cfg["mouse_profiles"][p]["linearity"] = self.gamma_var.get()
            cfg["mouse_profiles"][p]["invert_y"] = self.invert_y_var.get()
            
        save_config(cfg)
        self.sens_x_lbl.config(text=f"{self.sens_x_var.get():.2f}")
        self.sens_y_lbl.config(text=f"{self.sens_y_var.get():.2f}")
        self.dead_x_lbl.config(text=f"{self.dead_x_var.get():.2f}")
        self.dead_y_lbl.config(text=f"{self.dead_y_var.get():.2f}")
        self.gamma_lbl.config(text=f"{self.gamma_var.get():.2f}")
        self.pt_unit_lbl.config(text=f"{self.pt_unit_var.get():.1f}")
        
        global mouse_dx_queue, mouse_dy_queue
        mouse_dx_queue = deque(maxlen=int(self.smooth_var.get()))
        mouse_dy_queue = deque(maxlen=int(self.smooth_var.get()))

    def update_custom_input_fields(self, index, name, target):
        if index < len(cfg["custom_inputs"]):
            cfg["custom_inputs"][index]["name"] = name
            cfg["custom_inputs"][index]["target"] = target
            save_config(cfg)

    def on_custom_count_changed(self):
        try: val = int(self.custom_count_var.get())
        except Exception: return
        val = max(0, min(20, val))
        cfg["custom_count"] = val
        save_config(cfg)
        self.build_custom_inputs_ui()

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
        status = "ENABLED" if state else "DISABLED"
        self.status_var.set(f"Remap hooks master state synchronized: {status}")
        global mouse_locked
        if not state and mouse_locked: toggle_mouse_lock()

    def on_passthrough_toggled(self):
        cfg["controller_passthrough"]["enabled"] = self.pt_enabled_var.get()
        save_config(cfg)

    def on_passthrough_index_changed(self):
        try:
            val = int(self.pt_index_var.get())
            cfg["controller_passthrough"]["selected_index"] = val
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

    def manual_save_config(self):
        save_config(cfg)
        messagebox.showinfo("Config Management", "Active schema settings successfully flushed to disk JSON store.")

    def manual_load_config(self):
        global cfg
        cfg = load_config()
        self.custom_count_var.set(cfg.get("custom_count", 4))
        self.build_custom_inputs_ui()
        self.refresh_keyboard_bindings_ui()
        for k, lbl in self.leftstick_labels.items(): lbl.config(text=cfg.get("left_stick",{}).get(k,""))
        self.limiter_lbl.config(text=cfg.get("left_stick_limiter",{}).get("bind_key","ctrl_l"))
        self.limiter_toggle_var.set(cfg.get("left_stick_limiter",{}).get("is_toggle",False))
        self.limiter_val_var.set(cfg.get("left_stick_limiter",{}).get("value",0.45))
        self.hk_lock_lbl.config(text=cfg.get("hotkeys",{}).get("toggle_lock","f5"))
        self.hk_emu_lbl.config(text=cfg.get("hotkeys",{}).get("toggle_emulation","f6"))
        self.emulation_enabled_var.set(cfg.get("emulation_enabled",True))
        self.pt_enabled_var.set(cfg.get("controller_passthrough",{}).get("enabled",False))
        self.pt_index_var.set(cfg.get("controller_passthrough",{}).get("selected_index",0))
        self.exec_path_var.set(cfg.get("game_settings",{}).get("executable_path",""))
        self.exec_args_var.set(cfg.get("game_settings",{}).get("arguments",""))
        self.profiles_active_var.set(cfg.get("profiles_enabled", False))
        self.lbl_soldier_b.config(text=cfg.get("soldier_key", "e"))
        self.lbl_vehicle_b.config(text=cfg.get("vehicle_key", "t"))
        self.lbl_plane_b.config(text=cfg.get("plane_key", "y"))
        self.on_profiles_active_toggle()
        messagebox.showinfo("Config Management", "Schema states re-indexed from file successfully.")

    def start_game(self):
        exe = self.exec_path_var.get()
        args = self.exec_args_var.get()
        if not exe:
            messagebox.showwarning("Execution Pipeline", "No binary context path declared inside environment.")
            return
        import subprocess
        try:
            cmd = f'"{exe}" {args}'
            subprocess.Popen(cmd, shell=True)
            self.status_var.set("Target game execution environment spawned.")
        except Exception as e:
            messagebox.showerror("Execution Pipeline Critical", f"Failed to instantiate target process tree:\n{e}")

    def check_update(self, silent=True):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "v0.0")
                html_url = data.get("html_url", "")
                if latest_tag != CURRENT_VERSION:
                    if messagebox.askyesno("Update Hub", f"A fresh distribution runtime ({latest_tag}) is active on remote master.\nDo you intend to launch the browser environment to clone the bundle?"):
                        webbrowser.open(html_url)
                else:
                    if not silent: messagebox.showinfo("Update Hub", "Your localized toolkit runtime is synchronous with upstream master.")
        except Exception:
            if not silent: messagebox.showerror("Update Hub Failure", "Unable to establish handshake with GitHub remote endpoints.")

    def rebuild_custom_inputs_ui(self):
        self.build_custom_inputs_ui()

def toggle_mouse_lock():
    global mouse_locked, last_real_pos
    if not cfg.get("emulation_enabled", True):
        return
    mouse_locked = not mouse_locked
    if mouse_locked:
        cx, cy = screen_center
        last_real_pos = (cx, cy)
        SetCursorPos(cx, cy)
        set_cursor_visible(False)
        try: app.status_var.set("Target state synchronized: Mouse locked inside emulator.")
        except Exception: pass
    else:
        last_real_pos = None
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

def start_listeners_and_loop():
    global kb_listener, ms_listener, running, gamepad
    running = True
    
    # Alustetaan ja avataan uusi virtuaaliohjain vasta tässä kohdassa siististi
    try:
        gamepad = vg.VX360Gamepad()
    except Exception:
        pass
        
    kb_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    ms_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
    kb_listener.start(); ms_listener.start()
    t = threading.Thread(target=update_loop, daemon=True)
    t.start()

def stop_all():
    global running, kb_listener, ms_listener, gamepad
    running = False
    if kb_listener: kb_listener.stop()
    if ms_listener: ms_listener.stop()
    
    # Suljetaan ja vapautetaan ohjain täysin Windowsin ViGEm-ajurista roikkumasta
    if gamepad:
        try:
            del gamepad
            gamepad = None
        except Exception:
            pass

if __name__ == "__main__":
    start_listeners_and_loop()
    app = App()
    app.mainloop()
    stop_all()
