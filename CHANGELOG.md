# 变更日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。0.x 阶段,次版本号变更即可能含破坏性改动。

---

## [Unreleased]

### 修复
- **网络守卫探测错了对象**:此前只探测「能否连上 arXiv」,但 CI 上的真实情况是
  **能连上、但被限流**。限流时 `check_arxiv` 返回 None(未知),校验器据此报 `manual`
  而非 `reject` —— **行为正确**,是断言 `reject` 的测试失败了。
  金标集里 `c-attn` 有 title,能靠 OpenAlex 标题匹配兜底通过;`c-fake1` 无 title,
  无兜底,于是暴露出来。现改为探测**能力**:真 ID 必须确定为存在、假 ID 必须确定为不存在,
  任一为未知即跳过。
- **未遵守 arXiv 请求间隔**:官方 API 指南要求 ≥3 秒,而代码一直在连发 ——
  这正是被限流的原因。现加入限速(`COE_ARXIV_MIN_INTERVAL`,默认 3s),缓存命中不计入。
- **CI 遇错即中断**:一个套件失败就看不到其余 13 个结果。现改为全部跑完再统一报。
- **联网测试在 CI 上误判为失败**:`test_coe` 等 6 个套件会打真实学术 API,而 CI runner 常被
  arXiv / CrossRef 限流。此前只有 2 个套件带网络守卫,其余在 API 不可达时会因
  `assert status == "reject"` 失败 —— 但此时校验器返回 `manual`(连不上 ≠ 不存在)**是正确行为**,
  是测试假设了网络一定可用。现统一到 `tests/_netguard.py`,不可达时跳过而非失败。
  可用 `OPENSCI_SKIP_NETWORK_TESTS=1` 在本地复现离线场景。
- **守卫探测的能力与测试所需的能力不一致**:首版守卫只探测「能否连上 arXiv」,
  但普通查询可能成功、而查**不存在**的 ID 却被限流(403/429)降级为「未知」。
  此时校验器正确地报 `manual` 而非 `reject`,断言 `reject` 的测试仍会失败。
  现改为**双向探测**:已知真 ID 必须解析成功 **且** 已知假 ID 必须被明确否定,
  两者都成立才执行引用类断言。
- CI 改为跑完全部 14 个套件再统一报失败,便于一次看清所有问题。
- **守卫探测的端点与测试使用的端点不同**(第三次同形错误):守卫探测
  `check_arxiv(id)`(走 `id_list` 端点),而 `test_pipeline` / `test_integration`
  依赖 `literature(query)`(走 `search_query` 端点)。两个端点在限流下**独立失效** ——
  ID 查询返回 True,搜索却返回 0 篇,于是守卫放行、测试失败。
  现拆成两项独立能力探测:`can_judge_citations()` 与 `can_search_literature()`。

### 变更
- **Release 工作流实际会创建 Release 了**:原来只用 `upload-artifact`,产物存在 Actions
  运行记录里(90 天过期),**不会附到 Release 上**。现新增 `release` job,收集全部产物
  并通过 `softprops/action-gh-release` 发布,附带双语说明与免责声明。
- 桌面构建标记 `continue-on-error` —— Tauri 壳从未编译过,失败不应阻塞 Release,
  Python 包与源码归档照常发布。
- 移除 `push: false` 的 Docker job(构建完即丢弃,多架构 QEMU 编译还很慢)。
- 新增 `docs/assets/social-preview.png`(1280×640)与其生成器,用于 GitHub 社交预览。
- CI 中 `actions/*` 升级到最新大版本,消除 Node.js 20 弃用警告。

---

## [0.2.0] — 可达性框架(Reachability)

**主题:敢署名,且不因此变窄。**

上一版解决了「产出前有独立校验」。这一版解决它带来的新问题:
**校验器的能力边界,会悄悄变成生成器的世界边界。**

### ⚠ 破坏性变更(消费 verification_report 的调用方需适配)

| 变更 | 说明 | 迁移 |
|---|---|---|
| `Claim.status` 新增 `unresolved` | 索引/能力未覆盖,区别于 `reject`(确证捏造) | 按 `reject` 同等对待即可保持原行为(两者都阻断署名) |
| `Claim.type` 新增 `mechanism` / `domain` | 机制性命题与领域物理判据 | 未知类型按需忽略 |
| `stats.citations_rejected` 语义收紧 | 只计确证捏造,不再包含「查不到」 | 需要旧口径请改用 `citations_rejected + citations_unresolved` |
| `EvidenceChain.kind` 新增 `derivation` | 可重算的推导式证据 | — |

