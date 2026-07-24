#!/usr/bin/env python3
"""Regenerate the architecture and run-sequence diagrams.

Usage:
    python3 docs/assets/make_diagrams.py

Produces (in docs/assets/):
    architecture-layers.png / architecture-layers.zh-CN.png
    run-sequence.png       / run-sequence.zh-CN.png

Note: CJK text requires a font with CJK glyphs. We use Noto Sans CJK and fail
loudly if it is missing — silently falling back produces tofu boxes (□□□),
which is how the previous version of these diagrams got shipped broken.
"""
from __future__ import annotations
import os, sys
from PIL import Image, ImageDraw, ImageFont

# ---- palette (matches the project's docs) ----
INK   = "#09141A"; PANEL = "#0E1A20"; PANEL2 = "#122029"
LINE  = "#22414C"; SOFT  = "#16262D"
TEXT  = "#E9E5D9"; DIM   = "#9CB1B7"; MUTE = "#6B848C"
GOLD  = "#D9A441"; AZURE = "#5FA8E0"; ROSE = "#DB7BA6"
CORAL = "#E36A48"; TEAL  = "#3FAE8C"; PERI = "#8A8FE6"

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]

def _font_path() -> str:
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit(
        "✗ No CJK-capable font found. Install one, e.g.:\n"
        "    Debian/Ubuntu: sudo apt install fonts-noto-cjk\n"
        "    macOS/Windows: PingFang / Microsoft YaHei are used automatically\n"
        "  Rendering without a CJK font produces tofu boxes (□□□)."
    )

FP = _font_path()
_cache: dict[tuple[int, int], ImageFont.FreeTypeFont] = {}

def F(size: int, index: int = 0):
    key = (size, index)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(FP, size, index=index)
    return _cache[key]

