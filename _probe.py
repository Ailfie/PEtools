# -*- coding: utf-8 -*-
"""临时验证脚本：检查热键占用、是否有错误弹窗、剪贴板去格式是否生效。"""
import ctypes
import ctypes.wintypes as wt
import sys

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.RegisterHotKey.restype = wt.BOOL
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.RegisterClipboardFormatW.argtypes = [wt.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wt.UINT
user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL
user32.EmptyClipboard.restype = wt.BOOL
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wt.UINT]
user32.IsClipboardFormatAvailable.restype = wt.BOOL
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HANDLE
kernel32.GlobalLock.argtypes = [wt.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HANDLE]
kernel32.GlobalUnlock.restype = wt.BOOL

MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0002, 0x0004, 0x4000

print("=== 1. 热键占用检测 ===")
ok = user32.RegisterHotKey(None, 9001, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, ord("V"))
err = ctypes.get_last_error()
if ok:
    print("  Ctrl+Shift+V 可注册 -> 主程序【未】成功占用它（异常）")
    user32.UnregisterHotKey(None, 9001)
else:
    print("  Ctrl+Shift+V 注册失败, err=%d" % err)
    if err == 1409:
        print("  -> err=1409 (ERROR_HOTKEY_ALREADY_REGISTERED)")
        print("  -> 说明主程序已成功占用该热键 [OK]")
    else:
        print("  -> 其他错误，需排查")

print()
print("=== 2. 错误弹窗检测 (#32770 对话框) ===")
found = []
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def cb(hwnd, lparam):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    if buf.value == "#32770":
        tbuf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, tbuf, 256)
        found.append((hwnd, tbuf.value))
    return True


user32.EnumWindows(EnumWindowsProc(cb), 0)
if found:
    print("  发现对话框窗口: %r  -> 可能弹出了错误提示" % (found,))
else:
    print("  未发现 #32770 对话框 -> 无错误弹窗 [OK]")

print()
print("=== 3. 剪贴板去格式机制验证 ===")
CF_UNICODETEXT = 13
HTML_FORMAT = user32.RegisterClipboardFormatW("HTML Format")
print("  HTML Format 剪贴板格式 ID = %d" % HTML_FORMAT)


def set_fmt(fmt_id, raw_bytes):
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(0x0002, len(raw_bytes))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, raw_bytes, len(raw_bytes))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(fmt_id, h)
        return True
    finally:
        user32.CloseClipboard()


def has_fmt(fmt_id):
    return bool(user32.IsClipboardFormatAvailable(fmt_id))


def get_text():
    if not user32.OpenClipboard(None):
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        try:
            return ctypes.c_wchar_p(p).value
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


# 模拟"从网页/Word 复制"：同时放入富文本 HTML 和纯文本
html = ("Version:0.9\r\nStartHTML:0000000105\r\nEndHTML:0000000199\r\n"
        "StartFragment:0000000139\r\nEndFragment:0000000199\r\n"
        "<html><body><b style='color:red'>Hello</b> World</body></html>")
if set_fmt(HTML_FORMAT, html.encode("utf-8")):
    # 追加纯文本（不清空，模拟真实的富文本剪贴板）
    user32.OpenClipboard(None)
    data = "Hello World".encode("utf-16-le") + b"\x00\x00"
    h = kernel32.GlobalAlloc(0x0002, len(data))
    p = kernel32.GlobalLock(h)
    ctypes.memmove(p, data, len(data))
    kernel32.GlobalUnlock(h)
    user32.SetClipboardData(CF_UNICODETEXT, h)
    user32.CloseClipboard()

print("  写入富文本后: HTML格式存在=%s, 文本=%r" % (has_fmt(HTML_FORMAT), get_text()))

# 现在模拟主程序的动作：只写回纯文本
user32.OpenClipboard(None)
user32.EmptyClipboard()
data = "Hello World\r\n第二行".encode("utf-16-le") + b"\x00\x00"
h = kernel32.GlobalAlloc(0x0002, len(data))
p = kernel32.GlobalLock(h)
ctypes.memmove(p, data, len(data))
kernel32.GlobalUnlock(h)
user32.SetClipboardData(CF_UNICODETEXT, h)
user32.CloseClipboard()

print("  执行去格式后: HTML格式存在=%s, 文本=%r" % (has_fmt(HTML_FORMAT), get_text()))
if not has_fmt(HTML_FORMAT):
    print("  -> 富文本格式已被剥离，换行保留 [OK]")
else:
    print("  -> 格式未剥离 [FAIL]")
