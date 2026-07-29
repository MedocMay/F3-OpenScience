"""4 层引用核验 + 数字溯源 + 证据链门控。CoE 的判定核心。"""
import os
import re
from . import apis
from .relevance import get_scorer
from . import derivation as deriv
from . import dimensions as dims
from . import novelty as nov
from . import domains as dom

# Resolved per call, not at import. Binding the scorer at import time made the
# backend depend on which module the test happened to import first — an ordering
# landmine, and one that silently decides whether layer 4 gates or merely annotates.
# 每次调用时解析,而非导入时。导入时绑定会让后端取决于测试恰好先 import 了哪个模块 ——
# 一颗顺序地雷,而且它无声地决定了第 4 层是硬门控还是仅标注。
_SCORER_CACHE: dict = {}


def _scorer():
    key = (os.environ.get("COE_RELEVANCE", ""), os.environ.get("OPENSCI_MODEL", ""))
    if key not in _SCORER_CACHE:
        _SCORER_CACHE[key] = get_scorer()
    return _SCORER_CACHE[key]

REL_THRESHOLD = 0.10   # 相关性下限(heuristic;生产换 LLM 相关性打分)

def verify_citation(claim: dict) -> dict:
    """4 层:arXiv ID -> CrossRef/DataCite DOI -> OpenAlex 标题匹配 -> 相关性。
    存在性任一层过即"存在";都不过=fabricated->reject。存在但相关性低->manual。"""
    layers = {"arxiv_id": None, "crossref_datacite": None, "semantic_scholar": None, "llm_relevance": None}
    resolved_title, exists = None, False

    if claim.get("arxiv_id"):
        ok, title = apis.check_arxiv(claim["arxiv_id"])
        layers["arxiv_id"] = ok
        if ok: exists, resolved_title = True, title
    if not exists and claim.get("doi"):
        ok, title = apis.check_doi(claim["doi"])
        layers["crossref_datacite"] = ok
        if ok: exists, resolved_title = True, title
    # Layer 3:标题匹配(有声明标题或已解析标题时)
    title_for_match = claim.get("title") or resolved_title
    if title_for_match:
        ok, best, score = apis.match_openalex(title_for_match)
        layers["semantic_scholar"] = ok
        if ok and not exists:
            exists, resolved_title = True, best

    if exists is not True:
        unknown = all(v is None for v in [layers["arxiv_id"], layers["crossref_datacite"], layers["semantic_scholar"]])
        if unknown:
            return _claim(claim, "manual", "网络/熔断,存在性未知", layers)
        # 关键分野:哪些基质有权宣告"不存在"?
        #   arXiv ID / DOI 是稠密且权威的登记空间 —— 格式合法却解析不到 = 确证捏造。
        #   OpenAlex 标题匹配只是索引覆盖 —— 匹配不到 ≠ 不存在(新预印本、非英语、未收录会议)。
        authoritative_denial = (layers["arxiv_id"] is False) or (layers["crossref_datacite"] is False)
        if authoritative_denial:
            return _claim(claim, "reject", "权威登记处确证不存在 - 捏造引用", layers,
                          failure_kind="fabrication")
        return _claim(claim, "unresolved",
                      "索引未覆盖,无法确认存在性(非捏造判定;需补充可校验标识或扩展证据基质)",
                      layers, failure_kind="verification_gap")

    # Layer 4:相关性(可插拔)。LLM 后端:低相关 -> 硬门控(manual);启发式:仅标注。
    rel = _scorer().score(claim.get("text", ""), resolved_title or "", claim.get("abstract", ""))
    if rel == -1.0:                       # LLM 不可达 -> 回退 heuristic 标注语义
        rel = max(apis._token_overlap(claim.get("text", ""), resolved_title or ""),
                  apis._token_overlap(claim.get("title", ""), resolved_title or ""))
        llm_gate = False
    else:
        llm_gate = _scorer().is_llm
    layers["llm_relevance"] = round(rel, 3)
    ref = (f"arxiv:{claim['arxiv_id']}" if claim.get("arxiv_id") else
           (f"doi:{claim['doi']}" if claim.get("doi") else f"title:{(resolved_title or '')[:40]}"))
    ev = {"kind": "citation", "ref": ref,
          "fingerprint": "sha256:" + apis.hashlib.sha256((resolved_title or "").encode()).hexdigest()[:16]}
    if rel < REL_THRESHOLD:
        if llm_gate:                      # 生产:LLM 判定低相关 -> 硬门控,人工复核
            return _claim(claim, "manual", f"LLM 相关性低({rel:.2f}),疑似误引", layers, ev)
        out = _claim(claim, "pass", None, layers, ev)
        out["low_relevance"] = True       # 降级:仅标注,不阻断署名
        return out
    return _claim(claim, "pass", None, layers, ev)

