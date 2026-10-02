# -*- coding: utf-8 -*-
"""
PlainPaste —— Windows 纯文本粘贴小工具
================================================

功能：
  * 常驻后台（系统托盘），占用极低。
  * 在任何程序里按下 Ctrl+Shift+V，把剪贴板内容"去掉所有格式"
    （字体 / 颜色 / 字号 / 超链接 / 表格样式等），只保留纯文本和换行，
    然后自动粘贴到当前光标处。
  * 可选：Ctrl+Shift+C 复制时就转成纯文本。

技术要点：
  * 纯 ctypes 调用 Win32 API，零第三方依赖。
  * RegisterHotKey 注册全局热键（会拦截应用自身的同名快捷键）。
  * 剪贴板写入 CF_UNICODETEXT，格式信息天然被剥离。
  * SendInput 模拟 Ctrl+V，先释放修饰键避免冲突。
  * Shell_NotifyIcon 实现托盘图标与右键菜单。
  * 不需要管理员权限（HKCU 注册表项 + 用户态 API）。

作者：WorkBuddy AI
"""

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time
import traceback

try:
    import latex2text
except Exception:          # 模块缺失时优雅降级，不影响纯文本粘贴主功能
    latex2text = None

try:
    import image_codec
    import clipboard_history
except Exception:          # 图片/历史模块缺失时，仅关闭对应功能
    image_codec = None
    clipboard_history = None

# ============================================================ 基本常量

APP_NAME = "PlainPaste"
APP_TITLE = "纯文本粘贴"

IS_FROZEN = getattr(sys, "frozen", False)
if IS_FROZEN:
    # 打包成 exe 后：配置文件放在 exe 旁边（用户可编辑），
    # 图标等只读资源由 PyInstaller 解压到临时目录 _MEIPASS。
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = BASE_DIR
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "plainpaste.log")

DEFAULT_CONFIG = {
    "hotkey": "ctrl+shift+v",          # 纯文本粘贴热键
    "copy_hotkey": "ctrl+shift+c",     # 复制即转纯文本的热键
    "enable_copy_plain": False,        # 是否启用"复制即转纯文本"
    "latex_to_text": "auto",           # LaTeX 公式转换：auto / always / off
    "paste_delay_ms": 30,              # 发送 Ctrl+V 前的等待毫秒数
    "trim_whitespace": False,          # 是否去掉首尾空白
    "debug": False,                    # 是否写详细日志

    # ---- 剪贴板历史 ----
    "history_enabled": True,           # 是否自动记录复制内容
    "history_prefix": "alt+shift",     # 历史粘贴的修饰键（+1~9、+0 取第 1~10 条）
    "history_days": 7,                 # 超过多少天的记录自动清理
    "history_max_entries": 200,        # 最多保留多少条
    "history_max_text_kb": 512,        # 单条文本上限（KB）
    "history_max_image_mb": 10,        # 单张图片上限（MB）
    "history_max_total_mb": 200,       # 历史目录总容量上限（MB）
}

# LaTeX 转换模式的显示名
LATEX_MODE_LABELS = {"auto": "自动识别", "always": "总是转换", "off": "已关闭"}
LATEX_MODE_ORDER = ["auto", "always", "off"]

# ---- 窗口消息
WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_HOTKEY = 0x0312
WM_CLIPBOARDUPDATE = 0x031D
WM_NULL = 0x0000
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1

# ---- 托盘
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
NIIF_INFO = 0x01

# ---- 菜单
MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
MF_CHECKED = 0x0008
MF_DISABLED = 0x0002
MF_GRAYED = 0x0001
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100

# ---- 热键修饰符
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# ---- 键盘输入
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
VK_LWIN, VK_RWIN, VK_V, VK_C = 0x5B, 0x5C, 0x56, 0x43

# ---- 剪贴板
CF_UNICODETEXT = 13
CF_HDROP = 15          # 复制的"文件"，按要求不记录
GMEM_MOVEABLE = 0x0002

# ---- MessageBox
MB_OK = 0x00000000
MB_YESNO = 0x00000004
MB_ICONINFORMATION = 0x00000040
MB_ICONQUESTION = 0x00000020
MB_ICONWARNING = 0x00000030
MB_ICONERROR = 0x00000010
MB_TOPMOST = 0x00040000
IDYES = 6