def rrect(d, box, radius, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def text(d, xy, s, size=15, fill=TEXT, bold=False, anchor=None):
    d.text(xy, s, font=F(size, 2 if bold else 0), fill=fill, anchor=anchor)

def tw(d, s, size=15, bold=False) -> int:
    return int(d.textlength(s, font=F(size, 2 if bold else 0)))


# ══════════════════════════════════════════════════════════════════
# Diagram 1 — layered architecture
# ══════════════════════════════════════════════════════════════════
ARCH = {
    "en": {
        "title": "F3-OpenScience · Layered Architecture",
        "sub": "OpenScience breadth · ai4s delivery · EvoScientist memory · CoE+ARC verification (self-built)",
        "moat": "MOAT",
        "legend": [("OpenScience", CORAL), ("ai4s Desktop", TEAL),
                   ("EvoScientist", PERI), ("CoE + ARC (self-built)", ROSE)],
        "layers": [
            ("①", "Delivery · Shell", "Tauri desktop (Win/mac/Linux) · auditable workspace · artifact per stage", "ai4s", TEAL),
            ("②", "Execution · Sandbox", "hardened sandbox · env scrubbing · rlimits · optional network isolation", "ARC / ai4s", ROSE),
            ("③", "Model · Inference", "per-request routing · 8 providers · BYOK · local models (data stays home)", "OpenScience", CORAL),
            ("④", "Capability · Data", "skills · scientific DBs · MCP connectors · unified registry", "OpenScience + ai4s", CORAL),
            ("⑤", "Orchestration · Harness", "single state machine · AutonomyLevel L0–L6 · gate engine", "OpenScience", GOLD),
            ("⑥⑦", "Agents · Memory", "RA / EA / EMA roles · dual persistent memory (ideation + experiment)", "EvoScientist", PERI),
        ],
        "moat_layer": ("⑧", "Trust · Verification Kernel  +  Cross-user Flywheel", [
            "CoE Audit Kernel — every claim must carry an evidence chain; no evidence → reject",
            "Citations: arXiv ID → CrossRef/DataCite → OpenAlex → LLM relevance",
            "Numbers: traceable to run log, or recomputable via derivation",
            "Physics: dimensions / value range · mass conservation · valence limits  (index-independent)",
        ]),
        "store": ("Experience store · local → team → global", [
            "private-by-default · opt-in sharing · revocable · de-identified patterns only",
            "★ only `fabrication` may constrain generation; `verification_gap` becomes a capability backlog",
        ]),
        "right": [("Pre-signoff", "GATE", GOLD), ("verified?", "", DIM),
                  ("↓ no → blocked", "", CORAL), ("↓ yes", "", TEAL),
                  ("flywheel", "writeback", ROSE), ("consent?", "→ global", PERI),
                  ("sign", "→ package", GOLD)],
    },
    "zh": {
        "title": "F3-OpenScience · 分层架构",
        "sub": "OpenScience 给广度 · ai4s 给可信交付 · EvoScientist 给记忆 · CoE+ARC 校验内核自研",
        "moat": "护城河",
        "legend": [("OpenScience", CORAL), ("ai4s Desktop", TEAL),
                   ("EvoScientist", PERI), ("CoE + ARC 自研", ROSE)],
        "layers": [
            ("①", "交付 · 壳层", "Tauri 桌面(Win/mac/Linux)· 可审计工作区 · 每阶段落地 artifact", "ai4s 复用", TEAL),
            ("②", "执行 · 沙箱层", "强隔离沙箱 · 环境擦除 · 资源限额 · 可选网络隔离", "ARC / ai4s", ROSE),
            ("③", "模型 · 推理层", "per-request 路由 · 8 个 provider · BYOK · 本地模型(数据不出域)", "OpenScience 复用", CORAL),
            ("④", "能力 · 数据层", "技能库 · 科学数据库 · MCP 连接器 · 统一注册表", "OpenScience + ai4s", CORAL),
            ("⑤", "编排 · harness", "单条状态机 · 自主度 L0–L6 · gate 引擎", "OpenScience 改造", GOLD),
            ("⑥⑦", "智能体 · 记忆", "RA / EA / EMA 角色 · 双持久记忆(构思 + 实验)", "EvoScientist 复现", PERI),
        ],
        "moat_layer": ("⑧", "信任 · 校验内核  +  跨用户飞轮", [
            "CoE 审计内核 —— 每条论断必须挂证据链,无据即拒",
            "引用:arXiv ID → CrossRef/DataCite → OpenAlex → LLM 相关性",
            "数字:必须在运行日志有据,或可由推导式重算",
            "物理:量纲 / 取值域 · 质量守恒 · 价键上限  (与索引无关)",
        ]),
        "store": ("经验库 · local → team → global", [
            "默认仅本地 · 用户主动共享 · 可撤回 · 只上脱敏后的抽象模式",
            "★ 只有「确证捏造」可约束生成;「校验缺口」转为能力建设待办",
        ]),
        "right": [("署名前", "GATE", GOLD), ("校验全绿?", "", DIM),
                  ("↓ 否 → 阻断", "", CORAL), ("↓ 是", "", TEAL),
                  ("飞轮", "回写", ROSE), ("是否贡献?", "→ global", PERI),
                  ("确认署名", "→ 可复现包", GOLD)],
    },
}

def draw_architecture(lang: str, out: str):
    L = ARCH[lang]
    W, H = 1560, 1180
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)

    text(d, (54, 40), L["title"], 30, TEXT, bold=True)
    text(d, (54, 84), L["sub"], 14, MUTE)

    # legend
    x = 54
    for name, col in L["legend"]:
        d.rounded_rectangle([x, 118, x + 13, 131], radius=3, fill=col)
        text(d, (x + 21, 116), name, 13, DIM)
        x += tw(d, name, 13) + 60

    LX, LW = 54, 1180          # layer box
    RX, RW = 1266, 240         # right rail
    y = 156

    for num, name, desc, src, col in L["layers"]:
        h = 66
        rrect(d, [LX, y, LX + LW, y + h], 10, fill=PANEL, outline=col, width=2)
        text(d, (LX + 20, y + 12), f"{num}  {name}", 16, col, bold=True)
        text(d, (LX + 20, y + 38), desc, 13, DIM)
        text(d, (LX + LW - 20 - tw(d, src, 12), y + 40), src, 12, MUTE)
        y += h + 10

    # ---- moat layer (emphasised) ----
    num, name, lines = L["moat_layer"]
    h = 40 + 24 * len(lines)
    rrect(d, [LX, y, LX + LW, y + h], 12, fill=PANEL2, outline=GOLD, width=3)
    text(d, (LX + 20, y + 14), f"{num}  {name}", 18, GOLD, bold=True)
    badge = L["moat"]
    bw = tw(d, badge, 12, bold=True) + 22
    rrect(d, [LX + LW - bw - 16, y + 14, LX + LW - 16, y + 38], 6, fill=GOLD)
    text(d, (LX + LW - bw - 5, y + 18), badge, 12, INK, bold=True)
    yy = y + 46
    for ln in lines:
        col = GOLD if ln.strip().startswith(("Physics", "物理")) else DIM
        text(d, (LX + 30, yy), "· " + ln, 13, col)
        yy += 24
    moat_y = y
    y += h + 10

    # ---- experience store ----
    title, lines = L["store"]
    h = 36 + 22 * len(lines)
    d.rounded_rectangle([LX, y, LX + LW, y + h], radius=10, fill=SOFT, outline=GOLD, width=1)
    text(d, (LX + 20, y + 12), title, 15, GOLD, bold=True)
    yy = y + 38
    for ln in lines:
        text(d, (LX + 30, yy), ln, 12.5 and 13, PERI if ln.startswith("★") else DIM)
        yy += 22
    y += h

    # ---- right rail: the signing gate flow ----
    ry = 156
    d.rounded_rectangle([RX - 12, 148, RX + RW + 12, y + 6], radius=12, outline=LINE, width=1)
    for a, b, col in L["right"]:
        label = f"{a} {b}".strip()
        hh = 40
        rrect(d, [RX, ry, RX + RW, ry + hh], 8, fill=PANEL, outline=col, width=1)
        text(d, (RX + RW / 2, ry + hh / 2), label, 13, col, anchor="mm")
        ry += hh + 16

    # connector from moat to rail
    d.line([LX + LW, moat_y + 40, RX, moat_y + 40], fill=GOLD, width=2)

    im.save(out)
    return out


