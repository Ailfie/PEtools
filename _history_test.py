# -*- coding: utf-8 -*-
"""剪贴板历史功能测试。

阶段一（无需窗口）：验证复制文本 / 图片被自动记录
阶段二（需窗口）  ：验证 Alt+Shift+N 按顺序粘贴第 N 条

安全闸：发送按键前先确认前台窗口是本测试窗口，否则安全中止。
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import struct
import sys
import time
import tkinter as tk

BASE = os.path.dirname(os.path.abspath(__file__))
HIST_FILE = os.path.join(BASE, "history", "history.jsonl")

sys.path.insert(0, BASE)
import image_codec  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_MENU, VK_SHIFT = 0x12, 0x10
WINDOW_TITLE = "PlainPaste History Test"

user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL
user32.EmptyClipboard.restype = wt.BOOL
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
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


def set_text(text):
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return False
    try:
        user32.EmptyClipboard()
        raw = text.encode("utf-16-le") + b"\x00\x00"
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, raw, len(raw))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
        return True
    finally:
        user32.CloseClipboard()


def set_hdrop(paths):
    """把"文件列表"（CF_HDROP）放进剪贴板，模拟在资源管理器里复制文件。"""
    CF_HDROP = 15
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return False
    try:
        user32.EmptyClipboard()
        # DROPFILES: pFiles(4) + pt(8) + fNC(4) + fWide(4) = 20 字节
        blob = struct.pack("<IiiII", 20, 0, 0, 0, 1)
        blob += ("\0".join(paths) + "\0\0").encode("utf-16-le")
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(blob))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, blob, len(blob))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_HDROP, h)
        return True
    finally:
        user32.CloseClipboard()


def read_history():
    if not os.path.exists(HIST_FILE):
        return []
    out = []
    with open(HIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def force_foreground(hwnd, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if user32.GetForegroundWindow() == hwnd:
            return True
        fg = user32.GetForegroundWindow()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        my_thread = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(my_thread, fg_thread, True)
        _send([_kv(VK_MENU), _kv(VK_MENU, True)])
        user32.ShowWindow(hwnd, 9)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(my_thread, fg_thread, False)
        if user32.GetForegroundWindow() != hwnd:
            user32.SwitchToThisWindow(hwnd, True)
        time.sleep(0.2)
    return user32.GetForegroundWindow() == hwnd


TEXT_A = "历史测试条目 A —— 第一条"
TEXT_B = "历史测试条目 B —— 第二条"


def phase_one():
    print("=" * 70)
    print("阶段一：自动记录剪贴板")
    print("=" * 70)
    before = len(read_history())

    set_text(TEXT_A)
    time.sleep(1.3)
    set_text(TEXT_B)
    time.sleep(1.3)

    entries = read_history()
    print("  记录前 %d 条 -> 记录后 %d 条" % (before, len(entries)))
    texts = [e.get("text") for e in entries if e.get("type") == "text"]
    ok_a = TEXT_A in texts
    ok_b = TEXT_B in texts
    print("  [%s] 文本 A 已记录" % ("OK  " if ok_a else "FAIL"))
    print("  [%s] 文本 B 已记录" % ("OK  " if ok_b else "FAIL"))

    # 去重验证：再复制一次完全相同的内容
    n1 = len(read_history())
    set_text(TEXT_B)
    time.sleep(1.2)
    n2 = len(read_history())
    print("  [%s] 重复内容不重复记录（%d -> %d）"
          % ("OK  " if n2 == n1 else "FAIL", n1, n2))

    # 图片记录
    W, H = 80, 60
    pixels = bytearray(W * H * 4)
    for y in range(H):
        for x in range(W):
            i = (y * W + x) * 4
            pixels[i:i + 4] = bytes((x * 3 % 256, y * 4 % 256, 180, 255))
    image_codec.put_to_clipboard(W, H, bytes(pixels))
    time.sleep(2.0)

    entries = read_history()
    images = [e for e in entries if e.get("type") == "image"]
    print("  [%s] 图片已记录（共 %d 张）" % ("OK  " if images else "FAIL", len(images)))
    if images:
        last = images[-1]
        fp = os.path.join(BASE, "history", last["file"].replace("/", os.sep))
        exists = os.path.exists(fp)
        size = os.path.getsize(fp) if exists else 0
        print("      文件: %s" % last["file"])
        print("  [%s] PNG 文件已落盘（%d 字节）" % ("OK  " if exists else "FAIL", size))
        loaded = image_codec.load_png(fp) if exists else None
        if loaded:
            print("  [%s] 可正常读回（%dx%d）" % ("OK  ", loaded[0], loaded[1]))
        else:
            print("  [FAIL] 读回失败")

    # 复制的"文件"不应被记录（用户明确要求）
    n1 = len(read_history())
    set_hdrop([r"C:\Windows\notepad.exe", r"C:\Windows\explorer.exe"])
    time.sleep(1.5)
    n2 = len(read_history())
    print("  [%s] 复制的文件未被记录（%d -> %d）"
          % ("OK  " if n2 == n1 else "FAIL", n1, n2))

    return entries


class PhaseTwo(object):
    """用真实按键 Alt+Shift+N 验证历史粘贴。"""

    def __init__(self, cases):
        self.cases = cases
        self.results = []
        self.idx = 0
        self.aborted = None
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("560x220+130+130")
        self.box = tk.Text(self.root, font=("Consolas", 11))
        self.box.pack(fill="both", expand=True, padx=8, pady=8)
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.hwnd = None

    def run(self):
        self.root.after(400, self.prepare)
        self.root.mainloop()
        return self.report()

    def prepare(self):
        self.hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if not force_foreground(self.hwnd):
            self.aborted = "焦点未取得，已中止"
            self.root.destroy()
            return
        self.next_case()

    def next_case(self):
        if self.idx >= len(self.cases):
            self.root.destroy()
            return
        self.box.delete("1.0", "end")
        self.root.after(300, self.trigger)

    def trigger(self):
        if user32.GetForegroundWindow() != self.hwnd:
            if not force_foreground(self.hwnd, timeout=3.0):
                self.aborted = "焦点丢失，已中止"
                self.root.destroy()
                return
        self.box.focus_set()
        n = self.cases[self.idx][0]
        vk = ord("0") if n == 10 else ord(str(n))
        # 真实按下 Alt+Shift+N
        _send([_kv(VK_MENU), _kv(VK_SHIFT), _kv(vk),
               _kv(vk, True), _kv(VK_SHIFT, True), _kv(VK_MENU, True)])
        self.root.after(1300, self.collect)

    def collect(self):
        self.results.append((self.cases[self.idx], self.box.get("1.0", "end-1c")))
        self.idx += 1
        self.root.after(300, self.next_case)

    def report(self):
        print()
        print("=" * 70)
        print("阶段二：Alt+Shift+N 按顺序粘贴历史")
        print("=" * 70)
        if self.aborted:
            print("  已安全中止：%s" % self.aborted)
            return False
        passed = 0
        for (n, expect), got in self.results:
            ok = got.strip() == expect.strip()
            passed += 1 if ok else 0
            print("[%s] Alt+Shift+%d" % ("OK  " if ok else "FAIL", n))
            print("       期望: %r" % expect)
            print("       得到: %r" % got)
        print("通过 %d / %d" % (passed, len(self.results)))
        return passed == len(self.results)


def main():
    phase_one()
    # 历史顺序（最新在后）：… A, B, 图片
    #   index 1 = 图片, index 2 = B, index 3 = A
    cases = [(2, TEXT_B), (3, TEXT_A)]
    PhaseTwo(cases).run()


if __name__ == "__main__":
    main()