`all_green` 语义**未变**:`reject` / `unresolved` / `manual` 任一存在即为 `false`。**署名门槛没有放松。**

### 新增

**R0 · 可达性度量** — `coe_kernel/metrics.py`
- `reachability_metrics()`:误拒率、覆盖率、漏放率、新颖论断占比
- `flywheel_health()`:拦截率 / 可达率 / 探索率**三曲线并读**,区分 `learning` / `narrowing` / `conservative`
- 可达性回归集 `tests/golden/reachability_case.json` —— 专收「世界允许但校验器容易误杀」的论断

**R1+R2 · 失败语义分野与飞轮分流** — `verify.py` / `memory/store.py`
- 判据落在**证据基质的权威性**上:arXiv/DOI 登记处有权宣告不存在;OpenAlex 索引没有
- `Claim.failure_kind`:`fabrication`(世界不允许)vs `verification_gap`(我看不到)
- ★ `inject()` **只注入 `fabrication`** —— 校验缺口不得进入生成约束
- 新增 `capability_backlog()`:缺口转化为**能力建设需求**,而非生成禁区

**R3 · 推导式证据链** — `coe_kernel/derivation.py`
- 数字证据从「字面命中」升级为「**可重算**」:显式 `derivation` 字段 + 有界推导发现
- 推导式重算与声明值矛盾 → `fabrication`(**计算是权威裁判**)
- AST 白名单求值,禁函数调用/属性访问/未知符号

**R4 · 量纲与取值域** — `coe_kernel/dimensions.py`
- 第一个**与索引无关**的物理约束:准确率 > 1、量纲不可加、计数为负
- 量纲检查前置到推导发现的**求值之前** —— 物理约束重塑搜索空间,而非事后过滤

**R5 · 探索预算与新颖论断** — `coe_kernel/novelty.py` / `exploration.py`
- 补上反向缺口:机制性命题此前**完全不进校验**
- 新颖度决定**所需证据基质**,而非能否通过:索引无支撑 → 须由计算型证据背书
- 低先验假设强制配额(`OPENSCI_EXPLORATION_RATIO`,默认 0.3),候选不足时**如实报告未达成**

**R6 · 领域物理可达性** — `coe_kernel/domains/`
- 化学:原子守恒(质量守恒定律)、不饱和度、价键上限
- **零依赖**即可判定物理不可能;RDKit 为可选增强
- 可插拔、默认关闭,MVP 域(ML/CS)不受影响

### 修复

- **熔断器把「服务说没有」与「服务连不上」混为一谈**:HTTP 404 是登记处成功应答的否定结论,却被计入失败计数。连查几个捏造引用即触发熔断,系统随即丧失判定捏造的能力,且结果依赖调用顺序、不可复现。现 404/410 视为权威否定(不计失败、缓存保留该语义),判定已幂等。
- **量纲语义歧义导致误拒**:文本同时含 `accuracy` 与 `improvement` 时,武断按前者判定,把合法的「12.4% 提升」判成「概率超过 1,物理不可能」。现歧义即返回 `unknown`,不下断言。
- **arXiv 检索无重试**:外部 API 抖动会被误判为回归。现加指数退避,测试含网络可达性守卫。

### 贯穿全版本的一条纪律

同一个错误在三个层级各出现一次 —— 索引盲区、命名歧义、判据边界 —— 都是
**把自己的可观测边界误当成世界的边界**。现在整套代码贯彻:
**未知就是未知,不伪装成已知,也不伪装成不可能。**

### 测试
9 → **14 个测试套件**,全绿。新增可达性、推导、量纲、探索、领域物理五套。

---

## [0.1.0] — 首个可署名版本

- **CoE 校验内核**:真实 arXiv / CrossRef / DataCite / OpenAlex 4 层引用核验 + 数字溯源
- **校验记忆飞轮**:被拒模式 → 脱敏经验库 → 前置注入 → 拦截率下降(实测 `[1,0,0]`)
- **跨用户 global 治理**:脱敏 + ≥2 独立复现才晋升 + 用户 opt-in / 可撤回
- **多进程架构**:TS 大脑 + Python sidecar,JSON-RPC over stdio,只依赖 contracts
- **模型无关**:Claude / GPT / Gemini / Kimi / DeepSeek / Qwen + 本地 Ollama / vLLM
- **三种部署**:本地 / 云端(多租户 + BYOK 密管 + 沙箱强隔离)/ 混合
- **署名前 GATE + 可复现包**:代码 + 环境 + 数据清单 + 校验报告 + repro.sh
- Tauri 桌面壳、9 个安装包(Windows / macOS / Linux × 三种部署)
