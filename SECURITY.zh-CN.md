**简体中文** · [English](SECURITY.md)

# 安全策略

## 支持的版本

| 版本 | 安全更新 |
|---|---|
| 0.2.x | ✅ |
| 0.1.x | ❌ 请升级 |

## 报告漏洞

**请不要通过公开 Issue 报告安全漏洞。**

### 首选:GitHub 私密报告

[**→ 提交私密漏洞报告**](https://github.com/MedocMay/F3-OpenScience/security/advisories/new)

好处:结构化表单、可在修复前私下讨论、可直接申请 CVE、修复后一键公开披露。

### 备选:邮件

若不便使用 GitHub,可发送邮件至 **maymedoc@gmail.com**。

### 无论哪种方式,请包含

- 漏洞类型与影响范围
- 复现步骤(或 PoC)
- 受影响的版本与部署模式(本地 / 云端 / 混合)

我们会在 **48 小时内**确认收到,并在修复后于致谢中署名(除非你希望匿名)。

> ⚠️ 提醒:本项目为研究原型,**安全未经独立审计**(见 [STATUS.md](STATUS.zh-CN.md))。
> 我们会认真对待每一份报告,但请不要假设它已达到生产级安全水准。

## 本项目特别关注的攻击面

由于 F3-OpenScience 会**执行 AI 生成的代码**并**处理用户密钥**,以下区域风险最高:

### 1. 沙箱逃逸(`cloud/sandbox.py`)
Pipeline 执行的是模型生成的代码。沙箱提供:
- 环境擦除(生成代码读不到任何 `*_API_KEY`)
- 资源限额(内存 / CPU / 进程数 / 文件大小,POSIX)
- 目录 jail、可选网络隔离(`unshare -n`)

⚠ **Windows 无 `setrlimit`**,资源限额降级。面向不可信用户的公开服务
请部署在 Linux,或启用容器后端 `OPENSCI_SANDBOX=container`(生产建议 gVisor / Firecracker)。

### 2. 推导式求值(`coe_kernel/derivation.py`)
推导式来自模型生成,是代码注入的潜在入口。采用 **AST 白名单**求值:
禁函数调用、属性访问、下标、推导式、未知符号。发现任何绕过方式请立即报告。

### 3. 密钥管理(`cloud/vault.py`)
每用户 BYOK 密钥经 Fernet 加密落盘,主密钥由 `OPENSCI_MASTER_KEY` 注入。
明文仅在注入模型调用的瞬间解密,不进日志、不驻留。

⚠ **生产环境请从 KMS / Vault 注入主密钥**,不要写在 `.env` 文件里。

### 4. 多租户隔离(`cloud/tenancy.py`)
每租户独立经验库与密钥库。token 仅存哈希。
跨租户数据泄露属于**最高严重级别**。

### 5. global 记忆投毒
跨用户共享的经验需 ≥2 个不同贡献者独立复现才生效,且经脱敏门过滤。
若发现可绕过脱敏或伪造贡献者的方法,请报告。

## 部署安全清单

- [ ] `OPENSCI_MASTER_KEY` 来自 KMS,不在文件中
- [ ] `OPENSCI_TOKEN` / `OPENSCI_ADMIN_TOKEN` 使用 `openssl rand -hex 24` 生成
- [ ] 公开服务部署在 Linux,或启用容器沙箱
- [ ] 网关置于 TLS 反代之后(compose 已含 Caddy 自动 TLS)
- [ ] 定期备份 `data/`(经验库)与密钥库
