import tkinter as tk
from tkinter import ttk
import math
import config
from config import cfg

class MouseCurveWidget(ttk.Frame):
    def __init__(self, parent=None, width=380, height=300):
        super().__init__(parent)
        self.width = width
        self.height = height

        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)

        self.canvas_margin = 30
        self.canvas_width = self.width
        self.canvas_height = self.height - 30

        # Luodaan canvas ensin
        self.canvas = tk.Canvas(
            self.main_frame,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#cccccc"
        )
        self.canvas.pack(side="top", fill="both", expand=True, padx=5, pady=5)

        # Sidotaan ikkunan koon muutos vasta canvasin luonnin jälkeen
        self.canvas.bind("<Configure>", lambda event: self.draw_graph())

        self.label_frame = ttk.Frame(self.main_frame)
        self.label_frame.pack(side="bottom", fill="x", padx=5, pady=(0, 5))

        self.lbl_x = tk.Label(
            self.label_frame,
            text="X-AXIS",
            fg="red",
            font=("Segoe UI", 9, "bold"),
            bg="#f8f9fa"
        )
        self.lbl_x.pack(side="left", padx=(10, 15))

        self.lbl_y = tk.Label(
            self.label_frame,
            text="Y-AXIS",
            fg="blue",
            font=("Segoe UI", 9, "bold"),
            bg="#f8f9fa"
        )
        self.lbl_y.pack(side="left")

        # Live-tietojen näyttö
        self.lbl_live_info = tk.Label(
            self.label_frame,
            text="Raw: X:0.00 Y:0.00 | Out: X:0.00 Y:0.00",
            font=("Consolas", 8),
            fg="#495057",
            bg="#f8f9fa"
        )
        self.lbl_live_info.pack(side="right", padx=10)

        self.running = True
        self.draw_graph()
        self.update_dot_loop()

    def get_active_mouse_params(self):
        """Hakee aktiivisen profiilin mukaiset hiiriasetukset."""
        context = getattr(config.mapper if hasattr(config, 'mapper') else None, 'current_profile_context', 'soldier')
        
        if cfg.get("profiles_enabled", False) and context in ("vehicle", "plane"):
            p_data = cfg.get("mouse_profiles", {}).get(context, {})
            dz_x = float(p_data.get("deadzone_x", 0.0))
            dz_y = float(p_data.get("deadzone_y", 0.0))
            adz_x = float(p_data.get("anti_deadzone_x", 0.0))
            adz_y = float(p_data.get("anti_deadzone_y", 0.0))
            gamma_x = float(p_data.get("linearity_x", 1.0))
            gamma_y = float(p_data.get("linearity_y", 1.0))
        else:
            m_data = cfg.get("mouse", {})
            dz_x = float(m_data.get("deadzone_x", 0.0))
            dz_y = float(m_data.get("deadzone_y", 0.0))
            adz_x = float(m_data.get("anti_deadzone_x", 0.0))
            adz_y = float(m_data.get("anti_deadzone_y", 0.0))
            gamma_x = float(m_data.get("linearity_x", 1.0))
            gamma_y = float(m_data.get("linearity_y", 1.0))

        return dz_x, dz_y, adz_x, adz_y, gamma_x, gamma_y

    def calculate_output(self, raw_input, dz, adz, gamma):
        """Laskee ulostulon annetulle raaka-arvolle (0.0 - 1.0)."""
        if raw_input <= dz:
            return 0.0
        
        scaled_input = (raw_input - dz) / (1.0 - dz) if dz < 1.0 else 0.0
        val = adz + scaled_input * (1.0 - adz) if adz < 1.0 else scaled_input
        val = min(1.0, val)

        if gamma != 1.0 and val > 0:
            val = math.pow(val, gamma)

        return min(1.0, max(0.0, val))

    def draw_graph(self):
        """Piirtää taustan ja viivat."""
        self.canvas.delete("all")

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w <= 1: w = self.canvas_width
        if h <= 1: h = self.canvas_height

        margin = self.canvas_margin
        gw = w - 2 * margin
        gh = h - 2 * margin

        # Ruudukko
        for i in range(5):
            ratio = i / 4.0
            x = margin + ratio * gw
            y = margin + ratio * gh
            self.canvas.create_line(x, margin, x, h - margin, fill="#e9ecef", dash=(2, 2))
            self.canvas.create_line(margin, y, w - margin, y, fill="#e9ecef", dash=(2, 2))

        # Akselit
        self.canvas.create_line(margin, h - margin, w - margin, h - margin, fill="#6c757d", width=2)
        self.canvas.create_line(margin, margin, margin, h - margin, fill="#6c757d", width=2)

        dz_x, dz_y, adz_x, adz_y, gamma_x, gamma_y = self.get_active_mouse_params()

        # Deadzone viivat
        if dz_x > 0.0:
            dz_px_x = margin + dz_x * gw
            self.canvas.create_line(dz_px_x, margin, dz_px_x, h - margin, fill="#dc3545", dash=(4, 4), width=1.5)

        if dz_y > 0.0:
            dz_px_y = margin + dz_y * gw
            self.canvas.create_line(dz_px_y, margin, dz_px_y, h - margin, fill="#0d6efd", dash=(4, 4), width=1.5)

        steps = 50
        # X-akseli (Punainen)
        points_x = []
        for i in range(steps + 1):
            input_val = i / steps
            output_val = self.calculate_output(input_val, dz_x, adz_x, gamma_x)
            px = margin + input_val * gw
            py = (h - margin) - output_val * gh
            points_x.append((px, py))

        for i in range(len(points_x) - 1):
            self.canvas.create_line(points_x[i][0], points_x[i][1], points_x[i+1][0], points_x[i+1][1], fill="red", width=2, tags="curve")

        # Y-akseli (Sininen)
        points_y = []
        for i in range(steps + 1):
            input_val = i / steps
            output_val = self.calculate_output(input_val, dz_y, adz_y, gamma_y)
            px = margin + input_val * gw
            py = (h - margin) - output_val * gh
            points_y.append((px, py))

        for i in range(len(points_y) - 1):
            self.canvas.create_line(points_y[i][0], points_y[i][1], points_y[i+1][0], points_y[i+1][1], fill="blue", width=2, tags="curve")

    def update_dot_loop(self):
        """Päivittää reaaliaikaiset pallot akselikäyrille ja näyttää live-arvot."""
        if not self.running:
            return

        self.canvas.delete("live_dot")

        import mapper
        if cfg.get("emulation_enabled", True):
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            if w <= 1: w = self.canvas_width
            if h <= 1: h = self.canvas_height

            margin = self.canvas_margin
            gw = w - 2 * margin
            gh = h - 2 * margin

            # Luetaan mapperin päivittämät arvot
            raw_x = getattr(mapper, "raw_mouse_x", 0.0)
            raw_y = getattr(mapper, "raw_mouse_y", 0.0)
            out_x = abs(getattr(mapper, "target_rx", 0.0))
            out_y = abs(getattr(mapper, "target_ry", 0.0))

            # Tekstipäivitys
            self.lbl_live_info.config(
                text=f"Raw: X:{raw_x:.2f} Y:{raw_y:.2f} | Out: X:{out_x:.2f} Y:{out_y:.2f}"
            )

            # Visualisointipallot pohjaviivalla (Raw input)
            rx_px = margin + raw_x * gw
            ry_px = margin + raw_y * gw
            base_y = h - margin

            if raw_x > 0.0:
                self.canvas.create_oval(rx_px - 3, base_y - 3, rx_px + 3, base_y + 3, fill="#ffc107", outline="#000000", tags="live_dot")
            if raw_y > 0.0:
                self.canvas.create_oval(ry_px - 3, base_y - 3, ry_px + 3, base_y + 3, fill="#ffc107", outline="#000000", tags="live_dot")

            # Lasketaan todelliset ulostulot akselikohtaisesti käyrää varten
            dz_x, dz_y, adz_x, adz_y, gamma_x, gamma_y = self.get_active_mouse_params()
            curved_out_x = self.calculate_output(raw_x, dz_x, adz_x, gamma_x)
            curved_out_y = self.calculate_output(raw_y, dz_y, adz_y, gamma_y)

            # X-akselin pallo (Punainen käyrä)
            out_px_x = margin + raw_x * gw
            out_py_x = (h - margin) - curved_out_x * gh
            self.canvas.create_oval(out_px_x - 5, out_py_x - 5, out_px_x + 5, out_py_x + 5, fill="#ff0000", outline="#ffffff", width=1.5, tags="live_dot")

            # Y-akselin pallo (Sininen käyrä)
            out_px_y = margin + raw_y * gw
            out_py_y = (h - margin) - curved_out_y * gh
            self.canvas.create_oval(out_px_y - 5, out_py_y - 5, out_px_y + 5, out_py_y + 5, fill="#0055ff", outline="#ffffff", width=1.5, tags="live_dot")

        self.after(20, self.update_dot_loop)

class MouseCurveWindow(tk.Toplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Mouse Response Curve & Live Input")
        self.geometry("460x360")
        self.configure(bg="#f8f9fa")

        self.attributes("-topmost", True)
        self.resizable(True, True)

        self.widget = MouseCurveWidget(self, width=440, height=310)
        self.widget.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh(self):
        if hasattr(self.widget, "draw_graph"):
            self.widget.draw_graph()

    def destroy(self):
        if hasattr(self, 'widget'):
            self.widget.running = False
        super().destroy()