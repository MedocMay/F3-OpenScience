"""CoE 第 4 层 · 相关性打分(可插拔 + 模型无关)。
生产:LLMRelevance —— 经统一模型路由层(任意 provider:Claude/GPT/Gemini/Kimi/DeepSeek/Qwen/本地)判断
      "论文是否支持论断",低于阈值 -> 硬门控。
降级:HeuristicRelevance —— token 重合度,仅标注。
工厂按"是否配置了可用模型"自动选择。"""
from __future__ import annotations
import os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from model.router import ModelRouter

class RelevanceScorer:
    is_llm = False
    def score(self, claim_context: str, paper_title: str, paper_abstract: str = "") -> float:
        raise NotImplementedError

class HeuristicRelevance(RelevanceScorer):
    is_llm = False
    def score(self, claim_context, paper_title, paper_abstract="") -> float:
        ta = set(re.findall(r"[a-z0-9]+", (claim_context or "").lower()))
        tb = set(re.findall(r"[a-z0-9]+", ((paper_title or "") + " " + (paper_abstract or "")).lower()))
        return round(len(ta & tb) / len(ta | tb), 3) if ta and tb else 0.0

class LLMRelevance(RelevanceScorer):
    """模型无关:走 ModelRouter,底层可是任意 provider 或本地模型。"""
    is_llm = True
    def __init__(self, router: ModelRouter | None = None, model: str | None = None):
        self.router = router or ModelRouter()
        self.model = model
    def score(self, claim_context, paper_title, paper_abstract="") -> float:
        prompt = (f"Claim context:\n{claim_context}\n\nCited paper:\n{paper_title}\n"
                  f"{('Abstract: ' + paper_abstract) if paper_abstract else ''}\n\n"
                  "Does the cited paper plausibly support the claim? "
                  "Reply ONLY one number 0.0-1.0. No words.")
        r = self.router.complete([{"role": "user", "content": prompt}], model=self.model)
        if not r["ok"]:
            return -1.0                      # 模型不可达 -> verify 回退标注
        m = re.search(r"[01](?:\.\d+)?", r["text"])
        return float(m.group(0)) if m else 0.0

def get_scorer() -> RelevanceScorer:
    """配置了模型(OPENSCI_MODEL 或任一 provider key/本地 endpoint)-> LLM;否则降级 heuristic。

    COE_RELEVANCE=heuristic|llm overrides the auto-detection.
    COE_RELEVANCE=heuristic|llm 可显式覆盖自动判断。

    The override exists because auto-detection makes a verdict depend on whether the
    operator happens to hold an API key. That is fine for a deployment and wrong for
    a regression suite: whether a model considers paper X to support claim Y is not
    a property of the code under test, and a suite that changes its answer with the
    environment cannot tell anyone whether a change broke something.
    这个开关的必要性在于:自动判断会让结论取决于操作者手上有没有 API key。对一次部署
    这没问题,对回归套件是错的 —— 某个模型认不认为论文 X 支撑主张 Y,不是被测代码的
    属性,而一个会随环境改变答案的套件,没法告诉任何人某次改动有没有弄坏东西。
    """
    forced = os.environ.get("COE_RELEVANCE", "").strip().lower()
    if forced in ("heuristic", "off"):
        return HeuristicRelevance()
    if forced == "llm":
        return LLMRelevance()
    avail = ModelRouter.available()
    if os.environ.get("OPENSCI_MODEL") or any(avail.values()):
        return LLMRelevance()
    return HeuristicRelevance()
