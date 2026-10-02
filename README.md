# Easy Copy Paste（PlainPaste）

> **把 AI 回答里的公式，直接粘进 PPT。**

从 ChatGPT / Gemini / DeepSeek 复制带公式的技术内容，粘贴时自动转成可读文本：

```
复制到：  $$\sigma^2 = \frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2$$
粘贴出：  σ² = 1/n∑ᵢ₌₁ⁿ(xᵢ - x̄)²
```

同时剥离一切格式，只保留纯文本与换行 —— 字体、颜色、超链接、表格样式都不会粘过来。

Windows 托盘小工具 · **免安装** · **零第三方依赖** · **无需管理员权限**

**English** — A Windows tray utility that makes AI answers paste-ready. It converts **LaTeX** copied from ChatGPT / Gemini / DeepSeek into readable Unicode (`\frac{a}{b}` → `a/b`, `$x^2$` → `x²`, `\alpha` → `α`), strips all formatting so only plain text and line breaks survive, and keeps a re-pasteable clipboard history (`Alt+Shift+1~0`). Pure Python standard library — no PIL, no third-party packages, no admin rights.

---

## 它解决什么

**主要场景：AI 回答 → Word / PPT**

从 AI 复制的技术内容，公式全是 LaTeX 源码，粘进文档就是一堆 `\frac{a}{b}`、`$x^2$`、
`\int_0^\infty`，完全不能看。本工具在粘贴的瞬间把它转成普通文本与 Unicode 符号
（完整对照表见下方「LaTeX 公式自动转换」）。

**附带解决：从任何地方复制，都不带格式**

从网页、微信、PDF、其他文档复制的内容粘到 Word / PPT 时，总会带上字体、字号、颜色、
超链接、表格样式，排版全乱。本工具让**任何程序**里都能"只粘贴纯文本和换行"。

---

## 一、先确认：也许你不需要这个工具

| | 方案 A：Office 自带设置 | 方案 B：PlainPaste 工具 |
|---|---|---|
| 适用范围 | 仅 Word / PowerPoint | **所有程序**（Word、PPT、微信、网页编辑器、邮件等） |
| 是否装软件 | 不用，改个设置就行 | 需要运行一个小工具 |
| 触发方式 | 正常 Ctrl+V 即纯文本 | Ctrl+Shift+V |
| 能否临时粘贴带格式 | 不能（全局生效） | 能（普通 Ctrl+V 仍保留格式） |
| 推荐场景 | 你只在 Office 里遇到这个问题 | 你在任何地方都需要纯文本粘贴 |

**结论**：如果你的困扰只发生在 Word/PPT，直接用方案 A，零成本。如果到处都需要，用方案 B。

---

## 二、方案 A：Office 自带设置（零成本）

### 1. Word —— 改默认粘贴行为

`文件` → `选项` → `高级` → 找到 **剪切、复制和粘贴** 区域
→ 把 **"从其他程序粘贴"** 改为 **"仅保留文本"** → 确定

效果：以后从网页/微信复制的东西粘到 Word，自动变成纯文本。
注意：只影响"从其他程序粘贴"，Word 文档内部互相复制粘贴不受影响。

### 2. PowerPoint —— 同样的设置

`文件` → `选项` → `高级` → **剪切、复制和粘贴**
→ **"从其他程序粘贴"** 改为 **"仅保留文本"** → 确定

### 3. 临时粘贴（不想改全局设置时）

在 Word / PPT 里用 **`Ctrl + Alt + V`**，会弹出"选择性粘贴"对话框，
选 **"无格式文本"** 或 **"只保留文本"** 即可。

### 4. 给 Word 绑定一个纯文本粘贴快捷键（进阶）

Word 内置了一个叫 `PasteTextOnly` 的命令，只是默认没绑定快捷键：

