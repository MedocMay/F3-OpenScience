"""Claim 抽取 — 从 draft 里抽出 atomic claims(引用型 / 数字型)。
真实实现:引用型认 arXiv ID / DOI;数字型认"结果性数字"(带 % 或 = 或 accuracy/improve 等语境)。"""
import re
from . import apis

_NUM_CTX = re.compile(r"([^.。\n]*?(\d+\.\d+|\d+\s*%)[^.。\n]*)", re.I)  # 仅小数/百分号,排除计数
_RESULT_HINT = re.compile(r"(accuracy|f1|score|improv|reduc|increase|decrease|gain|auc|precision|recall|bleu|error|提升|下降|准确)", re.I)

def extract_claims(draft: str, provided: list | None = None) -> list:
    claims = list(provided or [])
    seen = {(c.get("arxiv_id"), c.get("doi"), c.get("text")) for c in claims}
    # 引用型:从正文扫 arXiv ID / DOI
    for m in apis._ARXIV_RE.finditer(draft or ""):
        aid = m.group(1)
        if not any(c.get("arxiv_id") == aid for c in claims):
            ctx = _window(draft, m.start())
            claims.append({"id": f"cite-arxiv-{aid}", "type": "citation", "arxiv_id": aid, "text": ctx})
    for m in apis._DOI_RE.finditer(draft or ""):
        doi = m.group(1).rstrip(".")
        if not any(c.get("doi") == doi for c in claims):
            ctx = _window(draft, m.start())
            claims.append({"id": f"cite-doi-{doi[-8:]}", "type": "citation", "doi": doi, "text": ctx})
    # 数字型:先屏蔽引用标记 / arXiv ID / DOI,避免把 ID 里的小数误当结果数字
    masked = re.sub(r"\[cite-[^\]]*\]", " ", draft or "")
    masked = apis._ARXIV_RE.sub(" ", masked)
    masked = apis._DOI_RE.sub(" ", masked)
    for m in _NUM_CTX.finditer(masked):
        sent = m.group(1).strip()
        _v = m.group(2).replace("%", "").strip()
        if _RESULT_HINT.search(sent) and not any(c.get("type") == "number" and _v == str(c.get("value","")) for c in claims):
            val = m.group(2).replace("%", "").strip()
            claims.append({"id": f"num-{m.start()}", "type": "number", "value": val, "text": sent})
    return claims

def _window(s: str, i: int, w: int = 80) -> str:
    return s[max(0, i - w): i + w].replace("\n", " ").strip()