# ---- 菜单命令 ID
ID_TOGGLE_ENABLED = 1
ID_TOGGLE_COPY_PLAIN = 2
ID_TOGGLE_AUTOSTART = 3
ID_OPEN_CONFIG = 4
ID_ABOUT = 5
ID_EXIT = 6
ID_TOGGLE_LATEX = 7
ID_TOGGLE_HISTORY = 8
ID_OPEN_HISTORY = 9
ID_CLEAR_HISTORY = 10
ID_HISTORY_HELP = 11

# ---- 热键 ID 分配
HOTKEY_PASTE = 1
HOTKEY_COPY_PLAIN = 2
HOTKEY_HISTORY_BASE = 100       # 100+1 .. 100+10 对应历史第 1~10 条

IDI_APPLICATION = 32512

# ============================================================ Win32 绑定

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
LRESULT = ctypes.c_ssize_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG), ("dy", wt.LONG),
        ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
        ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HANDLE),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD),
        ("Data4", ctypes.c_byte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD),
        ("dwStateMask", wt.DWORD),
        ("szInfo", wt.WCHAR * 256),
        ("uVersion", wt.UINT),
        ("szInfoTitle", wt.WCHAR * 64),
        ("dwInfoFlags", wt.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wt.HICON),
    ]


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

# ---- 函数签名（64 位下必须显式声明，否则指针会被截断）
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT

user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wt.WORD

user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wt.HWND

user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostQuitMessage.argtypes = [ctypes.c_int]

user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.RegisterHotKey.restype = wt.BOOL
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wt.BOOL

user32.AddClipboardFormatListener.argtypes = [wt.HWND]
user32.AddClipboardFormatListener.restype = wt.BOOL
user32.RemoveClipboardFormatListener.argtypes = [wt.HWND]
user32.RemoveClipboardFormatListener.restype = wt.BOOL

user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
user32.RegisterWindowMessageW.restype = wt.UINT

user32.LoadIconW.argtypes = [wt.HINSTANCE, wt.LPCWSTR]
user32.LoadIconW.restype = wt.HICON
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int,
                              ctypes.c_int, wt.UINT]
user32.LoadImageW.restype = wt.HANDLE

user32.CreatePopupMenu.restype = wt.HMENU
user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
user32.AppendMenuW.restype = wt.BOOL
user32.TrackPopupMenu.argtypes = [
    wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, ctypes.c_void_p,
]
user32.TrackPopupMenu.restype = wt.UINT
user32.DestroyMenu.argtypes = [wt.HMENU]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.MessageBoxW.argtypes = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT]
user32.MessageBoxW.restype = ctypes.c_int
user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wt.UINT

user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL
user32.CloseClipboard.restype = wt.BOOL
user32.EmptyClipboard.restype = wt.BOOL
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wt.UINT]
user32.IsClipboardFormatAvailable.restype = wt.BOOL

kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HINSTANCE
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HANDLE
kernel32.GlobalLock.argtypes = [wt.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HANDLE]
kernel32.GlobalUnlock.restype = wt.BOOL
kernel32.GlobalFree.argtypes = [wt.HANDLE]
kernel32.GlobalFree.restype = wt.HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
kernel32.CreateMutexW.restype = wt.HANDLE

shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wt.BOOL

# ============================================================ 小工具函数


def log(msg):
    """写日志（仅 debug 模式或出错时）。"""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def dlog(msg):
    if CONFIG.get("debug"):
        log(msg)


def show_message(text, title=APP_TITLE, flags=MB_OK | MB_ICONINFORMATION | MB_TOPMOST):
    user32.MessageBoxW(None, text, title, flags)


# ============================================================ 配置

CONFIG = dict(DEFAULT_CONFIG)


def load_config():
    """读取配置；文件不存在或缺少新增项时，自动补齐并写回。"""
    global CONFIG
    need_save = False
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k in data:
                    CONFIG[k] = data[k]
                else:
                    need_save = True      # 老版本配置缺少新项，稍后补写
        except Exception as e:
            log("读取配置失败，使用默认值: %r" % (e,))
    else:
        need_save = True
    if need_save:
        save_config()
    return CONFIG


# ============================================================ 热键解析

