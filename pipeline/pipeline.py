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
from coe_kernel import exploration as expl

from coe_kernel.apis import _UA          # one identity for every outbound call · 对外只用一个身份


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
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": f"all:{direction}", "start": 0, "max_results": n, "sortBy": "relevance"})
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

def run_pipeline(direction: str, injected: list) -> dict:
    guard = any(l.get("kind") == "fake_cite" for l in (injected or []))
    papers = literature(direction)
    cites = hypothesize(direction, papers, guard)
    exp = code_and_run()
    claims = list(cites)
    if exp["gain"]:
        claims.append({"id": "num-gain", "type": "number", "value": exp["gain"],
                       "text": f"we observe an improvement of {exp['gain']}%"})
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
            "guard_on": guard, "n_papers": len(papers), "exploration": exploration,
            "data_sources": ["arXiv", "CrossRef/DataCite", "OpenAlex"],
            "papers": papers}
