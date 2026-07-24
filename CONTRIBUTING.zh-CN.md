**简体中文** · [English](CONTRIBUTING.md)

# 贡献指南

感谢你考虑为 F3-OpenScience 做贡献。

本项目是一个**科研产出校验系统**——它的价值完全建立在「判定是否可信」之上。
因此这里的贡献纪律比一般项目更严格,尤其在**校验逻辑**上。请先读完本文。

---

## 一条必须理解的原则

> **未知就是未知,不伪装成已知,也不伪装成不可能。**

这是整个项目的认识论底线。它在代码里反复出现:

```
索引里查不到      ≠  这篇论文不存在
语义无法辨识      ≠  这个值物理上不可能
库没安装          ≠  该结构不合法
判据不适用        ≠  判定为假
```

把「我看不到」当成「世界不允许」,是本项目最严重的一类缺陷 ——
它会让系统学会绕开难以校验的区域,最终退化成只敢说安全话的平庸机器。

**任何新增判据的 PR,都必须回答:当你判断不了的时候,会发生什么?**

详见 [docs/REACHABILITY.md](docs/REACHABILITY.md)。

**动手前请先读 [STATUS.md](STATUS.zh-CN.md)** —— 它列出了尚未验证的部分,也是最需要贡献的地方。

---

## 校验逻辑的贡献要求

修改 `coe_kernel/` 下的判定逻辑时,PR 必须包含:

1. **明确该判据的权威来源**
   - 谁有权宣告「不存在 / 不可能」?是登记处、是计算、还是物理定律?
   - 索引类数据源(如 OpenAlex)**没有**否定权 —— 它们只能确认,不能证伪。

2. **失败必须分类**
   - `fabrication` —— 确证矛盾,可作为生成约束
   - `verification_gap` —— 能力/覆盖不足,**不得**作为生成约束

3. **在可达性回归集中加用例**
   - `tests/golden/reachability_case.json`
   - 尤其欢迎**误拒陷阱**:那些「世界允许但校验器容易误杀」的论断。
     这个集合的价值不是刷高分,而是暴露边界。

4. **误拒率必须保持 0**
   ```bash
   python3 tests/test_reachability.py
   ```
   `false_rejection_rate` 上升的 PR 不会被合并,即使它提高了拦截率。

---

## 开发环境

```bash
git clone <your-fork>
cd opensci
pip install -e '.[test]'                     # 核心零依赖;test 组含 jsonschema
bash demo.sh                                 # 冒烟:校验内核 + 飞轮 + 多进程链路
```

可选:
```bash
pip install -e '.[cloud]'                    # 云端:BYOK 密管 / Postgres / Redis
pip install -e '.[chem]'                     # 化学价键判据(守恒/不饱和度无需它)
cd orchestrator-ts && npm i                  # TS 大脑
cd apps/shell && npm i                       # 桌面壳(另需 Rust)
```

## 跑测试

```bash
make test                                    # 全部 14 个套件
python3 tests/test_reachability.py           # 可达性回归(改判定逻辑必跑)
```

部分套件需要网络(真实 arXiv / CrossRef / OpenAlex)。它们内置了可达性守卫:
外部 API 不可达时会跳过而非失败。**请不要通过放宽断言来"修复"网络波动。**

## 修改契约

`contracts/` 是跨语言的唯一真源。改动流程:

```bash
# 1. 编辑 contracts/*.schema.json
# 2. 重新生成两端类型
bash ../scripts/gen-types.sh        # 或见 scripts/ 内说明
# 3. 提交 contracts/ 与 generated/ 的改动
```

破坏性变更(枚举增删、字段语义改变)必须在 `CHANGELOG.md` 写迁移说明。

---

## 提交规范

提交信息用祈使句,首行 ≤ 72 字符:

```
verify: 区分索引未覆盖与确证捏造
memory: 飞轮只注入 fabrication 类经验
docs: 补充量纲判据的适用边界
fix: 熔断器不再把 404 计入失败
```

前缀参考:`verify` `memory` `pipeline` `model` `cloud` `deploy` `docs` `fix` `test` `chore`

## Pull Request

- 一个 PR 只做一件事
- 附上测试;改判定逻辑的必须附可达性用例
- 说明**这个改动在判断不了的时候如何表现**
- CI 必须全绿(契约校验 + 14 套件 + wheel 构建 + TS 类型检查)

## 报告问题

- **误拒**(真实的东西被判成捏造)—— 最高优先级,请附上完整 `verification_report`
- **漏放**(捏造的东西通过了)—— 同样高优先级
- 安全问题请**不要**开 Issue,见 [SECURITY.md](SECURITY.zh-CN.md)

## 行为准则

参与本项目即表示你同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.zh-CN.md)。

## 许可

提交贡献即表示你同意以 [Apache-2.0](LICENSE) 授权你的代码。
