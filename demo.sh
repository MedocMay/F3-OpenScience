#!/usr/bin/env bash
# F3-OpenScience 端到端演示。展示核心论点:产出前独立校验 + 校验记忆飞轮(跨用户/跨语言)。
set -e; cd "$(dirname "$0")"
echo "══════════════════════════════════════════════════════════════"
echo " F3-OpenScience Demo — 第一个产出前有独立校验、可署名的科研 Agent"
echo "══════════════════════════════════════════════════════════════"
echo ""
echo "▶ 1/3  CoE 校验内核(真实 arXiv/CrossRef/OpenAlex 4 层核验)"
python3 tests/test_coe.py
echo ""
echo "▶ 2/3  校验记忆飞轮(拦截率随使用下降)"
python3 memory/flywheel_demo.py
echo ""
echo "▶ 3/3  完整多进程链路(Python 大脑 + 3 sidecar,真实检索+沙箱执行+署名)"
rm -f /tmp/orch_demo.db
python3 orchestrator/run_cli.py
echo ""
echo "✓ Demo 完成。可署名产出 = 独立校验(0 幻觉)+ 数字溯源 + 可复现包。"