def verify_number(claim: dict, run_log: str) -> dict:
    """数字溯源(R3):证据可以是「字面命中」,也可以是「可重算的推导」。

    放宽的是证据形式,不是证明责任 —— 数字仍必须能被独立重算,
    只是「重算」不再等同于「这个字符串在日志里出现过」。

    判定顺序:
      1) 日志字面命中            -> pass(kind=log)
      2) claim 自带推导式,重算成立 -> pass(kind=derivation)
      3) 有界算子空间自动发现推导  -> pass(kind=derivation,附表达式供人工复核)
      4) 都不成立                -> unresolved / verification_gap(不判捏造)
    """
    val = str(claim.get("value", "")).strip()

    # ★ R4:取值域检查 —— 完全不依赖任何索引或日志。
    # 准确率 1.35、步数 -3、耗时 -5s:世界不允许,查什么数据库都一样。
    try:
        fv = float(val)
        probe = f"{claim.get('name','')} {claim.get('text','')}"
        ok_bound, why_bound = dims.check_value(probe, fv)
        if not ok_bound:
            return _claim(claim, "reject", f"取值域违反:{why_bound}", {}, failure_kind="fabrication")
    except (TypeError, ValueError):
        pass

    if val and run_log and val in run_log:
        line = _find_line(run_log, val)
        ev = {"kind": "log", "ref": f"run.log#{line}",
              "fingerprint": "sha256:" + apis.hashlib.sha256((val + line).encode()).hexdigest()[:16]}
        return _claim(claim, "pass", None, {}, ev)

    symbols = deriv.parse_log_symbols(run_log)

    # 2) 显式推导式:作者主动声明如何算出来的
    expr = claim.get("derivation")
    if expr:
        # ★ R4:先查量纲。量纲不一致是物理否定,优先于数值比对。
        ok_dim, why_dim = dims.check_expression(expr, symbols)
        if not ok_dim:
            return _claim(claim, "reject", f"推导式量纲不一致:{why_dim}",
                          {}, failure_kind="fabrication")
        ok, got, why = deriv.verify_explicit(expr, val, symbols)
        if ok:
            ev = {"kind": "derivation", "ref": f"derivation:{expr}", "derivation": expr,
                  "computed_value": round(got, 12), "fingerprint": deriv.fingerprint(expr, got)}
            return _claim(claim, "pass", None, {}, ev)
        return _claim(claim, "reject" if got is not None else "unresolved",
                      why or f"推导式重算得 {got},与声明值 {val} 不符 - 数字与证据矛盾",
                      {}, failure_kind="fabrication" if got is not None else "verification_gap")

    # 3) 有界推导发现:保守搜索(仅有意义算子、仅日志具名量、精度不足则放弃)
    found = deriv.discover(val, symbols)
    if found:
        expr, got = found
        ev = {"kind": "derivation", "ref": f"derivation:{expr}", "derivation": expr,
              "computed_value": round(got, 12), "fingerprint": deriv.fingerprint(expr, got)}
        return _claim(claim, "pass", None, {}, ev)

    return _claim(claim, "unresolved",
                  "数字既未在日志中出现,也无法由日志量重算(可补 derivation 字段声明推导方式)",
                  {}, failure_kind="verification_gap")

def _find_line(log: str, val: str) -> str:
    for i, ln in enumerate(log.splitlines(), 1):
        if val in ln:
            return f"L{i}"
    return "L?"

