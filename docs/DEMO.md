# F3-OpenScience · Demo 录屏(文字版)

> 以下为真实运行输出(打真实 arXiv / CrossRef / OpenAlex API + 真实沙箱执行),非示意。
> 复现:`bash demo.sh`

```console
$ bash demo.sh
════════════════════════════════════════════════════════════════
 F3-OpenScience Demo — 第一个产出前有独立校验、可署名的科研 Agent
════════════════════════════════════════════════════════════════
```

## ① CoE 校验内核 —— 真实 4 层引用核验

拿一份"埋了雷"的草稿:2 条真引用 + 2 条捏造引用 + 1 个有源数字 + 1 个无源数字。

```console
$ python3 tests/test_coe.py
▶ 1/3  CoE 校验内核(真实 arXiv / CrossRef / OpenAlex 4 层核验)
   [PASS  ] c-attn     arxiv:1706.03762
   [PASS  ] c-af       doi:10.1038/s41586-021-03819-2
   [REJECT] c-fake1    引用不存在(4 层均未解析)- 疑似捏造
   [REJECT] c-fake2    引用不存在(4 层均未解析)- 疑似捏造
   [PASS  ] n-acc      run.log#L1
   [REJECT] n-energy   数字在运行日志中无据 - 疑似捏造/无源
   -> all_green=False  hallucinated_citations=2  (1.5s, live API)
```

**真引用过、捏造引用全拦、无源数字拦下。** 这是"敢署名"的地基——`hallucinated_citations=0` 漏放。

## ② 校验记忆飞轮 —— 拦截率随使用下降

同一题连跑 3 次,看飞轮。

```console
$ python3 memory/flywheel_demo.py
▶ 2/3  校验记忆飞轮(拦截率随使用下降)
   === 飞轮闭环:同题连跑 3 次 ===
     RUN 1: injected=0 guard=off claims=3 rejected=1 all_green=False -> ❌ blocked
     RUN 2: injected=1 guard=ON  claims=2 rejected=0 all_green=True -> ✅ signed
     RUN 3: injected=1 guard=ON  claims=2 rejected=0 all_green=True -> ✅ signed

     拦截曲线(每 run 被拦假引用数): [1, 0, 0]
     🎯 飞轮闭环成立:拦截率 1 → 0,后续 run 一次过署名
```

**RUN 1 犯错被拦并回写经验;RUN 2 起前置注入触发"生成前预核验",规避同类错误,一次过署名。** 拦截曲线 `[1, 0, 0]` = 护城河复利。

## ③ 完整多进程链路 —— 真实检索 + 沙箱执行 + 署名

大脑 + 3 个独立 sidecar 进程(CoE / Pipeline / 经验库),JSON-RPC over stdio。

```console
$ python3 orchestrator/run_cli.py
▶ 3/3  完整多进程链路(大脑 + 3 sidecar,真实检索 + 沙箱执行 + 署名)

################ 多进程 RUN 1 ################
    [event] start     log      {'run_id': 'run-94e287d4', 'autonomy': 1}
    [壳] GATE:题目确认 -> 确认
    [event] inject    log      {'n_lessons': 0}
    [event] generate  log      {'guard_on': False, 'n_claims': 5}
    [壳] GATE:实验设计 -> 确认
    [event] verify    log      {'all_green': False, 'hallucinated_citations': 1}
    [event] flywheel  log      {'written': ['L06b40cce278f5b0b']}
    [event] signoff   gate     {'blocked': True, 'reason': '校验未全绿'}
    => RESULT: blocked_pre_signoff

################ 多进程 RUN 2 ################
    [event] inject    log      {'n_lessons': 1}
    [event] generate  log      {'guard_on': True, 'n_claims': 4}
    [event] verify    log      {'all_green': True, 'hallucinated_citations': 0}
    [壳] GATE:署名前(hard) -> 确认
    [event] package   artifact {'reproducible_package': '/tmp/opensci_packages/run-398a1f6a'}
    => RESULT: signed
```

**RUN 1**:真实检索 3 篇 arXiv + 沙箱跑出真实数字,幻觉引用被拦 → blocked。
**RUN 2**:飞轮跨进程生效,规避幻觉 → 署名 → **产出可复现包**。

## 可复现包(署名产出)

```console
$ ls run-398a1f6a/
draft.md  experiment.py  run.log  verification_report.json  manifest.json  repro.sh
$ cd run-398a1f6a && bash repro.sh
baseline_acc 0.52
improved_acc 0.597
improvement 14.8%          # 与 run.log 一致 -> 可复现性验证通过
```

---

**一句话:** 研究方向 → 真实检索 → 假设 → 沙箱执行 → CoE 核验(0 幻觉 + 数字溯源)→ 飞轮回写 → 署名 → 可复现包。全部真实代码、真实 API、真实执行。