VK_SPECIAL = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
    "esc": 0x1B, "escape": 0x1B, "space": 0x20,
    "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "insert": 0x2D, "delete": 0x2E, "del": 0x2E,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}
VK_NAMES = {v: k for k, v in VK_SPECIAL.items()}
VK_NAMES.update({
    0x0D: "Enter", 0x1B: "Esc", 0x20: "Space",
    0x21: "PageUp", 0x22: "PageDown", 0x23: "End", 0x24: "Home",
    0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2D: "Insert", 0x2E: "Delete",
})


def parse_hotkey(spec):
    """'ctrl+shift+v' -> (modifiers, vk)。解析失败抛 ValueError。"""
    mods = MOD_NOREPEAT
    vk = None
    for part in str(spec).lower().replace(" ", "").split("+"):
        if not part:
            continue
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part == "alt":
            mods |= MOD_ALT
        elif part in ("win", "super", "meta"):
            mods |= MOD_WIN
        elif len(part) == 1 and part.isalpha():
            vk = ord(part.upper())
        elif len(part) == 1 and part.isdigit():
            vk = ord(part)
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x70 + int(part[1:]) - 1
        elif part in VK_SPECIAL:
            vk = VK_SPECIAL[part]
        else:
            raise ValueError("无法识别的按键: %s" % part)
    if vk is None:
        raise ValueError("热键缺少主按键: %s" % spec)
    if not (mods & (MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_WIN)):
        raise ValueError("热键必须包含 Ctrl / Alt / Shift / Win 中的至少一个: %s" % spec)
    return mods, vk


def parse_modifier_prefix(spec):
    """解析 'alt+shift' 这类**纯修饰键**前缀 -> 修饰符位掩码。"""
    mods = MOD_NOREPEAT
    for part in str(spec).lower().replace(" ", "").split("+"):
        if not part:
            continue
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part == "alt":
            mods |= MOD_ALT
        elif part in ("win", "super", "meta"):
            mods |= MOD_WIN
        else:
            raise ValueError("无法识别的修饰键: %s" % part)
    if not (mods & (MOD_CONTROL | MOD_ALT | MOD_SHIFT | MOD_WIN)):
        raise ValueError("修饰键前缀必须至少包含一个修饰键: %s" % spec)
    return mods


def modifier_prefix_display(spec):
    try:
        mods = parse_modifier_prefix(spec)
    except ValueError:
        return str(spec)
    parts = []
    if mods & MOD_CONTROL:
        parts.append("Ctrl")
    if mods & MOD_ALT:
        parts.append("Alt")
    if mods & MOD_SHIFT:
        parts.append("Shift")
    if mods & MOD_WIN:
        parts.append("Win")
    return "+".join(parts)


def hotkey_display(spec):
    """'ctrl+shift+v' -> 'Ctrl+Shift+V'"""
    try:
        mods, vk = parse_hotkey(spec)
    except ValueError:
        return str(spec)
    parts = []
    if mods & MOD_CONTROL:
        parts.append("Ctrl")
    if mods & MOD_SHIFT:
        parts.append("Shift")
    if mods & MOD_ALT:
        parts.append("Alt")
    if mods & MOD_WIN:
        parts.append("Win")
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        parts.append(chr(vk))
    elif 0x70 <= vk <= 0x87:
        parts.append("F%d" % (vk - 0x70 + 1))
    else:
        parts.append(VK_NAMES.get(vk, "0x%02X" % vk))
    return "+".join(parts)


# ============================================================ 剪贴板

