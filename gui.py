# gui.py
# Complete, ready-to-run GUI for vgamepad mapping with:
# - Keys / Mouse tabs
# - Custom inputs per-row with dynamic count (0-20) and working save/load
# - Record buttons with short-press to bind and long-press (>=3s) to clear
# - Hotkey shown as non-editable label with Record button
# - Mouse lock that preserves identical delta behavior locked vs free
# - Separate X/Y sensitivity and deadzone, and linearity (gamma) control
# - Immediate application of mouse settings and saving/loading config.json
# - Left stick movement limiter with toggle checkbox and multiplier slider
# - Game executable and visible arguments block
# - Check Update button for future GitHub support
# - Save/Load Config buttons moved exclusively to Settings tab
# - Embedded app.ico support for PyInstaller EXE bundle
# - Version v 0.1
#
# Requires: vgamepad, pynput, ViGEmBus driver installed on Windows

import json
import threading
import time
import ctypes
import os
import sys
from collections import deque
import vgamepad as vg
from pynput import keyboard, mouse
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# --- Default configuration ---
DEFAULT_CONFIG = {
    "keyboard": {
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
    "mouse": {
        "sensitivity_x": 3.0,
        "sensitivity_y": 3.0,
        "deadzone_x": 0.0,
        "deadzone_y": 0.0,
        "linearity_x": 0.42,
        "linearity_y": 0.42,
        "linearity": 0.42,
        "invert_y": True,
        "pixel_to_unit": 20.0,
        "smoothing_samples": 1
    },
    "update_rate_hz": 60,
    "hotkeys": {"toggle_lock": "f5"},
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
        "is_toggle": False,
        "value": 0.5
    },
    "menu_buttons": {"up":"up","down":"down","left":"left","right":"right","select":"enter","back":"backspace"},
    "game_settings": {
        "executable_path": "",
        "arguments": "--no-gui \"%RPCS3_GAMEID%:NPEB00092\""
    }
}

CONFIG_FILE = "config.json"

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if "left_stick_limiter" not in loaded:
                loaded["left_stick_limiter"] = DEFAULT_CONFIG["left_stick_limiter"].copy()
            if "custom_count" not in loaded:
                loaded["custom_count"] = len(loaded.get("custom_inputs", []))
            return loaded
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

cfg = load_config()

# --- Action descriptions shown in UI ---
ACTION_DESCRIPTIONS = {
    "cross":    {"soldier":"Jump","vehicle":"Change","airplane":"-"},
    "circle":   {"soldier":"Enter/Use Pickup","vehicle":"Exit","airplane":"Exit"},
    "square":   {"soldier":"Reload","vehicle":"-","airplane":"-"},
    "triangle": {"soldier":"Draw Knife","vehicle":"-","airplane":"-"},
    "l1":       {"soldier":"Zoom","vehicle":"Throttle","airplane":"Throttle"},
    "r1":       {"soldier":"Fire","vehicle":"Fire","airplane":"Fire"},
    "l2":       {"soldier":"Throw Grenade/Explosives","vehicle":"Brake","airplane":"Hold Free Look"},
    "r2":       {"soldier":"Toggle Weapon","vehicle":"Secondary fire","airplane":"Drop bombs"},
    "l3":       {"soldier":"Run","vehicle":"-","airplane":"-"},
    "r3":       {"soldier":"Crouch","vehicle":"-","airplane":"-"},
    "select":   {"soldier":"Command(press)Score(Hold)","vehicle":"Command(press)Score(Hold)","airplane":"Command(press)Score(Hold)"},
    "start":    {"soldier":"In-Game Menu","vehicle":"In-Game Menu","airplane":"In-Game Menu"},
    "dpad_up":  {"soldier":"-","vehicle":"Change Camera","airplane":"Change Camera"},
    "dpad_down":{"soldier":"-","vehicle":"Look back","airplane":"Look back"}
}

gamepad = vg.VX360Gamepad()

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
    elif target_type == "hotkey":
        cfg["hotkeys"]["toggle_lock"] = ""
    save_config(cfg)
    if widget:
        try:
            widget.config(text="")
        except Exception:
            try:
                widget.delete(0, tk.END); widget.insert(0, "")
            except Exception:
                pass

