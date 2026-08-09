import os
import sys
import json
import urllib.request
import webbrowser
import subprocess
from collections import deque
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from utils import BASE_DIR, CONFIG_FILE
from config import cfg, save_config, DEFAULT_CONFIG, ACTION_DESCRIPTIONS, CURRENT_VERSION, GITHUB_REPO, ensure_config_defaults
from game_start import start_game_process
from controller import ControllerMappingWindow
import mapper
import config


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, width=860, height=700, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, width=width, height=height, bg="#f8f9fa")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style="TFrame")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._bind_mouse_wheel(self)

    def _bind_mouse_wheel(self, widget):
        widget.bind("<MouseWheel>", self._on_mouse_wheel)
        widget.bind("<Button-4>", self._on_mouse_wheel)
        widget.bind("<Button-5>", self._on_mouse_wheel)
        for child in widget.winfo_children():
            self._bind_mouse_wheel(child)

    def _on_mouse_wheel(self, event):
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        mapper.app_instance = self
        self.title("vgamepad Mapping Toolkit")
        self.geometry("1040x880")
        self.configure(bg="#f8f9fa")

        self.status_var = tk.StringVar(value="Ready")
        self.active_config_name_var = tk.StringVar(value=os.path.basename(CONFIG_FILE))
        self.pt_enabled_var = tk.BooleanVar(value=cfg.get("controller_passthrough", {}).get("enabled", False))

        pt_key = cfg.get("hotkeys", {}).get("toggle_passthrough", "f8")
        if pt_key:
            self.bind(f"<{pt_key.upper()}>", lambda e: self.toggle_passthrough_shortcut())
        
        if pt_key:
            self.bind(f"<{pt_key.upper()}>", lambda e: self.toggle_passthrough_shortcut())

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
        self.menu_ui_elements = []

        self.mouse_profile_var = tk.StringVar(value="soldier")

        self.create_widgets()
        self.rebuild_custom_inputs_ui()

    def create_widgets(self):
        top_bar = tk.Frame(self, bg="#ffffff", height=60, bd=0, highlightthickness=1, highlightbackground="#dee2e6")
        top_bar.pack(side="top", fill="x")
        top_bar.pack_propagate(False)

        title_lbl = tk.Label(top_bar, text="vgamepad Remapper Toolkit", font=("Segoe UI", 14, "bold"), bg="#ffffff", fg="#212529")
        title_lbl.pack(side="left", padx=20)

        start_btn = ttk.Button(top_bar, text="▶ Start Game", style="Action.TButton", command=self.start_game)
        start_btn.pack(side="right", padx=(10, 20))

        cfg_info_frame = tk.Frame(top_bar, bg="#ffffff")
        cfg_info_frame.pack(side="right", padx=10)

        cfg_title_lbl = tk.Label(cfg_info_frame, text="Config:", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#6c757d")
        cfg_title_lbl.pack(side="left", padx=(0, 4))

        cfg_name_lbl = tk.Label(cfg_info_frame, textvariable=self.active_config_name_var, font=("Segoe UI", 9, "bold"), bg="#e9ecef", fg="#007bff", padx=8, pady=2, relief="flat")
        cfg_name_lbl.pack(side="left")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=20, pady=15)

        sf_keys = ScrollableFrame(nb, width=980, height=720)
        sf_mouse = ScrollableFrame(nb, width=980, height=720)
        sf_settings = ScrollableFrame(nb, width=980, height=720)

        nb.add(sf_keys, text="⌨️Keyboard Mapping")
        nb.add(sf_mouse, text="🖱️Mouse Input Settings")
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

        main_desc = ttk.Label(self.keys_frame, text="Configure keyboard inputs to emulate controller actions. Press 'Bind' to set a key.", style="SubHeader.TLabel")
        main_desc.grid(column=0, row=1, columnspan=6, sticky=tk.W, pady=(10, 15), padx=20)

        headers = ["Gamepad Target", "Current Binding", "Action", "Soldier Context", "Vehicle Context", "Aircraft Context"]
        for i, h in enumerate(headers):
            lbl_h = ttk.Label(self.keys_frame, text=h, font=("Segoe UI", 9, "bold"), foreground="#6c757d")
            lbl_h.grid(column=i, row=2, padx=10, pady=8, sticky=tk.W if i != 1 else tk.EW)

        self.bind_widgets = {}
        row = 3
        for ps_key, entry in cfg.get("keyboard", {}).items():
            display = entry.get("display", ps_key)
            ttk.Label(self.keys_frame, text=display, font=("Segoe UI", 10, "bold"), width=15).grid(column=0, row=row, padx=10, pady=6, sticky=tk.W)

            lbl = ttk.Label(self.keys_frame, text=entry.get("bind_key", ""), width=16, style="KeyBind.TLabel", padding=4)
            lbl.grid(column=1, row=row, padx=10, pady=6, sticky=tk.EW)

            btn_bind = ttk.Button(self.keys_frame, text="Bind", width=6, command=lambda t="keyboard", k=ps_key, w=lbl: mapper.start_recording(t, k, w))
            btn_bind.grid(column=2, row=row, padx=(5, 2), pady=6)

            btn_clear = ttk.Button(self.keys_frame, text="Clear", width=6, command=lambda t="keyboard", k=ps_key, w=lbl: mapper.clear_binding(t, k, w))
            btn_clear.grid(column=3, row=row, padx=(2, 5), pady=6)

            desc = ACTION_DESCRIPTIONS.get(ps_key, {"soldier": "-", "vehicle": "-", "airplane": "-"})
            ttk.Label(self.keys_frame, text=desc["soldier"], foreground="#495057").grid(column=4, row=row, padx=10, pady=6, sticky=tk.W)
            ttk.Label(self.keys_frame, text=desc["vehicle"], foreground="#495057").grid(column=5, row=row, padx=10, pady=6, sticky=tk.W)
            ttk.Label(self.keys_frame, text=desc["airplane"], foreground="#495057").grid(column=6, row=row, padx=10, pady=6, sticky=tk.W)

            self.bind_widgets[ps_key] = lbl
            row += 1

        row = self.create_section_divider(self.keys_frame, row, "Left Analog Stick Emulation")

        self.leftstick_labels = {}
        for dirk in ("up", "down", "left", "right"):
            ttk.Label(self.keys_frame, text=f"Stick {dirk.capitalize()}", font=("Segoe UI", 10), width=15).grid(column=0, row=row, padx=10, pady=5, sticky=tk.W)
            lbl = ttk.Label(self.keys_frame, text=cfg.get("left_stick", {}).get(dirk, ""), width=16, style="KeyBind.TLabel", padding=4)
            lbl.grid(column=1, row=row, padx=10, pady=5, sticky=tk.EW)

            btn_bind = ttk.Button(self.keys_frame, text="Bind", width=6, command=lambda t="leftstick", k=dirk, w=lbl: mapper.start_recording(t, k, w))
            btn_bind.grid(column=2, row=row, padx=(5, 2), pady=5)

            btn_clear = ttk.Button(self.keys_frame, text="Clear", width=6, command=lambda t="leftstick", k=dirk, w=lbl: mapper.clear_binding(t, k, w))
            btn_clear.grid(column=3, row=row, padx=(2, 5), pady=5)

            self.leftstick_labels[dirk] = lbl
            row += 1

        ttk.Label(self.keys_frame, text="Stick Limiter(Walk)", font=("Segoe UI", 10), width=15).grid(column=0, row=row, padx=10, pady=8, sticky=tk.W)
        self.limiter_lbl = ttk.Label(self.keys_frame, text=cfg.get("left_stick_limiter", {}).get("bind_key", "ctrl_l"), width=16, style="KeyBind.TLabel", padding=4)
        self.limiter_lbl.grid(column=1, row=row, padx=10, pady=8, sticky=tk.EW)

        btn_lim_bind = ttk.Button(self.keys_frame, text="Bind", width=6, command=lambda t="limiter", k="bind_key", w=self.limiter_lbl: mapper.start_recording(t, k, w))
        btn_lim_bind.grid(column=2, row=row, padx=(5, 2), pady=8)

        btn_lim_clear = ttk.Button(self.keys_frame, text="Clear", width=6, command=lambda t="limiter", k="bind_key", w=self.limiter_lbl: mapper.clear_binding(t, k, w))
        btn_lim_clear.grid(column=3, row=row, padx=(2, 5), pady=8)

        self.limiter_toggle_var = tk.BooleanVar(value=cfg.get("left_stick_limiter", {}).get("is_toggle", False))
        chk_lim = ttk.Checkbutton(self.keys_frame, text="Toggle Mode", variable=self.limiter_toggle_var, command=self.on_limiter_toggle_changed)
        chk_lim.grid(column=4, row=row, sticky=tk.W, padx=10, pady=8)

        slider_frame = ttk.Frame(self.keys_frame)
        slider_frame.grid(column=5, row=row, sticky=tk.W, padx=10, pady=8)
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

        self.menu_labels = {}

        # === MOUSE TAB ===
        ttk.Label(mouse_frame, text="Fine-tune Emulated Right Stick Sensitivity and Curves", style="SubHeader.TLabel").grid(column=0, row=0, columnspan=3, sticky=tk.W, pady=(15, 15), padx=20)

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
        ttk.Label(settings_frame, text="System Hotkeys & Global Emulation State", style="SubHeader.TLabel").grid(column=0, row=0, columnspan=3, sticky=tk.W, pady=(15, 10), padx=20)

        self.emulation_enabled_var = tk.BooleanVar(value=cfg.get("emulation_enabled", True))
        chk_master = ttk.Checkbutton(settings_frame, text="Master Emulation Active (Uncheck to suspend all background inputs completely)", variable=self.emulation_enabled_var, command=self.on_master_toggle_changed)
        chk_master.grid(column=0, row=1, columnspan=3, padx=20, pady=5, sticky=tk.W)

        ttk.Label(settings_frame, text="Toggle Mouse Lock Hotkey:").grid(column=0, row=2, padx=20, pady=6, sticky=tk.W)
        self.hk_lock_lbl = ttk.Label(settings_frame, text=cfg.get("hotkeys", {}).get("toggle_lock", "f5"), width=12, style="KeyBind.TLabel", padding=4)
        self.hk_lock_lbl.grid(column=1, row=2, padx=10, pady=6, sticky=tk.W)
        btn_hl = ttk.Button(settings_frame, text="Bind", width=6, command=lambda t="hotkey_lock", k="toggle_lock", w=self.hk_lock_lbl: mapper.start_recording(t, k, w))
        btn_hl.grid(column=2, row=2, padx=5, pady=6, sticky=tk.W)

        ttk.Label(settings_frame, text="Toggle Emulation Hotkey:").grid(column=0, row=3, padx=20, pady=6, sticky=tk.W)
        self.hk_emu_lbl = ttk.Label(settings_frame, text=cfg.get("hotkeys", {}).get("toggle_emulation", "f6"), width=12, style="KeyBind.TLabel", padding=4)
        self.hk_emu_lbl.grid(column=1, row=3, padx=10, pady=6, sticky=tk.W)
        btn_he = ttk.Button(settings_frame, text="Bind", width=6, command=lambda t="hotkey_emu", k="toggle_emulation", w=self.hk_emu_lbl: mapper.start_recording(t, k, w))
        btn_he.grid(column=2, row=3, padx=5, pady=6, sticky=tk.W)

        ttk.Label(settings_frame, text="Custom Macro Row Allocation Count (0-20):").grid(column=0, row=4, padx=20, pady=12, sticky=tk.W)
        self.custom_count_var = tk.IntVar(value=cfg.get("custom_count", 4))
        sp_cc = tk.Spinbox(settings_frame, from_=0, to=20, textvariable=self.custom_count_var, width=6, command=self.on_custom_count_changed)
        sp_cc.grid(column=1, row=4, padx=10, pady=12, sticky=tk.W)
        sp_cc.bind("<KeyRelease>", lambda e: self.on_custom_count_changed())

        ttk.Label(settings_frame, text="Hardware Controller Mixed Passthrough (Direct input injection coexistence)", style="SubHeader.TLabel").grid(column=0, row=5, columnspan=3, sticky=tk.W, pady=(15, 10), padx=20)

        ttk.Label(settings_frame, text="Hardware Controller Mixed Passthrough (Direct input injection coexistence)", style="SubHeader.TLabel").grid(column=0, row=5, columnspan=3, sticky=tk.W, pady=(15, 10), padx=20)

        # Frame napille ja täpälle
        pt_frame = ttk.Frame(settings_frame)
        pt_frame.grid(column=0, row=6, columnspan=3, padx=20, pady=8, sticky=tk.W)

        btn_open_controller_window = ttk.Button(
            pt_frame, 
            text="⚙️ Configure Controller Passthrough & Bindings", 
            command=self.open_controller_mapping_window
        )
        btn_open_controller_window.pack(side="left", padx=(0, 10))

        chk_pt = ttk.Checkbutton(
            pt_frame, 
            text="Enable Passthrough", 
            variable=self.pt_enabled_var, 
            command=self.on_passthrough_toggled
        )
        chk_pt.pack(side="left")

        # Uusi rivi Passthrough Hotkey -sidonnalle (vastaava kuin Mouse Lock)
        ttk.Label(settings_frame, text="Toggle Passthrough Hotkey:").grid(column=0, row=7, padx=20, pady=6, sticky=tk.W)
        
        # Oletuksena f8, jos hotkeys-sanakirjassa ei ole vielä arvoa
        pt_hotkey = cfg.get("hotkeys", {}).get("toggle_passthrough", "f8")
        self.hk_passthrough_lbl = ttk.Label(settings_frame, text=pt_hotkey, width=12, style="KeyBind.TLabel", padding=4)
        self.hk_passthrough_lbl.grid(column=1, row=7, padx=10, pady=6, sticky=tk.W)
        
        btn_pt_hk = ttk.Button(
            settings_frame, 
            text="Bind", 
            width=6, 
            command=lambda t="hotkey_passthrough", k="toggle_passthrough", w=self.hk_passthrough_lbl: mapper.start_recording(t, k, w)
        )
        btn_pt_hk.grid(column=2, row=7, padx=5, pady=6, sticky=tk.W)

        

        ttk.Label(settings_frame, text="Target Software / Environment Settings", style="SubHeader.TLabel").grid(column=0, row=8, columnspan=3, sticky=tk.W, pady=(20, 10), padx=20)

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

        ttk.Label(settings_frame, text="Context Profiles Settings", style="SubHeader.TLabel").grid(column=0, row=11, columnspan=3, sticky=tk.W, pady=(20, 10), padx=20)
        self.profiles_enabled_var = tk.BooleanVar(value=cfg.get("profiles_enabled", False))
        chk_prof = ttk.Checkbutton(settings_frame, text="Enable Context Profiles (Soldier / Vehicle / Plane)", variable=self.profiles_enabled_var, command=self.on_profiles_toggled)
        chk_prof.grid(column=0, row=12, columnspan=3, padx=20, pady=5, sticky=tk.W)

        ttk.Label(settings_frame, text="Soldier Profile Key:").grid(column=0, row=13, padx=20, pady=6, sticky=tk.W)
        self.soldier_key_lbl = ttk.Label(settings_frame, text=cfg.get("soldier_key", "z"), width=12, style="KeyBind.TLabel", padding=4)
        self.soldier_key_lbl.grid(column=1, row=13, padx=10, pady=6, sticky=tk.W)
        btn_sk = ttk.Button(settings_frame, text="Bind", width=6, command=lambda t="soldier_bind", k="soldier_key", w=self.soldier_key_lbl: mapper.start_recording(t, k, w))
        btn_sk.grid(column=2, row=13, padx=5, pady=6, sticky=tk.W)

        ttk.Label(settings_frame, text="Vehicle Profile Key:").grid(column=0, row=14, padx=20, pady=6, sticky=tk.W)
        self.vehicle_key_lbl = ttk.Label(settings_frame, text=cfg.get("vehicle_key", "x"), width=12, style="KeyBind.TLabel", padding=4)
        self.vehicle_key_lbl.grid(column=1, row=14, padx=10, pady=6, sticky=tk.W)
        btn_vk = ttk.Button(settings_frame, text="Bind", width=6, command=lambda t="vehicle_bind", k="vehicle_key", w=self.vehicle_key_lbl: mapper.start_recording(t, k, w))
        btn_vk.grid(column=2, row=14, padx=5, pady=6, sticky=tk.W)

        ttk.Label(settings_frame, text="Plane Profile Key:").grid(column=0, row=15, padx=20, pady=6, sticky=tk.W)
        self.plane_key_lbl = ttk.Label(settings_frame, text=cfg.get("plane_key", "v"), width=12, style="KeyBind.TLabel", padding=4)
        self.plane_key_lbl.grid(column=1, row=15, padx=10, pady=6, sticky=tk.W)
        btn_pk = ttk.Button(settings_frame, text="Bind", width=6, command=lambda t="plane_bind", k="plane_key", w=self.plane_key_lbl: mapper.start_recording(t, k, w))
        btn_pk.grid(column=2, row=15, padx=5, pady=6, sticky=tk.W)

        cfg_btn_frame = ttk.Frame(settings_frame)
        cfg_btn_frame.grid(column=0, row=16, columnspan=3, padx=20, pady=20, sticky=tk.W)
        ttk.Button(cfg_btn_frame, text="Save Config File", command=self.save_config_file).pack(side="left", padx=5)
        ttk.Button(cfg_btn_frame, text="Load Config File", command=self.load_config_file).pack(side="left", padx=5)
        ttk.Button(cfg_btn_frame, text="Check for Updates", command=lambda: self.check_update(silent=False)).pack(side="left", padx=5)

        self.version_lbl = ttk.Label(settings_frame, text=f"Active Local Software Version: {CURRENT_VERSION}", foreground="#6c757d")
        self.version_lbl.grid(column=0, row=17, columnspan=3, padx=20, pady=(0,0), sticky=tk.W)

    def create_section_divider(self, parent, row, title):
        sep = ttk.Separator(parent, orient=tk.HORIZONTAL)
        sep.grid(column=0, row=row, columnspan=6, sticky=tk.EW, pady=(15, 10))
        lbl = ttk.Label(parent, text=title, style="Header.TLabel")
        lbl.grid(column=0, row=row + 1, columnspan=6, sticky=tk.W, padx=10, pady=(0, 10))
        return row + 2

    def refresh_keyboard_bindings_ui(self):
        ctx = mapper.current_profile_context
        for ps_key, lbl_widget in self.bind_widgets.items():
            bind_val = cfg.get("keyboard", {}).get(ps_key, {}).get("bind_key", "")
            if cfg.get("profiles_enabled", False) and ctx == "vehicle":
                bind_val = cfg.get("keyboard_vehicle", {}).get(ps_key, bind_val)
            elif cfg.get("profiles_enabled", False) and ctx == "plane":
                bind_val = cfg.get("keyboard_plane", {}).get(ps_key, bind_val)
            lbl_widget.config(text=bind_val)

    def load_mouse_profile_ui(self):
        ctx = mapper.current_profile_context
        if cfg.get("profiles_enabled", False) and ctx in ("vehicle", "plane"):
            p_data = cfg.get("mouse_profiles", {}).get(ctx, {})
            self.sens_x_var.set(p_data.get("sensitivity_x", 3.0))
            self.sens_y_var.set(p_data.get("sensitivity_y", 3.2))
            self.dead_x_var.set(p_data.get("deadzone_x", 0.0))
            self.dead_y_var.set(p_data.get("deadzone_y", 0.0))
            self.adz_x_var.set(p_data.get("anti_deadzone_x", 0.0))
            self.adz_y_var.set(p_data.get("anti_deadzone_y", 0.0))
            self.gamma_var.set(p_data.get("linearity", 1.5))
            self.invert_y_var.set(p_data.get("invert_y", True))
        else:
            self.sens_x_var.set(cfg.get("mouse", {}).get("sensitivity_x", 3.0))
            self.sens_y_var.set(cfg.get("mouse", {}).get("sensitivity_y", 3.2))
            self.dead_x_var.set(cfg.get("mouse", {}).get("deadzone_x", 0.0))
            self.dead_y_var.set(cfg.get("mouse", {}).get("deadzone_y", 0.0))
            self.adz_x_var.set(cfg.get("mouse", {}).get("anti_deadzone_x", 0.0))
            self.adz_y_var.set(cfg.get("mouse", {}).get("anti_deadzone_y", 0.0))
            self.gamma_var.set(cfg.get("mouse", {}).get("linearity", 1.5))
            self.invert_y_var.set(cfg.get("mouse", {}).get("invert_y", True))

        self.sens_x_lbl.config(text=f"{self.sens_x_var.get():.2f}")
        self.sens_y_lbl.config(text=f"{self.sens_y_var.get():.2f}")
        self.dead_x_lbl.config(text=f"{self.dead_x_var.get():.2f}")
        self.dead_y_lbl.config(text=f"{self.dead_y_var.get():.2f}")
        self.adz_x_lbl.config(text=f"{self.adz_x_var.get():.3f}")
        self.adz_y_lbl.config(text=f"{self.adz_y_var.get():.3f}")
        self.gamma_lbl.config(text=f"{self.gamma_var.get():.2f}")

    def on_mouse_profile_tab_changed(self):
        new_ctx = self.mouse_profile_var.get()
        mapper.set_profile_context(new_ctx)

    def update_mouse_config(self):
        ctx = mapper.current_profile_context
        if cfg.get("profiles_enabled", False) and ctx in ("vehicle", "plane"):
            if "mouse_profiles" not in cfg: cfg["mouse_profiles"] = {}
            if ctx not in cfg["mouse_profiles"]: cfg["mouse_profiles"][ctx] = {}
            cfg["mouse_profiles"][ctx]["sensitivity_x"] = round(self.sens_x_var.get(), 2)
            cfg["mouse_profiles"][ctx]["sensitivity_y"] = round(self.sens_y_var.get(), 2)
            cfg["mouse_profiles"][ctx]["deadzone_x"] = round(self.dead_x_var.get(), 2)
            cfg["mouse_profiles"][ctx]["deadzone_y"] = round(self.dead_y_var.get(), 2)
            cfg["mouse_profiles"][ctx]["anti_deadzone_x"] = round(self.adz_x_var.get(), 3)
            cfg["mouse_profiles"][ctx]["anti_deadzone_y"] = round(self.adz_y_var.get(), 3)
            cfg["mouse_profiles"][ctx]["linearity"] = round(self.gamma_var.get(), 2)
            cfg["mouse_profiles"][ctx]["invert_y"] = self.invert_y_var.get()
        else:
            cfg["mouse"]["sensitivity_x"] = round(self.sens_x_var.get(), 2)
            cfg["mouse"]["sensitivity_y"] = round(self.sens_y_var.get(), 2)
            cfg["mouse"]["deadzone_x"] = round(self.dead_x_var.get(), 2)
            cfg["mouse"]["deadzone_y"] = round(self.dead_y_var.get(), 2)
            cfg["mouse"]["anti_deadzone_x"] = round(self.adz_x_var.get(), 3)
            cfg["mouse"]["anti_deadzone_y"] = round(self.adz_y_var.get(), 3)
            cfg["mouse"]["linearity"] = round(self.gamma_var.get(), 2)
            cfg["mouse"]["invert_y"] = self.invert_y_var.get()

        cfg["mouse"]["pixel_to_unit"] = round(self.pt_unit_var.get(), 1)
        try:
            val = int(self.smooth_var.get())
            cfg["mouse"]["smoothing_samples"] = max(1, min(10, val))
            mapper.mouse_dx_queue = deque(maxlen=cfg["mouse"]["smoothing_samples"])
            mapper.mouse_dy_queue = deque(maxlen=cfg["mouse"]["smoothing_samples"])
        except Exception: pass

        self.sens_x_lbl.config(text=f"{self.sens_x_var.get():.2f}")
        self.sens_y_lbl.config(text=f"{self.sens_y_var.get():.2f}")
        self.dead_x_lbl.config(text=f"{self.dead_x_var.get():.2f}")
        self.dead_y_lbl.config(text=f"{self.dead_y_var.get():.2f}")
        self.adz_x_lbl.config(text=f"{self.adz_x_var.get():.3f}")
        self.adz_y_lbl.config(text=f"{self.adz_y_var.get():.3f}")
        self.gamma_lbl.config(text=f"{self.gamma_var.get():.2f}")
        self.pt_unit_lbl.config(text=f"{self.pt_unit_var.get():.1f}")
        save_config(cfg)

    def reset_mouse_defaults(self):
        cfg["mouse"] = DEFAULT_CONFIG["mouse"].copy()
        cfg["mouse_profiles"] = DEFAULT_CONFIG["mouse_profiles"].copy()
        save_config(cfg)
        self.load_mouse_profile_ui()
        self.pt_unit_var.set(cfg["mouse"]["pixel_to_unit"])
        self.smooth_var.set(cfg["mouse"]["smoothing_samples"])
        self.pt_unit_lbl.config(text=f"{self.pt_unit_var.get():.1f}")

    def reset_keyboard_defaults(self):
        cfg["keyboard"] = DEFAULT_CONFIG["keyboard"].copy()
        cfg["left_stick"] = DEFAULT_CONFIG["left_stick"].copy()
        cfg["left_stick_limiter"] = DEFAULT_CONFIG["left_stick_limiter"].copy()
        save_config(cfg)
        self.refresh_keyboard_bindings_ui()
        for dirk, lbl in self.leftstick_labels.items():
            lbl.config(text=cfg["left_stick"].get(dirk, ""))
        self.limiter_lbl.config(text=cfg["left_stick_limiter"].get("bind_key", ""))
        self.limiter_toggle_var.set(cfg["left_stick_limiter"].get("is_toggle", False))
        self.limiter_val_var.set(cfg["left_stick_limiter"].get("value", 0.5))

    def open_controller_mapping_window(self):
        ControllerMappingWindow(self)

    def rebuild_custom_inputs_ui(self):
        for elem in getattr(self, "menu_ui_elements", []):
            try:
                if elem.winfo_exists():
                    elem.destroy()
            except tk.TclError:
                pass
        self.menu_ui_elements = []

        for w_dict in self.custom_widgets:
            for w in w_dict.values():
                try:
                    if w.winfo_exists():
                        w.destroy()
                except tk.TclError:
                    pass
        self.custom_widgets.clear()

        c_count = int(cfg.get("custom_count", len(cfg.get("custom_inputs", []))))
        curr_row = self.custom_start_row

        if c_count > 0:
            self.custom_sep.grid(column=0, row=curr_row - 2, columnspan=6, sticky=tk.EW, pady=(15, 10))
            self.custom_title_lbl.grid(column=0, row=curr_row - 1, columnspan=6, sticky=tk.W, padx=10, pady=(0, 10))

            targets = list(cfg.get("keyboard", {}).keys())
            targets.extend(["soldier_profile", "vehicle_profile", "plane_profile"])

            for i in range(c_count):
                # Varmistetaan että alkiolla on name-kenttä
                while len(cfg["custom_inputs"]) <= i:
                    cfg["custom_inputs"].append({"name": f"Custom {i+1}", "target": "cross", "bind_key": ""})

                ci = cfg["custom_inputs"][i]

                # Vasemman puolen teksti on AINA juokseva Custom 1 - 20
                static_label_text = f"Custom {i+1}"
                lbl_name = ttk.Label(self.keys_frame, text=static_label_text, font=("Segoe UI", 10, "bold"), width=15)
                lbl_name.grid(column=0, row=curr_row, padx=10, pady=5, sticky=tk.W)

                lbl_bind = ttk.Label(self.keys_frame, text=ci.get("bind_key", ""), width=16, style="KeyBind.TLabel", padding=4)
                lbl_bind.grid(column=1, row=curr_row, padx=10, pady=5, sticky=tk.EW)

                btn_bind = ttk.Button(self.keys_frame, text="Bind", width=6, command=lambda t="custom", k=str(i), w=lbl_bind: mapper.start_recording(t, k, w))
                btn_bind.grid(column=2, row=curr_row, padx=(5, 2), pady=5)

                btn_clear = ttk.Button(self.keys_frame, text="Clear", width=6, command=lambda t="custom", k=str(i), w=lbl_bind: mapper.clear_binding(t, k, w))
                btn_clear.grid(column=3, row=curr_row, padx=(2, 5), pady=5)

                target_var = tk.StringVar(value=ci.get("target", "cross"))
                cb_target = ttk.Combobox(self.keys_frame, textvariable=target_var, values=targets, width=14, state="readonly")
                cb_target.grid(column=4, row=curr_row, padx=10, pady=5, sticky=tk.W)
                cb_target.bind("<<ComboboxSelected>>", lambda e, idx=i, var=target_var: self.on_custom_target_changed(idx, var.get()))

                # Oikean puolen kirjoituslaatikko tallentaa nyt "name"-kenttään (korvaa vanhan descriptionin)
                name_var = tk.StringVar(value=ci.get("name", f"Custom {i+1}"))
                ent_name = ttk.Entry(self.keys_frame, textvariable=name_var, width=25)
                ent_name.grid(column=5, row=curr_row, columnspan=2, padx=10, pady=5, sticky=tk.W)
                ent_name.bind("<KeyRelease>", lambda e, idx=i, var=name_var: self.on_custom_name_changed(idx, var.get()))

                self.custom_widgets.append({
                    "lbl_name": lbl_name,
                    "lbl_bind": lbl_bind, 
                    "btn_bind": btn_bind, 
                    "btn_clear": btn_clear,
                    "cb_target": cb_target, 
                    "ent_desc": ent_name
                })
                curr_row += 1
        else:
            self.custom_sep.grid_remove()
            self.custom_title_lbl.grid_remove()

        menu_sep = ttk.Separator(self.keys_frame, orient=tk.HORIZONTAL)
        menu_sep.grid(column=0, row=curr_row, columnspan=6, sticky=tk.EW, pady=(20, 10))
        
        menu_title_lbl = ttk.Label(self.keys_frame, text="Menu Navigation Shortcuts (Select->A, Back->B Directly)", style="Header.TLabel")
        menu_title_lbl.grid(column=0, row=curr_row + 1, columnspan=6, sticky=tk.W, padx=10, pady=(0, 10))
        
        self.menu_ui_elements.extend([menu_sep, menu_title_lbl])
        curr_row += 2

        self.menu_labels = {}
        for mkey, mname in [("select", "Select/Accept"), ("back", "Back/Cancel"), ("up", "Menu Up"), ("down", "Menu Down"), ("left", "Menu Left"), ("right", "Menu Right")]:
            lbl_m = ttk.Label(self.keys_frame, text=mname, font=("Segoe UI", 10), width=20)
            lbl_m.grid(column=0, row=curr_row, padx=10, pady=5, sticky=tk.W)

            lbl_b = ttk.Label(self.keys_frame, text=cfg.get("menu_buttons", {}).get(mkey, ""), width=16, style="KeyBind.TLabel", padding=4)
            lbl_b.grid(column=1, row=curr_row, padx=10, pady=5, sticky=tk.EW)

            btn_r = ttk.Button(self.keys_frame, text="Record", width=9, command=lambda t="menu", k=mkey, w=lbl_b: mapper.start_recording(t, k, w))
            btn_r.grid(column=2, row=curr_row, padx=10, pady=5)

            self.menu_labels[mkey] = lbl_b
            self.menu_ui_elements.extend([lbl_m, lbl_b, btn_r])
            curr_row += 1

    def on_custom_target_changed(self, idx, new_target):
        if idx < len(cfg.get("custom_inputs", [])):
            cfg["custom_inputs"][idx]["target"] = new_target
            save_config(cfg)

    # Korvattu on_custom_desc_changed uudella nimellä:
    def on_custom_name_changed(self, idx, new_name):
        if idx < len(cfg.get("custom_inputs", [])):
            cfg["custom_inputs"][idx]["name"] = new_name
            save_config(cfg)

    def on_custom_count_changed(self):
        try:
            val = int(self.custom_count_var.get())
            val = max(0, min(20, val))
            cfg["custom_count"] = val
            save_config(cfg)
            self.rebuild_custom_inputs_ui()
        except Exception: pass

    def on_limiter_toggle_changed(self):
        cfg["left_stick_limiter"]["is_toggle"] = self.limiter_toggle_var.get()
        save_config(cfg)

    def on_limiter_val_changed(self):
        cfg["left_stick_limiter"]["value"] = round(self.limiter_val_var.get(), 2)
        save_config(cfg)

    def on_master_toggle_changed(self):
        state = self.emulation_enabled_var.get()
        cfg["emulation_enabled"] = state
        save_config(cfg)
        status = "ENABLED" if state else "DISABLED"
        self.status_var.set(f"Remap hooks state shifted: {status}")
        if not state and mapper.mouse_locked: mapper.toggle_mouse_lock()

    def on_passthrough_toggled(self):
        cfg["controller_passthrough"]["enabled"] = self.pt_enabled_var.get()
        save_config(cfg)

    def on_passthrough_index_changed(self):
        try:
            val = int(self.pt_index_var.get())
            cfg["controller_passthrough"]["selected_index"] = max(0, val)
            save_config(cfg)
        except Exception: pass

    def on_profiles_toggled(self):
        state = self.profiles_enabled_var.get()
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
            self.on_mouse_profile_tab_changed()

    def save_game_settings(self):
        if "game_settings" not in cfg: cfg["game_settings"] = {}
        cfg["game_settings"]["executable_path"] = self.exec_path_var.get()
        cfg["game_settings"]["arguments"] = self.exec_args_var.get()
        save_config(cfg)

    def browse_executable(self):
        file_selected = filedialog.askopenfilename(filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")])
        if file_selected:
            self.exec_path_var.set(file_selected)
            self.save_game_settings()

    def on_passthrough_toggled(self):
        """Päivittää passthrough-tilan konfiguraatioon täpän tai pikanäppäimen muuttuessa."""
        if "controller_passthrough" not in cfg:
            cfg["controller_passthrough"] = {}
        
        state = self.pt_enabled_var.get()
        cfg["controller_passthrough"]["enabled"] = state
        save_config(cfg)
        
        status = "ENABLED" if state else "DISABLED"
        self.status_var.set(f"Controller Passthrough shifted: {status}")

    def toggle_passthrough_shortcut(self):
        new_state = not self.pt_enabled_var.get()
        self.pt_enabled_var.set(new_state)
        self.on_passthrough_toggled()

    def rebind_passthrough_shortcut(self):
        """Päivittää Tkinterin ikkunakohtaisen pikanäppäinsidonnan."""
        pt_key = cfg.get("hotkeys", {}).get("toggle_passthrough", "f8")
        if pt_key:
            self.bind(f"<{pt_key.upper()}>", lambda e: self.toggle_passthrough_shortcut())

    def save_config_file(self):
        file_path = filedialog.asksaveasfilename(
            initialdir=BASE_DIR,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
        )
        if file_path:
            try:
                save_config(cfg, custom_path=file_path)
                self.active_config_name_var.set(os.path.basename(file_path))
                messagebox.showinfo(
                    "Config Saved", f"Configuration saved to:\n{file_path}"
                )
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to save configuration:\n{e}"
                )

    def load_config_file(self):
        file_path = filedialog.askopenfilename(
            initialdir=BASE_DIR, filetypes=[("JSON Files", "*.json")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    sanitized = ensure_config_defaults(loaded)
                    cfg.clear()
                    cfg.update(sanitized)

                config.current_config_path = file_path
                save_config(cfg)

                self.active_config_name_var.set(os.path.basename(file_path))
                self.refresh_keyboard_bindings_ui()
                self.load_mouse_profile_ui()
                self.custom_count_var.set(cfg.get("custom_count", 4))
                self.rebuild_custom_inputs_ui()
                self.emulation_enabled_var.set(
                    cfg.get("emulation_enabled", True)
                )
                self.pt_enabled_var.set(
                    cfg.get("controller_passthrough", {}).get("enabled", False)
                )
                self.pt_index_var.set(
                    cfg.get("controller_passthrough", {}).get(
                        "selected_index", 0
                    )
                )
                self.profiles_enabled_var.set(cfg.get("profiles_enabled", False))
                self.hk_lock_lbl.config(
                    text=cfg.get("hotkeys", {}).get("toggle_lock", "f5")
                )
                self.hk_emu_lbl.config(
                    text=cfg.get("hotkeys", {}).get("toggle_emulation", "f6")
                )
                self.soldier_key_lbl.config(text=cfg.get("soldier_key", "z"))
                self.vehicle_key_lbl.config(text=cfg.get("vehicle_key", "x"))
                self.plane_key_lbl.config(text=cfg.get("plane_key", "v"))
                self.exec_path_var.set(
                    cfg.get("game_settings", {}).get("executable_path", "")
                )
                self.exec_args_var.set(
                    cfg.get("game_settings", {}).get("arguments", "")
                )
                self.on_profiles_toggled()
                messagebox.showinfo(
                    "Config Loaded", f"Configuration loaded from:\n{file_path}"
                )
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to load configuration:\n{e}"
                )

    def start_game(self):
        start_game_process(self)

    def check_update(self, silent=True):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                latest_ver = data.get("tag_name", "")
                if latest_ver and latest_ver != CURRENT_VERSION:
                    if messagebox.askyesno("Update Available", f"A new version ({latest_ver}) is available!\nYour version: {CURRENT_VERSION}\n\nWould you like to open the releases page?"):
                        webbrowser.open(data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"))
                elif not silent:
                    messagebox.showinfo("Up to Date", f"You are running the latest version ({CURRENT_VERSION}).")
        except Exception as e:
            if not silent:
                messagebox.showerror("Check Failed", f"Could not check for updates:\n{e}")