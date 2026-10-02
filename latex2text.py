# -*- coding: utf-8 -*-
"""
latex2text —— 把 LaTeX 数学公式转成可直接粘贴到 PPT / Word 的纯文本与 Unicode 符号。

设计原则：
  1. 能转成 Unicode 符号的，一律转成符号（α × ≤ ∑ √ ² 等）。
  2. 转不成的，退化为可读的线性写法（\\frac{a}{b} -> a/b，x^{n+1} -> x^(n+1)）。
  3. 纯文本里没有 LaTeX 特征时不做任何改动，避免误伤正常文本（如 Windows 路径 C:\\Users）。

支持范围：
  - 数学模式定界符：$...$  $$...$$  \\(...\\)  \\[...\\]
  - 希腊字母、运算/关系/箭头/大型运算符、花体字母等数百个符号
  - 上下标：x^2 -> x²，x_i -> xᵢ，x^{n+1} -> x^(n+1)
  - 结构命令：\\frac \\sqrt \\binom \\left...\\right 等
  - 文本包装命令：\\text \\textbf \\mathrm \\mathbf \\boxed 等（提取内容）
  - 重音命令：\\hat \\bar \\vec \\dot \\tilde（组合字符）
  - 转义字符：\\% \\_ \\& \\# \\$ \\{ \\}
  - 环境命令：\\begin{...} \\end{...}（删除，内容保留）
"""

import re

# ============================================================ 符号表

SYMBOLS = {
    # ---------- 希腊字母（小写） ----------
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "omicron": "ο", "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ",
    "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    # ---------- 希腊字母（大写） ----------
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ",
    "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",

    # ---------- 二元运算符 ----------
    "times": "×", "div": "÷", "cdot": "·", "pm": "±", "mp": "∓",
    "ast": "∗", "star": "⋆", "circ": "∘", "bullet": "•",
    "oplus": "⊕", "ominus": "⊖", "otimes": "⊗", "oslash": "⊘", "odot": "⊙",
    "cap": "∩", "cup": "∪", "sqcap": "⊓", "sqcup": "⊔",
    "vee": "∨", "lor": "∨", "wedge": "∧", "land": "∧",
    "setminus": "∖", "smallsetminus": "∖", "dagger": "†", "ddagger": "‡",
    "amalg": "⨿", "wr": "≀", "diamond": "◇", "bigtriangleup": "△",
    "bigtriangledown": "▽", "triangleleft": "◁", "triangleright": "▷",

    # ---------- 关系符号 ----------
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "neq": "≠", "ne": "≠", "equiv": "≡", "sim": "∼", "simeq": "≃",
    "approx": "≈", "cong": "≅", "propto": "∝", "ll": "≪", "gg": "≫",
    "subset": "⊂", "supset": "⊃", "subseteq": "⊆", "supseteq": "⊇",
    "subsetneq": "⊊", "supsetneq": "⊋", "in": "∈", "notin": "∉", "ni": "∋",
    "perp": "⊥", "parallel": "∥", "mid": "∣", "nmid": "∤",
    "prec": "≺", "succ": "≻", "preceq": "⪯", "succeq": "⪰",
    "doteq": "≐", "asymp": "≍", "bowtie": "⋈", "models": "⊨",
    "vdash": "⊢", "dashv": "⊣", "smile": "⌣", "frown": "⌢",

    # ---------- 箭头 ----------
    "rightarrow": "→", "to": "→", "leftarrow": "←", "gets": "←",
    "leftrightarrow": "↔", "Rightarrow": "⇒", "Leftarrow": "⇐",
    "Leftrightarrow": "⇔", "uparrow": "↑", "downarrow": "↓",
    "updownarrow": "↕", "Uparrow": "⇑", "Downarrow": "⇓",
    "Updownarrow": "⇕", "mapsto": "↦", "longmapsto": "⟼",
    "longrightarrow": "⟶", "longleftarrow": "⟵",
    "Longrightarrow": "⟹", "Longleftarrow": "⟸",
    "Longleftrightarrow": "⟺", "longleftrightarrow": "⟷",
    "hookrightarrow": "↪", "hookleftarrow": "↩",
    "nearrow": "↗", "searrow": "↘", "swarrow": "↙", "nwarrow": "↖",
    "rightharpoonup": "⇀", "leftharpoonup": "↼",

    # ---------- 大型运算符 ----------
    "sum": "∑", "prod": "∏", "coprod": "∐",
    "int": "∫", "iint": "∬", "iiint": "∭", "oint": "∮",
    "bigcup": "⋃", "bigcap": "⋂", "bigoplus": "⨁", "bigotimes": "⨂",
    "bigodot": "⨀", "bigvee": "⋁", "bigwedge": "⋀", "biguplus": "⨄",
    "bigsqcup": "⨆",

    # ---------- 其他常用符号 ----------
    "infty": "∞", "partial": "∂", "nabla": "∇", "forall": "∀",
    "exists": "∃", "nexists": "∄", "emptyset": "∅", "varnothing": "∅",
    "angle": "∠", "measuredangle": "∡", "triangle": "△", "square": "□",
    "Box": "□", "blacksquare": "■", "blacktriangle": "▲",
    "degree": "°", "prime": "′", "ldots": "…", "dots": "…", "cdots": "⋯",
    "vdots": "⋮", "ddots": "⋱",
    "hbar": "ℏ", "ell": "ℓ", "Re": "ℜ", "Im": "ℑ", "aleph": "ℵ",
    "wp": "℘", "neg": "¬", "lnot": "¬", "top": "⊤", "bot": "⊥",
    "S": "§", "P": "¶", "copyright": "©", "pounds": "£", "euro": "€",
    "yen": "¥", "checkmark": "✓", "therefore": "∴", "because": "∵",
    "surd": "√", "clubsuit": "♣", "diamondsuit": "♢", "heartsuit": "♡",
    "spadesuit": "♠", "flat": "♭", "natural": "♮", "sharp": "♯",
    "imath": "ı", "jmath": "ȷ", "mho": "℧", "Finv": "Ⅎ",

    # ---------- 括号 / 定界符 ----------
    "langle": "⟨", "rangle": "⟩", "lceil": "⌈", "rceil": "⌉",
    "lfloor": "⌊", "rfloor": "⌋", "vert": "|", "Vert": "‖",
    "lVert": "‖", "rVert": "‖", "lvert": "|", "rvert": "|",
    "backslash": "\\",

    # ---------- 转义字符 ----------
    "{": "{", "}": "}", "%": "%", "&": "&", "#": "#",
    "_": "_", "$": "$", "&amp;": "&",

    # ---------- 间距命令 ----------
    ",": "", ";": " ", ":": " ", "!": "", " ": " ",
    "quad": " ", "qquad": "  ", "enspace": " ", "enskip": " ",
    "thinspace": "", "medspace": " ", "thickspace": " ",
    "negthinspace": "", "negmedspace": "", "negthickspace": "",

    # ---------- 换行 ----------
    "\\": "\n",

    # ---------- 数学模式定界符（直接丢弃） ----------
    "(": "", ")": "", "[": "", "]": "",
}

