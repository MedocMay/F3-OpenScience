"""真实 Pipeline 主线(M5):literature -> hypothesis -> code -> run(沙箱执行)。
- literature:真实 arXiv 检索,得到真实引用(真 arXiv ID/标题)。
- hypothesis:从检索结果构造假设(生产换 LLM);无 guard 时注入 1 条"幻觉引用"模拟 LLM 捏造。
- code:生成带 seed 的实验脚本。
- run:subprocess 沙箱执行(超时),产出真实运行日志与真实数字。"""
from __future__ import annotations
import sys, os, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET
import subprocess, tempfile, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from cloud.sandbox import get_sandbox
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coe_kernel import apis
from coe_kernel.extract import extract_claims
from coe_kernel import exploration as expl

from coe_kernel.apis import _UA          # one identity for every outbound call · 对外只用一个身份


_SPLIT_RE = re.compile(r"\b(?:for|of|in|on|with|to|using|via|and|under|from|between)\b", re.I)


def _query_ladder(direction: str) -> list[tuple[str, str]]:
    """Progressively looser arXiv queries, strictest first. 由严到松的查询阶梯。

    `all:<whole sentence>` applies the field prefix to the first word only and lets
    the rest match loosely. That is why "few-shot reinforcement learning for battery
    health" returned FADL — a paper on federated learning for electronic health
    records — which matched on the word "health". Three loosely-related papers were
    then cited as "prior work on battery health", and the relevance layer was right
    to score them 0.00.
    `all:<整句>` 只把字段前缀作用于第一个词,其余松散匹配。这就是为什么
    「few-shot reinforcement learning for battery health」会返回 FADL —— 一篇联邦
    学习做电子健康病历的论文 —— 它命中的是 health 这个词。那三篇随后被当作
    「prior work on battery health」引用,而相关性层判 0.00 是对的。

    Quoting the phrases and ANDing them fixes precision, but the strictest form often
    returns nothing ("few-shot reinforcement learning" is not a phrase anyone writes
    in a title). English noun phrases are head-final, so the next rung keeps the last
    two words of each. Only if both miss does it fall back to the old loose form.
    把短语加引号再 AND 解决了精度,但最严的一级常常返回空(没人会把
    「few-shot reinforcement learning」原样写进标题)。英语名词短语中心语在后,
    所以下一级保留每个短语的后两个词。两级都落空才回落到原先的松散形式。

    The rung that produced the result travels with each paper as `_match`. A caller
    that cites a `loose` hit as prior work is making a much weaker claim than one
    citing a `phrases` hit, and it should be able to tell the difference.
    命中的级别随每篇论文以 `_match` 字段带出。把 `loose` 命中当作前作引用,与把
    `phrases` 命中当作前作引用,是强度差很远的两种主张,调用方应当分得清。
    """
    parts = [" ".join(p.split()) for p in _SPLIT_RE.split(direction) if p.strip()]
    rungs = []
    if len(parts) >= 2:
        rungs.append(("phrases", " AND ".join(f'all:"{p}"' for p in parts)))
        heads = [" ".join(p.split()[-2:]) if len(p.split()) > 2 else p for p in parts]
        if heads != parts:
            rungs.append(("heads", " AND ".join(f'all:"{h}"' for h in heads)))
    rungs.append(("loose", f"all:{direction}"))
    return rungs


def literature(direction: str, n: int = 3, retries: int = 3) -> list[dict]:
    """真实 arXiv 检索。外部 API 会限流/抖动 -> 指数退避重试;仍失败返回 [](上层容错)。"""
    import time as _t
    # Plaintext http times out on some networks while https resolves fine. The same
    # one-character bug was fixed in coe_kernel/apis.py (9b70097) and missed here, so
    # topic search kept returning [] — which reads downstream as "search unavailable"
    # rather than "this call path is broken".
    # 明文 http 在部分网络上超时,https 正常。同一个字符的 bug 在 coe_kernel/apis.py
    # (9b70097)修过,这里漏了,于是主题检索一直返回 [] —— 下游读成「检索不可用」,
    # 而不是「这条调用路径是坏的」。
    for _level, _q in _query_ladder(direction):
        _hits = _fetch(_q, n, retries)
        if _hits:
            for h in _hits:
                h["_match"] = _level
            return _hits
    return []


def _fetch(query: str, n: int, retries: int) -> list[dict]:
    import time as _t
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": query, "start": 0, "max_results": n, "sortBy": "relevance"})
    raw = None
    for i in range(retries):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=30).read().decode()
            break
        except Exception:
            if i < retries - 1: _t.sleep(2 ** i)
    if raw is None:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in ET.fromstring(raw).findall("a:entry", ns):
        aid = e.find("a:id", ns).text.split("/abs/")[-1].split("v")[0]
        title = " ".join((e.find("a:title", ns).text or "").split())
        out.append({"arxiv_id": aid, "title": title})
    return out

