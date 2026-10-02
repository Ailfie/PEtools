# -*- coding: utf-8 -*-
"""
clipboard_history —— 剪贴板历史记录管理。

存储结构（默认放在 exe/脚本同级的 history 目录）：
    history/
        history.jsonl      每条记录一行 JSON：文本内联存储，图片只存路径
        images/            所有图片（截图和普通图片统一存放）

记录顺序即复制顺序；查询时 index=1 表示**最新**一条。

自动清理四道闸门：
    1. 超过 history_days 天的记录
    2. 超过 history_max_entries 条时，淘汰最旧的
    3. 历史目录总容量超过 history_max_total_mb 时，淘汰最旧的
    4. 单条文本 / 单张图片超过上限时直接不记录
"""

import hashlib
import json
import os
import time

import image_codec


def _now_stamp():
    return time.strftime("%Y%m%d_%H%M%S") + "_%03d" % (int(time.time() * 1000) % 1000)


def _sha1(data):
    return hashlib.sha1(data).hexdigest()[:16]


class HistoryManager(object):

    def __init__(self, base_dir, config):
        self.base = base_dir
        self.dir = os.path.join(base_dir, "history")
        self.images_dir = os.path.join(self.dir, "images")
        self.path = os.path.join(self.dir, "history.jsonl")
        self.config = config
        self.entries = []
        self.last_error = None
        self._ensure_dirs()
        self.reload()

    # ---------------- 配置读取 ----------------

    @property
    def enabled(self):
        return bool(self.config.get("history_enabled", True))

    @property
    def days(self):
        return max(1, int(self.config.get("history_days", 7)))

    @property
    def max_entries(self):
        return max(1, int(self.config.get("history_max_entries", 200)))

    @property
    def max_text_bytes(self):
        return max(1, int(self.config.get("history_max_text_kb", 512))) * 1024

    @property
    def max_image_bytes(self):
        return max(1, int(self.config.get("history_max_image_mb", 10))) * 1024 * 1024

    @property
    def max_total_bytes(self):
        return max(1, int(self.config.get("history_max_total_mb", 200))) * 1024 * 1024

    # ---------------- 目录与加载 ----------------

    def _ensure_dirs(self):
        for d in (self.dir, self.images_dir):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception as e:
                self.last_error = "创建历史目录失败: %r" % (e,)

    def reload(self):
        """从 jsonl 载入内存索引（图片文件已丢失的记录会被剔除）。"""
        self.entries = []
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    if e.get("type") == "image":
                        fp = os.path.join(self.dir, e.get("file", ""))
                        if not os.path.exists(fp):
                            continue
                    self.entries.append(e)
        except Exception as ex:
            self.last_error = "读取历史失败: %r" % (ex,)
        # 只保留最近 max_entries 条在内存里
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    # ---------------- 记录 ----------------

    def record_text(self, text):
        """记录一条文本。返回记录或 None（被跳过时）。"""
        if not self.enabled or not text:
            return None
        raw = text.encode("utf-8")
        if len(raw) > self.max_text_bytes:
            self.last_error = "文本超过单条上限 %d KB，已跳过" % (self.max_text_bytes // 1024)
            return None
        digest = _sha1(raw)
        if self.entries and self.entries[-1].get("hash") == digest:
            return None                       # 与上一条重复，跳过
        entry = {
            "t": time.time(),
            "type": "text",
            "text": text,
            "hash": digest,
        }
        self._append(entry)
        return entry

    def record_image(self, width, height, bgra_topdown):
        """记录一张位图（自动判断是否为整屏截图）。返回记录或 None。"""
        if not self.enabled:
            return None
        digest = _sha1(bgra_topdown[:65536]) + "-%dx%d" % (width, height)
        if self.entries and self.entries[-1].get("hash") == digest:
            return None
        estimated = width * height * 4
        if estimated > self.max_image_bytes * 4:
            # 粗筛：原始像素就远超上限，不必尝试压缩
            self.last_error = "图片过大，已跳过"
            return None

        name = "%s_%dx%d.png" % (_now_stamp(), width, height)
        rel = "images/" + name
        full = os.path.join(self.images_dir, name)
        try:
            image_codec.save_png(full, width, height, bgra_topdown)
        except Exception as e:
            self.last_error = "保存图片失败: %r" % (e,)
            return None
        if os.path.getsize(full) > self.max_image_bytes:
            try:
                os.remove(full)
            except Exception:
                pass
            self.last_error = "图片超过单张上限，已跳过"
            return None

        entry = {
            "t": time.time(),
            "type": "image",
            "file": rel,
            "w": width,
            "h": height,
            "hash": digest,
        }
        self._append(entry)
        return entry

    def _append(self, entry):
        self.entries.append(entry)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            self.last_error = "写入历史失败: %r" % (e,)
        self.cleanup()

    # ---------------- 查询 ----------------

    def count(self):
        return len(self.entries)

    def get(self, index):
        """index=1 表示最新一条，index=2 表示倒数第二条……"""
        if index < 1 or index > len(self.entries):
            return None
        return self.entries[-index]

    def preview(self, entry, limit=60):
        if not entry:
            return ""
        if entry.get("type") == "text":
            s = " ".join(entry.get("text", "").split())
            return s[:limit] + ("…" if len(s) > limit else "")
        return "[图片 %dx%d]" % (entry.get("w", 0), entry.get("h", 0))

    def abs_path(self, entry):
        if not entry or entry.get("type") != "image":
            return None
        return os.path.join(self.dir, entry.get("file", "").replace("/", os.sep))

    # ---------------- 清理 ----------------

    def cleanup(self):
        """按 时间 / 条数 / 总容量 三重规则清理，并重写索引文件。"""
        if not self.entries:
            if os.path.exists(self.path):
                self._rewrite()
            return 0
        removed = []
        now = time.time()
        cutoff = now - self.days * 86400

        # 1) 按天数
        keep = []
        for e in self.entries:
            if e.get("t", 0) < cutoff:
                removed.append(e)
            else:
                keep.append(e)
        self.entries = keep

        # 2) 按条数
        if len(self.entries) > self.max_entries:
            removed.extend(self.entries[:len(self.entries) - self.max_entries])
            self.entries = self.entries[-self.max_entries:]

        # 3) 按总容量（从最旧的开始淘汰）
        while self.entries and self._total_bytes() > self.max_total_bytes:
            removed.append(self.entries.pop(0))

        if removed:
            self._delete_files(removed)
        self._rewrite()
        return len(removed)

    def _total_bytes(self):
        total = 0
        if os.path.exists(self.path):
            try:
                total += os.path.getsize(self.path)
            except Exception:
                pass
        for e in self.entries:
            if e.get("type") == "image":
                fp = self.abs_path(e)
                if fp and os.path.exists(fp):
                    try:
                        total += os.path.getsize(fp)
                    except Exception:
                        pass
        return total

    def _delete_files(self, entries):
        for e in entries:
            if e.get("type") == "image":
                fp = self.abs_path(e)
                if fp and os.path.exists(fp):
                    try:
                        os.remove(fp)
                    except Exception:
                        pass

    def _rewrite(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for e in self.entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            if os.path.exists(self.path):
                os.remove(self.path)
            os.rename(tmp, self.path)
        except Exception as e:
            self.last_error = "重写历史失败: %r" % (e,)

    def clear(self):
        """清空全部历史（含图片文件）。"""
        n = len(self.entries)
        for d in (self.images_dir,):
            if not os.path.isdir(d):
                continue
            for name in os.listdir(d):
                try:
                    os.remove(os.path.join(d, name))
                except Exception:
                    pass
        self.entries = []
        self._rewrite()
        return n

    def stats(self):
        total = self._total_bytes()
        return {
            "count": len(self.entries),
            "total_bytes": total,
            "images": sum(1 for e in self.entries if e.get("type") == "image"),
            "texts": sum(1 for e in self.entries if e.get("type") == "text"),
        }


if __name__ == "__main__":
    import tempfile
    import shutil

    print("=" * 66)
    print("clipboard_history 自测")
    print("=" * 66)

    tmp = os.path.join(tempfile.gettempdir(), "pp_hist_test")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)

    cfg = {"history_enabled": True, "history_days": 7, "history_max_entries": 5,
           "history_max_text_kb": 512, "history_max_image_mb": 10,
           "history_max_total_mb": 200}
    hm = HistoryManager(tmp, cfg)

    # 记录若干文本
    for i in range(1, 8):
        hm.record_text("第 %d 条内容" % i)
    print("  记录 7 条文本后，实际保留 %d 条（上限 5）" % hm.count())
    print("  第 1 条(最新) = %r" % hm.get(1)["text"])
    print("  第 2 条        = %r" % hm.get(2)["text"])
    print("  第 5 条        = %r" % hm.get(5)["text"])
    print("  第 6 条(越界)  = %r" % hm.get(6))

    # 去重
    before = hm.count()
    hm.record_text("第 7 条内容")
    print("  重复记录同一条 -> 数量不变: %s" % (hm.count() == before))

    # 超长文本被拒
    hm.record_text("x" * (600 * 1024))
    print("  超长文本被拒绝: %s (%s)" % (hm.count() == before, hm.last_error))

    # 图片记录
    W, H = 40, 30
    pixels = bytes([128, 64, 32, 255] * (W * H))
    e = hm.record_image(W, H, pixels)
    print("  图片记录: %s -> %s" % (bool(e), e and e["file"]))
    print("  图片文件存在: %s" % os.path.exists(hm.abs_path(e)))

    print("  统计: %s" % hm.stats())

    # 清理测试：把时间改成 10 天前
    for ent in hm.entries:
        ent["t"] = time.time() - 10 * 86400
    hm._rewrite()
    hm.reload()
    print("  改写为 10 天前后，载入 %d 条" % hm.count())
    removed = hm.cleanup()
    print("  按 7 天规则清理掉 %d 条，剩余 %d 条" % (removed, hm.count()))
    print("  图片文件已被删除: %s" % (not os.path.exists(hm.abs_path(e))))

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("  自测完成")
