# 录制时的操作脚本(照着点,~40 秒一条完整链路)

窗口标题:**F3-OpenScience · 可署名的科研工作台**

1. **研究方向** 输入框填:`few-shot RL for battery health`(或任意方向)
2. **模型** 下拉选:`Claude`(或切 `DeepSeek` / `本地 Ollama` 展示模型无关)
3. **自主度** 滑到 `L1`(协作模式,会在关键点暂停)
4. 点 **【运行】**
5. 观察 **事件流**:`inject → generate → verify`。第一次会 `all_green=false`(埋的幻觉引用被 CoE 拦下)
6. **GATE 弹窗**依次弹出:题目确认 → 实验设计 → 点【确认】
7. 命中 **署名前 GATE(hard)**:因校验未过 → 状态变 `blocked_pre_signoff`(红)。**这是卖点:不给不可信产出署名**
8. 再点一次 **【运行】**(同题):这次 `inject=1`、`guard=ON`,幻觉引用被飞轮规避 → `verify all_green=true` → 署名前确认 → 状态 `signed`(绿)
9. 切到 **用户主权面板** → 点【刷新】:看到自己的贡献(scope/reuse)→ 演示【撤回】

**建议镜头**:全程录窗口;在第 7 步(blocked 红)和第 8 步(signed 绿)各停 1–2 秒,对比最有冲击力。