# 直接提取内容、丢弃命令本身
PLAIN_WRAPPERS = {
    "text", "textbf", "textit", "textrm", "textsf", "texttt", "textnormal",
    "textup", "textsl", "textsc", "textmd", "mbox", "hbox", "fbox",
    "mathrm", "mathbf", "mathit", "mathcal", "mathbb", "mathfrak",
    "mathsf", "mathtt", "mathnormal", "boldsymbol", "bm", "operatorname",
    "underline", "emph", "boxed", "displaystyle", "textstyle",
    "scriptstyle", "scriptscriptstyle", "limits", "nolimits",
}

# 重音命令 -> 组合字符
ACCENTS = {
    "hat": "\u0302", "widehat": "\u0302", "bar": "\u0304",
    "overline": "\u0304", "tilde": "\u0303", "widetilde": "\u0303",
    "dot": "\u0307", "ddot": "\u0308", "vec": "\u20d7",
    "check": "\u030c", "breve": "\u0306", "acute": "\u0301",
    "grave": "\u0300", "mathring": "\u030a",
}

# 带参数但直接丢弃的命令（连同参数一起删）
DROP_WITH_ARG = {
    "label", "tag", "ref", "eqref", "nonumber", "notag", "hspace",
    "vspace", "phantom", "hphantom", "vphantom", "color", "textcolor",
    "pagecolor", "fontsize", "setlength", "index", "cite", "hline",
    "cline", "rule", "kern", "mkern",
}

# 分数类命令
FRAC_COMMANDS = {"frac", "dfrac", "tfrac", "cfrac", "genfrac"}

# 定界符映射（\left( 这种）
DELIMS = {"(": "(", ")": ")", "[": "[", "]": "]",
          "|": "|", "{": "{", "}": "}", ".": ""}

# 已知命令全集（用于判断一段文本像不像 LaTeX）
KNOWN_COMMANDS = (set(SYMBOLS) | set(PLAIN_WRAPPERS) | set(ACCENTS)
                  | set(DROP_WITH_ARG))
