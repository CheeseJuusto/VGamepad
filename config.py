import json
import os
from utils import CONFIG_FILE

CURRENT_VERSION = "v3.0"
GITHUB_REPO = "CheeseJuusto/VGamepad"

DEFAULT_CONFIG = {
    "profiles_enabled": False,
    "soldier_key": "z",
    "vehicle_key": "x",
    "plane_key": "v",
    "keyboard": {
        "cross": {"display": "Cross", "bind_key": "space", "xinput": "A"},
        "circle": {"display": "Circle", "bind_key": "e", "xinput": "B"},
        "square": {"display": "Square", "bind_key": "r", "xinput": "X"},
        "triangle": {"display": "Triangle", "bind_key": "f", "xinput": "Y"},
        "l1": {"display": "L1", "bind_key": "mouse2", "xinput": "LEFT_SHOULDER"},
        "r1": {"display": "R1", "bind_key": "mouse1", "xinput": "RIGHT_SHOULDER"},
        "l2": {"display": "L2", "bind_key": "g", "xinput": "LEFT_TRIGGER"},
        "r2": {"display": "R2", "bind_key": "q", "xinput": "RIGHT_TRIGGER"},
        "l3": {"display": "L3", "bind_key": "shift", "xinput": "LEFT_THUMB"},
        "r3": {"display": "R3", "bind_key": "c", "xinput": "RIGHT_THUMB"},
        "select": {"display": "Select", "bind_key": "tab", "xinput": "BACK"},
        "start": {"display": "Start", "bind_key": "esc", "xinput": "START"},
        "dpad_up": {"display": "Dpad Up", "bind_key": "c", "xinput": "DPAD_UP"},
        "dpad_down": {"display": "Dpad Down", "bind_key": "b", "xinput": "DPAD_DOWN"}
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
        {"name": "custom1", "target": "cross", "bind_key": "", "description": ""},
        {"name": "custom2", "target": "circle", "bind_key": "", "description": ""},
        {"name": "custom3", "target": "square", "bind_key": "", "description": ""},
        {"name": "custom4", "target": "triangle", "bind_key": "", "description": ""}
    ],
    "left_stick": {"up": "w", "down": "s", "left": "a", "right": "d"},
    "left_stick_limiter": {
        "bind_key": "ctrl_l",
        "is_toggle": True,
        "value": 0.45
    },
    "menu_buttons": {"up": "up", "down": "down", "left": "left", "right": "right", "select": "enter", "back": "backspace"},
    "game_settings": {
        "executable_path": "",
        "arguments": "--no-gui \"%RPCS3_GAMEID%:NPEB00092\""
    },
    "controller_passthrough": {
        "enabled": False,
        "selected_index": 0
    }
}

ACTION_DESCRIPTIONS = {
    "cross":    {"soldier": "Jump", "vehicle": "Change", "airplane": "-"},
    "circle":   {"soldier": "Enter/Use Pickup", "vehicle": "Exit", "airplane": "Exit"},
    "square":   {"soldier": "Reload", "vehicle": "-", "airplane": "-"},
    "triangle": {"soldier": "Draw Knife", "vehicle": "-", "airplane": "-"},
    "l1":       {"soldier": "Zoom", "vehicle": "Throttle", "airplane": "Throttle"},
    "r1":       {"soldier": "Fire", "vehicle": "Fire", "airplane": "Fire"},
    "l2":       {"soldier": "Throw Grenade", "vehicle": "Brake", "airplane": "Hold Free Look"},
    "r2":       {"soldier": "Toggle Weapon", "vehicle": "Secondary fire", "airplane": "Drop bombs"},
    "l3":       {"soldier": "Run", "vehicle": "-", "airplane": "-"},
    "r3":       {"soldier": "Crouch", "vehicle": "-", "airplane": "-"},
    "select":   {"soldier": "Command / Score", "vehicle": "Command / Score", "airplane": "Command / Score"},
    "start":    {"soldier": "In-Game Menu", "vehicle": "In-Game Menu", "airplane": "In-Game Menu"},
    "dpad_up":  {"soldier": "-", "vehicle": "Change Camera", "airplane": "Change Camera"},
    "dpad_down": {"soldier": "-", "vehicle": "Look back", "airplane": "Look back"}
}


def ensure_config_defaults(loaded):
    if not isinstance(loaded, dict):
        return DEFAULT_CONFIG.copy()

    if "mouse" not in loaded:
        loaded["mouse"] = DEFAULT_CONFIG["mouse"].copy()
    if "mouse_profiles" not in loaded:
        loaded["mouse_profiles"] = {}

    for key, val in DEFAULT_CONFIG["mouse"].items():
        if key not in loaded["mouse"]:
            loaded["mouse"][key] = val

    for profile_name in ("vehicle", "plane"):
        if profile_name not in loaded["mouse_profiles"]:
            loaded["mouse_profiles"][profile_name] = DEFAULT_CONFIG["mouse_profiles"][profile_name].copy()
        else:
            for k, v in DEFAULT_CONFIG["mouse_profiles"][profile_name].items():
                if k not in loaded["mouse_profiles"][profile_name]:
                    loaded["mouse_profiles"][profile_name][k] = v

    if "keyboard" not in loaded:
        loaded["keyboard"] = DEFAULT_CONFIG["keyboard"].copy()
    if "keyboard_vehicle" not in loaded:
        loaded["keyboard_vehicle"] = {}
    if "keyboard_plane" not in loaded:
        loaded["keyboard_plane"] = {}
    if "left_stick" not in loaded:
        loaded["left_stick"] = DEFAULT_CONFIG["left_stick"].copy()
    if "left_stick_limiter" not in loaded:
        loaded["left_stick_limiter"] = DEFAULT_CONFIG["left_stick_limiter"].copy()
    if "custom_inputs" not in loaded:
        loaded["custom_inputs"] = DEFAULT_CONFIG["custom_inputs"].copy()
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


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            return ensure_config_defaults(loaded)
    except Exception:
        return DEFAULT_CONFIG.copy()


current_config_path = None  # Seurataan aktiivista tiedostopolkua


def save_config(config_data, custom_path=None):
    global current_config_path

    if custom_path:
        current_config_path = custom_path

    # Jos erillistä polkua ei ole määritelty, käytetään oletustiedostoa (config.json)
    target_path = current_config_path if current_config_path else CONFIG_FILE

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
    except Exception as e:
        print(f"Error saving config to {target_path}: {e}")


cfg = load_config()