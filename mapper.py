import time
import threading
import tkinter as tk
from collections import deque
import vgamepad as vg
import pygame
from config import cfg, save_config
from utils import (
    SetCursorPos, set_cursor_visible, update_screen_center,
    apply_deadzone_value, apply_anti_deadzone, apply_linearity
)

gamepad = None
app_instance = None

current_profile_context = "soldier"
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

screen_center = update_screen_center()


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
        if app_instance:
            try:
                app_instance.mouse_profile_var.set(new_context)
                app_instance.load_mouse_profile_ui()
                app_instance.refresh_keyboard_bindings_ui()
                app_instance.status_var.set(f"Context switched to: {new_context.capitalize()}")
            except Exception:
                pass


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
    elif target_type == "hotkey_passthrough":
        cfg["hotkeys"]["toggle_passthrough"] = bind_name
    save_config(cfg)
    
    target_widget = widget or recording_widget
    if target_widget:
        try: target_widget.config(text=bind_name)
        except Exception:
            try:
                target_widget.delete(0, tk.END)
                target_widget.insert(0, bind_name)
            except Exception: pass


def start_recording(target_type, key_name, widget):
    """Aloittaa näppäimen nauhoituksen."""
    global recording_target, recording_widget
    recording_target = (target_type, key_name)
    recording_widget = widget
    if widget and hasattr(widget, "config"):
        widget.config(text="[Press Key...]")


def record_button_press(target_type, target_key, widget):
    """Aloittaa nauhoituksen (yhteensopiva Application Settings -valikon kanssa)."""
    start_recording(target_type, target_key, widget)


def record_button_release(event):
    """Käsittelee painikkeen vapautuksen (tarvittaessa)."""
    pass


def clear_binding(target_type, key_name, widget):
    """Tyhjentää valitun näppäinsidonnan suoraan."""
    global recording_target, recording_widget
    if recording_target:
        recording_target = None
        recording_widget = None

    if target_type == "keyboard":
        if cfg.get("profiles_enabled", False) and current_profile_context == "vehicle":
            cfg["keyboard_vehicle"][key_name] = ""
        elif cfg.get("profiles_enabled", False) and current_profile_context == "plane":
            cfg["keyboard_plane"][key_name] = ""
        else:
            cfg["keyboard"][key_name]["bind_key"] = ""
    elif target_type == "custom":
        idx = int(key_name)
        if idx < len(cfg["custom_inputs"]):
            cfg["custom_inputs"][idx]["bind_key"] = ""
    elif target_type == "leftstick":
        cfg["left_stick"][key_name] = ""
    elif target_type == "limiter":
        cfg["left_stick_limiter"]["bind_key"] = ""
    elif target_type == "menu":
        cfg["menu_buttons"][key_name] = ""
    elif target_type == "hotkey_lock":
        cfg["hotkeys"]["toggle_lock"] = ""
    elif target_type == "hotkey_emu":
        cfg["hotkeys"]["toggle_emulation"] = ""
    elif target_type in ("soldier_bind", "vehicle_bind", "plane_bind"):
        cfg[key_name] = ""

    save_config(cfg)
    if widget:
        try: widget.config(text="")
        except Exception:
            try: widget.delete(0, tk.END); widget.insert(0, "")
            except Exception: pass


