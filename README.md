# VGamepad (v1.1)

his app is made ONLY for emulators. Using the app with native PC games may result in your account being BANNED.

VGamepad is an advanced mouse and keyboard remapping utility built with Python, Tkinter, and Pygame that emulates a virtual Xbox 360 controller on Windows. It is specifically designed for simulation and shooter games that require seamless, on-the-fly profile switching (Soldier, Vehicle, Plane) and highly customizable mouse-to-analog-stick translation behavior.

## Features

- **Context-Specific Profiles:** Completely independent keybindings, mouse settings, and custom macro lists for three distinct game modes: *Soldier*, *Vehicle*, and *Plane*.
- **Dynamic Auxiliary Macros:** Dynamically configure between 0 to 20 custom macro rows or triggers per profile context directly from the interface.
- **Advanced Mouse Emulation:**
  - Independent X/Y axis sensitivity and deadzone adjustments.
  - Linearity (Gamma/Curve) controls for precise aiming physics.
  - Centered mouse capture toggled via a hotkey, preserving pure raw mouse delta behavior.
  - Extended mouse mapping support (Mouse 1-5, Scroll Wheel Up/Down).
- **Controller Passthrough:** Pygame integration enables simultaneous support for a physical gamepad alongside your mouse and keyboard inputs.
- **Left Stick Limiter:** Built-in modifier for restricting analog stick input range (e.g., for walking/sneaking mechanics) with an adjustable multiplier slider and toggle.
- **Game Launcher Management:** Specify a target game executable (`.exe`) and set custom boot arguments directly inside the UI.
- **Automated Update Checks:** Embedded version control that checks for software updates directly from the GitHub repository on launch.

## Requirements

VGamepad requires a **Windows Operating System** and the following driver installed on the host system:

1. **ViGEmBus Driver** (Strictly required for virtual controller injection)
   - Download and install the latest release from the official repository before running the application: [ViGEmBus GitHub Releases](https://github.com/ViGEm/ViGEmBus/releases)

## Installation & Running

Since VGamepad is distributed as a standalone executable, no Python installation or environment setup is required:

1. Download the latest `vgamepad.exe` release.
2. Ensure the **ViGEmBus Driver** is installed on your PC.
3. Launch `vgamepad.exe` to open the control panel.

## How to Use

### Recording Keybindings
- **Short Press:** Click the "Record" button next to any action, then press your desired keyboard key or mouse button to bind it.
- **Long Press (≥ 1 second):** Click and hold the "Record" button to completely clear the current input binding.

### Switching Profile Contexts
Use the profile keys to switch between **Soldier**, **Vehicle**, and **Plane** contexts. The UI dynamically destroys and rebuilds the macro rows and settings on the fly, loading the precise configuration stored for that specific profile without requiring an application restart.

**Project implemented using AI**

### My Discord channel
https://discord.gg/k7WNAnPtsZ