def _claim(claim, status, reason, layers, ev=None, failure_kind=None):
    out = {"id": claim["id"], "text": claim.get("text", "")[:200], "type": claim.get("type", "citation"), "status": status}
    if failure_kind: out["failure_kind"] = failure_kind
    # 探索标记必须保留到报告里 —— 否则署名产出中无法追溯哪些主张是低先验探索
    if claim.get("prior"): out["prior"] = claim["prior"]
    if ev: out["evidence_chain"] = ev
    if reason: out["reason"] = reason
    if layers: out["citation_layers"] = {k: v for k, v in layers.items() if v is not None}
    return out


def verify_mechanism(claim: dict, artifacts: dict | None = None) -> dict:
    """机制性命题校验(R5)。

    新颖度决定**所需证据基质**,而非能否通过:
      文献中有支撑        -> 引用型或计算型证据均可
      索引中未见支撑      -> 必须由计算型证据背书(可复现包 / 推导 / 运行日志)

    ★ 索引里找不到 ≠ 该命题是新的 —— 二者在证据上无法区分。
      因此绝不宣告 novel,只报 unestablished_in_index,且据此**提高**证据要求。
      这样系统才能为「世界允许但模型不熟悉」的主张署名,而不退化为查重器。
    """
    artifacts = artifacts or {}
    text = claim.get("text", "")
    support, best, score = nov.literature_support(text)
    required = nov.required_substrate(support)

    ev = claim.get("evidence_chain")
    if not ev and artifacts.get("reproducible_package"):
        # 可复现包可作为计算型证据:代码 + 环境 + 日志 + 校验报告
        pkg = artifacts["reproducible_package"]
        ev = {"kind": "code+data", "ref": f"package:{pkg}",
              "fingerprint": "sha256:" + apis.hashlib.sha256(str(pkg).encode()).hexdigest()[:16]}

    out_extra = {"literature_support": support, "required_substrate": required}
    if best:
        out_extra["closest_prior_work"] = best[:120]

    if not nov.evidence_satisfies(ev, required):
        why = ("命题在索引中未见既有支撑,需由可复现包/推导等计算型证据背书"
               if required == "computational" else "命题缺少可核验的证据链")
        r = _claim(claim, "unresolved", why, {}, failure_kind="verification_gap")
        r.update(out_extra)
        return r

    # 若命题内含具体数值,顺带做取值域检查(物理约束与文献无关)
    for num in re.findall(r"-?\d+\.\d+|-?\d+", text):
        okb, whyb = dims.check_value(text, float(num))
        if not okb:
            r = _claim(claim, "reject", f"命题含物理不可能的取值:{whyb}", {},
                       failure_kind="fabrication")
            r.update(out_extra)
            return r

    r = _claim(claim, "pass", None, {}, ev)
    r.update(out_extra)
    return r


def verify_domain(claim: dict) -> dict:
    """领域物理判据(R6)—— 由领域规律裁决,与任何数据库是否收录无关。

        原子不守恒        违反质量守恒定律      -> fabrication
        不饱和度 < 0      氢超过骨架承载上限    -> fabrication
        价键超出上限      该结构不可能存在      -> fabrication
        自由基/离子       真实存在              -> 不判死,标记待确认
        超出判据适用范围   我们判断不了          -> unresolved,绝不冒充结论
    """
    verdict = claim.get("verdict")
    why = claim.get("why", "")
    ev_ref = f"{claim.get('domain','domain')}:{claim.get('expr','')}"
    if verdict == "impossible":
        return _claim(claim, "reject", why, {}, failure_kind="fabrication")
    if verdict == "plausible":
        ev = {"kind": "code+data", "ref": ev_ref,
              "fingerprint": "sha256:" + apis.hashlib.sha256(ev_ref.encode()).hexdigest()[:16]}
        r = _claim(claim, "pass", None, {}, ev)
        if "半整数" in why:
            r["status"] = "manual"; r["reason"] = why       # 自由基:存在但需确认
        return r
    return _claim(claim, "unresolved", why or "领域判据不适用", {},
                  failure_kind="verification_gap")