def _candidate_hypotheses(direction: str, papers: list[dict]) -> list[dict]:
    """构造假设候选池,显式标注先验高低。
    高先验 = 沿着检索到的既有工作外推(模型熟悉、易通过校验)
    低先验 = 偏离主流的机制性猜想(模型不喜欢,但物理上未被禁止)
    真实系统中这一步由模型生成;此处为可测的最小实现。"""
    cands = [{"prior": "high", "text": f"We propose that {direction} benefits from the mechanism reported in prior work."}]
    for p in papers[:2]:
        cands.append({"prior": "high", "text": f"Our method improves on {p['title'][:60]} because of shared inductive bias."})
    # 低先验:刻意偏离主流的机制性猜想
    cands += [
        {"prior": "low", "text": f"We hypothesize that {direction} is driven by a rarely-observed regime rather than the dominant pathway."},
        {"prior": "low", "text": f"We propose that the effect in {direction} results in non-monotonic behaviour outside the commonly sampled range."},
    ]
    return cands

def hypothesize(direction: str, papers: list[dict], guard: bool) -> list[dict]:
    """引用型 claims。真实论文来自检索;无 guard 时追加 1 条幻觉引用(模拟 LLM 捏造)。
    guard 开启(注入了 fake_cite 教训):生成前逐条预核验,丢弃不存在的引用。"""
    cites = [{"id": f"cite-{p['arxiv_id']}", "type": "citation", "arxiv_id": p["arxiv_id"],
              "title": p["title"], "text": f"prior work on {direction}"} for p in papers]
    # 模拟 LLM 幻觉:凭空造一条不存在的引用
    hallucinated = {"id": "cite-halluc", "type": "citation", "arxiv_id": "2099.98765",
                    "title": "A fabricated study that does not exist", "text": f"claimed prior work on {direction}"}
    if guard:
        exists, _ = apis.check_arxiv(hallucinated["arxiv_id"])
        if exists is not False:                      # 只有确证存在才保留
            cites.append(hallucinated)
    else:
        cites.append(hallucinated)
    return cites

_EXPERIMENT = '''
import random
random.seed(42)                         # 固定 seed -> 可复现(数字重跑核验的前提)
base = [random.random() for _ in range(1000)]
improved = [min(1.0, x*1.18) for x in base]
b = sum(1 for x in base if x > 0.5) / len(base)
i = sum(1 for x in improved if x > 0.5) / len(improved)
gain = round((i - b) / b * 100, 1)
print(f"baseline_acc {round(b,3)}")
print(f"improved_acc {round(i,3)}")
print(f"improvement {gain}%")
'''

def code_and_run(timeout: int = 20) -> dict:
    """生成实验代码 -> 强隔离沙箱执行(环境擦除 + 资源限制)-> 真实运行日志。"""
    res = get_sandbox().run(textwrap.dedent(_EXPERIMENT))
    log = res.stdout.strip() if res.ok else f"SANDBOX_BLOCKED:{res.killed_reason} {res.stderr[:100]}"
    m = re.search(r"improvement ([\d.]+)%", log)
    gain = m.group(1) if m else None
    return {"run_log": log, "gain": gain, "code": textwrap.dedent(_EXPERIMENT)}

_DRAFT_PROMPT = """You are drafting the results section of a short research note.

Direction: {direction}

Retrieved prior work (real, from arXiv):
{papers}

Experiment log produced by a sandboxed run:
{run_log}

Write 4-6 sentences. Cite prior work inline using arXiv IDs in the form [arXiv:XXXX.XXXXX].
State the measured improvement. Do not invent numbers that are not in the log.
"""


# Providers the router knows how to reach, and the variable each one needs.
# 路由认识的供应商,以及各自需要的环境变量。
_KEY_ENV = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
            "MOONSHOT_API_KEY", "DASHSCOPE_API_KEY", "GEMINI_API_KEY")


def _ANY_MODEL_KEY() -> bool:
    """Is any provider configured at all? 到底配了哪家没有?

    Without this the router dutifully walks its whole fallback chain on every run,
    collecting a 401 from each provider in turn. That is several seconds of network
    spent proving something a single environment lookup already knows — and it makes
    "no model configured" look like "every model rejected us", which are different
    findings.
    没有这一步,路由会在每次运行时老老实实走完整条回退链,挨家收一个 401。那是花几秒
    网络去证明一件查一下环境变量就知道的事 —— 而且会让「没配模型」看起来像「所有模型
    都拒绝了我们」,那是两种不同的结论。
    """
    return any(os.environ.get(k, "").strip() for k in _KEY_ENV)


