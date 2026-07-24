"""可复现包打包器(T7)。署名通过后产出:代码 + 环境 + 数据清单 + 校验报告 + 草稿 + repro.sh。
第三方可在干净环境复跑。"""
from __future__ import annotations
import os, json, sys, hashlib, time

def _sha(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()[:16]

def build_package(run_id: str, direction: str, gen: dict, report: dict, out_root: str) -> str:
    pkg = os.path.join(out_root, f"{run_id}")
    os.makedirs(pkg, exist_ok=True)
    # 1) 草稿
    open(os.path.join(pkg, "draft.md"), "w").write(gen.get("draft", ""))
    # 2) 实验代码
    open(os.path.join(pkg, "experiment.py"), "w").write(gen.get("code", "# (code unavailable)"))
    # 3) 运行日志
    open(os.path.join(pkg, "run.log"), "w").write(gen.get("run_log", ""))
    # 4) 校验报告(0 幻觉引用的证据)
    json.dump(report, open(os.path.join(pkg, "verification_report.json"), "w"), ensure_ascii=False, indent=2)
    # 5) 数据清单 + 环境 + 指纹
    manifest = {
        "run_id": run_id, "direction": direction, "created_at": time.time(),
        "environment": {"python": sys.version.split()[0], "seed": 42},
        "data_sources": gen.get("data_sources", []),
        "citations": [{"arxiv_id": p.get("arxiv_id"), "title": p.get("title")} for p in gen.get("papers", [])],
        "verification": {"all_green": report.get("all_green"),
                          "hallucinated_citations": report.get("stats", {}).get("hallucinated_citations"),
                          "numbers_sourced": report.get("stats", {}).get("numbers_sourced")},
        "fingerprints": {"draft": _sha(gen.get("draft", "")), "code": _sha(gen.get("code", "")),
                         "run_log": _sha(gen.get("run_log", ""))},
    }
    json.dump(manifest, open(os.path.join(pkg, "manifest.json"), "w"), ensure_ascii=False, indent=2)
    # 6) repro 脚本
    open(os.path.join(pkg, "repro.sh"), "w").write(
        "#!/usr/bin/env bash\n# 干净环境复跑实验,核对 run.log 中的数字\nset -e\npython3 experiment.py\n")
    os.chmod(os.path.join(pkg, "repro.sh"), 0o755)
    return pkg
