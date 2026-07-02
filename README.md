# vgamepad Configurator

A lightweight, high-performance Python and Tkinter-based GUI utility to map Keyboard and Mouse inputs into a virtual Xbox 360 controller. Built specifically for games or emulators (like RPCS3) where native mouse-look or customized keyboard binds need to be seamlessly translated into controller axes and buttons.

Version: v0.1

## Features

- **Keyboard Mapping:** Map any standard keyboard key or mouse click directly to Xbox 360 controller buttons (A, B, X, Y, Triggers, D-pad, etc.).
- **Dynamic Custom Inputs:** Create, name, and describe up to 20 custom key combinations/alternate binds per profile.
- **Advanced Mouse-to-Joystick Translation:**
  - Separate X and Y sensitivity sliders.
  - Hardware/Software deadzone adjustments.
  - Linearity (Gamma curve) controls for fine-tuning smooth mouse-look.
  - Invert Y-axis toggle.
  - Identical delta behavior whether the mouse is locked to the center or free.
- **Mouse Lock Toggle:** Lock the mouse cursor using a global hotkey (`F5`) to enable full 360-degree camera control in-game.
- **Left Stick Limiter:** Bind a modifier key (e.g., `Left Ctrl`) to scale down left stick movement speed, useful for walking vs. running. Supports both hold and toggle modes.
- **Profile Management:** Fully working Save and Load features that write directly to a local `config.json` file.
- **Integrated Game Launcher:** Specify your game's executable path and arguments (e.g., RPCS3 CLI commands) to launch directly from the GUI.

## Prerequisites

Before running or building the application, ensure your system has the following requirements installed:

1. **Windows OS** (64-bit recommended)
2. **ViGEmBus Driver:** The application relies on the Virtual Gamepad Emulation Bus. Download and install the latest release from the official repository or vendor installer.
  https://github.com/nefarius/ViGEmBus/releases#release-v1.22.0