KNOWN_COMMANDS |= FRAC_COMMANDS | {"sqrt", "binom", "dbinom", "tbinom",
                                   "left", "right", "begin", "end",
                                   "big", "Big", "bigg", "Bigg",
                                   "bigl", "bigr", "Bigl", "Bigr",
                                   "biggl", "biggr", "Biggl", "Biggr",
                                   "displaystyle", "substack", "stackrel"}

# ---------- Unicode 上下标 ----------
SUPERSCRIPT = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ",
}
SUBSCRIPT = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}


def to_superscript(s):
    if not s:
        return ""
    if all(c in SUPERSCRIPT for c in s):
        return "".join(SUPERSCRIPT[c] for c in s)
    if len(s) == 1:
        return "^" + s
    return "^(%s)" % s


def to_subscript(s):
    if not s:
        return ""
    if all(c in SUBSCRIPT for c in s):
        return "".join(SUBSCRIPT[c] for c in s)
    if len(s) == 1:
        return "_" + s
    return "_(%s)" % s


def _needs_paren(s):
    """判断作为分子/分母时是否需要加括号。

    只在**括号外层**出现低优先级运算符时才加，因此：
      a+b        -> 需要    (a+b)/c
      -b ± √(...) -> 需要    (-b ± √(...))/2a
      n(n+1)     -> 不需要  n(n+1)/2      （+ 在括号内）
      P(A)P(B)   -> 不需要  P(A)P(B)/P(C) （纯乘积）
    """
    s = s.strip()
    if len(s) <= 1:
        return False
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth <= 0 and ch in "+-=<>|":
            return True
    return False


def _format_frac(num, den):
    if _needs_paren(num):
        num = "(%s)" % num.strip()
    if _needs_paren(den):
        den = "(%s)" % den.strip()
    return "%s/%s" % (num, den)


# ============================================================ 解析器