def _draft_via_model(direction: str, papers: list[dict], exp: dict) -> tuple[str | None, str]:
    """Ask the configured model to write the draft. Returns (text, provenance).

    请配置好的模型撰写 draft,返回 (文本, 来源说明)。

    Returns (None, reason) when no model is reachable, and the caller falls back to
    the template — but the reason travels with the result and lands in the report as
    `draft_source`. A run that quietly used the template while the operator believed
    a model wrote it would be this project's own failure mode one level up: a
    stand-in reported as the real thing. STATUS.md's "never run end-to-end with a
    real LLM" can only be retired by a run that can prove which path it took.
    没有可用模型时返回 (None, 原因),调用方回落到模板 —— 但那个原因会跟着结果走,
    最终出现在报告的 `draft_source` 字段里。如果一次运行悄悄用了模板,而操作者以为
    是模型写的,那就是本项目自己的失效模式上移一层:替身被当成了真身。
    STATUS.md 里「从未用真实 LLM 端到端跑过」这一条,只能由一次**能自证走了哪条路**
    的运行来撤销。
    """
    # A regression suite must not change its verdict because the operator happens to
    # have an API key. Model-backed generation is opt-out here and pinned off in
    # tests: real-model behaviour belongs in an experiment, not in a suite whose job
    # is to say whether a code change broke something.
    # 回归套件不能因为操作者恰好有 API key 就改变结论。模型生成在此可关闭,并在测试里
    # 钉死为关 —— 真实模型的行为属于实验,不属于一个职责是「代码改动有没有弄坏东西」
    # 的套件。
    if os.environ.get("OPENSCI_PIPELINE_MODEL", "").strip() in ("0", "off", "false"):
        return None, "template (model generation disabled · 已显式关闭)"
    if not _ANY_MODEL_KEY():
        return None, ("template (no model configured · 未配置模型 —— set one of "
                      + "/".join(k.split("_API")[0] for k in _KEY_ENV) + "_API_KEY)")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from model.router import ModelRouter
    except Exception as e:                                  # noqa: BLE001
        return None, f"template (router unavailable · 路由不可用: {type(e).__name__})"

    r = ModelRouter()
    prompt = _DRAFT_PROMPT.format(
        direction=direction,
        papers="\n".join(f"- [arXiv:{p['arxiv_id']}] {p['title']}" for p in papers) or "(none)",
        run_log=exp["run_log"] or "(no log)")
    try:
        out = r.complete([{"role": "user", "content": prompt}])
    except Exception as e:                                  # noqa: BLE001
        return None, f"template (model call raised · 模型调用抛错: {type(e).__name__})"
    if not out.get("ok") or not out.get("text", "").strip():
        return None, f"template (model unavailable · 模型不可用: {out.get('error', 'empty response')})"
    return out["text"].strip(), out["model_used"]


def run_pipeline(direction: str, injected: list) -> dict:
    guard = any(l.get("kind") == "fake_cite" for l in (injected or []))
    papers = literature(direction)
    cites = hypothesize(direction, papers, guard)
    exp = code_and_run()
    claims = list(cites)
    if exp["gain"]:
        claims.append({"id": "num-gain", "type": "number", "value": exp["gain"],
                       "text": f"we observe an improvement of {exp['gain']}%"})
    # Real model first; template only as a declared fallback.
    # 优先用真实模型;模板只作为**声明过的**回落。
    model_draft, draft_source = _draft_via_model(direction, papers, exp)
    if model_draft:
        draft = f"# {direction}\n\n{model_draft}"
        # Whatever the model cited goes through the same verification as anything
        # else — including citations it invented. That is the point: the draft is
        # now something a model actually wrote, not something we assembled for it.
        # 模型引用了什么,就和其他一切一样走同一套校验 —— 包括它自己编出来的引用。
        # 这正是重点:draft 现在是模型真写的,而不是我们替它拼的。
        for extra in extract_claims(draft):
            if extra["id"] not in {c["id"] for c in claims}:
                claims.append(extra)
    else:
        draft = (f"# {direction}\n\nBased on {len(papers)} retrieved works "
                 + " ".join(f"[{c['id']}]" for c in cites)
                 + f", we observe an improvement of {exp['gain']}%.")
    # R5:探索预算 —— 强制给低先验假设留配额,并如实报告达成率
    selected = expl.allocate(_candidate_hypotheses(direction, papers))
    exploration = expl.measure(selected)

    # ★ 生成器必须为自己的机制性主张附上证据,否则不得主张。
    #   本次实验产出的代码与运行日志即计算型证据基质;
    #   至于该实验是否**充分证成**这个因果命题,CoE 明确不作判断(见 kernel 的已知盲区),
    #   由人在署名前 GATE 复核 —— 系统负责"有据可查",不冒充因果裁判。
    import hashlib as _h
    art_ref = f"run:{_h.sha256((exp['code'] + exp['run_log']).encode()).hexdigest()[:12]}"
    for i, c in enumerate(selected):
        claims.append({
            "id": f"mech-gen-{i}", "type": "mechanism", "text": c["text"],
            "evidence_chain": {"kind": "code+data", "ref": art_ref,
                               "fingerprint": "sha256:" + _h.sha256(art_ref.encode()).hexdigest()[:16]},
            "prior": c.get("prior"),
        })
    draft += "\n" + "\n".join(c["text"] for c in selected)

    return {"draft": draft, "claims": claims, "run_log": exp["run_log"], "code": exp["code"],
            "draft_source": draft_source,
            "guard_on": guard, "n_papers": len(papers), "exploration": exploration,
            "data_sources": ["arXiv", "CrossRef/DataCite", "OpenAlex"],
            "papers": papers}
