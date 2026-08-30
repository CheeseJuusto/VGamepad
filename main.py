import threading
import sys
import vgamepad as vg
from config import cfg
import mapper
from raw_input import RawInputWindow
from ui import App


def main():
    # Alustetaan vgamepad-ohjain
    try:
        mapper.gamepad = vg.VX360Gamepad()
    except Exception as e:
        print(f"Failed to initialize ViGEmBus gamepad: {e}")

    # Käynnistetään päivityssilmukka taustasäikeessä
    update_thread = threading.Thread(target=mapper.update_loop, daemon=True)
    update_thread.start()

    # Käynnistetään Raw Input -ikkuna taustasäikeessä
    raw_input_win = RawInputWindow()
    raw_thread = threading.Thread(target=raw_input_win.start, daemon=True)
    raw_thread.start()

    # Käynnistetään Tkinter GUI pääsäikeessä
    app = App()

    # Ajetaan päivitystarkistus vasta kun käyttöliittymä on käynnistynyt (1 sekunnin viiveellä)
    app.after(1000, lambda: threading.Thread(target=app.check_update, kwargs={"silent": True}, daemon=True).start())

    def on_closing():
        mapper.running = False
        app.destroy()
        sys.exit(0)

    app.protocol("WM_DELETE_WINDOW", on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()