class _Parser(object):
    """逐字符扫描的 LaTeX 解析器。"""

    def __init__(self, text):
        self.s = text
        self.n = len(text)
        self.i = 0
        self.stack = []        # 输出片段栈，供 \right 回删尾部空白
        self.env_stack = []    # 环境栈，用于判断是否处于矩阵/对齐环境

    # ---------------- 主循环 ----------------

    def parse(self, stop=None):
        out = []
        self.stack.append(out)
        try:
            while self.i < self.n:
                c = self.s[self.i]
                if stop is not None and c == stop:
                    break
                if c == "\\":
                    out.append(self.parse_command())
                elif c == "{":
                    self.i += 1
                    inner = self.parse("}")
                    if self.i < self.n and self.s[self.i] == "}":
                        self.i += 1
                    out.append(inner)
                elif c == "}":
                    self.i += 1
                elif c == "$":
                    self.i += 1
                elif c == "^":
                    self.i += 1
                    out.append(to_superscript(self.read_arg()))
                elif c == "_":
                    self.i += 1
                    out.append(to_subscript(self.read_arg()))
                elif c == "~":
                    self.i += 1
                    out.append(" ")
                elif c == "&":
                    # 矩阵 / cases / align 环境里 & 是列分隔符，转成空格更可读
                    self.i += 1
                    out.append("  " if self.env_stack else "&")
                else:
                    out.append(c)
                    self.i += 1
        finally:
            self.stack.pop()
        return "".join(out)

    def trim_trailing_space(self):
        """回删当前输出缓冲区末尾的空白（用于 \\right 前的多余空格）。"""
        if not self.stack:
            return
        cur = self.stack[-1]
        while cur:
            last = cur[-1]
            stripped = last.rstrip()
            if stripped == last:
                break
            cur.pop()
            if stripped:
                cur.append(stripped)
                break

    # ---------------- 命令 ----------------

    def parse_command(self):
        self.i += 1                      # 吃掉反斜杠
        if self.i >= self.n:
            return ""
        c = self.s[self.i]
        if c.isalpha():
            j = self.i
            while j < self.n and self.s[j].isalpha():
                j += 1
            name = self.s[self.i:j]
            self.i = j
        else:
            name = c                  # 单字符命令，如 \, \% \\ \{
            self.i += 1
        return self.apply_command(name)

    def apply_command(self, name):
        # 0) 换行命令：\\ 后面的源码空格在 LaTeX 里会被忽略
        if name == "\\":
            self.skip_space()
            return "\n"

        # 1) 已知符号
        if name in SYMBOLS:
            return SYMBOLS[name]

        # 2) 分数
        if name in FRAC_COMMANDS:
            num = self.read_arg()
            den = self.read_arg()
            return _format_frac(num, den)

        # 3) 根号
        if name == "sqrt":
            index = self.read_optional()
            body = self.read_arg()
            body = "(%s)" % body.strip() if _needs_paren(body) else body
            if index:
                return "%s√%s" % (to_superscript(index), body)
            return "√%s" % body

        # 4) 组合数
        if name in ("binom", "dbinom", "tbinom"):
            top = self.read_arg()
            bottom = self.read_arg()
            return "C(%s, %s)" % (top.strip(), bottom.strip())

        # 5) 文本包装（提取内容）
        if name in PLAIN_WRAPPERS:
            return self.read_arg()

        # 6) 重音
        if name in ACCENTS:
            arg = self.read_arg()
            if len(arg) == 1:
                return arg + ACCENTS[name]
            return arg

        # 7) 定界符缩放命令
        #    \right 前面的空格要回删，\left 后面的空格要吞掉，
        #    否则 \left( \frac{1}{2} \right)^n 会输出 "( 1/2 )ⁿ"
        if name in ("right", "middle"):
            self.trim_trailing_space()
            return self.read_delimiter()
        if name in ("left", "big", "Big", "bigg", "Bigg",
                    "bigl", "bigr", "Bigl", "Bigr",
                    "biggl", "biggr", "Biggl", "Biggr"):
            delim = self.read_delimiter()
            self.skip_space()
            return delim

        # 8) 环境命令
        if name in ("begin", "end"):
            env = self.read_arg().strip()
            self.skip_space()
            if name == "begin":
                self.env_stack.append(env)
            elif self.env_stack:
                self.env_stack.pop()
            return ""

        # 9) 带参数且整体丢弃
        if name in DROP_WITH_ARG:
            self.read_arg()
            return ""

        # 10) 其他已知但无参数的丢弃命令
        if name in ("nonumber", "notag", "noindent", "centering"):
            return ""

        # 11) 未知命令：去掉反斜杠保留命令名，避免信息完全丢失
        return name

    # ---------------- 参数读取 ----------------

    def skip_space(self):
        while self.i < self.n and self.s[self.i] in " \t\n":
            self.i += 1

    def read_arg(self):
        """读取一个参数：{...} 或单个 token。"""
        self.skip_space()
        if self.i >= self.n:
            return ""
        c = self.s[self.i]
        if c == "{":
            self.i += 1
            val = self.parse("}")
            if self.i < self.n and self.s[self.i] == "}":
                self.i += 1
            return val
        if c == "\\":
            return self.parse_command()
        self.i += 1
        return c

    def read_optional(self):
        """读取可选参数 [...]，没有则返回空串。"""
        save = self.i
        self.skip_space()
        if self.i < self.n and self.s[self.i] == "[":
            self.i += 1
            val = self.parse("]")
            if self.i < self.n and self.s[self.i] == "]":
                self.i += 1
            return val
        self.i = save
        return ""

    def read_delimiter(self):
        """读取 \\left 后面的定界符。"""
        self.skip_space()
        if self.i >= self.n:
            return ""
        c = self.s[self.i]
        if c == "\\":
            self.i += 1
            if self.i >= self.n:
                return ""
            d = self.s[self.i]
            if not d.isalpha():
                self.i += 1
                return DELIMS.get(d, d)
            j = self.i
            while j < self.n and self.s[j].isalpha():
                j += 1
            name = self.s[self.i:j]
            self.i = j
            return SYMBOLS.get(name, "")
        self.i += 1
        return DELIMS.get(c, c)


# ============================================================ 对外接口

_LATEX_COMMAND_RE = re.compile(r"\\([a-zA-Z]+)")
_MATH_DOLLAR_RE = re.compile(r"\$[^$\n]{2,}\$")


def looks_like_latex(text):
    """判断一段文本是否包含 LaTeX 特征（用于 auto 模式，避免误伤普通文本）。"""
    if not text:
        return False
    for m in _LATEX_COMMAND_RE.finditer(text):
        if m.group(1) in KNOWN_COMMANDS:
            return True
    if _MATH_DOLLAR_RE.search(text):
        return True
    if "\\(" in text or "\\[" in text or "$$" in text:
        return True
    return False


def latex_to_text(text):
    """把 LaTeX 转成纯文本 / Unicode 符号。"""
    if not text:
        return text
    result = _Parser(text).parse()
    # 清理：合并排版残留的连续空格、去掉行尾空格、压缩多余空行
    result = re.sub(r" {3,}", " ", result)
    result = "\n".join(line.rstrip() for line in result.split("\n"))
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def convert(text, mode="auto"):
    """
    按模式转换。
      mode="off"   : 不转换
      mode="auto"  : 仅当检测到 LaTeX 特征时才转换（默认，最安全）
      mode="always": 总是转换
    """
    if not text or mode == "off":
        return text
    if mode == "always" or looks_like_latex(text):
        return latex_to_text(text)
    return text