def bind_and_save(target_type, target_key, bind_name, widget=None):
    if target_type == "keyboard":
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
    elif target_type == "hotkey":
        cfg["hotkeys"]["toggle_lock"] = bind_name
    save_config(cfg)
    if widget:
        try:
            widget.config(text=bind_name)
        except Exception:
            try:
                widget.delete(0, tk.END)
                widget.insert(0, bind_name)
            except Exception:
                pass

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
    if held >= 3.0:
        clear_binding(ttype, tkey, widget)
        try:
            app.status_var.set(f"Cleared binding for {ttype} {tkey}")
        except Exception:
            pass
        return
    recording_target = (ttype, tkey)
    recording_widget = widget
    try:
        widget.config(text="(press key...)")
    except Exception:
        try:
            widget.delete(0, tk.END); widget.insert(0, "(press key...)")
        except Exception:
            pass
    try:
        app.status_var.set(f"Recording {ttype} {tkey} — press a key or mouse button")
    except Exception:
        pass

def on_key_press(key):
    global recording_target, left_stick_state, limiter_active
    kname = normalize_key_name(key)
    if recording_target:
        ttype, tkey = recording_target
        bind_and_save(ttype, tkey, kname, recording_widget)
        recording_target = None
        try:
            app.status_var.set(f"Bound {kname}")
        except Exception:
            pass
        return

    hk = cfg.get("hotkeys", {}).get("toggle_lock", "f5").lower()
    if kname == hk:
        toggle_mouse_lock()
        return

    lk = cfg.get("left_stick_limiter", {}).get("bind_key", "ctrl_l").lower()
    if kname == lk and lk != "":
        if cfg.get("left_stick_limiter", {}).get("is_toggle", False):
            limiter_active = not limiter_active
        else:
            limiter_active = True
        return

    for ps_key, entry in cfg.get("keyboard", {}).items():
        if entry.get("bind_key") == kname:
            xinp = entry.get("xinput", "").upper()
            if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
                triggers_pressed.add(xinp)
            else:
                if xinp:
                    buttons_pressed.add(xinp)
                    
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
                if xinp:
                    buttons_pressed.add(xinp)
                    
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
    kname = normalize_key_name(key)
    
    lk = cfg.get("left_stick_limiter", {}).get("bind_key", "ctrl_l").lower()
    if kname == lk and lk != "":
        if not cfg.get("left_stick_limiter", {}).get("is_toggle", False):
            limiter_active = False
        return

    for ps_key, entry in cfg.get("keyboard", {}).items():
        if entry.get("bind_key") == kname:
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
    bname = str(button).split('.')[-1].lower()
    keyname = "mouse1" if bname == "left" else "mouse2"
    global recording_target, recording_widget
    if recording_target:
        ttype, tkey = recording_target
        bind_and_save(ttype, tkey, keyname, recording_widget)
        recording_target = None
        try:
            app.status_var.set(f"Bound {keyname}")
        except Exception:
            pass
        return
    for ps_key, entry in cfg.get("keyboard", {}).items():
        if entry.get("bind_key") == keyname:
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