def get_clipboard_text():
    """读取剪贴板纯文本；没有文本返回 None。"""
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return None
    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.c_wchar_p(ptr).value
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text):
    """把纯文本写入剪贴板（覆盖全部格式）。成功返回 True。"""
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        log("打开剪贴板失败")
        return False
    try:
        if not user32.EmptyClipboard():
            return False
        data = text.encode("utf-16-le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True  # 内存所有权已移交系统，不可再释放
    finally:
        user32.CloseClipboard()


def normalize_text(text):
    """统一换行为 CRLF，可选去除首尾空白。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if CONFIG.get("trim_whitespace"):
        text = text.strip()
    return text.replace("\n", "\r\n")


def transform_text(text):
    """内容层转换：把 LaTeX 公式（\\frac{a}{b}、$x^2$、\\alpha 等）转成普通文本与 Unicode 符号。"""
    mode = CONFIG.get("latex_to_text", "auto")
    if mode == "off" or latex2text is None:
        return text
    try:
        converted = latex2text.convert(text, mode)
        if converted != text:
            dlog("LaTeX 转换: %d 字符 -> %d 字符" % (len(text), len(converted)))
        return converted
    except Exception:
        log("LaTeX 转换失败，按原文粘贴:\n" + traceback.format_exc())
        return text


# ============================================================ 模拟按键

def _key_event(vk, keyup=False):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki = KEYBDINPUT(
        wVk=vk, wScan=0,
        dwFlags=(KEYEVENTF_KEYUP if keyup else 0),
        time=0, dwExtraInfo=0,
    )
    return inp


def send_paste():
    """释放修饰键后模拟 Ctrl+V。"""
    seq = [
        # 先确保 Ctrl / Shift / Alt / Win 处于抬起状态，避免热键残留修饰键
        _key_event(VK_CONTROL, True),
        _key_event(VK_SHIFT, True),
        _key_event(VK_MENU, True),
        _key_event(VK_LWIN, True),
        _key_event(VK_RWIN, True),
    ]
    delay = max(0, int(CONFIG.get("paste_delay_ms", 30))) / 1000.0
    if delay:
        time.sleep(delay)
    seq += [
        _key_event(VK_CONTROL, False),
        _key_event(VK_V, False),
        _key_event(VK_V, True),
        _key_event(VK_CONTROL, True),
    ]
    arr = (INPUT * len(seq))(*seq)
    sent = user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
    if sent != len(seq):
        log("SendInput 未完全发送: %d/%d, err=%d" % (sent, len(seq), ctypes.get_last_error()))


# ============================================================ 开机自启

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_launch_command():
    if IS_FROZEN:
        return '"%s"' % os.path.abspath(sys.executable)
    pythonw = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    return '"%s" "%s"' % (pythonw, os.path.abspath(__file__))


def is_autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except Exception:
        return False


def set_autostart(enable):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_launch_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        log("设置开机启动失败: %r" % (e,))
        return False


# ============================================================ 主程序

class PlainPasteApp(object):

    def __init__(self):
        self.hwnd = None
        self.hicon = None
        self.wndproc_ref = None
        self.class_name = "PlainPasteHiddenWindow"
        self.tray_added = False
        self.enabled = True
        self.wm_taskbar_created = 0
        self.registered = set()
        self.paste_spec = CONFIG["hotkey"]
        self.copy_spec = CONFIG["copy_hotkey"]
        self.nid = NOTIFYICONDATAW()
        self._self_write_until = 0.0     # 抑制窗口：自身写剪贴板时不重复记录
        self.listening = False
        self.history = None
        if clipboard_history is not None:
            self.history = clipboard_history.HistoryManager(BASE_DIR, CONFIG)

    # ---------------- 窗口

    def _register_window_class(self):
        hinst = kernel32.GetModuleHandleW(None)
        self.wndproc_ref = WNDPROC(self._wnd_proc)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(self.wndproc_ref, ctypes.c_void_p)
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = hinst
        wc.hIcon = self.hicon
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = self.class_name
        wc.hIconSm = self.hicon
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                raise OSError("RegisterClassExW 失败, err=%d" % err)

    def _create_window(self):
        hinst = kernel32.GetModuleHandleW(None)
        self.hwnd = user32.CreateWindowExW(
            0, self.class_name, APP_TITLE, 0,
            0, 0, 0, 0,
            None, None, hinst, None,
        )
        if not self.hwnd:
            raise OSError("CreateWindowExW 失败, err=%d" % ctypes.get_last_error())

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_HOTKEY:
                if wparam == HOTKEY_PASTE:
                    self.do_plain_paste()
                elif wparam == HOTKEY_COPY_PLAIN:
                    self.do_plain_copy()
                elif wparam > HOTKEY_HISTORY_BASE:
                    self.paste_history(wparam - HOTKEY_HISTORY_BASE)
                return 0

            if msg == WM_CLIPBOARDUPDATE:
                self.on_clipboard_update()
                return 0

            if msg == WM_TRAYICON:
                if lparam == WM_RBUTTONUP:
                    self.show_menu()
                elif lparam == WM_LBUTTONDBLCLK:
                    self.enabled = not self.enabled
                    self.update_tip()
                return 0

            if msg == self.wm_taskbar_created and self.wm_taskbar_created:
                # 资源管理器重启后重建托盘图标
                self.tray_added = False
                self.add_tray_icon()
                return 0

            if msg == WM_COMMAND:
                self.on_menu(wparam & 0xFFFF)
                return 0

            if msg == WM_DESTROY:
                self.shutdown()
                user32.PostQuitMessage(0)
                return 0
        except Exception:
            log("窗口过程异常:\n" + traceback.format_exc())
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # ---------------- 托盘

    def add_tray_icon(self):
        nid = self.nid
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self.hicon
        nid.szTip = "%s —— 按 %s 粘贴纯文本" % (APP_TITLE, hotkey_display(self.paste_spec))
        if shell32.Shell_NotifyIconW(NIM_ADD if not self.tray_added else NIM_MODIFY,
                                     ctypes.byref(nid)):
            self.tray_added = True
        else:
            log("添加托盘图标失败, err=%d" % ctypes.get_last_error())

    def update_tip(self):
        if not self.tray_added:
            return
        tip = "%s%s —— %s 粘贴纯文本" % (
            APP_TITLE, "" if self.enabled else "（已暂停）",
            hotkey_display(self.paste_spec),
        )
        self.nid.szTip = tip[:127]
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self.nid))

    def remove_tray_icon(self):
        if self.tray_added:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self.nid))
            self.tray_added = False

    def balloon(self, text, title=APP_TITLE):
        if not self.tray_added:
            return
        nid = self.nid
        nid.uFlags = NIF_INFO
        nid.szInfo = text[:255]
        nid.szInfoTitle = title[:63]
        nid.dwInfoFlags = NIIF_INFO
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    # ---------------- 菜单

    def show_menu(self):
        hmenu = user32.CreatePopupMenu()
        if not hmenu:
            return
        try:
            user32.AppendMenuW(
                hmenu, MF_STRING | MF_DISABLED | MF_GRAYED, 0,
                "纯文本粘贴   %s" % hotkey_display(self.paste_spec))
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(
                hmenu, MF_STRING | (MF_CHECKED if self.enabled else 0),
                ID_TOGGLE_ENABLED, "启用快捷键")
            user32.AppendMenuW(
                hmenu, MF_STRING | (MF_CHECKED if CONFIG.get("enable_copy_plain") else 0),
                ID_TOGGLE_COPY_PLAIN,
                "复制即转纯文本   %s" % hotkey_display(self.copy_spec))
            latex_mode = CONFIG.get("latex_to_text", "auto")
            user32.AppendMenuW(
                hmenu, MF_STRING | (MF_CHECKED if latex_mode != "off" else 0),
                ID_TOGGLE_LATEX,
                "LaTeX 公式转普通文本（%s）"
                % LATEX_MODE_LABELS.get(latex_mode, latex_mode))
            user32.AppendMenuW(
                hmenu, MF_STRING | (MF_CHECKED if is_autostart_enabled() else 0),
                ID_TOGGLE_AUTOSTART, "开机自动启动")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

            # ---- 剪贴板历史 ----
            hist_on = CONFIG.get("history_enabled", True)
            user32.AppendMenuW(
                hmenu, MF_STRING | (MF_CHECKED if hist_on else 0),
                ID_TOGGLE_HISTORY, "记录剪贴板历史")
            cnt = self.history.count() if self.history else 0
            prefix_disp = modifier_prefix_display(
                CONFIG.get("history_prefix", "alt+shift"))
            user32.AppendMenuW(
                hmenu, MF_STRING | MF_DISABLED | MF_GRAYED, 0,
                "  %s+1 最新 / +2 次新…（现有 %d 条）" % (prefix_disp, cnt))
            user32.AppendMenuW(hmenu, MF_STRING, ID_OPEN_HISTORY, "打开历史文件夹")
            user32.AppendMenuW(hmenu, MF_STRING, ID_CLEAR_HISTORY, "清空历史记录")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)

            user32.AppendMenuW(hmenu, MF_STRING, ID_OPEN_CONFIG, "打开配置文件")
            user32.AppendMenuW(hmenu, MF_STRING, ID_ABOUT, "使用说明")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, ID_EXIT, "退出")

            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(self.hwnd)
            cmd = user32.TrackPopupMenu(
                hmenu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                pt.x, pt.y, 0, self.hwnd, None)
            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(hmenu)
        if cmd:
            self.on_menu(cmd)

    def on_menu(self, cmd):
        if cmd == ID_TOGGLE_ENABLED:
            self.enabled = not self.enabled
            self.update_tip()
        elif cmd == ID_TOGGLE_COPY_PLAIN:
            CONFIG["enable_copy_plain"] = not CONFIG.get("enable_copy_plain")
            save_config()
            self.register_hotkeys()
        elif cmd == ID_TOGGLE_LATEX:
            cur = CONFIG.get("latex_to_text", "auto")
            idx = LATEX_MODE_ORDER.index(cur) if cur in LATEX_MODE_ORDER else 0
            CONFIG["latex_to_text"] = LATEX_MODE_ORDER[(idx + 1) % len(LATEX_MODE_ORDER)]
            save_config()
            dlog("LaTeX 转换模式切换为 %s" % CONFIG["latex_to_text"])
        elif cmd == ID_TOGGLE_HISTORY:
            CONFIG["history_enabled"] = not CONFIG.get("history_enabled", True)
            save_config()
            self.register_hotkeys()
        elif cmd == ID_OPEN_HISTORY:
            if self.history:
                try:
                    os.startfile(self.history.dir)
                except Exception as e:
                    show_message("无法打开历史文件夹：%r" % (e,))
        elif cmd == ID_CLEAR_HISTORY:
            if self.history and self.history.count() > 0:
                r = user32.MessageBoxW(
                    None,
                    "确定清空全部剪贴板历史吗？\n（包括已保存的图片文件，不可恢复）",
                    APP_TITLE, MB_YESNO | MB_ICONQUESTION | MB_TOPMOST)
                if r == IDYES:
                    n = self.history.clear()
                    dlog("已清空 %d 条历史" % n)
        elif cmd == ID_TOGGLE_AUTOSTART:
            want = not is_autostart_enabled()
            if not set_autostart(want):
                show_message("设置开机启动失败，可能是注册表权限受限。",
                             flags=MB_OK | MB_ICONWARNING | MB_TOPMOST)
        elif cmd == ID_OPEN_CONFIG:
            try:
                os.startfile(CONFIG_PATH)
            except Exception as e:
                show_message("无法打开配置文件：%r" % (e,))
        elif cmd == ID_ABOUT:
            latex_mode = CONFIG.get("latex_to_text", "auto")
            prefix_disp = modifier_prefix_display(
                CONFIG.get("history_prefix", "alt+shift"))
            cnt = self.history.count() if self.history else 0
            show_message(
                "PlainPaste —— 纯文本粘贴工具\n"
                "\n"
                "【纯文本粘贴】\n"
                "· 按 " + hotkey_display(self.paste_spec) + " ：\n"
                "  自动去掉字体、颜色、超链接等格式，只粘贴纯文本和换行。\n"
                "\n"
                "【LaTeX 公式自动转换】\n"
                "  \\frac{a}{b} → a/b      x^2 → x²      \\alpha → α\n"
                "  当前模式：" + LATEX_MODE_LABELS.get(latex_mode, latex_mode) + "\n"
                "\n"
                "【剪贴板历史】\n"
                "· 复制的内容会自动记录（文本存一个文件，图片存文件夹）\n"
                "· 按 " + prefix_disp + "+1 粘贴最新一条\n"
                "  按 " + prefix_disp + "+2 粘贴倒数第二条，以此类推（+0 为第 10 条）\n"
                "· 当前已有 " + str(cnt) + " 条记录\n"
                "· 超过 " + str(CONFIG.get("history_days", 7)) + " 天自动清理\n"
                "\n"
                "【其他】\n"
                "· 左键双击托盘图标：临时启用 / 暂停。\n"
                "· 右键托盘图标：更多设置。\n"
                "· 修改热键：编辑 config.json 后重启本程序。\n"
                "\n"
                "提示：若目标程序以管理员身份运行，本工具也需以管理员身份运行。"
            )
        elif cmd == ID_EXIT:
            self.shutdown()
            user32.PostQuitMessage(0)

    # ---------------- 热键

    def register_hotkeys(self):
        for hid in list(self.registered):
            user32.UnregisterHotKey(self.hwnd, hid)
        self.registered.clear()

        failures = []
        try:
            mods, vk = parse_hotkey(self.paste_spec)
            if user32.RegisterHotKey(self.hwnd, HOTKEY_PASTE, mods, vk):
                self.registered.add(HOTKEY_PASTE)
            else:
                failures.append((hotkey_display(self.paste_spec), ctypes.get_last_error()))
        except ValueError as e:
            failures.append((str(e), -1))

        if CONFIG.get("enable_copy_plain"):
            try:
                mods, vk = parse_hotkey(self.copy_spec)
                if user32.RegisterHotKey(self.hwnd, HOTKEY_COPY_PLAIN, mods, vk):
                    self.registered.add(HOTKEY_COPY_PLAIN)
                else:
                    failures.append((hotkey_display(self.copy_spec), ctypes.get_last_error()))
            except ValueError as e:
                failures.append((str(e), -1))

        # 历史粘贴热键：冲突时只记日志，不打扰用户
        self.register_history_hotkeys()

        if failures:
            detail = "\n".join(
                "  · %s（错误码 %s）" % (name, err) for name, err in failures)
            log("热键注册失败:\n" + detail)
            show_message(
                "以下热键注册失败：\n%s\n\n"
                "常见原因：该组合键已被其他程序全局占用，或格式写错。\n"
                "请编辑 config.json 里的 hotkey 换成别的组合后重启本程序。"
                % detail,
                flags=MB_OK | MB_ICONWARNING | MB_TOPMOST)

    def register_history_hotkeys(self):
        """注册 历史前缀+1~9 / +0 共 10 个热键（对应第 1~10 条）。"""
        if self.history is None or not CONFIG.get("history_enabled", True):
            return
        prefix = CONFIG.get("history_prefix", "alt+shift")
        try:
            mods = parse_modifier_prefix(prefix)
        except ValueError as e:
            log("历史粘贴修饰键无效，已跳过: %s" % e)
            return
        ok = 0
        for n in range(1, 11):
            vk = ord("0") if n == 10 else ord(str(n))
            if user32.RegisterHotKey(self.hwnd, HOTKEY_HISTORY_BASE + n, mods, vk):
                self.registered.add(HOTKEY_HISTORY_BASE + n)
                ok += 1
        dlog("历史粘贴热键注册 %d/10 个（前缀 %s）" % (ok, prefix))
        if ok == 0:
            log("历史粘贴热键一个都没注册成功，可能是前缀 %s 被占用" % prefix)

    # ---------------- 核心动作

    def _mark_self_write(self):
        """标记"接下来 1 秒内是自己写剪贴板"，避免被历史重复记录。"""
        self._self_write_until = time.time() + 1.0

    def do_plain_paste(self):
        if not self.enabled:
            return
        text = get_clipboard_text()
        if text is None:
            # 剪贴板里不是文本（例如图片），保持原生粘贴行为
            send_paste()
            return
        # 先做内容转换（LaTeX -> 普通符号），再统一换行符
        new_text = normalize_text(transform_text(text))
        self._mark_self_write()
        if not set_clipboard_text(new_text):
            log("写入剪贴板失败，改为直接粘贴")
        send_paste()
        dlog("已粘贴纯文本 %d 字符" % len(new_text))

    def do_plain_copy(self):
        if not self.enabled or not CONFIG.get("enable_copy_plain"):
            return
        text = get_clipboard_text()
        if text is None:
            return
        self._mark_self_write()
        set_clipboard_text(normalize_text(transform_text(text)))

    # ---------------- 剪贴板历史

    def on_clipboard_update(self):
        """剪贴板内容变化时自动记录历史。"""
        if self.history is None or not CONFIG.get("history_enabled", True):
            return
        if time.time() < self._self_write_until:
            self._self_write_until = 0.0      # 自己写入的，不重复记录
            return
        try:
            # 复制的"文件"不记录（用户明确要求）
            if user32.IsClipboardFormatAvailable(CF_HDROP):
                dlog("剪贴板是文件，跳过记录")
                return
            # 图片优先于文本
            if image_codec is not None and image_codec.clipboard_has_image():
                self._record_clipboard_image()
                return
            text = get_clipboard_text()
            if text:
                if self.history.record_text(text):
                    dlog("记录文本 %d 字符" % len(text))
        except Exception:
            log("记录剪贴板失败:\n" + traceback.format_exc())

    def _record_clipboard_image(self):
        for _ in range(10):
            if user32.OpenClipboard(None):
                break
            time.sleep(0.03)
        else:
            return
        try:
            grabbed = image_codec.grab_from_clipboard()
        finally:
            user32.CloseClipboard()
        if not grabbed:
            return
        w, h, pixels = grabbed
        entry = self.history.record_image(w, h, pixels)
        if entry:
            dlog("记录图片 %dx%d -> %s" % (w, h, entry["file"]))

    def paste_history(self, index):
        """粘贴历史里第 index 条（1 = 最新一条）。"""
        if self.history is None or not CONFIG.get("history_enabled", True):
            return
        entry = self.history.get(index)
        if entry is None:
            dlog("历史第 %d 条不存在（当前共 %d 条）" % (index, self.history.count()))
            return
        self._mark_self_write()
        if entry.get("type") == "text":
            text = normalize_text(transform_text(entry.get("text", "")))
            if not set_clipboard_text(text):
                log("写入剪贴板失败")
                return
        else:
            if image_codec is None:
                return
            path = self.history.abs_path(entry)
            loaded = image_codec.load_png(path) if path else None
            if not loaded:
                log("读取历史图片失败: %s" % path)
                return
            w, h, pixels = loaded
            if not image_codec.put_to_clipboard(w, h, pixels):
                log("写入图片到剪贴板失败")
                return
        send_paste()
        dlog("已粘贴历史第 %d 条: %s" % (index, self.history.preview(entry)))

    # ---------------- 生命周期

    def shutdown(self):
        if self.listening:
            user32.RemoveClipboardFormatListener(self.hwnd)
            self.listening = False
        self.remove_tray_icon()
        for hid in list(self.registered):
            user32.UnregisterHotKey(self.hwnd, hid)
        self.registered.clear()

    def _load_icon(self):
        """优先加载自定义图标，失败则退回系统默认图标。"""
        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x0010, 0x0040
        for folder in (RESOURCE_DIR, BASE_DIR):
            ico = os.path.join(folder, "plainpaste.ico")
            if os.path.exists(ico):
                handle = user32.LoadImageW(None, ico, IMAGE_ICON, 0, 0,
                                           LR_LOADFROMFILE | LR_DEFAULTSIZE)
                if handle:
                    return handle
        log("未找到自定义图标，使用系统默认图标")
        return user32.LoadIconW(
            None, ctypes.cast(ctypes.c_void_p(IDI_APPLICATION), wt.LPCWSTR))

    def start_clipboard_listener(self):
        """注册剪贴板变化监听（Vista+ 的 AddClipboardFormatListener）。"""
        if self.history is None:
            return
        if user32.AddClipboardFormatListener(self.hwnd):
            self.listening = True
            dlog("已开始监听剪贴板变化")
        else:
            log("AddClipboardFormatListener 失败, err=%d" % ctypes.get_last_error())

    def run(self):
        self.hicon = self._load_icon()
        self.wm_taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self._register_window_class()
        self._create_window()
        self.start_clipboard_listener()
        self.add_tray_icon()
        self.register_hotkeys()
        self.update_tip()

        msg = wt.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0:
                break
            if ret == -1:
                log("GetMessageW 失败, err=%d" % ctypes.get_last_error())
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        return 0


def save_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("保存配置失败: %r" % (e,))


def main():
    # 单实例
    mutex = kernel32.CreateMutexW(None, False, APP_NAME + "_SingleInstance_Mutex")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        show_message("%s 已经在运行了。\n\n请在右下角托盘区找到它的图标（蓝色小方块），"
                     "右键可退出或修改设置。" % APP_TITLE,
                     flags=MB_OK | MB_ICONINFORMATION | MB_TOPMOST)
        return 1

    load_config()
    try:
        app = PlainPasteApp()
        app.run()
        return 0
    except Exception:
        log("启动失败:\n" + traceback.format_exc())
        show_message("启动失败：\n\n%s" % traceback.format_exc(),
                     flags=MB_OK | MB_ICONERROR | MB_TOPMOST)
        return 1
    finally:
        try:
            kernel32.CloseHandle(mutex)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
