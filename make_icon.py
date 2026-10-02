# -*- coding: utf-8 -*-
"""生成 PlainPaste 的托盘图标 plainpaste.ico（纯标准库，无需 PIL）。

图标内容：圆角蓝色方块 + 白色字母 T（代表 Text）。
ICO 采用 32x32 / 32bpp BGRA + AND 掩码，兼容所有 Windows 版本。
"""
import struct
import os

W = H = 32
RADIUS = 7
BG_BGR = (0xE8, 0x6B, 0x1F)      # BGRA 顺序 -> 实际颜色 #1F6BE8（蓝色）
FG_BGR = (0xFF, 0xFF, 0xFF)      # 白色

# 7x7 点阵的字母 T
GLYPH = [
    [1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 0, 0],
    [0, 0, 1, 1, 1, 0, 0],
]
SCALE = 3
GLYPH_W = len(GLYPH[0]) * SCALE
GLYPH_H = len(GLYPH) * SCALE
OX = (W - GLYPH_W) // 2
OY = (H - GLYPH_H) // 2


def in_round_rect(x, y, w, h, r):
    cx = min(max(x, r), w - 1 - r)
    cy = min(max(y, r), h - 1 - r)
    dx, dy = x - cx, y - cy
    return dx * dx + dy * dy <= r * r


def glyph_at(x, y):
    gx, gy = x - OX, y - OY
    if 0 <= gx < GLYPH_W and 0 <= gy < GLYPH_H:
        return bool(GLYPH[gy // SCALE][gx // SCALE])
    return False


def build_pixels():
    """返回 bottom-up 的 BGRA 像素字节。"""
    rows = []
    for y in range(H - 1, -1, -1):          # bottom-up
        row = bytearray()
        for x in range(W):
            if in_round_rect(x, y, W, H, RADIUS):
                b, g, r = FG_BGR if glyph_at(x, y) else BG_BGR
                row += bytes((b, g, r, 0xFF))
            else:
                row += bytes((0, 0, 0, 0x00))   # 透明
        rows.append(bytes(row))
    return b"".join(rows)


def build_and_mask():
    """32x32 单色掩码，每行 4 字节，全 0 表示不透明（靠 alpha 通道控制）。"""
    line = b"\x00\x00\x00\x00"
    return line * H


def build_ico(path):
    pixels = build_pixels()
    mask = build_and_mask()

    bmp_header = struct.pack(
        "<IiiHHIIiiII",
        40,          # biSize
        W,           # biWidth
        H * 2,       # biHeight（含 AND 掩码，故为两倍）
        1,           # biPlanes
        32,          # biBitCount
        0,           # biCompression
        len(pixels) + len(mask),  # biSizeImage
        0, 0, 0, 0,
    )
    image = bmp_header + pixels + mask

    icondir = struct.pack("<HHH", 0, 1, 1)          # reserved, type=icon, count
    entry = struct.pack(
        "<BBBBHHII",
        W, H, 0, 0, 1, 32, len(image), 6 + 16,       # 数据偏移 = 6 + 16
    )
    with open(path, "wb") as f:
        f.write(icondir + entry + image)
    return path


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plainpaste.ico")
    build_ico(out)
    print("已生成: %s (%d 字节)" % (out, os.path.getsize(out)))
