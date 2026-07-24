"""机制性命题与新颖论断(R5)—— 补上「对引用和数字之外的一切失明」这个反向缺口。

此前 CoE 只抽取引用型与数字型论断。像
    「我们提出机制 X 导致 Y」「该改进源于 Z 的正则化效应」
这类命题根本不进校验 —— 系统对它们既不拦截也不背书。
结果是:真正的科学主张不在校验范围内,而系统却在为整篇草稿署名。

R5 的立场:**新颖度决定「需要哪种证据基质」,而不是「能否通过」。**

    命题在既有文献中有支撑  -> 可用引用型证据背书
    索引中找不到支撑        -> 必须由计算型证据背书(可复现包 / 推导 / 量纲自洽)

注意第二条不是「更宽松」,而是**换了一种更硬的基质**:
从书目学(有没有人说过)转向计算(能不能被重算与复现)。
这正是让系统能够为「世界允许但模型不熟悉」的东西署名的关键 ——
否则系统只会退化成查重器,永远无法主张新东西。

★ 同时必须防住 R2 的老陷阱:索引里找不到 ≠ 该命题是新的。
   索引覆盖不足与真正新颖在证据上无法区分,因此本模块只报
   `unestablished_in_index`(索引中未见既有支撑),绝不断言 `novel`。
"""
from __future__ import annotations
import re
from . import apis

# 断言性命题的语言标记(保守:宁可漏抽,不可把描述句当成主张)
_ASSERTION = re.compile(
    r"(we (propose|show|demonstrate|find|argue|hypothesize|introduce)"
    r"|our (method|approach|model) (improves|enables|achieves|outperforms)"
    r"|(is|are) (caused by|attributable to|driven by|explained by)"
    r"|(leads? to|results? in|gives? rise to)"
    r"|因此|我们提出|我们证明|源于|导致|归因于)", re.I)

_SENT = re.compile(r"[^.。!?\n]+[.。!?]?")

def extract_mechanism_claims(draft: str, existing: list | None = None) -> list[dict]:
    """从草稿抽取机制性命题。只收带断言标记的句子,且排除已被其它类型覆盖的部分。"""
    existing = existing or []
    seen_text = {c.get("text", "")[:40] for c in existing}
    out = []
    for m in _SENT.finditer(draft or ""):
        s = m.group(0).strip()
        if len(s) < 20 or not _ASSERTION.search(s):
            continue
        # 已被引用/数字型 claim 覆盖的句子不重复抽取
        if any(s[:40] == t for t in seen_text):
            continue
        out.append({
            "id": f"mech-{m.start()}",
            "type": "mechanism",
            "text": s[:300],
        })
    return out

def literature_support(text: str) -> tuple[str, str | None, float]:
    """在文献索引中找该命题的既有支撑。

    返回 (状态, 最佳匹配标题, 相似度):
      supported                -> 索引中存在高度相关的既有工作
      unestablished_in_index   -> 索引中未见支撑(**不等于**该命题是新的)
      unknown                  -> 网络/熔断,无法判断
    """
    if not text:
        return "unknown", None, 0.0
    ok, best, score = apis.match_openalex(text[:200])
    if ok is None:
        return "unknown", None, 0.0
    if ok and score >= 0.35:
        return "supported", best, score
    return "unestablished_in_index", best, score

# 计算型证据可接受的种类:可复现包 / 推导 / 运行日志
_COMPUTATIONAL = {"code+data", "derivation", "log"}

def required_substrate(support_status: str) -> str:
    """由文献支撑状态决定所需证据基质。"""
    return "citation_or_computational" if support_status == "supported" else "computational"

def evidence_satisfies(ev: dict | None, required: str) -> bool:
    if not ev:
        return False
    kind = ev.get("kind")
    if required == "computational":
        return kind in _COMPUTATIONAL
    return kind in (_COMPUTATIONAL | {"citation"})
