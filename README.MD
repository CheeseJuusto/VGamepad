# VGamepad - Keyboard & Mouse to Virtual Xbox 360 Controller Remapper

**Version:** v3.0  
**GitHub Repository:** [CheeseJuusto/VGamepad](https://github.com/CheeseJuusto/VGamepad)

## IMPORTANT - This app is made ONLY for emulators. Using the app with native PC games may result in your account being BANNED.

VGamepad is a high-performance input remapping tool designed for Windows. The application converts keyboard and mouse inputs in real time into virtual Xbox 360 controller inputs via the ViGEmBus driver. It is specifically built for emulator use (such as RPCS3) and games that require precise analog mouse control along with versatile control profiles.

---

## 🌟 Key Features (v3.0)

- **ViGEmBus Virtual Controller (VX360Gamepad):** Reliable, low-latency Xbox 360 controller emulation.
- **Raw Input Processing:** Utilizes the Windows Raw Input API to read mouse and keyboard hardware inputs directly without OS delays.
- **Context Profiles:** Separate key and mouse configurations for different gameplay scenarios (**Soldier**, **Vehicle**, **Plane**). Switch profiles automatically or using dedicated hotkeys.
- **High Polling Rate Support (Up to 120 Hz):** Configurable update rates (30, 60, 100, 120 Hz) ensure smooth and precise analog responsiveness.
- **Advanced Mouse Fine-Tuning:**
  - Independent X and Y axis sensitivity
  - Deadzones and Anti-Deadzones
  - Linearity / Gamma curve adjustment
  - Invert Y-axis option
  - Mouse smoothing samples and Pixel-to-Unit conversion factor
- **Controller Passthrough:** Connect a physical USB controller and pass its inputs directly through to the emulated controller, or remap its axes and buttons.
- **Auxiliary Macros:** Define up to 20 custom macro/input slots for custom actions.
- **Left Stick Limiter (Walk Key):** Emulate walk/run states with an analog stick multiplier (supports Toggle/Hold modes).
- **In-Game Mouse Lock:** Locks the cursor to the center of the screen/emulator window in windowed and fullscreen modes.
- **Direct Game Launch Integration:** Specify the executable path and launch arguments (e.g., RPCS3 `--no-gui` flags) directly inside the app.
- **Make config files** for other games, save and load it easily
- **Enhanced UI** and simplified application structure

---

## 📋 System Requirements

- **Operating System:** Windows 10 / 11 (64-bit)
- **Required Drivers:**
  - **[ViGEmBus Driver](https://github.com/nefarius/ViGEmBus/releases):** Mandatory for virtual controller emulation.

---

## 🛠️ Installation & Setup

### 1. Install the ViGEmBus Driver
Download and install the latest **ViGEmBus driver** from:  
👉 [https://github.com/nefarius/ViGEmBus/releases](https://github.com/nefarius/ViGEmBus/releases)

### 2. Run the Application
1. Download the latest release from the GitHub Releases page.
2. Launch `VGamepad.exe`.

---

## 🎮 Usage Guide

### Graphical User Interface (GUI)

VGamepad features three main tabs:

1. **⌨️ Keyboard Mapping:**
   - Map keyboard keys to virtual controller buttons (A, B, X, Y, L1, R1, L2, R2, L3, R3, Select, Start, D-Pad).
   - Select an active profile (**Soldier**, **Vehicle**, **Plane**) to view or adjust context-specific key bindings.
   - Configure Left Stick movement keys (W/A/S/D) and the Walk Key / Stick Limiter.

2. **🖱️ Mouse Input Settings:**
   - Adjust Right Stick emulation parameters including sensitivity, deadzones, anti-deadzones, and linearity for X and Y axes.
   - Configure profile-specific mouse behavior for Soldier, Vehicle, and Plane modes.
   - Set the update rate (**Update Rate HZ**: 30, 60, 100, 120 Hz) and mouse smoothing samples.

3. **⚙️ Application Settings:**
   - **Hotkeys:**
     - `F5` *(default)*: Toggle Mouse Lock (Locks/unlocks the mouse cursor).
     - `F6` *(default)*: Toggle Master Emulation (Enables/disables overall emulation).
     - `F8` *(default)*: Toggle Passthrough (Enables/disables physical controller passthrough).
   - **Controller Passthrough:** Configure physical USB controller axes and button mappings.
   - **Game Settings:** Set the path to your game or emulator executable (`executable_path`) and set startup commands (`arguments`).
   - **Context Profiles Toggle:** Enable or disable context-sensitive profiles and assign profile-switching keys.

---

## ⚙️ Configuration File (`config.json`)

The application automatically creates and manages a `config.json` file in its folder. Below is an example default configuration (`v3.0`):

```json
{
  "profiles_enabled": false,
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
  "mouse": {
    "sensitivity_x": 3.0,
    "sensitivity_y": 3.2,
    "deadzone_x": 0.0,
    "deadzone_y": 0.0,
    "anti_deadzone_x": 0.0,
    "anti_deadzone_y": 0.0,
    "linearity": 1.5,
    "invert_y": true,
    "pixel_to_unit": 100.0,
    "smoothing_samples": 1
  },
  "update_rate_hz": 120,
  "hotkeys": {
    "toggle_lock": "f5",
    "toggle_emulation": "f6",
    "toggle_passthrough": "f8"
  },
  "emulation_enabled": true,
  "left_stick": {"up": "w", "down": "s", "left": "a", "right": "d"},
  "left_stick_limiter": {
    "bind_key": "ctrl_l",
    "is_toggle": true,
    "value": 0.45
  },
  "controller_passthrough": {
    "enabled": false,
    "selected_index": 0,
    "bindings": {}
  }
}