import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import config
from config import cfg, save_config

# Alustetaan pygamen joystick-moduuli ohjainten tunnistamista varten
pygame.init()
pygame.joystick.init()

# Standardit virtuaaliohjaimen napit ja akselit (suunnat + ja - eroteltu omiksi kohteikseen)
DEFAULT_TARGET_BUTTONS = [
    ("A / Cross", "btn_a"),
    ("B / Circle", "btn_b"),
    ("X / Square", "btn_x"),
    ("Y / Triangle", "btn_y"),
    ("LB / L1", "btn_lb"),
    ("RB / R1", "btn_rb"),
    ("LT / L2 Trigger", "trigger_lt"),
    ("RT / R2 Trigger", "trigger_rt"),
    ("Back / Select", "btn_select"),
    ("Start", "btn_start"),
    ("Left Stick Click (L3)", "btn_ls"),
    ("Right Stick Click (R3)", "btn_rs"),
    ("D-Pad Up", "dpad_up"),
    ("D-Pad Down", "dpad_down"),
    ("D-Pad Left", "dpad_left"),
    ("D-Pad Right", "dpad_right"),
    ("Left Stick X+ (Right)", "axis_lx_pos"),
    ("Left Stick X- (Left)", "axis_lx_neg"),
    ("Left Stick Y+ (Up)", "axis_ly_pos"),
    ("Left Stick Y- (Down)", "axis_ly_neg"),
    ("Right Stick X+ (Right)", "axis_rx_pos"),
    ("Right Stick X- (Left)", "axis_rx_neg"),
    ("Right Stick Y+ (Up)", "axis_ry_pos"),
    ("Right Stick Y- (Down)", "axis_ry_neg"),
]


class ControllerMappingWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Controller Passthrough & Button Binding")
        self.geometry("580x680")
        self.configure(bg="#f8f9fa")
        self.transient(parent)
        self.grab_set()

        if "controller_passthrough" not in cfg:
            cfg["controller_passthrough"] = {"enabled": False, "selected_index": 0, "bindings": {}}
        if "bindings" not in cfg["controller_passthrough"]:
            cfg["controller_passthrough"]["bindings"] = {}

        self.recording_target = None
        self.active_joystick = None
        self.axis_baseline = {}
        self.poll_job = None

        self.detect_controllers()
        self.create_widgets()
        self.init_selected_joystick()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def detect_controllers(self):
        """Etsii kaikki kytketyt USB-peliohjaimet Pygamella."""
        pygame.joystick.quit()
        pygame.joystick.init()
        self.controllers = {}
        
        count = pygame.joystick.get_count()
        for i in range(count):
            try:
                js = pygame.joystick.Joystick(i)
                js.init()
                self.controllers[f"[{i}] {js.get_name()}"] = i
            except pygame.error:
                pass

    def init_selected_joystick(self):
        """Alustaa valitun ohjaimen akselien nollatasoja varten."""
        idx = cfg["controller_passthrough"].get("selected_index", 0)
        try:
            if pygame.joystick.get_count() > idx:
                self.active_joystick = pygame.joystick.Joystick(idx)
                self.active_joystick.init()
                pygame.event.pump()
                self.axis_baseline = {
                    i: self.active_joystick.get_axis(i)
                    for i in range(self.active_joystick.get_numaxes())
                }
        except pygame.error:
            self.active_joystick = None

    def create_widgets(self):
        top_frame = ttk.LabelFrame(self, text="Passthrough Device Settings", padding=10)
        top_frame.pack(fill="x", padx=15, pady=10)

        self.pt_enabled_var = tk.BooleanVar(value=cfg["controller_passthrough"].get("enabled", False))
        chk_enable = ttk.Checkbutton(
            top_frame, text="Enable Controller Passthrough",
            variable=self.pt_enabled_var, command=self.on_toggle_enabled
        )
        chk_enable.pack(anchor="w", pady=2)

        idx_frame = ttk.Frame(top_frame)
        idx_frame.pack(fill="x", pady=5)
        ttk.Label(idx_frame, text="Source Controller:").pack(side="left", padx=(0, 5))

        combo_values = list(self.controllers.keys()) if self.controllers else ["No Controllers Detected"]
        self.combo_var = tk.StringVar()
        
        saved_idx = cfg["controller_passthrough"].get("selected_index", 0)
        selected_name = combo_values[0]
        for name, idx in self.controllers.items():
            if idx == saved_idx:
                selected_name = name
                break
        self.combo_var.set(selected_name)

        self.cb_controllers = ttk.Combobox(
            idx_frame, textvariable=self.combo_var, values=combo_values, state="readonly", width=35
        )
        self.cb_controllers.pack(side="left", padx=5)
        self.cb_controllers.bind("<<ComboboxSelected>>", self.on_controller_selected)

        btn_refresh = ttk.Button(idx_frame, text="🔄", width=3, command=self.refresh_controller_list)
        btn_refresh.pack(side="left")

        list_frame = ttk.LabelFrame(self, text="Button & Axis Mappings", padding=10)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        canvas = tk.Canvas(list_frame, borderwidth=0, highlightthickness=0, bg="#f8f9fa")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.bind_labels = {}

        for row, (display_name, target_key) in enumerate(DEFAULT_TARGET_BUTTONS):
            ttk.Label(scrollable_frame, text=display_name, font=("Segoe UI", 9, "bold"), width=24)\
                .grid(row=row, column=0, padx=5, pady=4, sticky="w")

            current_bind = cfg["controller_passthrough"]["bindings"].get(target_key, "None")
            lbl_bind = ttk.Label(
                scrollable_frame, text=str(current_bind), width=18,
                relief="solid", borderwidth=1, anchor="center", background="#ffffff"
            )
            lbl_bind.grid(row=row, column=1, padx=5, pady=4)

            btn_rec = ttk.Button(
                scrollable_frame, text="Bind", width=8,
                command=lambda k=target_key, l=lbl_bind: self.start_recording(k, l)
            )
            btn_rec.grid(row=row, column=2, padx=5, pady=4)

            btn_clear = ttk.Button(
                scrollable_frame, text="Clear", width=6,
                command=lambda k=target_key, l=lbl_bind: self.clear_binding(k, l)
            )
            btn_clear.grid(row=row, column=3, padx=5, pady=4)

            self.bind_labels[target_key] = lbl_bind

        bottom_frame = ttk.Frame(self, padding=10)
        bottom_frame.pack(fill="x")
        ttk.Button(bottom_frame, text="Close", command=self.on_close).pack(side="right")

    def refresh_controller_list(self):
        self.detect_controllers()
        combo_values = list(self.controllers.keys()) if self.controllers else ["No Controllers Detected"]
        self.cb_controllers["values"] = combo_values
        if combo_values:
            self.combo_var.set(combo_values[0])
            self.on_controller_selected(None)

    def on_controller_selected(self, event):
        selected_text = self.combo_var.get()
        if selected_text in self.controllers:
            idx = self.controllers[selected_text]
            cfg["controller_passthrough"]["selected_index"] = idx
            save_config(cfg)
            self.init_selected_joystick()

    def on_toggle_enabled(self):
        cfg["controller_passthrough"]["enabled"] = self.pt_enabled_var.get()
        save_config(cfg)

    def start_recording(self, target_key, label_widget):
        if not self.active_joystick:
            messagebox.showwarning("Warning", "No active controller selected or initialized.")
            return

        if self.recording_target:
            old_key, old_label = self.recording_target
            old_label.config(text=cfg["controller_passthrough"]["bindings"].get(old_key, "None"))

        label_widget.config(text="[ Move / Press... ]")
        self.recording_target = (target_key, label_widget)

        pygame.event.pump()
        self.axis_baseline = {
            i: self.active_joystick.get_axis(i)
            for i in range(self.active_joystick.get_numaxes())
        }

        if self.poll_job is None:
            self.poll_input()

    def poll_input(self):
        if not self.recording_target or not self.active_joystick:
            self.poll_job = None
            return

        pygame.event.pump()
        detected_input = None

        # 1. Napit
        for b in range(self.active_joystick.get_numbuttons()):
            if self.active_joystick.get_button(b):
                detected_input = f"Button {b}"
                break

        # 2. Akselit (+ / -)
        if not detected_input:
            for a in range(self.active_joystick.get_numaxes()):
                val = self.active_joystick.get_axis(a)
                base = self.axis_baseline.get(a, 0.0)
                if abs(val - base) > 0.5:
                    direction = "+" if val > 0 else "-"
                    detected_input = f"Axis {a} {direction}"
                    break

        # 3. Hatut / D-Pad
        if not detected_input:
            for h in range(self.active_joystick.get_numhats()):
                hat_val = self.active_joystick.get_hat(h)
                if hat_val != (0, 0):
                    detected_input = f"Hat {h} {hat_val}"
                    break

        if detected_input:
            self.finish_recording(detected_input)
        else:
            self.poll_job = self.after(30, self.poll_input)

    def finish_recording(self, detected_input):
        if self.recording_target:
            target_key, label_widget = self.recording_target
            cfg["controller_passthrough"]["bindings"][target_key] = detected_input
            save_config(cfg)
            label_widget.config(text=detected_input)
            self.recording_target = None
            self.poll_job = None

    def clear_binding(self, target_key, label_widget):
        if target_key in cfg["controller_passthrough"]["bindings"]:
            del cfg["controller_passthrough"]["bindings"][target_key]
            save_config(cfg)
        label_widget.config(text="None")

    def on_close(self):
        if self.poll_job:
            self.after_cancel(self.poll_job)
        self.destroy()