if __name__ == "__main__":
    import unicodedata

    samples = [
        (r"$\frac{a}{b}$", "a/b"),
        (r"$x^2 + y^2 = z^2$", "x² + y² = z²"),
        (r"$E = mc^2$", "E = mc²"),
        (r"$\alpha + \beta = \gamma$", "α + β = γ"),
        (r"$\int_0^\infty e^{-x}\,dx$", "∫₀^∞ e^(-x)dx"),
        (r"$\sqrt{x^2 + y^2}$", "√(x² + y²)"),
        (r"$\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$", "(-b ± √(b² - 4ac))/2a"),
        (r"$\sum_{i=1}^{n} i = \frac{n(n+1)}{2}$", "∑ᵢ₌₁ⁿ i = n(n+1)/2"),
        (r"$\lim_{x \to \infty} \frac{1}{x} = 0$", "lim_(x → ∞) 1/x = 0"),
        (r"$\vec{F} = m\vec{a}$", "F⃗ = ma⃗"),
        (r"$\hat{y} = \theta_0 + \theta_1 x_1$", "ŷ = θ₀ + θ₁ x₁"),
        (r"\textbf{结论}：$A \subseteq B$", "结论：A ⊆ B"),
        (r"$A \times B \neq C$", "A × B ≠ C"),
        (r"$\left( \frac{1}{2} \right)^n$", "(1/2)ⁿ"),
        (r"$P(A \mid B) = \frac{P(B \mid A)P(A)}{P(B)}$",
         "P(A ∣ B) = P(B ∣ A)P(A)/P(B)"),
        (r"$\lim_{n \to \infty}\left(1 + \frac{1}{n}\right)^n = e$",
         "lim_(n → ∞)(1 + 1/n)ⁿ = e"),
        (r"$\mathcal{L}\{f(t)\} = \int_0^\infty e^{-st} f(t)\,dt$",
         "L{f(t)} = ∫₀^∞ e^(-st) f(t)dt"),
        (r"$\frac{\partial^2 u}{\partial x^2} + \frac{\partial^2 u}{\partial y^2} = 0$",
         "∂² u/∂ x² + ∂² u/∂ y² = 0"),
        (r"$\begin{cases} x > 0 & \text{正} \\ x < 0 & \text{负} \end{cases}$",
         "x > 0 正\nx < 0 负"),
        (r"$\begin{pmatrix} a & b \\ c & d \end{pmatrix}$", "a b\nc d"),
        # 非 LaTeX 文本必须原样保留
        ("普通的文本，没有公式。", "普通的文本，没有公式。"),
        (r"C:\Users\name\Documents", r"C:\Users\name\Documents"),
        ("价格是 $100 美元", "价格是 $100 美元"),
        ("邮箱 a@b.com，折扣 50% & 免运费", "邮箱 a@b.com，折扣 50% & 免运费"),
    ]

    def norm(s):
        return unicodedata.normalize("NFC", (s or "").strip())

    print("=" * 72)
    print("LaTeX -> 纯文本 转换测试")
    print("=" * 72)
    passed = failed = 0
    for src, expect in samples:
        got = convert(src, "auto")
        ok = norm(got) == norm(expect)
        if ok:
            passed += 1
            flag = "OK  "
        else:
            failed += 1
            flag = "FAIL"
        print("[%s] %s" % (flag, src[:60]))
        print("       得到: %r" % got)
        if not ok:
            print("       期望: %r" % expect)
    print("=" * 72)
    print("通过 %d / %d" % (passed, passed + failed))

    # 真实场景：一段带公式的 AI 回答
    print()
    print("=" * 72)
    print("真实场景演示（从 AI 回答复制的内容）")
    print("=" * 72)
    demo = (
        "根据贝叶斯定理，后验概率计算如下：\n"
        r"$$P(\theta \mid D) = \frac{P(D \mid \theta) P(\theta)}{P(D)}$$" "\n"
        r"其中 $P(\theta)$ 是先验，$P(D \mid \theta)$ 是似然。" "\n"
        r"当 $\alpha = 0.05$ 时，拒绝域为 $|z| > 1.96$。" "\n"
        r"方差公式为 $\sigma^2 = \frac{1}{n}\sum_{i=1}^{n}(x_i - \bar{x})^2$。"
    )
    print("【转换前】")
    print(demo)
    print()
    print("【转换后】")
    print(convert(demo, "always"))