# ══════════════════════════════════════════════════════════════════
# Diagram 2 — run sequence
# ══════════════════════════════════════════════════════════════════
SEQ = {
    "en": {
        "title": "A single run · sequence (topic → verify → signable package)",
        "sub": "AutonomyLevel L1–L2 · pre-signoff GATE cannot be auto-approved · dashed = external API / cross-process",
        "actors": [("Shell / User", TEAL), ("Orchestrator", GOLD), ("Pipeline", CORAL),
                   ("CoE Kernel", ROSE), ("Memory", PERI), ("External APIs", MUTE)],
        "steps": [
            ("msg", 0, 1, "research direction + AutonomyLevel", TEAL),
            ("self", 1, None, "GATE ① confirm topic", GOLD),
            ("msg", 1, 4, "query experience store (fabrication patterns only)", PERI),
            ("msg", 1, 2, "run state machine", GOLD),
            ("msg", 2, 5, "literature: real arXiv search", CORAL, True),
            ("self", 2, None, "hypothesis (with exploration quota) + code", CORAL),
            ("note", None, None, "Exploration budget: low-prior hypotheses get a mandatory quota — but no lower evidence bar", AZURE),
            ("self", 1, None, "GATE ② confirm experiment design", GOLD),
            ("self", 2, None, "sandboxed execution (env scrubbed, rlimits)", CORAL),
            ("msg", 2, 3, "draft + claims + run log", CORAL),
            ("note", None, None, "CoE Audit Kernel: extract atomic claims → attach evidence chain → verify", ROSE),
            ("msg", 3, 5, "citations: arXiv → CrossRef/DataCite → OpenAlex", ROSE, True),
            ("self", 3, None, "numbers: log match or derivation recompute", ROSE),
            ("self", 3, None, "physics: dimensions · conservation · valence  (no index needed)", GOLD),
            ("msg", 3, 1, "verification_report (per-claim verdict) + all_green", ROSE),
            ("self", 1, None, "GATE ③ pre-signoff  (hard — cannot be skipped)", GOLD),
            ("note", None, None, "all_green? no → blocked, list rejects;  yes → proceed", GOLD),
            ("msg", 1, 4, "flywheel: write back  fabrication → constraint · gap → backlog", PERI),
            ("msg", 1, 0, "consent: contribute this lesson?", PERI),
            ("msg", 1, 4, "agree → de-identify + quorum (≥2 contributors) → promote to global", PERI, True),
            ("msg", 1, 0, "human confirms signature", GOLD),
            ("out", None, None, "Reproducible package = draft + code + env + data sources + verification report + repro.sh", TEAL),
        ],
    },
    "zh": {
        "title": "一次完整 run · 时序(题目 → 校验 → 可署名包)",
        "sub": "自主度 L1–L2 · 署名前 GATE 不可自动跳过 · 虚线 = 外部 API / 跨进程",
        "actors": [("壳 / 用户", TEAL), ("Orchestrator", GOLD), ("Pipeline", CORAL),
                   ("CoE 校验内核", ROSE), ("经验库", PERI), ("外部 API", MUTE)],
        "steps": [
            ("msg", 0, 1, "研究方向 + 自主度", TEAL),
            ("self", 1, None, "GATE ① 题目确认", GOLD),
            ("msg", 1, 4, "查经验库(只取「确证捏造」类)", PERI),
            ("msg", 1, 2, "驱动 state-machine", GOLD),
            ("msg", 2, 5, "literature:真实 arXiv 检索", CORAL, True),
            ("self", 2, None, "hypothesis(含探索配额)+ code 生成", CORAL),
            ("note", None, None, "探索预算:低先验假设有强制配额 —— 但证据标准不降低", AZURE),
            ("self", 1, None, "GATE ② 实验设计确认", GOLD),
            ("self", 2, None, "沙箱执行(环境擦除 · 资源限额)", CORAL),
            ("msg", 2, 3, "draft + claims + 运行日志", CORAL),
            ("note", None, None, "CoE 审计内核:抽 atomic claim → 挂证据链 → 逐条核验", ROSE),
            ("msg", 3, 5, "引用:arXiv → CrossRef/DataCite → OpenAlex", ROSE, True),
            ("self", 3, None, "数字:日志命中 或 推导式重算", ROSE),
            ("self", 3, None, "物理:量纲 · 守恒 · 价键  (不查任何索引)", GOLD),
            ("msg", 3, 1, "verification_report(逐条判定)+ all_green", ROSE),
            ("self", 1, None, "GATE ③ 署名前(hard,不可跳过)", GOLD),
            ("note", None, None, "all_green? 否 → 阻断并列出未过项;  是 → 继续", GOLD),
            ("msg", 1, 4, "飞轮回写:捏造 → 生成约束 · 缺口 → 能力待办", PERI),
            ("msg", 1, 0, "consent:是否贡献这条经验?", PERI),
            ("msg", 1, 4, "同意 → 脱敏 + 质量门(≥2 贡献者)→ 晋升 global", PERI, True),
            ("msg", 1, 0, "人工确认署名", GOLD),
            ("out", None, None, "可复现包 = 草稿 + 代码 + 环境 + 数据清单 + 校验报告 + repro.sh", TEAL),
        ],
    },
}

