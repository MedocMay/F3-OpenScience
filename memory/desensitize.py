"""脱敏管线 — global 上行的强门控。只放行"抽象模式",拦截任何原始内容/PII/可识别标识。
规则:模式必须短、且不含 email/DOI/arXiv-id/URL/长自由文本。命中即拒(降级 local)。"""
import re

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_DOI   = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
_ARXIV = re.compile(r"\d{4}\.\d{4,5}")
_URL   = re.compile(r"https?://|www\.")
# MVP 允许的抽象模式白名单(distill 的产物)
_ALLOWED = {"NONEXISTENT_CITATION", "UNSOURCED_RESULT_NUMBER", "FIG_CODE_MISMATCH"}

def desensitize(lesson: dict) -> tuple[bool, str]:
    """返回 (ok, reason)。ok=False 表示含敏感/原始内容,不得上 global。"""
    pat = str(lesson.get("pattern", ""))
    if lesson.get("kind") not in {"fake_cite", "unsourced_num", "fig_code_mismatch"}:
        return False, "unknown_kind"
    if pat in _ALLOWED:
        return True, "ok"
    # 非白名单:严格体检
    if _EMAIL.search(pat): return False, "contains_email"
    if _DOI.search(pat):   return False, "contains_doi"
    if _ARXIV.search(pat): return False, "contains_arxiv_id"
    if _URL.search(pat):   return False, "contains_url"
    if len(pat) > 60:      return False, "too_long_freetext"
    if re.search(r"[\u4e00-\u9fff]{6,}", pat): return False, "contains_raw_cjk_text"
    return True, "ok_generalized"
