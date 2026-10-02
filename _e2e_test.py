# -*- coding: utf-8 -*-
"""端到端测试：验证「热键 -> 去格式 + LaTeX 转换 -> 自动粘贴」的完整链路。

流程（每个用例）：
  1. 往剪贴板里塞"富文本 + 原文"（模拟从网页 / AI 回答复制）
  2. 用 SendInput 真实按下 Ctrl+Shift+V，触发主程序
  3. 读取窗口里被粘贴进来的内容，与期望值比对

安全闸：发送按键前先确认前台窗口是本测试窗口，
否则会把内容误粘贴到用户正在使用的程序里，此时安全中止。
"""
import ctypes
import ctypes.wintypes as wt
import time
import tkinter as tk

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_SHIFT, VK_CONTROL, VK_V = 0x10, 0x11, 0x56
VK_MENU = 0x12

user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL
user32.EmptyClipboard.restype = wt.BOOL
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wt.UINT]
user32.IsClipboardFormatAvailable.restype = wt.BOOL
user32.RegisterClipboardFormatW.argtypes = [wt.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wt.UINT
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.c_void_p]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.AttachThreadInput.restype = wt.BOOL
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.SwitchToThisWindow.argtypes = [wt.HWND, wt.BOOL]
user32.SendInput.argtypes = [wt.UINT, ctypes.c_void_p, ctypes.c_int]
user32.SendInput.restype = wt.UINT
kernel32.GetCurrentThreadId.restype = wt.DWORD
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HANDLE
kernel32.GlobalLock.argtypes = [wt.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HANDLE]
kernel32.GlobalUnlock.restype = wt.BOOL

WINDOW_TITLE = "PlainPaste E2E Test"


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def _kv(vk, up=False):
    i = INPUT()
    i.type = INPUT_KEYBOARD
    i.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=(KEYEVENTF_KEYUP if up else 0),
                      time=0, dwExtraInfo=0)
    return i


def _send(seq):
    arr = (INPUT * len(seq))(*seq)
    return user32.SendInput(len(seq), ctypes.byref(arr), ctypes.sizeof(INPUT))


def set_rich_clipboard(text):
    """模拟富文本剪贴板：HTML Format + CF_UNICODETEXT。"""
    html_fmt = user32.RegisterClipboardFormatW("HTML Format")
    html = ("Version:0.9\r\nStartHTML:0000000105\r\nEndHTML:0000000199\r\n"
            "StartFragment:0000000139\r\nEndFragment:0000000199\r\n"
            "<html><body><span style='font-family:宋体;font-size:24pt;color:red'>"
            + text + "</span></body></html>")
    if not user32.OpenClipboard(None):
        return False
    user32.EmptyClipboard()
    for fmt, raw in ((html_fmt, html.encode("utf-8")),
                     (CF_UNICODETEXT, text.encode("utf-16-le") + b"\x00\x00")):
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, raw, len(raw))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(fmt, h)
    user32.CloseClipboard()
    return True


def force_foreground(hwnd, timeout=8.0):
    """把窗口抢到前台。Windows 默认禁止后台进程抢焦点，这里用三种手段轮番尝试。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if user32.GetForegroundWindow() == hwnd:
            return True
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        my_thread = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(my_thread, fg_thread, True)
        _send([_kv(VK_MENU), _kv(VK_MENU, True)])
        user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(my_thread, fg_thread, False)
        if user32.GetForegroundWindow() != hwnd:
            user32.SwitchToThisWindow(hwnd, True)
        time.sleep(0.2)
    return user32.GetForegroundWindow() == hwnd


# ---------------------------------------------------------------- 测试用例

CASES = [
    {
        "label": "基础：富文本去格式，保留换行",
        "clipboard": "第一行标题\r\n第二行正文",
        "expect": "第一行标题\n第二行正文",
    },
    {
        "label": "LaTeX：行内公式转普通符号",
        "clipboard": r"当 $\alpha = 0.05$ 时，$\frac{a}{b} = x^2$，且 $A \times B \neq C$。",
        "expect": "当 α = 0.05 时，a/b = x²，且 A × B ≠ C。",
    },
    {
        "label": "LaTeX：块级公式与希腊字母",
        "clipboard": ("方差公式为：\n"
                      r"$$\sigma^2 = \frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2$$" "\n"
                      r"其中 $\mu$ 为均值，$\theta$ 为参数。"),
        "expect": "方差公式为：\nσ² = 1/n∑ᵢ₌₁ⁿ(xᵢ - x̄)²\n其中 μ 为均值，θ 为参数。",
    },
    {
        "label": "安全：普通文本（含反斜杠路径）不被误改",
        "clipboard": r"路径 C:\Users\name\Documents，折扣 50%。",
        "expect": r"路径 C:\Users\name\Documents，折扣 50%。",
    },
]


class E2ETest(object):

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("520x200+120+120")
        self.box = tk.Text(self.root, font=("Consolas", 11))
        self.box.pack(fill="both", expand=True, padx=8, pady=8)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.hwnd = None
        self.results = []
        self.idx = 0
        self.aborted = None

    def run(self):
        self.root.after(400, self.prepare)
        self.root.mainloop()
        self.report()

    def prepare(self):
        self.hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if not force_foreground(self.hwnd):
            self.aborted = "焦点未取得，已中止（保护机制：避免误粘贴到其他程序）"
            self.root.destroy()
            return
        self.next_case()

    def next_case(self):
        if self.idx >= len(CASES):
            self.root.destroy()
            return
        case = CASES[self.idx]
        self.box.delete("1.0", "end")
        set_rich_clipboard(case["clipboard"])
        self.root.after(250, self.trigger)

    def trigger(self):
        if user32.GetForegroundWindow() != self.hwnd:
            if not force_foreground(self.hwnd, timeout=3.0):
                self.aborted = "焦点丢失，已中止"
                self.root.destroy()
                return
        self.box.focus_set()
        # 真实模拟按下 Ctrl+Shift+V
        _send([_kv(VK_CONTROL), _kv(VK_SHIFT), _kv(VK_V),
               _kv(VK_V, True), _kv(VK_SHIFT, True), _kv(VK_CONTROL, True)])
        self.root.after(1300, self.collect)

    def collect(self):
        case = CASES[self.idx]
        got = self.box.get("1.0", "end-1c")
        self.results.append((case, got))
        self.idx += 1
        self.root.after(300, self.next_case)

    def report(self):
        print("=" * 72)
        print("端到端测试：热键 -> 去格式 + LaTeX 转换 -> 自动粘贴")
        print("=" * 72)
        if self.aborted:
            print("  已安全中止：%s" % self.aborted)
            print("  （这是保护机制，不影响工具本身的功能）")
            return
        passed = 0
        for case, got in self.results:
            ok = got.strip() == case["expect"].strip()
            passed += 1 if ok else 0
            print("[%s] %s" % ("OK  " if ok else "FAIL", case["label"]))
            print("       剪贴板原文: %r" % case["clipboard"])
            print("       粘贴得到  : %r" % got)
            if not ok:
                print("       期望      : %r" % case["expect"])
        print("=" * 72)
        print("通过 %d / %d" % (passed, len(self.results)))
        if passed == len(self.results):
            print("\n结论：完整链路工作正常。")
        else:
            print("\n结论：存在不一致，需排查。")


if __name__ == "__main__":
    E2ETest().run()