1. `文件` → `选项` → `自定义功能区`
2. 左下角 `键盘快捷方式: 自定义...`
3. 左侧"类别"选 **所有命令**
4. 在命令列表里找到 **PasteTextOnly**
5. 光标点进"请按新快捷键"框，按下你想用的组合（例如 `Ctrl+Shift+V`）
6. 点 `指定` → `关闭`

以后在 Word 里按这个组合就是纯文本粘贴。**注意**：这个快捷键只在 Word 里有效。

### 方案 A 的局限

- 只在 Office 里管用，微信、飞书、浏览器编辑器、邮件客户端都管不到
- 第 4 条的快捷键是应用内的，换到别的程序就失效
- 无法"这一次要纯文本、下一次要带格式"灵活切换

---

## 三、方案 B：PlainPaste 工具

### 下载

从本仓库的 **[Releases](https://github.com/Ailfie/PEtools/releases)** 页面下载 `PlainPaste.exe`，放到任意文件夹（例如桌面），双击即用。

> 仓库源码中**不包含** exe —— 它有 7 MB 多，属于二进制产物，放进 Git 历史会让仓库迅速膨胀。
> 需要自行编译的话见文末「从源码构建」。

### 怎么运行

**方式一（推荐）：双击 `PlainPaste.exe`**

双击后没有窗口弹出是正常的 —— 它常驻在系统托盘（任务栏右下角，时钟旁边）。
如果没看到图标，点一下托盘区的 `^` 小箭头展开折叠区，把图标拖出来固定住。

**方式二：双击 `启动PlainPaste.vbs`**

如果 exe 没能生成或被杀毒软件拦了，用这个方式，效果一样（静默后台启动）。

### 怎么用

1. 在任何地方正常 `Ctrl+C` 复制内容（网页、微信、PDF、别的文档都行）
2. 在目标程序里按 **`Ctrl + Shift + V`**
3. 粘进去的就是纯文本 —— 字体、颜色、超链接、表格样式全部被剥掉，**换行和段落结构完整保留**

普通 `Ctrl + V` 不受影响，仍然是原样粘贴。两种方式随时切换。

> 小技巧：按过一次 `Ctrl+Shift+V` 之后，剪贴板里已经是纯文本了，
> 紧接着继续按普通 `Ctrl+V` 也是干净的，适合连续粘贴多次。

### LaTeX 公式自动转换

从 AI 回答（ChatGPT / Gemini / DeepSeek 等）复制的数学公式，会自动转成可读的普通文本与 Unicode 符号：

| 复制到的原文 | 粘贴出来的效果 |
|---|---|
| `$\frac{a}{b}$` | `a/b` |
| `$x^2 + y^2 = z^2$` | `x² + y² = z²` |
| `$\alpha + \beta = \gamma$` | `α + β = γ` |
| `$\int_0^\infty e^{-x}dx$` | `∫₀^∞ e^(-x)dx` |
| `$\sqrt{x^2+y^2}$` | `√(x²+y²)` |
| `$\frac{-b \pm \sqrt{b^2-4ac}}{2a}$` | `(-b ± √(b² - 4ac))/2a` |
| `$\sum_{i=1}^{n} x_i$` | `∑ᵢ₌₁ⁿ xᵢ` |
| `$A \times B \neq C$` | `A × B ≠ C` |
| `$\hat{y} = \theta_0 + \theta_1 x_1$` | `ŷ = θ₀ + θ₁ x₁` |

**实际效果演示**

复制到的原文：

```
方差公式为：
$$\sigma^2 = \frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2$$
其中 $\mu$ 为均值，$\theta$ 为参数。
```

按 `Ctrl+Shift+V` 粘贴出来：

```
方差公式为：
σ² = 1/n∑ᵢ₌₁ⁿ(xᵢ - x̄)²
其中 μ 为均值，θ 为参数。
```

**三种模式**（右键托盘图标 → "LaTeX 公式转普通文本" 循环切换）：

| 模式 | 行为 |
|---|---|
| **自动识别**（默认） | 仅在检测到 LaTeX 特征时转换，普通文本原样保留 |
| 总是转换 | 无论内容如何都执行转换 |
| 已关闭 | 只去格式，不处理 LaTeX |

> 默认的"自动识别"很安全：`C:\Users\name` 这类含反斜杠的路径、
> `价格 $100`、`折扣 50% & 免运费` 等普通文本都不会被误改。

**支持范围**：`$...$` / `$$...$$` / `\(...\)` / `\[...\]` 四种定界符；
希腊字母、运算/关系/箭头/大型运算符等数百个符号；上下标（`x^2` → `x²`、`x_i` → `xᵢ`）；
`\frac` `\sqrt` `\binom` `\left...\right` 等结构命令；`\text` `\textbf` `\mathbf` `\boxed`
等文本包装；`\hat` `\bar` `\vec` 等重音；`\begin{matrix}` / `cases` / `align` 环境。

### 剪贴板历史

复制过的内容会自动记录下来，按快捷键直接粘贴，不用来回切换窗口找。

| 快捷键 | 效果 |
|---|---|
| `Alt + Shift + 1` | 粘贴**最新**一条 |
| `Alt + Shift + 2` | 粘贴倒数第二条 |
| `Alt + Shift + 3` | 粘贴倒数第三条 |
| … | 依次类推 |
| `Alt + Shift + 0` | 粘贴第 10 条 |

> **为什么不用 `Alt+1~9`？** 因为 Word / Excel / PowerPoint 里 `Alt+1~9` 是"快速访问工具栏"的快捷键，
> `Ctrl+Alt+1~3` 在 Word 里是标题样式、`Ctrl+Shift+1~6` 在 Excel 里是数字格式，都会打架。
> **`Alt+Shift+数字` 在 Office 三件套里都没有默认绑定**，所以选它。如果仍与你的其他软件冲突，
> 改配置里的 `history_prefix` 即可（例如 `"ctrl+alt"`）。

**存了什么、存在哪**

工具目录下的 `history` 文件夹：

```
history/
    history.jsonl     所有文本记录（就这一个文件，每行一条，可直接用记事本翻看）
    images/           所有图片，PNG 格式，文件名带时间戳
```

- **文本**：统一记录在 `history.jsonl` 一个文件里
- **图片**：保存到 `images/` 文件夹（截图和普通图片放一起）
- **复制的文件**（在资源管理器里 `Ctrl+C` 的文件）：**不记录**，按要求跳过

**自动清理**（每次记录后自动执行，超期的记录连同图片文件一起删除）

| 规则 | 默认值 | 配置项 |
|---|---|---|
| 超过多少天自动清理 | 7 天 | `history_days` |
| 最多保留多少条 | 200 条 | `history_max_entries` |
| 单条文本上限 | 512 KB | `history_max_text_kb` |
| 单张图片上限 | 10 MB | `history_max_image_mb` |
| 历史目录总容量上限 | 200 MB | `history_max_total_mb` |

**托盘菜单里的历史操作**

- **记录剪贴板历史** —— 开关自动记录
- **打开历史文件夹** —— 直接打开 `history` 目录
- **清空历史记录** —— 一键清空（会二次确认）

### 托盘图标上的操作

| 操作 | 效果 |
|---|---|
| 鼠标悬停 | 显示当前快捷键 |
| **左键双击** | 临时启用 / 暂停 |
| **右键单击** | 打开菜单 |

右键菜单项：

- **启用快捷键** —— 临时关掉工具（比如这次就是要保留格式）
- **复制即转纯文本** —— 打开后，`Ctrl+Shift+C` 复制时就转成纯文本（默认关闭）
- **LaTeX 公式转普通文本** —— 循环切换 自动识别 / 总是转换 / 已关闭
- **开机自动启动** —— 勾选后每次开机自动在后台运行（写的是当前用户注册表，不需要管理员权限）
- **打开配置文件** —— 直接编辑 `config.json`
- **使用说明** —— 弹出快捷键说明
- **退出** —— 关闭工具

### 修改快捷键

编辑同目录下的 `config.json`，改完**重启程序**生效：

```json
{
  "hotkey": "ctrl+shift+v",        // 纯文本粘贴热键
  "copy_hotkey": "ctrl+shift+c",   // 复制即转纯文本热键
  "enable_copy_plain": false,      // 是否启用上面这个功能
  "latex_to_text": "auto",         // LaTeX 转换：auto 自动识别 / always 总是 / off 关闭
  "paste_delay_ms": 30,            // 粘贴前的等待毫秒数，偶发粘不上时可调大
  "trim_whitespace": false,        // 是否去掉首尾空白行
  "debug": false,                  // 排错时改成 true，会写日志

  "history_enabled": true,         // 是否自动记录剪贴板历史
  "history_prefix": "alt+shift",   // 历史粘贴修饰键（+1~9、+0 取第 1~10 条）
  "history_days": 7,               // 超过多少天自动清理
  "history_max_entries": 200,      // 最多保留多少条
  "history_max_text_kb": 512,      // 单条文本上限（KB）
  "history_max_image_mb": 10,      // 单张图片上限（MB）
  "history_max_total_mb": 200      // 历史目录总容量上限（MB）
}
```

热键写法：`ctrl` / `shift` / `alt` / `win` 用 `+` 连接，主键可以是字母、数字、`f1`~`f24`。
例如 `"alt+q"`、`"ctrl+shift+f9"`、`"ctrl+alt+v"`。

---

## 四、常见问题

**Q：按了没反应？**

1. 确认托盘图标在（双击看是否能切换启用状态）
2. 可能热键被别的软件占了。右键 → 打开配置文件，把 `hotkey` 换成 `ctrl+alt+q` 之类，重启程序
3. 目标程序如果是**以管理员身份运行**的（某些编辑器、终端），本工具也必须以管理员身份运行才能对它生效

**Q：粘贴出来还是带格式？**

说明工具没生效（热键被拦或已暂停）。检查托盘图标状态。

**Q：粘贴后剪贴板里的内容被改成了纯文本，我后面还想用带格式的怎么办？**

这是有意设计 —— 保持纯文本状态更适合连续粘贴。需要带格式时，重新复制一次即可。

**Q：Word 里 Ctrl+Shift+V 原本是"粘贴并匹配格式"，被工具抢了怎么办？**

按方案 A 第 4 条，把 Word 的纯文本粘贴绑到别的键（比如 `Ctrl+Shift+Q`），
或者改本工具的 `hotkey` 避开它。

**Q：LaTeX 转换结果不符合预期，或误改了普通文本？**

右键托盘图标 → "LaTeX 公式转普通文本"，切换到**已关闭**或**自动识别**。
如果某个符号没转换成功，可以在 `latex2text.py` 的 `SYMBOLS` 字典里补一行映射
（格式：`"命令名": "符号"`），重新打包即可。

**Q：`Alt+Shift+1` 没反应？**

1. 先确认有过复制动作（历史为空时按了没效果，托盘菜单会显示"现有 N 条"）
2. 若与其他软件冲突，改配置里的 `history_prefix`，例如 `"ctrl+alt"` 或 `"ctrl+shift+alt"`
3. 部分输入法会占用 `Alt+Shift` 切换语言，可在输入法设置里关掉该快捷键

**Q：历史记录会不会占满硬盘？**

不会。四道闸门同时生效：超过 `history_days` 天（默认 7 天）自动清理、最多 `history_max_entries`
条（默认 200）、单条文本超 512 KB 不收、单图超 10 MB 不收、整个历史目录超 200 MB 时从最旧的开始淘汰。

**Q：杀毒软件报毒？**

用 PyInstaller 打包的 Python 程序偶尔会被误报（因为打包器本身的行为特征）。
本工具不联网、不写系统目录、只读写剪贴板和注册表当前用户项。
如果介意，直接用方案 A，或改用方式二（`启动PlainPaste.vbs`）。

---

## 五、文件说明

| 文件 | 用途 |
|---|---|
| `plain_paste.py` | 主程序源码，纯 Python 标准库，无第三方依赖 |
| `latex2text.py` | LaTeX → 纯文本/Unicode 转换模块，可独立运行自测 |
| `clipboard_history.py` | 剪贴板历史管理（存储、索引、自动清理），可独立运行自测 |
| `image_codec.py` | 剪贴板位图 ↔ PNG 编解码（纯标准库手写 PNG），可独立运行自测 |
| `plainpaste.ico` | 托盘图标 |
| `make_icon.py` | 重新生成图标的脚本（纯 `struct` 手写 ICO） |
| `config.example.json` | 配置模板；首次运行会自动生成 `config.json` |
| `build.bat` | 一键打包脚本（PyInstaller） |
| `_probe.py` | 自检脚本：验证热键占用与剪贴板去格式机制 |
| `_e2e_test.py` | 端到端自测：热键→去格式+LaTeX转换→自动粘贴 |
| `_history_test.py` | 端到端自测：剪贴板记录 + Alt+Shift+N 历史粘贴 |

以下为**运行期自动生成**，已在 `.gitignore` 中排除，不会进入仓库：

| 文件 | 说明 |
|---|---|
| `config.json` | 你的个人配置 |
| `history/` | 剪贴板历史数据（含个人复制内容） |
| `plainpaste.log` | 运行日志（仅出错或 `debug=true` 时产生） |
| `PlainPaste.exe` | 打包产物，请从 Releases 下载 |

---

## 六、从源码构建

需要 Python 3.8+，然后：

```bat
build.bat
```

脚本会自动安装 PyInstaller 并产出 `dist\PlainPaste.exe`。等价的手工命令是：

```bat
python -m PyInstaller --onefile --noconsole --name PlainPaste ^
    --icon plainpaste.ico --add-data "plainpaste.ico;." ^
    --clean --noconfirm plain_paste.py
```

不打包也能直接跑（需要 `pythonw.exe` 才不弹黑框）：

```bat
pythonw plain_paste.py
```

三个核心模块都支持独立自测，改完代码建议跑一遍：

```bat
python latex2text.py        REM 24 项转换用例
python clipboard_history.py REM 存储/去重/上限/清理
python image_codec.py       REM PNG 编解码往返一致性
```

---

## 七、技术要点

有意为之的几个设计，供二次开发参考：

- **纯 `ctypes` 调 Win32**，不依赖 `pywin32` / `keyboard` / `Pillow`，因此打包体积小、免安装、不需要管理员权限。
- **去格式靠 `EmptyClipboard()`** —— 清空剪贴板所有格式后只写 `CF_UNICODETEXT`，比逐个删除格式可靠。
- **热键用 `RegisterHotKey` + `MOD_NOREPEAT`**，避免长按重复触发；注册失败返回 `1409` 时静默跳过而不弹窗。
- **剪贴板监听用 `AddClipboardFormatListener`**（`WM_CLIPBOARDUPDATE`），比老的 `SetClipboardViewer` 稳定，且能自动应对资源管理器重启。
- **模拟粘贴前先显式抬起修饰键**，否则 `Ctrl+Shift+V` 的 Shift 残留会导致粘出错误结果。
- **手写 PNG 编解码**（`struct` + `zlib`，含 0~4 号 filter 与 Paeth 预测器）替代 Pillow。注意剪贴板位图的 alpha 通道常全为 0，直接保存会得到全透明图，需在检测到全零时补齐为不透明。
- **历史粘贴热键避开 Office**：`Alt+1~9` 是快速访问工具栏、`Ctrl+Alt+1~3` 是 Word 标题样式、`Ctrl+Shift+1~6` 是 Excel 数字格式，故选用无冲突的 `Alt+Shift+数字`。

---

## 八、许可证

[MIT](LICENSE) —— 可自由使用、修改、商用，只需保留版权声明。

