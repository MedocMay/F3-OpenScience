# 发布前检查清单

首次推送到 GitHub 前,有 **4 项占位符**必须确认或替换。它们是开发时填的示例值,
不改会导致:CI 徽章 404、安全报告邮件退信、学术引用元数据错误。

---

> ✅ **本仓库的占位符已替换为 `MedocMay/F3-OpenScience` 与 `maymedoc@gmail.com`。**
> 若要改到别的账号/邮箱,再跑一次下面的脚本即可。

## 一键替换(推荐)

```bash
bash scripts/setup-repo.sh
```

交互式询问四项,自动替换全仓库并校验无残留。也可非交互:

```bash
GITHUB_USER=你的用户名 REPO_NAME=f3-openscience \
SECURITY_EMAIL=你的安全邮箱 CONDUCT_EMAIL=你的准则邮箱 \
AUTHOR_NAME="你的署名" \
bash scripts/setup-repo.sh
```

---

## 需要替换的四项

| # | 占位符 | 出现处 | 不改的后果 |
|---|---|---|---|
| 1 | `FrontierFirmFund/f3-openscience` | `README.md`(徽章、BibTeX)· `CITATION.cff` · `.github/ISSUE_TEMPLATE/config.yml` | CI 徽章图片 404;Issue 页的「安全漏洞」「讨论区」链接 404;学术引用地址错误 |
| 2 | `security@frontierfirm.fund` | `SECURITY.md:14` | **漏洞报告邮件退信** —— 安全问题无人接收 |
| 3 | `conduct@frontierfirm.fund` | `CODE_OF_CONDUCT.md:41` | 行为准则投诉无人接收 |
| 4 | `FrontierFirm.Fund` | `pyproject.toml` · `CITATION.cff` · `LICENSE:190` · `tauri.conf.json` | 署名主体错误(若你的署名就是这个,无需改) |

> 脚本会跳过本文件与 `scripts/setup-repo.sh` 自身 —— 它们把占位符作为说明保留。

## 手动替换(不用脚本时)

```bash
grep -rl "FrontierFirmFund/f3-openscience" . --include="*.md" --include="*.yml" --include="*.cff" \
  | xargs sed -i 's|FrontierFirmFund/f3-openscience|你的用户名/你的仓库名|g'
sed -i 's|security@frontierfirm.fund|你的邮箱|' SECURITY.md
sed -i 's|conduct@frontierfirm.fund|你的邮箱|' CODE_OF_CONDUCT.md
```

---

## 推送前自检

```bash
make test                                    # 14 套件全绿
git init && git add -A
git ls-files | grep -E '\.env$|\.db$' && echo "⚠ 有敏感文件被跟踪!" || echo "✓ 干净"
git commit -m "F3-OpenScience v0.2.0"
git remote add origin git@github.com:<你的用户名>/<仓库名>.git
git push -u origin main
```

## GitHub 仓库设置建议

- **About**:填描述 + topics(`ai4science` `research-agent` `llm` `verification` `reproducibility`)
- **Settings → General**:开启 **Discussions**(Issue 模板已指向它,不开会是死链)
- **Settings → Security**:开启 **Private vulnerability reporting** ⚠️ **必开** —— `SECURITY.md` 已把它列为漏洞报告首选路径,不开会是死链
- **Settings → Actions**:确认 workflow 权限允许上传 artifact(Release 流水线需要)
- 首个 Release:打 tag `v0.2.0` 触发四平台安装包自动构建

## 发布前请再读一遍

- [STATUS.md](STATUS.md) —— 确认你认可其中列出的验证边界
- [INNOVATION.md](INNOVATION.md) —— 确认原创与整合的划分符合你的判断