def draw_sequence(lang: str, out: str):
    L = SEQ[lang]
    actors = L["actors"]
    n = len(actors)
    W = 1740
    left, right = 100, W - 130
    span = (right - left) / (n - 1)
    xs = [left + i * span for i in range(n)]

    row_h, top = 46, 210
    H = top + row_h * len(L["steps"]) + 90
    im = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(im)

    text(d, (54, 38), L["title"], 27, TEXT, bold=True)
    text(d, (54, 78), L["sub"], 13, MUTE)

    # lifelines + headers
    for i, (name, col) in enumerate(actors):
        w = tw(d, name, 14, bold=True) + 34
        rrect(d, [xs[i] - w / 2, 120, xs[i] + w / 2, 156], 8, fill=PANEL, outline=col, width=2)
        text(d, (xs[i], 138), name, 14, col, bold=True, anchor="mm")
        for yy in range(160, H - 40, 9):
            d.line([xs[i], yy, xs[i], yy + 4], fill=LINE, width=1)

    def arrow(x0, x1, y, col, dashed=False):
        if dashed:
            step, xx = 11, min(x0, x1)
            while xx < max(x0, x1):
                d.line([xx, y, min(xx + 6, max(x0, x1)), y], fill=col, width=2)
                xx += step
        else:
            d.line([x0, y, x1, y], fill=col, width=2)
        s = 8 if x1 > x0 else -8
        d.polygon([(x1, y), (x1 - s, y - 5), (x1 - s, y + 5)], fill=col)

    y = top
    for step in L["steps"]:
        kind = step[0]
        if kind == "note":
            _, _, _, msg, col = step
            w = tw(d, msg, 13) + 40
            x0 = (W - w) / 2
            rrect(d, [x0, y - 15, x0 + w, y + 17], 8, fill=PANEL2, outline=col, width=1)
            text(d, (W / 2, y + 1), msg, 13, col, anchor="mm")
        elif kind == "out":
            _, _, _, msg, col = step
            w = tw(d, msg, 14, bold=True) + 48
            rrect(d, [54, y - 17, 54 + w, y + 19], 9, fill=SOFT, outline=col, width=2)
            text(d, (78, y + 1), msg, 14, col, bold=True, anchor="lm")
        elif kind == "self":
            _, a, _, msg, col = step
            x = xs[a]
            d.line([x, y - 8, x + 46, y - 8], fill=col, width=2)
            d.line([x + 46, y - 8, x + 46, y + 8], fill=col, width=2)
            arrow(x + 46, x + 2, y + 8, col)
            text(d, (x + 60, y - 8), msg, 13, col, anchor="lm")
        else:
            dashed = len(step) > 5 and step[5]
            _, a, b, msg, col = step[:5]
            x0, x1 = xs[a], xs[b]
            arrow(x0, x1, y, col, dashed)
            mid = (x0 + x1) / 2
            text(d, (mid, y - 13), msg, 13, col, anchor="mm")
        y += row_h

    im.save(out)
    return out


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    outs = [
        draw_architecture("en", os.path.join(here, "architecture-layers.png")),
        draw_architecture("zh", os.path.join(here, "architecture-layers.zh-CN.png")),
        draw_sequence("en", os.path.join(here, "run-sequence.png")),
        draw_sequence("zh", os.path.join(here, "run-sequence.zh-CN.png")),
    ]
    for o in outs:
        print("✓", os.path.relpath(o, here), Image.open(o).size)