def on_key_press_raw(kname):
    global recording_target, recording_widget, left_stick_state, limiter_active
    if recording_target:
        ttype, tkey = recording_target
        bind_and_save(ttype, tkey, kname, recording_widget)
        recording_target = None
        recording_widget = None
        if app_instance:
            try: 
                app_instance.status_var.set(f"Bound {kname}")
                # Päivitetään Tkinter-ikkunan sidonta jos kyseessä oli passthrough-hotkey
                if ttype == "hotkey_passthrough":
                    app_instance.rebind_passthrough_shortcut()
            except Exception: pass
        return

    # Passthrough-pikanäppäimen tarkistus
    pt_hk = cfg.get("hotkeys", {}).get("toggle_passthrough", "f8").lower()
    if kname == pt_hk and pt_hk != "":
        if app_instance:
            app_instance.toggle_passthrough_shortcut()
        return

    emu_hk = cfg.get("hotkeys", {}).get("toggle_emulation", "f6").lower()
    if kname == emu_hk and emu_hk != "":
        toggle_master_emulation()
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
            recording_widget = None
            if app_instance:
                try: app_instance.status_var.set(f"Bound {keyname}")
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
            axis = "y" if dirk in ("up", "down") else "x"
            val = 1.0 if dirk in ("up", "right") else -1.0
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
        recording_widget = None
        if app_instance:
            try: app_instance.status_var.set(f"Bound {keyname}")
            except Exception: pass
        return

    def pulse_button(xinp):
        if xinp in ("LEFT_TRIGGER", "RIGHT_TRIGGER"):
            triggers_pressed.add(xinp)
            threading.Thread(
                target=lambda: (time.sleep(0.08), triggers_pressed.discard(xinp)),
                daemon=True
            ).start()
        else:
            buttons_pressed.add(xinp)
            threading.Thread(
                target=lambda: (time.sleep(0.08), buttons_pressed.discard(xinp)),
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


def check_input_match(js, bound_str):
    if not bound_str or bound_str == "None":
        return False, 0.0

    if bound_str.startswith("Button "):
        try:
            btn_idx = int(bound_str.split()[1])
            if btn_idx < js.get_numbuttons() and js.get_button(btn_idx):
                return True, 1.0
        except Exception:
            pass

    elif bound_str.startswith("Axis "):
        try:
            parts = bound_str.split()
            axis_idx = int(parts[1])
            direction = parts[2]
            if axis_idx < js.get_numaxes():
                val = js.get_axis(axis_idx)
                if direction == "+" and val > 0.25:
                    return True, val
                elif direction == "-" and val < -0.25:
                    return True, abs(val)
        except Exception:
            pass

    elif bound_str.startswith("Hat "):
        try:
            hat_idx = int(bound_str.split()[1])
            expected_tuple = bound_str.split("(")[1].replace(")", "")
            hx, hy = map(int, expected_tuple.split(","))
            if hat_idx < js.get_numhats():
                if js.get_hat(hat_idx) == (hx, hy):
                    return True, 1.0
        except Exception:
            pass

    return False, 0.0


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

                    bindings = pt_config.get("bindings", {})

                    btn_map = {
                        "btn_a": "A", "btn_b": "B", "btn_x": "X", "btn_y": "Y",
                        "btn_lb": "LEFT_SHOULDER", "btn_rb": "RIGHT_SHOULDER",
                        "btn_select": "BACK", "btn_start": "START",
                        "btn_ls": "LEFT_THUMB", "btn_rs": "RIGHT_THUMB",
                        "dpad_up": "DPAD_UP", "dpad_down": "DPAD_DOWN",
                        "dpad_left": "DPAD_LEFT", "dpad_right": "DPAD_RIGHT"
                    }

                    for b_key, vg_name in btn_map.items():
                        is_pressed, _ = check_input_match(js, bindings.get(b_key, ""))
                        if is_pressed:
                            active_buttons.add(vg_name)

                    lt_pressed, lt_val = check_input_match(js, bindings.get("trigger_lt", ""))
                    if lt_pressed: target_lt = int(lt_val * 255)

                    rt_pressed, rt_val = check_input_match(js, bindings.get("trigger_rt", ""))
                    if rt_pressed: target_rt = int(rt_val * 255)

                    lx_pos_p, lx_pos_v = check_input_match(js, bindings.get("axis_lx_pos", ""))
                    lx_neg_p, lx_neg_v = check_input_match(js, bindings.get("axis_lx_neg", ""))
                    if lx_pos_p: target_lx += lx_pos_v
                    if lx_neg_p: target_lx -= lx_neg_v

                    ly_pos_p, ly_pos_v = check_input_match(js, bindings.get("axis_ly_pos", ""))
                    ly_neg_p, ly_neg_v = check_input_match(js, bindings.get("axis_ly_neg", ""))
                    if ly_pos_p: target_ly += ly_pos_v
                    if ly_neg_p: target_ly -= ly_neg_v

                    rx_pos_p, rx_pos_v = check_input_match(js, bindings.get("axis_rx_pos", ""))
                    rx_neg_p, rx_neg_v = check_input_match(js, bindings.get("axis_rx_neg", ""))
                    if rx_pos_p: target_rx += rx_pos_v
                    if rx_neg_p: target_rx -= rx_neg_v

                    ry_pos_p, ry_pos_v = check_input_match(js, bindings.get("axis_ry_pos", ""))
                    ry_neg_p, ry_neg_v = check_input_match(js, bindings.get("axis_ry_neg", ""))
                    if ry_pos_p: target_ry += ry_pos_v
                    if ry_neg_p: target_ry -= ry_neg_v

                    target_lx = max(-1.0, min(1.0, target_lx))
                    target_ly = max(-1.0, min(1.0, target_ly))
                    target_rx = max(-1.0, min(1.0, target_rx))
                    target_ry = max(-1.0, min(1.0, target_ry))

                except Exception:
                    pass

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
        if app_instance:
            try: app_instance.status_var.set("Target state synchronized: Mouse locked inside emulator.")
            except Exception: pass
    else:
        set_cursor_visible(True)
        if app_instance:
            try: app_instance.status_var.set("Target state synchronized: Mouse tracking context released.")
            except Exception: pass


def toggle_master_emulation():
    state = not cfg.get("emulation_enabled", True)
    cfg["emulation_enabled"] = state
    save_config(cfg)
    if app_instance:
        try:
            app_instance.emulation_enabled_var.set(state)
            status = "ENABLED" if state else "DISABLED"
            app_instance.status_var.set(f"Remap hooks state shifted via Hotkey: {status}")
        except Exception: pass
    global mouse_locked
    if not state and mouse_locked: toggle_mouse_lock()