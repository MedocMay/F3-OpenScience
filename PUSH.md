# 推送到 GitHub(两条命令)

本目录**已经是一个初始化好的 git 仓库**,提交已经做完。你只需要接上远程并推送。

```bash
git remote add origin https://github.com/MedocMay/F3-OpenScience.git
git push -u --force origin main
```

## 为什么要 `--force`

你在 GitHub 建库时勾选了生成 README 和 LICENSE,那边已有一个 initial commit。
本仓库是独立的提交历史,直接 push 会被拒绝。

`--force` 会用本仓库覆盖那个 initial commit —— 这是**安全的**:
那边只有 GitHub 自动生成的两个文件,而本仓库里有更完整的版本
(双语 README 带徽章和架构图、完整 Apache-2.0 全文 + 你的版权行)。

## 认证

首次 push 会要求登录:

- **HTTPS(上面的命令)**:用户名填 `MedocMay`,密码填 **Personal Access Token**
  (不是 GitHub 登录密码)。生成:Settings → Developer settings →
  Personal access tokens → Tokens (classic) → Generate new token,勾选 `repo`。
- **SSH(已配好密钥的话)**:把远程地址换成
  `git@github.com:MedocMay/F3-OpenScience.git`

## 推送后必做两件事

否则仓库文档里有死链:

1. **Settings → General → Features** 勾选 **Discussions**
   (Issue 模板里的「使用问题与讨论」指向它)
2. **Settings → Security → Private vulnerability reporting** 开启
   (`SECURITY.md` 把它列为漏洞报告的首选路径)

顺便在右上 About 齿轮里填 topics:
`ai4science` `research-agent` `llm` `verification` `reproducibility`

## 想先看看要推什么

```bash
git log --stat --oneline | head -30   # 提交内容
git ls-files | wc -l                  # 184 个文件
git ls-files | grep -E '\.env$|\.db$' # 应无输出
```

## 之后的日常提交

```bash
git add -A
git commit -m "你的说明"
git push
```
