# -*- coding: utf-8 -*-
"""
image_codec —— 剪贴板位图 <-> PNG 文件的编解码（纯标准库，不依赖 PIL）。

职责：
  * 从剪贴板取出位图（CF_BITMAP），统一转成 32 位 BGRA 像素
  * 把像素编码为 PNG 文件（struct + zlib 手写 PNG）
  * 读取 PNG 文件还原像素（支持 filter 0~4、color type 2/6）
  * 把像素写回剪贴板（CF_DIB）
"""

import ctypes
import ctypes.wintypes as wt
import struct
import zlib

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CF_BITMAP = 2
CF_DIB = 8
CF_DIBV5 = 17
BI_RGB = 0
DIB_RGB_COLORS = 0
GMEM_MOVEABLE = 0x0002


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
    ]


class BITMAP(ctypes.Structure):
    _fields_ = [
        ("bmType", wt.LONG), ("bmWidth", wt.LONG), ("bmHeight", wt.LONG),
        ("bmWidthBytes", wt.LONG), ("bmPlanes", wt.WORD),
        ("bmBitsPixel", wt.WORD), ("bmBits", ctypes.c_void_p),
    ]


# ---------------------------------------------------------------- 函数签名

user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.ReleaseDC.restype = ctypes.c_int
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
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

gdi32.GetObjectW.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p]
gdi32.GetObjectW.restype = ctypes.c_int
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HANDLE, wt.UINT, wt.UINT,
                            ctypes.c_void_p, ctypes.POINTER(BITMAPINFOHEADER),
                            wt.UINT]
gdi32.GetDIBits.restype = ctypes.c_int

kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HANDLE
kernel32.GlobalLock.argtypes = [wt.HANDLE]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HANDLE]
kernel32.GlobalUnlock.restype = wt.BOOL
kernel32.GlobalFree.argtypes = [wt.HANDLE]
kernel32.GlobalFree.restype = wt.HANDLE

SM_CXSCREEN, SM_CYSCREEN = 0, 1
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79


# ---------------------------------------------------------------- 剪贴板取图

def clipboard_has_image():
    """剪贴板里是否有位图。"""
    return bool(user32.IsClipboardFormatAvailable(CF_BITMAP)
                or user32.IsClipboardFormatAvailable(CF_DIB)
                or user32.IsClipboardFormatAvailable(CF_DIBV5))


def screen_size():
    """返回 (虚拟屏幕宽, 虚拟屏幕高)，用于判断是否整屏截图。"""
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CXSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CYSCREEN)
    return vw, vh


def grab_from_clipboard():
    """
    从剪贴板取出位图。**调用前必须先 OpenClipboard**。
    返回 (width, height, bgra_topdown_bytes)；失败返回 None。
    """
    hbmp = user32.GetClipboardData(CF_BITMAP)
    if not hbmp:
        return None
    return _hbitmap_to_bgra(hbmp)


def _hbitmap_to_bgra(hbmp):
    bm = BITMAP()
    if not gdi32.GetObjectW(hbmp, ctypes.sizeof(BITMAP), ctypes.byref(bm)):
        return None
    w, h = int(bm.bmWidth), int(bm.bmHeight)
    if w <= 0 or h <= 0:
        return None

    hdc = user32.GetDC(None)
    if not hdc:
        return None
    try:
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h          # 负值 = 返回 top-down 数据
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = BI_RGB
        buf = ctypes.create_string_buffer(w * h * 4)
        got = gdi32.GetDIBits(hdc, hbmp, 0, h, buf, ctypes.byref(bmi),
                              DIB_RGB_COLORS)
        if not got:
            return None
        data = bytearray(buf.raw)
    finally:
        user32.ReleaseDC(None, hdc)

    # 剪贴板位图的 alpha 通道常常全是 0，会导致存成完全透明的图
    if not any(data[3::4]):
        data[3::4] = b"\xff" * (w * h)
    return w, h, bytes(data)


# ---------------------------------------------------------------- PNG 编码

def _png_chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def save_png(path, width, height, bgra_topdown, level=6):
    """把 BGRA top-down 像素写成 PNG 文件。"""
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        row = bgra_topdown[y * stride:(y + 1) * stride]
        raw.append(0)                      # filter type 0 = None
        # BGRA -> RGBA
        rgba = bytearray(len(row))
        rgba[0::4] = row[2::4]
        rgba[1::4] = row[1::4]
        rgba[2::4] = row[0::4]
        rgba[3::4] = row[3::4]
        raw += rgba

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8bit RGBA
    png = (b"\x89PNG\r\n\x1a\n"
           + _png_chunk(b"IHDR", ihdr)
           + _png_chunk(b"IDAT", zlib.compress(bytes(raw), level))
           + _png_chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return path


# ---------------------------------------------------------------- PNG 解码

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw, width, height, bpp):
    stride = width * bpp
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ft == 0:
            pass
        elif ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(a, b, c)) & 0xFF
        out += line
        prev = line
    return bytes(out)


