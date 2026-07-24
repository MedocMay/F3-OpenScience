## 这个 PR 做了什么

<!-- 一句话说明。一个 PR 只做一件事。 -->

## 类型

- [ ] 修复 bug
- [ ] 新增功能
- [ ] **修改校验判定逻辑**(需填写下方「可达性影响」)
- [ ] 契约变更(需在 CHANGELOG 写迁移说明)
- [ ] 文档 / 测试 / 构建

## 可达性影响(改动 `coe_kernel/` 判定逻辑时必填)

**该判据的权威来源是什么?**
<!-- 登记处 / 计算 / 物理定律?索引类数据源没有否定权。 -->

**当它判断不了的时候会发生什么?**
<!-- 必须是 unresolved / verification_gap,不得是 reject。 -->

**失败分类**
- [ ] 新增的失败路径已正确标注 `fabrication` 或 `verification_gap`
- [ ] 仅 `fabrication` 会进入生成约束

## 测试

- [ ] `make test` 全绿(14 套件)
- [ ] `python3 tests/test_reachability.py` 误拒率仍为 0
- [ ] 改判定逻辑的,已在 `tests/golden/reachability_case.json` 加用例

## 其他

- [ ] 契约有改动时,已重新生成 `generated/` 两端类型
- [ ] 破坏性变更已写入 `CHANGELOG.md`
