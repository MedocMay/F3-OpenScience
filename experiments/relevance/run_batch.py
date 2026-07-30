#!/usr/bin/env python3
"""Does layer 4 tell a misattributed citation from an accurate one?

第 4 层分得清「张冠李戴」和「准确引用」吗?

WHY · 起因
----------
On 2026-07-29, given no retrieved papers, DeepSeek cited arXiv:2305.18290 — a real,
heavily-cited paper (Direct Preference Optimization) — to support a claim about
few-shot classification in data-limited domains, which that paper says nothing
about. The citation was not fabricated. The registry confirms it exists, and an
authoritative registry is therefore useless here: existence and support are
different properties, and only layer 4 covers the second.
2026-07-29,在不给检索结果的情况下,DeepSeek 引用了 arXiv:2305.18290 —— 一篇真实且
被引上万次的论文(DPO)—— 去支撑一个关于数据稀缺领域少样本分类的主张,而那篇论文
对此只字未提。这条引用不是捏造。登记处确认它存在,因此权威登记处在这里帮不上忙:
存在性与支撑性是两种不同的属性,只有第 4 层管后者。

That was n=1, on one pair of texts, and a relevance score of 0.00 could just as
easily have been token non-overlap. This measures it.
那是 n=1、单一文本对,而 0.00 的相关性完全可能只是词不重叠。本实验去测它。

DESIGN · 设计
-------------
Each case pairs a REAL paper with a claim. The accurate claim is drawn from that
paper's own abstract; the misattributed claim is drawn from a DIFFERENT real
paper's abstract. Nothing is invented, so the ground truth is auditable by anyone
who opens the two arXiv links — the label does not rest on the author's word.
每个用例把一篇**真实论文**与一条论断配对。准确引用取自该论文自己的摘要;张冠李戴
取自**另一篇真实论文**的摘要。全部不是编的,所以地面真值任何人打开两个 arXiv 链接
就能复核 —— 标注不依赖作者的一面之词。

READ THE RESULT AS · 结果怎么读
-------------------------------
    false negative  a misattribution that passed        漏放:张冠李戴被放行
    false positive  an accurate citation that was gated 误拒:准确引用被拦

Both matter, and they trade off: a scorer tuned to catch every misattribution will
start gating accurate citations, which is the false-rejection failure this project
exists to avoid. Reporting only one of the two is how a gate gets tuned into
uselessness in either direction.
两者都重要,而且互为代偿:一个调到能抓住每一条张冠李戴的打分器,会开始拦准确引用 ——
那正是本项目要避免的误拒。只报其中一个,是把门控往任一方向调废的标准做法。

USAGE · 用法
------------
    python3 experiments/relevance/run_batch.py            # uses whatever backend is configured
    python3 experiments/relevance/run_batch.py --json out.json

The backend is whatever `coe_kernel.relevance.get_scorer()` returns: an LLM when a
provider is configured, otherwise a token-overlap heuristic that only annotates.
That difference is itself worth measuring — run it both ways.
后端由 `coe_kernel.relevance.get_scorer()` 决定:配了供应商就是 LLM,否则是只标注
不阻断的词重叠启发式。这个差别本身值得测 —— 两种都跑一遍。
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from coe_kernel.relevance import get_scorer          # noqa: E402
from coe_kernel.verify import verify_citation        # noqa: E402

CASES = json.loads((pathlib.Path(__file__).parent / "cases.json").read_text())


def judge(paper: dict, text: str) -> dict:
    r = verify_citation({"id": "rb", "type": "citation",
                         "arxiv_id": paper["arxiv_id"], "text": text})
    return {"status": r["status"],
            "relevance": (r.get("layers") or {}).get("llm_relevance"),
            "low_relevance": r.get("low_relevance", False),
            "reason": r.get("reason")}


def gated(v: dict) -> bool:
    """Did the system actually stop it, rather than merely note it?
    系统真的拦住了,还是只是记了一笔?"""
    return v["status"] != "pass"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", help="write full results here · 结果写到这里")
    args = ap.parse_args()

    backend = type(get_scorer()).__name__
    print(f"relevance backend · 打分后端: {backend}")
    print(f"cases · 用例: {len(CASES)} papers × 2 claims each\n")

    rows, fn, fp = [], [], []
    for c in CASES:
        acc = judge(c, c["accurate"])
        mis = judge(c, c["misattributed"])
        rows.append({"arxiv_id": c["arxiv_id"], "title": c["title"],
                     "accurate": acc, "misattributed": mis,
                     "misattribution_source": c["misattribution_source"]})
        if not gated(mis):
            fn.append(c["arxiv_id"])
        if gated(acc):
            fp.append(c["arxiv_id"])
        m = "GATED " if gated(mis) else "passed"
        a = "GATED " if gated(acc) else "passed"
        print(f"  {c['arxiv_id']:16s} accurate={a}  misattributed={m}   {c['title'][:38]}")

    n = len(CASES)
    print(f"\n  misattributions gated · 张冠李戴被拦 : {n-len(fn)}/{n}"
          f"      missed · 漏放: {len(fn)}")
    print(f"  accurate citations passed · 准确引用通过 : {n-len(fp)}/{n}"
          f"   false-rejected · 误拒: {len(fp)}")
    if fn:
        print(f"      missed: {', '.join(fn)}")
    if fp:
        print(f"      false-rejected: {', '.join(fp)}")

    if backend != "LLMRelevance":
        print("\n  ⚠️  This backend only annotates; it does not gate. A deployment without")
        print("      model credentials lets every misattribution through the signing gate.")
        print("      本后端只标注、不阻断。没有模型凭据的部署会放行每一条张冠李戴。")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(
            {"backend": backend, "n": n, "missed": fn, "false_rejected": fp, "rows": rows},
            ensure_ascii=False, indent=2) + "\n")
        print(f"\n  → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
