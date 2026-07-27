"""真实学术 API 客户端 — CoE 4 层引用核验的数据层。
带磁盘缓存 + 超时 + 熔断(连续失败则短路,照 ARC 的 circuit breaker)。
仅用标准库 urllib,零依赖。生产可替换为 httpx + Semantic Scholar(需 key)。"""
from __future__ import annotations
import json, re, time, hashlib, urllib.request, urllib.parse, os, tempfile, xml.etree.ElementTree as ET

_CACHE_DIR = os.environ.get("COE_CACHE") or os.path.join(tempfile.gettempdir(), "coe_cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
_UA = {"User-Agent": "f3-coe/0.1 (mailto:research@opensci.dev)"}
_fails = {"arxiv": 0, "crossref": 0, "openalex": 0}
_BREAK = int(os.environ.get("COE_BREAK", "4"))   # 连续失败 >= 4 触发熔断

# Transient failures get retried before they are recorded as "I cannot see".
# 瞬时失败先重试,再被记为「我看不到」。
#
# This does NOT move the fabrication / verification_gap line. An exhausted retry
# still returns unknown — never a verdict. What changes is how often a single
# network blip *manufactures* an unknown, and unknowns are the input that whole
# distinction is computed from. Fewer spurious unknowns is strictly better: it can
# never turn a real citation into a fabricated one, only stop a real one from being
# mislabelled unverifiable.
# 这不移动 fabrication / verification_gap 的分界线。重试耗尽仍然返回未知,绝不会
# 变成判定。改变的是一次网络抖动**制造**未知的频率 —— 而整个区分正是以未知为输入。
# 少一些虚假的未知严格更好:它不可能把真引用变成捏造,只能避免真引用被误标为无法核验。
#
# Retry and the breaker threshold trade off against each other: with 2 retries, one
# breaker failure now costs 3 attempts, so _BREAK=4 buys ~12 attempts of patience
# where it used to buy 4. The threshold itself therefore does not need raising —
# raising it would only lengthen the time wasted on a service that is genuinely down.
# 重试与熔断阈值互为代偿:有 2 次重试后,一次熔断计数要花 3 次尝试,于是 _BREAK=4
# 现在买到的耐心约等于过去的 12 次。阈值本身因此不必上调 —— 上调只会延长在一个
# 真正宕掉的服务上浪费的时间。
_RETRY = int(os.environ.get("COE_RETRY", "2"))
_RETRY_BASE = float(os.environ.get("COE_RETRY_BASE", "1.0"))


def _worth_retry(code: int) -> bool:
    """429 (rate limited) and 5xx (server-side) may succeed later; other 4xx will not.
    429(限流)与 5xx(服务端)稍后可能成功;其他 4xx 不会 —— 重试它们只是加重限流。
    404/410 never reach here: they are handled as authoritative denials first.
    404/410 走不到这里:它们先被当作权威否定处理掉了。"""
    return code == 429 or 500 <= code < 600


def _retry_after(e) -> float | None:
    """Honour the service's own Retry-After when it gives one. 服务方给了就照它的来。"""
    try:
        v = e.headers.get("Retry-After")
        return min(float(v), 30.0) if v else None
    except Exception:
        return None

# arXiv 官方 API 指南要求请求间隔 >= 3 秒。连发会被限流,
# 被限流时 check_arxiv 返回 None(未知)—— 校验器据此报 manual 而非 reject,
# 行为正确,但会让依赖确定答案的调用方拿不到结论。
# 缓存命中不计入限速(不产生实际请求)。
_MIN_INTERVAL = {"arxiv": float(os.environ.get("COE_ARXIV_MIN_INTERVAL", "3.0")),
                 "crossref": float(os.environ.get("COE_CROSSREF_MIN_INTERVAL", "0.5")),
                 # OpenAlex 无 API key 时限流较紧;不节流会连续失败并打开熔断,
                 # 使「索引未覆盖」被误报为「网络未知」。
                 "openalex": float(os.environ.get("COE_OPENALEX_MIN_INTERVAL", "1.0"))}
_last_call = {"arxiv": 0.0, "crossref": 0.0, "openalex": 0.0}


def _throttle(svc: str) -> None:
    """Respect the service's minimum request interval. 遵守服务方的最小请求间隔。"""
    gap = _MIN_INTERVAL.get(svc, 0.0)
    if gap <= 0:
        return
    wait = gap - (time.time() - _last_call[svc])
    if wait > 0:
        time.sleep(wait)
    _last_call[svc] = time.time()

def _cache_path(key: str) -> str:
    return os.path.join(_CACHE_DIR, hashlib.sha256(key.encode()).hexdigest()[:20] + ".json")

def _get(url: str, svc: str, timeout: int = 15):
    if _fails[svc] >= _BREAK:
        return None, "circuit_open"
    cp = _cache_path(url)
    if os.path.exists(cp):
        cached = json.load(open(cp))
        # 缓存回放必须保留"权威否定"语义,否则第二次查询会退化为"未知"
        return cached, ("not_found" if cached.get("not_found") else "cache")
    reason = "error:unknown"
    for attempt in range(_RETRY + 1):
        _throttle(svc)      # 缓存未命中才走到这里,此时才需要限速;每次重试同样遵守
        try:
            req = urllib.request.Request(url, headers=_UA)
            raw = urllib.request.urlopen(req, timeout=timeout).read().decode(errors="replace")
            _fails[svc] = 0
            data = {"raw": raw}
            json.dump(data, open(cp, "w"))
            return data, "live" if attempt == 0 else f"live_after_retry{attempt}"
        except urllib.error.HTTPError as e:
            # 关键区分(可达性):404/410 是登记处**成功应答的否定结论** —— 权威地告诉我们"不存在",
            # 不是服务故障,绝不能计入熔断失败,也绝不重试。否则连查几个捏造引用就会打开熔断,
            # 系统随即丧失"判定捏造"的能力,一切退化为 unresolved,且判定依赖调用顺序。
            if e.code in (404, 410):
                _fails[svc] = 0
                json.dump({"raw": None, "not_found": True}, open(cp, "w"))
                return {"raw": None, "not_found": True}, "not_found"
            reason = f"http_error:{e.code}"
            if not _worth_retry(e.code) or attempt == _RETRY:
                break
            time.sleep(_retry_after(e) or _RETRY_BASE * (2 ** attempt))
        except Exception as e:
            reason = f"error:{type(e).__name__}"
            if attempt == _RETRY:
                break
            time.sleep(_RETRY_BASE * (2 ** attempt))

    # One exhausted call counts as ONE breaker failure, not one per attempt —
    # otherwise retrying would open the breaker three times faster than not retrying.
    # 一次「重试耗尽」只计一次熔断失败,而非每次尝试各计一次 ——
    # 否则重试反而会让熔断打开得比不重试快三倍。
    _fails[svc] += 1
    return None, reason if _RETRY == 0 else f"{reason}:exhausted"

_ARXIV_RE = re.compile(r"\b(\d{4}\.\d{4,5})(v\d+)?\b")
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")

def check_arxiv(arxiv_id: str):
    """Layer 1:arXiv ID 是否真实存在。返回 (exists, title)。"""
    m = _ARXIV_RE.search(arxiv_id or "")
    if not m:
        return False, None
    aid = m.group(1)
    data, src = _get(f"https://export.arxiv.org/api/query?id_list={aid}", "arxiv")
    if not data:
        return None, None  # 未知(熔断/网络)——不等于不存在
    try:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(data["raw"])
        entry = root.find("a:entry", ns)
        if entry is None:
            return False, None
        title = (entry.find("a:title", ns).text or "").strip()
        # arXiv 对不存在的 id 也返回一个空 entry;用 id 里是否含该号判定
        eid = (entry.find("a:id", ns).text or "")
        return (aid in eid), (title if aid in eid else None)
    except Exception:
        return None, None

def check_doi(doi: str):
    """Layer 2:CrossRef(失败回落 DataCite)DOI 是否解析。返回 (exists, title)。"""
    m = _DOI_RE.search(doi or "")
    if not m:
        return False, None
    d = m.group(1).rstrip(".")
    data, src = _get(f"https://api.crossref.org/works/{urllib.parse.quote(d)}", "crossref")
    denied = False
    if data and data.get("raw"):
        try:
            j = json.loads(data["raw"])
            t = j["message"].get("title", [""])
            return True, (t[0] if t else "")
        except Exception:
            pass
    denied = denied or (src == "not_found")
    # DataCite 回落
    data2, src2 = _get(f"https://api.datacite.org/dois/{urllib.parse.quote(d)}", "crossref")
    if data2 and data2.get("raw"):
        try:
            j = json.loads(data2["raw"])
            return True, (j["data"]["attributes"].get("titles", [{}])[0].get("title", ""))
        except Exception:
            pass
    denied = denied or (src2 == "not_found")
    if denied:
        return False, None            # 两家登记处都权威否定 -> 确证不存在
    return None, None                 # 网络/熔断 -> 未知,不得判为捏造

def match_openalex(title: str):
    """Layer 3:OpenAlex 标题匹配(Semantic Scholar 的可替换等价物,无需 key)。
    返回 (matched, best_title, score)。score = 标题 token 重合度。"""
    if not title:
        return False, None, 0.0
    q = urllib.parse.quote(title[:200])
    data, src = _get(f"https://api.openalex.org/works?search={q}&per_page=1", "openalex")
    if not data:
        return None, None, 0.0
    try:
        j = json.loads(data["raw"])
        results = j.get("results", [])
        if not results:
            return False, None, 0.0
        best = results[0].get("title", "") or ""
        score = _token_overlap(title, best)
        return (score >= 0.6), best, round(score, 3)
    except Exception:
        return None, None, 0.0

def _token_overlap(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
