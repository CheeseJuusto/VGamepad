import ctypes
from ctypes import wintypes
from utils import user32, normalize_vk_code
import mapper

user32 = ctypes.windll.user32

# Määritetään CreateWindowExW:n paluutyyppi ja argumenttityypit
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,     # dwExStyle
    wintypes.LPCWSTR,   # lpClassName
    wintypes.LPCWSTR,   # lpWindowName
    wintypes.DWORD,     # dwStyle
    ctypes.c_int,       # x
    ctypes.c_int,       # y
    ctypes.c_int,       # nWidth
    ctypes.c_int,       # nHeight
    wintypes.HWND,      # hWndParent
    wintypes.HMENU,     # hMenu
    wintypes.HINSTANCE, # hInstance
    wintypes.LPVOID     # lpParam (Argumentti 11)
]

WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100

RI_MOUSE_LEFT_BUTTON_DOWN   = 0x0001
RI_MOUSE_LEFT_BUTTON_UP     = 0x0002
RI_MOUSE_RIGHT_BUTTON_DOWN  = 0x0004
RI_MOUSE_RIGHT_BUTTON_UP    = 0x0008
RI_MOUSE_MIDDLE_BUTTON_DOWN = 0x0010
RI_MOUSE_MIDDLE_BUTTON_UP   = 0x0020
RI_MOUSE_BUTTON_4_DOWN      = 0x0040
RI_MOUSE_BUTTON_4_UP        = 0x0080
RI_MOUSE_BUTTON_5_DOWN      = 0x0100
RI_MOUSE_BUTTON_5_UP        = 0x0200
RI_MOUSE_WHEEL              = 0x0400

RI_KEY_BREAK = 0x01
RI_KEY_E0    = 0x02


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWMOUSE(ctypes.Structure):
    class _U1(ctypes.Union):
        class _S1(ctypes.Structure):
            _fields_ = [
                ("usButtonFlags", wintypes.WORD),
                ("usButtonData", wintypes.WORD),
            ]
        _fields_ = [
            ("ulButtons", wintypes.ULONG),
            ("s1", _S1),
        ]
    _fields_ = [
        ("usFlags", wintypes.WORD),
        ("u1", _U1),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.WORD),
        ("Flags", wintypes.WORD),
        ("Reserved", wintypes.WORD),
        ("VKey", wintypes.WORD),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [
            ("mouse", RAWMOUSE),
            ("keyboard", RAWKEYBOARD),
        ]
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("u", _U),
    ]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RawInputWindow:
    def __init__(self):
        self.hwnd = None

    def start(self):
        kernel32 = ctypes.windll.kernel32

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM
        )

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                dw_size = wintypes.DWORD()
                user32.GetRawInputData(wintypes.HANDLE(lparam), RID_INPUT, None, ctypes.byref(dw_size), ctypes.sizeof(RAWINPUTHEADER))
                if dw_size.value > 0:
                    raw_buf = ctypes.create_string_buffer(dw_size.value)
                    if user32.GetRawInputData(wintypes.HANDLE(lparam), RID_INPUT, raw_buf, ctypes.byref(dw_size), ctypes.sizeof(RAWINPUTHEADER)) == dw_size.value:
                        raw = ctypes.cast(raw_buf, ctypes.POINTER(RAWINPUT)).contents
                        if raw.header.dwType == 0:
                            self.process_raw_mouse(raw.u.mouse)
                        elif raw.header.dwType == 1:
                            self.process_raw_keyboard(raw.u.keyboard)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self.wnd_proc_cb = WNDPROC(wnd_proc)
        if not hasattr(ctypes.wintypes, 'HCURSOR'):
            ctypes.wintypes.HCURSOR = ctypes.wintypes.HANDLE

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ('style', ctypes.c_uint),
                ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int),
                ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HICON),
                ('hCursor', wintypes.HANDLE),
                ('hbrBackground', wintypes.HBRUSH),
                ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR)
            ]

        wndclass = WNDCLASSW()
        wndclass.lpszClassName = "RawInputClass"
        wndclass.lpfnWndProc = self.wnd_proc_cb
        wndclass.hInstance = kernel32.GetModuleHandleW(None)

        user32.RegisterClassW(ctypes.byref(wndclass))

        self.hwnd = user32.CreateWindowExW(
            0, "RawInputClass", "RawInputWindow",
            0, 0, 0, 0, 0,
            0, 0, wndclass.hInstance, None
        )

        devices = (RAWINPUTDEVICE * 2)()
        devices[0].usUsagePage = 0x01
        devices[0].usUsage = 0x02
        devices[0].dwFlags = RIDEV_INPUTSINK
        devices[0].hwndTarget = self.hwnd

        devices[1].usUsagePage = 0x01
        devices[1].usUsage = 0x06
        devices[1].dwFlags = RIDEV_INPUTSINK
        devices[1].hwndTarget = self.hwnd

        user32.RegisterRawInputDevices(ctypes.byref(devices), 2, ctypes.sizeof(RAWINPUTDEVICE))

        msg = wintypes.MSG()
        while mapper.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def process_raw_mouse(self, mouse_data):
        if not mapper.cfg.get("emulation_enabled", True) and not mapper.recording_target:
            return

        dx = mouse_data.lLastX
        dy = mouse_data.lLastY
        if dx != 0 or dy != 0:
            mapper.mouse_dx_queue.append(dx)
            mapper.mouse_dy_queue.append(dy)

        flags = mouse_data.u1.s1.usButtonFlags

        if flags & RI_MOUSE_LEFT_BUTTON_DOWN: mapper.on_click(0, 0, "mouse1", True)
        if flags & RI_MOUSE_LEFT_BUTTON_UP: mapper.on_click(0, 0, "mouse1", False)

        if flags & RI_MOUSE_RIGHT_BUTTON_DOWN: mapper.on_click(0, 0, "mouse2", True)
        if flags & RI_MOUSE_RIGHT_BUTTON_UP: mapper.on_click(0, 0, "mouse2", False)

        if flags & RI_MOUSE_MIDDLE_BUTTON_DOWN: mapper.on_click(0, 0, "mouse3", True)
        if flags & RI_MOUSE_MIDDLE_BUTTON_UP: mapper.on_click(0, 0, "mouse3", False)

        if flags & RI_MOUSE_BUTTON_4_DOWN: mapper.on_click(0, 0, "mouse4", True)
        if flags & RI_MOUSE_BUTTON_4_UP: mapper.on_click(0, 0, "mouse4", False)

        if flags & RI_MOUSE_BUTTON_5_DOWN: mapper.on_click(0, 0, "mouse5", True)
        if flags & RI_MOUSE_BUTTON_5_UP: mapper.on_click(0, 0, "mouse5", False)

        if flags & RI_MOUSE_WHEEL:
            wheel_delta = ctypes.c_short(mouse_data.u1.s1.usButtonData).value
            if wheel_delta > 0:
                mapper.on_scroll(0, 0, 0, 1)
            elif wheel_delta < 0:
                mapper.on_scroll(0, 0, 0, -1)

    def process_raw_keyboard(self, kb_data):
        vk = kb_data.VKey
        if vk == 0 or vk == 0xFF:
            return

        flags = kb_data.Flags
        is_up = bool(flags & RI_KEY_BREAK)
        is_e0 = bool(flags & RI_KEY_E0)

        key_name = normalize_vk_code(vk, is_e0)

        if is_up:
            mapper.physically_pressed_keys.discard(key_name)
            mapper.on_key_release_raw(key_name)
        else:
            mapper.physically_pressed_keys.add(key_name)
            mapper.on_key_press_raw(key_name)