def load_png(path):
    """读取 PNG，返回 (width, height, bgra_topdown_bytes)；失败返回 None。"""
    with open(path, "rb") as f:
        blob = f.read()
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos = 8
    width = height = None
    bit_depth = color_type = None
    idat = bytearray()
    while pos + 8 <= len(blob):
        length = struct.unpack(">I", blob[pos:pos + 4])[0]
        tag = blob[pos + 4:pos + 8]
        data = blob[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", data[:10])
        elif tag == b"IDAT":
            idat += data
        elif tag == b"IEND":
            break
    if not width or not height or bit_depth != 8:
        return None
    if color_type == 6:
        bpp = 4
    elif color_type == 2:
        bpp = 3
    else:
        return None

    raw = zlib.decompress(bytes(idat))
    pixels = _unfilter(raw, width, height, bpp)

    # 统一转成 BGRA top-down
    out = bytearray(width * height * 4)
    if bpp == 4:
        out[0::4] = pixels[2::4]     # B
        out[1::4] = pixels[1::4]     # G
        out[2::4] = pixels[0::4]     # R
        out[3::4] = pixels[3::4]     # A
    else:
        n = width * height
        out[0::4] = pixels[2::4][:n]
        out[1::4] = pixels[1::4][:n]
        out[2::4] = pixels[0::4][:n]
        out[3::4] = b"\xff" * n
    return width, height, bytes(out)


# ---------------------------------------------------------------- 写回剪贴板

def put_to_clipboard(width, height, bgra_topdown):
    """把 BGRA top-down 像素以 CF_DIB 写回剪贴板。成功返回 True。"""
    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = width
    header.biHeight = height        # 正值 = bottom-up（CF_DIB 约定）
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = BI_RGB
    header.biSizeImage = width * height * 4

    stride = width * 4
    rows = [bgra_topdown[y * stride:(y + 1) * stride] for y in range(height)]
    body = b"".join(reversed(rows))          # 翻成 bottom-up
    header_bytes = ctypes.string_at(ctypes.byref(header),
                                    ctypes.sizeof(header))
    blob = header_bytes + body

    import time
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.03)
    else:
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(blob))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, blob, len(blob))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_DIB, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


if __name__ == "__main__":
    import os
    import tempfile

    print("=" * 66)
    print("image_codec 自测：PNG 编解码往返")
    print("=" * 66)

    W, H = 64, 48
    # 造一张测试图：红绿渐变 + 右下角蓝色方块
    src = bytearray(W * H * 4)
    for y in range(H):
        for x in range(W):
            i = (y * W + x) * 4
            src[i + 0] = (x * 4) & 0xFF          # B
            src[i + 1] = (y * 5) & 0xFF          # G
            src[i + 2] = 200                     # R
            src[i + 3] = 255                     # A
    for y in range(H - 16, H):
        for x in range(W - 16, W):
            i = (y * W + x) * 4
            src[i + 0], src[i + 1], src[i + 2], src[i + 3] = 255, 0, 0, 255
    src = bytes(src)

    tmp = os.path.join(tempfile.gettempdir(), "pp_codec_test.png")
    save_png(tmp, W, H, src)
    size = os.path.getsize(tmp)
    print("  写入 PNG: %s (%d 字节)" % (tmp, size))

    loaded = load_png(tmp)
    if not loaded:
        print("  [FAIL] 解码失败")
    else:
        w2, h2, back = loaded
        print("  读回尺寸: %dx%d" % (w2, h2))
        if (w2, h2) == (W, H) and back == src:
            print("  [OK] 像素完全一致，PNG 编解码往返成功")
        else:
            diff = sum(1 for a, b in zip(back, src) if a != b)
            print("  [FAIL] 有 %d 字节不一致" % diff)

    # 验证文件确实是标准 PNG
    with open(tmp, "rb") as f:
        magic = f.read(8)
    print("  PNG 魔数正确: %s" % (magic == b"\x89PNG\r\n\x1a\n"))

    # 验证外部工具能否识别（用 Windows 自带的图片信息）
    print()
    print("  屏幕尺寸: %s" % (screen_size(),))
    print("  剪贴板当前有图片: %s" % clipboard_has_image())
    try:
        os.remove(tmp)
    except Exception:
        pass