def update_loop():
    update_rate = int(cfg.get("update_rate_hz", 60))
    period = 1.0 / update_rate
    global last_user_move_time, mouse_locked, screen_center, last_real_pos, limiter_active
    
    while running:
        pixel_to_unit = float(cfg.get("mouse", {}).get("pixel_to_unit", 20.0))
        sens_x = float(cfg.get("mouse", {}).get("sensitivity_x", 3.0))
        sens_y = float(cfg.get("mouse", {}).get("sensitivity_y", 3.0))
        dead_x = float(cfg.get("mouse", {}).get("deadzone_x", 0.0))
        dead_y = float(cfg.get("mouse", {}).get("deadzone_y", 0.0))
        gamma = float(cfg.get("mouse", {}).get("linearity", 0.42))
        invert_y = bool(cfg.get("mouse", {}).get("invert_y", True))

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
        vx = apply_linearity(vx, gamma)
        vy = apply_linearity(vy, gamma)

        if invert_y: vy = -vy
        try: gamepad.right_joystick_float(vx, vy)
        except Exception: pass

        try:
            lx = max(-1.0, min(1.0, left_stick_state["x"]))
            ly = max(-1.0, min(1.0, left_stick_state["y"]))
            if limiter_active:
                mod = float(cfg.get("left_stick_limiter", {}).get("value", 0.5))
                lx *= mod; ly *= mod
            gamepad.left_joystick_float(lx, ly)
        except Exception: pass

        try:
            gamepad.left_trigger(255 if "LEFT_TRIGGER" in triggers_pressed else 0)
            gamepad.right_trigger(255 if "RIGHT_TRIGGER" in triggers_pressed else 0)
        except Exception: pass

        try:
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
                if name in buttons_pressed: gamepad.press_button(button=enum)
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
        canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, width=width, height=height)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("vgamepad Config")
        self.geometry("960x820")
        
        # --- EXE Embedded Icon Support ---
        try:
            if hasattr(sys, '_MEIPASS'):
                icon_path = os.path.join(sys._MEIPASS, "app.ico")
            else:
                icon_path = os.path.join(os.path.dirname(__file__), "app.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self.custom_widgets = []
        self.custom_rows_pool = []
        self.create_widgets()
        self.rebuild_custom_inputs_ui()

    def create_widgets(self):
        top_bar = ttk.Frame(self, padding="5")
        top_bar.pack(side="top", fill="x")
        ttk.Button(top_bar, text="Start Game", command=self.start_game).pack(side="right", padx=10, pady=5)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        sf_keys = ScrollableFrame(nb, width=920, height=740)
        sf_mouse = ScrollableFrame(nb, width=920, height=740)
        sf_settings = ScrollableFrame(nb, width=920, height=740)
        
        nb.add(sf_keys, text="Keys")
        nb.add(sf_mouse, text="Mouse")
        nb.add(sf_settings, text="Settings")

        self.keys_frame = sf_keys.scrollable_frame
        mouse_frame = sf_mouse.scrollable_frame
        settings_frame = sf_settings.scrollable_frame

        # === KEYS TAB ===
        ttk.Label(self.keys_frame, text="PS buttons — Bound key; press Record to assign").grid(column=0, row=0, columnspan=6, sticky=tk.W, pady=(6,4), padx=(40, 4))
        headers = ["PS Button","Bound Key","Record","Soldier","Vehicle","Airplane"]
        for i,h in enumerate(headers):
            padx_val = (40, 4) if i == 0 else 4
            ttk.Label(self.keys_frame, text=h, font=("Segoe UI",9,"bold")).grid(column=i, row=1, padx=padx_val, pady=4)
        
        self.bind_widgets = {}
        row = 2
        for ps_key, entry in cfg.get("keyboard", {}).items():
            display = entry.get("display", ps_key)
            ttk.Label(self.keys_frame, text=display, width=12).grid(column=0, row=row, padx=(40, 4))
            lbl = ttk.Label(self.keys_frame, text=entry.get("bind_key",""), width=20, relief=tk.SUNKEN, background="#e9e9e9")
            lbl.grid(column=1, row=row, padx=4)
            btn = ttk.Button(self.keys_frame, text="Record", width=10)
            btn.grid(column=2, row=row, padx=4)
            btn.bind("<ButtonPress-1>", lambda e, t="keyboard", k=ps_key, w=lbl: record_button_press(t, k, w))
            btn.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
            desc = ACTION_DESCRIPTIONS.get(ps_key, {"soldier":"-","vehicle":"-","airplane":"-"})
            ttk.Label(self.keys_frame, text=desc["soldier"], width=18).grid(column=3, row=row, padx=4)
            ttk.Label(self.keys_frame, text=desc["vehicle"], width=18).grid(column=4, row=row, padx=4)
            ttk.Label(self.keys_frame, text=desc["airplane"], width=18).grid(column=5, row=row, padx=4)
            self.bind_widgets[ps_key] = lbl
            row += 1

        # Left stick mapping
        ttk.Separator(self.keys_frame, orient=tk.HORIZONTAL).grid(column=0, row=row, columnspan=6, sticky="ew", pady=8, padx=(40, 4))
        row += 1
        ttk.Label(self.keys_frame, text="Left Stick (map directions)").grid(column=0, row=row, columnspan=6, sticky=tk.W, padx=(40, 4))
        row += 1
        self.leftstick_labels = {}
        for dirk in ("up","down","left","right"):
            ttk.Label(self.keys_frame, text=dirk.upper(), width=12).grid(column=0, row=row, padx=(40, 4))
            lbl = ttk.Label(self.keys_frame, text=cfg.get("left_stick", {}).get(dirk,""), width=20, relief=tk.SUNKEN, background="#e9e9e9")
            lbl.grid(column=1, row=row, padx=4)
            btn = ttk.Button(self.keys_frame, text="Record", width=10)
            btn.grid(column=2, row=row, padx=4)
            btn.bind("<ButtonPress-1>", lambda e, t="leftstick", k=dirk, w=lbl: record_button_press(t, k, w))
            btn.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
            self.leftstick_labels[dirk] = lbl
            row += 1

        # Left Stick Limiter
        ttk.Label(self.keys_frame, text="LIMITER KEY", width=12).grid(column=0, row=row, padx=(40, 4))
        self.limiter_lbl = ttk.Label(self.keys_frame, text=cfg.get("left_stick_limiter", {}).get("bind_key","ctrl_l"), width=20, relief=tk.SUNKEN, background="#e9e9e9")
        self.limiter_lbl.grid(column=1, row=row, padx=4)
        btn_lim = ttk.Button(self.keys_frame, text="Record", width=10)
        btn_lim.grid(column=2, row=row, padx=4)
        btn_lim.bind("<ButtonPress-1>", lambda e, t="limiter", k="bind_key", w=self.limiter_lbl: record_button_press(t, k, w))
        btn_lim.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
        
        self.limiter_toggle_var = tk.BooleanVar(value=cfg.get("left_stick_limiter", {}).get("is_toggle", False))
        chk_lim = ttk.Checkbutton(self.keys_frame, text="Toggle", variable=self.limiter_toggle_var, command=self.on_limiter_toggle_changed)
        chk_lim.grid(column=3, row=row, sticky=tk.W, padx=4)
        
        self.limiter_val_var = tk.DoubleVar(value=cfg.get("left_stick_limiter", {}).get("value", 0.5))
        sld_lim = ttk.Scale(self.keys_frame, from_=0.1, to=1.0, variable=self.limiter_val_var, orient=tk.HORIZONTAL, length=150, command=lambda e: self.on_limiter_val_changed())
        sld_lim.grid(column=4, row=row, columnspan=2, sticky=tk.W, padx=4)
        row += 1

        self.custom_sep = ttk.Separator(self.keys_frame, orient=tk.HORIZONTAL)
        self.custom_sep.grid(column=0, row=row, columnspan=6, sticky="ew", pady=8, padx=(40, 4))
        row += 1
        self.custom_title_lbl = ttk.Label(self.keys_frame, text="Custom inputs (name, target PS, bound key, Record, description)")
        self.custom_title_lbl.grid(column=0, row=row, columnspan=6, sticky=tk.W, padx=(40, 4))
        row += 1
        
        self.custom_start_row = row

        self.menu_sep = ttk.Separator(self.keys_frame, orient=tk.HORIZONTAL)
        self.menu_title_lbl = ttk.Label(self.keys_frame, text="Menu Buttons (Select->A, Back->B)")
        self.menu_labels = {}
        self.menu_ui_elements = []

        # === MOUSE TAB ===
        mfrm = mouse_frame
        ttk.Label(mfrm, text="Mouse settings (changes apply immediately)").grid(column=0, row=0, sticky=tk.W, pady=(6,4), padx=(40, 4))

        ttk.Label(mfrm, text="Pixel to unit").grid(column=0, row=1, sticky=tk.W, padx=(40, 4))
        self.p2u = tk.DoubleVar(value=cfg.get("mouse", {}).get("pixel_to_unit",20.0))
        p2u_scale = ttk.Scale(mfrm, from_=5.0, to=100.0, variable=self.p2u, orient=tk.HORIZONTAL, length=360)
        p2u_scale.grid(column=1, row=1, sticky=tk.W, padx=4)
        p2u_scale.bind("<B1-Motion>", lambda e: self.on_p2u_changed())
        p2u_scale.bind("<ButtonRelease-1>", lambda e: self.on_p2u_changed())

        ttk.Label(mfrm, text="Sensitivity X").grid(column=0, row=2, sticky=tk.W, padx=(40, 4))
        self.sens_x = tk.DoubleVar(value=cfg.get("mouse", {}).get("sensitivity_x",3.0))
        sensx_scale = ttk.Scale(mfrm, from_=0.1, to=5.0, variable=self.sens_x, orient=tk.HORIZONTAL, length=360)
        sensx_scale.grid(column=1, row=2, sticky=tk.W, padx=4)
        sensx_scale.bind("<B1-Motion>", lambda e: self.on_sens_xy_changed())
        sensx_scale.bind("<ButtonRelease-1>", lambda e: self.on_sens_xy_changed())

        ttk.Label(mfrm, text="Sensitivity Y").grid(column=0, row=3, sticky=tk.W, padx=(40, 4))
        self.sens_y = tk.DoubleVar(value=cfg.get("mouse", {}).get("sensitivity_y",3.0))
        sensy_scale = ttk.Scale(mfrm, from_=0.1, to=5.0, variable=self.sens_y, orient=tk.HORIZONTAL, length=360)
        sensy_scale.grid(column=1, row=3, sticky=tk.W, padx=4)
        sensy_scale.bind("<B1-Motion>", lambda e: self.on_sens_xy_changed())
        sensy_scale.bind("<ButtonRelease-1>", lambda e: self.on_sens_xy_changed())

        ttk.Label(mfrm, text="Deadzone X").grid(column=0, row=4, sticky=tk.W, padx=(40, 4))
        self.dead_x = tk.DoubleVar(value=cfg.get("mouse", {}).get("deadzone_x",0.0))
        deadx_scale = ttk.Scale(mfrm, from_=0.0, to=0.3, variable=self.dead_x, orient=tk.HORIZONTAL, length=360)
        deadx_scale.grid(column=1, row=4, sticky=tk.W, padx=4)
        deadx_scale.bind("<B1-Motion>", lambda e: self.on_deadzone_xy_changed())
        deadx_scale.bind("<ButtonRelease-1>", lambda e: self.on_deadzone_xy_changed())

        ttk.Label(mfrm, text="Deadzone Y").grid(column=0, row=5, sticky=tk.W, padx=(40, 4))
        self.dead_y = tk.DoubleVar(value=cfg.get("mouse", {}).get("deadzone_y",0.0))
        deady_scale = ttk.Scale(mfrm, from_=0.0, to=0.3, variable=self.dead_y, orient=tk.HORIZONTAL, length=360)
        deady_scale.grid(column=1, row=5, sticky=tk.W, padx=4)
        deady_scale.bind("<B1-Motion>", lambda e: self.on_deadzone_xy_changed())
        deady_scale.bind("<ButtonRelease-1>", lambda e: self.on_deadzone_xy_changed())

        ttk.Label(mfrm, text="Linearity (Gamma)").grid(column=0, row=6, sticky=tk.W, padx=(40, 4))
        self.linearity = tk.DoubleVar(value=cfg.get("mouse", {}).get("linearity", 0.42))
        lin_scale = ttk.Scale(mfrm, from_=0.1, to=2.0, variable=self.linearity, orient=tk.HORIZONTAL, length=360)
        lin_scale.grid(column=1, row=6, sticky=tk.W, padx=4)
        lin_scale.bind("<B1-Motion>", lambda e: self.on_linearity_changed())
        lin_scale.bind("<ButtonRelease-1>", lambda e: self.on_linearity_changed())

        self.invert_y_var = tk.BooleanVar(value=cfg.get("mouse", {}).get("invert_y", True))
        chk_inv = ttk.Checkbutton(mfrm, text="Invert Y Axis", variable=self.invert_y_var, command=self.on_invert_y_changed)
        chk_inv.grid(column=0, row=7, columnspan=2, sticky=tk.W, pady=8, padx=(40, 4))

        # === SETTINGS TAB ===
        ttk.Label(settings_frame, text="Game Settings", font=("Segoe UI", 12, "bold")).grid(column=0, row=0, sticky=tk.W, pady=(10,10), padx=(40, 4))
        ttk.Label(settings_frame, text="v 0.1", font=("Segoe UI", 10, "italic"), foreground="gray").grid(column=1, row=0, sticky=tk.W, pady=(10,10), padx=5)
        
        ttk.Button(settings_frame, text="Check Update", command=self.check_update).grid(column=2, row=0, padx=5, sticky=tk.E)

        ttk.Label(settings_frame, text="Custom Keys amount (0-20):").grid(column=0, row=1, sticky=tk.W, pady=5, padx=(40, 4))
        self.custom_count_cmb = ttk.Combobox(settings_frame, values=[str(x) for x in range(21)], width=6, state="readonly")
        self.custom_count_cmb.set(str(cfg.get("custom_count", 4)))
        self.custom_count_cmb.grid(column=1, row=1, sticky=tk.W, pady=5, padx=5)
        self.custom_count_cmb.bind("<<ComboboxSelected>>", self.on_custom_count_changed)

        ttk.Label(settings_frame, text="Game Executable Path:").grid(column=0, row=2, sticky=tk.W, pady=5, padx=(40, 4))
        self.exec_entry = ttk.Entry(settings_frame, width=60)
        self.exec_entry.insert(0, cfg.get("game_settings", {}).get("executable_path", ""))
        self.exec_entry.grid(column=0, row=3, columnspan=2, sticky=tk.W, pady=2, padx=(40, 4))
        ttk.Button(settings_frame, text="Browse...", command=self.browse_executable).grid(column=2, row=3, padx=5, sticky=tk.W)

        ttk.Label(settings_frame, text="Arguments:").grid(column=0, row=4, sticky=tk.W, pady=5, padx=(40, 4))
        self.args_entry = ttk.Entry(settings_frame, width=60)
        self.args_entry.insert(0, cfg.get("game_settings", {}).get("arguments", ""))
        self.args_entry.grid(column=0, row=5, columnspan=2, sticky=tk.W, pady=2, padx=(40, 4))

        ttk.Separator(settings_frame, orient=tk.HORIZONTAL).grid(column=0, row=6, columnspan=3, sticky="ew", pady=15, padx=(40, 4))
        
        btns_frame = ttk.Frame(settings_frame)
        btns_frame.grid(column=0, row=7, columnspan=3, sticky=tk.W, padx=(40, 4), pady=5)
        
        ttk.Button(btns_frame, text="Save config", command=self.save_config).pack(side="left", padx=0)
        ttk.Button(btns_frame, text="Load config", command=self.load_config_file).pack(side="left", padx=10)

        self.status_var = tk.StringVar(value="Running. Press hotkey to toggle mouse lock.")
        status_lbl = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_lbl.pack(side="bottom", fill="x")

    def rebuild_custom_inputs_ui(self):
        # Kerätään nykyiset arvot talteen ennen käyttöliittymän tyhjentämistä
        for i, (cmb, lbl_bind, ent) in enumerate(self.custom_widgets):
            if i < len(cfg["custom_inputs"]):
                cfg["custom_inputs"][i]["target"] = cmb.get()
                cfg["custom_inputs"][i]["description"] = ent.get()

        for elem in self.custom_rows_pool: elem.grid_forget()
        for elem in self.menu_ui_elements: elem.grid_forget()
            
        self.custom_widgets.clear()
        self.custom_rows_pool.clear()
        self.menu_ui_elements.clear()

        c_count = int(cfg.get("custom_count", 4))
        current_row = self.custom_start_row
        ps_options = list(cfg.get("keyboard", {}).keys())
        
        while len(cfg["custom_inputs"]) < c_count:
            cfg["custom_inputs"].append({"name": f"custom{len(cfg['custom_inputs'])+1}", "target": "cross", "bind_key": "", "description": ""})

        if c_count > 0:
            self.custom_sep.grid(column=0, row=self.custom_start_row-2, columnspan=6, sticky="ew", pady=8, padx=(40, 4))
            self.custom_title_lbl.grid(column=0, row=self.custom_start_row-1, columnspan=6, sticky=tk.W, padx=(40, 4))
            
            for i in range(c_count):
                ci = cfg["custom_inputs"][i]
                name = ci.get("name", f"custom{i+1}")
                
                lbl_name = ttk.Label(self.keys_frame, text=name, width=12)
                lbl_name.grid(column=0, row=current_row, padx=(40, 4))
                self.custom_rows_pool.append(lbl_name)
                
                cmb = ttk.Combobox(self.keys_frame, values=ps_options, width=14, state="readonly")
                cmb.set(ci.get("target","cross"))
                cmb.grid(column=1, row=current_row, padx=4)
                self.custom_rows_pool.append(cmb)
                
                lbl_bind = ttk.Label(self.keys_frame, text=ci.get("bind_key",""), width=18, relief=tk.SUNKEN, background="#e9e9e9")
                lbl_bind.grid(column=2, row=current_row, padx=4)
                self.custom_rows_pool.append(lbl_bind)
                
                btn = ttk.Button(self.keys_frame, text="Record", width=10)
                btn.grid(column=3, row=current_row, padx=4)
                btn.bind("<ButtonPress-1>", lambda e, t="custom", k=i, w=lbl_bind: record_button_press(t, k, w))
                btn.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
                self.custom_rows_pool.append(btn)
                
                ent = ttk.Entry(self.keys_frame, width=28)
                ent.insert(0, ci.get("description",""))
                ent.grid(column=4, row=current_row, columnspan=2, sticky=tk.W, padx=4)
                self.custom_rows_pool.append(ent)
                
                self.custom_widgets.append((cmb, lbl_bind, ent))
                current_row += 1
        else:
            self.custom_sep.grid_forget()
            self.custom_title_lbl.grid_forget()

        self.menu_sep.grid(column=0, row=current_row, columnspan=6, sticky="ew", pady=8, padx=(40, 4))
        self.menu_ui_elements.append(self.menu_sep)
        current_row += 1
        
        self.menu_title_lbl.grid(column=0, row=current_row, columnspan=6, sticky=tk.W, padx=(40, 4))
        self.menu_ui_elements.append(self.menu_title_lbl)
        current_row += 1
        
        for m in ("up","down","left","right","select","back"):
            lbl_mname = ttk.Label(self.keys_frame, text=m.upper(), width=12)
            lbl_mname.grid(column=0, row=current_row, padx=(40, 4))
            self.menu_ui_elements.append(lbl_mname)
            
            lbl_mbind = ttk.Label(self.keys_frame, text=cfg.get("menu_buttons", {}).get(m,""), width=20, relief=tk.SUNKEN, background="#e9e9e9")
            lbl_mbind.grid(column=1, row=current_row, padx=4)
            self.menu_ui_elements.append(lbl_mbind)
            
            btn_mrec = ttk.Button(self.keys_frame, text="Record", width=10)
            btn_mrec.grid(column=2, row=current_row, padx=4)
            btn_mrec.bind("<ButtonPress-1>", lambda e, t="menu", k=m, w=lbl_mbind: record_button_press(t, k, w))
            btn_mrec.bind("<ButtonRelease-1>", lambda e: record_button_release(e))
            self.menu_ui_elements.append(btn_mrec)
            
            self.menu_labels[m] = lbl_mbind
            current_row += 1

    def check_update(self):
        messagebox.showinfo("Check Update", "You are running the latest version (v 0.1).\nGitHub support coming soon!")

    def on_custom_count_changed(self, event):
        val = int(self.custom_count_cmb.get())
        cfg["custom_count"] = val
        save_config(cfg)
        self.rebuild_custom_inputs_ui()
        self.status_var.set(f"Custom rows changed to {val}")

    def on_p2u_changed(self):
        cfg["mouse"]["pixel_to_unit"] = float(self.p2u.get())
        save_config(cfg)

    def on_sens_xy_changed(self):
        cfg["mouse"]["sensitivity_x"] = float(self.sens_x.get())
        cfg["mouse"]["sensitivity_y"] = float(self.sens_y.get())
        save_config(cfg)

    def on_deadzone_xy_changed(self):
        cfg["mouse"]["deadzone_x"] = float(self.dead_x.get())
        cfg["mouse"]["deadzone_y"] = float(self.dead_y.get())
        save_config(cfg)

    def on_linearity_changed(self):
        cfg["mouse"]["linearity"] = float(self.linearity.get())
        save_config(cfg)

    def on_invert_y_changed(self):
        cfg["mouse"]["invert_y"] = bool(self.invert_y_var.get())
        save_config(cfg)

    def on_limiter_toggle_changed(self):
        cfg["left_stick_limiter"]["is_toggle"] = bool(self.limiter_toggle_var.get())
        save_config(cfg)

    def on_limiter_val_changed(self):
        cfg["left_stick_limiter"]["value"] = float(self.limiter_val_var.get())
        save_config(cfg)

    def browse_executable(self):
        path = filedialog.askopenfilename(filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")])
        if path:
            self.exec_entry.delete(0, tk.END)
            self.exec_entry.insert(0, path)
            if "game_settings" not in cfg: cfg["game_settings"] = {}
            cfg["game_settings"]["executable_path"] = path
            save_config(cfg)

    def start_game(self):
        import subprocess
        path = self.exec_entry.get()
        args = self.args_entry.get()
        if not path:
            messagebox.showwarning("Warning", "Please select a game executable path first from Settings tab.")
            return
        try:
            subprocess.Popen(f'"{path}" {args}', shell=True)
            self.status_var.set("Game started successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start game: {e}")

    # --- KORJATTU TALLENNUSFUNKTIO ---
    def save_config(self):
        # Luetaan arvot suoraan GUI-elementeistä ja viedään config-objektiin
        c_count = int(cfg.get("custom_count", 4))
        for i, (cmb, lbl, ent) in enumerate(self.custom_widgets):
            if i < c_count:
                cfg["custom_inputs"][i]["target"] = cmb.get()
                cfg["custom_inputs"][i]["bind_key"] = lbl.cget("text")
                cfg["custom_inputs"][i]["description"] = ent.get()
                
        if "game_settings" not in cfg: cfg["game_settings"] = {}
        cfg["game_settings"]["executable_path"] = self.exec_entry.get()
        cfg["game_settings"]["arguments"] = self.args_entry.get()
        
        save_config(cfg)
        self.status_var.set("Configuration saved to config.json")

    def load_config_file(self):
        global cfg
        cfg = load_config()
        self.exec_entry.delete(0, tk.END)
        self.exec_entry.insert(0, cfg.get("game_settings", {}).get("executable_path", ""))
        self.args_entry.delete(0, tk.END)
        self.args_entry.insert(0, cfg.get("game_settings", {}).get("arguments", ""))
        self.custom_count_cmb.set(str(cfg.get("custom_count", 4)))
        self.rebuild_custom_inputs_ui()
        
        # Päivitetään myös peruspainikkeiden näkymä
        for ps_key, entry in cfg.get("keyboard", {}).items():
            if ps_key in self.bind_widgets:
                self.bind_widgets[ps_key].config(text=entry.get("bind_key",""))
        for dirk in ("up","down","left","right"):
            if dirk in self.leftstick_labels:
                self.leftstick_labels[dirk].config(text=cfg.get("left_stick", {}).get(dirk,""))
        self.limiter_lbl.config(text=cfg.get("left_stick_limiter", {}).get("bind_key","ctrl_l"))
        self.limiter_toggle_var.set(cfg.get("left_stick_limiter", {}).get("is_toggle", False))
        self.limiter_val_var.set(cfg.get("left_stick_limiter", {}).get("value", 0.5))

        self.status_var.set("Configuration loaded from config.json")

def toggle_mouse_lock():
    global mouse_locked, screen_center, last_real_pos
    mouse_locked = not mouse_locked
    screen_center = update_screen_center()
    if mouse_locked:
        cx, cy = screen_center
        last_real_pos = (cx, cy)
        SetCursorPos(cx, cy)
        set_cursor_visible(False)
        try: app.status_var.set("Mouse locked")
        except Exception: pass
    else:
        last_real_pos = None
        set_cursor_visible(True)
        try: app.status_var.set("Mouse free")
        except Exception: pass

def start_listeners_and_loop():
    global kb_listener, ms_listener, running
    running = True
    kb_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    ms_listener = mouse.Listener(on_move=on_move, on_click=on_click)
    kb_listener.start(); ms_listener.start()
    t = threading.Thread(target=update_loop, daemon=True)
    t.start()

def stop_all():
    global running, kb_listener, ms_listener
    running = False
    if kb_listener: kb_listener.stop()
    if ms_listener: ms_listener.stop()

if __name__ == "__main__":
    app = App()
    start_listeners_and_loop()
    app.mainloop()
    stop_all()