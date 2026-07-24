**English** · [简体中文](SECURITY.zh-CN.md)

# Security Policy

## Supported versions

| Version | Security updates |
|---|---|
| 0.2.x | ✅ |
| 0.1.x | ❌ please upgrade |

## Reporting a vulnerability

**Please do not report security vulnerabilities through public issues.**

### Preferred: GitHub private reporting

[**→ Submit a private vulnerability report**](https://github.com/MedocMay/F3-OpenScience/security/advisories/new)

Benefits: structured form, private discussion before a fix, direct CVE request, one-click
public disclosure after the fix.

### Alternative: email

If GitHub is inconvenient, email **maymedoc@gmail.com**.

### Either way, please include

- Vulnerability type and impact scope
- Reproduction steps (or PoC)
- Affected version and deployment mode (local / cloud / hybrid)

We will acknowledge receipt within **48 hours** and credit you after the fix (unless you prefer anonymity).

> ⚠️ Note: this project is a research prototype and its **security has not been independently
> audited** (see [STATUS.md](STATUS.md)). We take every report seriously, but please do not
> assume it meets production-grade security standards.

## Attack surfaces of particular concern

Because F3-OpenScience **executes AI-generated code** and **handles user keys**, these areas
carry the highest risk:

### 1. Sandbox escape (`cloud/sandbox.py`)
The pipeline executes model-generated code. The sandbox provides:
- Environment scrubbing (generated code cannot read any `*_API_KEY`)
- Resource limits (memory / CPU / process count / file size, POSIX)
- Directory jail, optional network isolation (`unshare -n`)

⚠ **Windows has no `setrlimit`**, so resource limits degrade. For public services exposed to
untrusted users, deploy on Linux or enable the container backend `OPENSCI_SANDBOX=container`
(gVisor / Firecracker recommended in production).

### 2. Derivation evaluation (`coe_kernel/derivation.py`)
Derivation expressions come from model generation and are a potential code-injection entry point.
We use **AST whitelist** evaluation: no function calls, attribute access, subscripts,
comprehensions, or unknown symbols. Report any bypass immediately.

### 3. Key management (`cloud/vault.py`)
Per-user BYOK keys are Fernet-encrypted at rest; the master key is injected via
`OPENSCI_MASTER_KEY`. Plaintext is decrypted only at the moment of injection into a model call —
never logged, never retained.

⚠ **In production, inject the master key from a KMS / Vault** — do not put it in a `.env` file.

### 4. Multi-tenant isolation (`cloud/tenancy.py`)
Each tenant has an independent experience store and key vault. Tokens are stored hashed only.
Cross-tenant data leakage is the **highest severity class**.

### 5. Global memory poisoning
Shared cross-user experience requires ≥2 distinct contributors independently reproducing it,
and passes a de-identification gate. Report any way to bypass de-identification or forge contributors.

## Deployment security checklist

- [ ] `OPENSCI_MASTER_KEY` comes from a KMS, not a file
- [ ] `OPENSCI_TOKEN` / `OPENSCI_ADMIN_TOKEN` generated with `openssl rand -hex 24`
- [ ] Public services deployed on Linux, or with the container sandbox enabled
- [ ] Gateway behind a TLS reverse proxy (compose already includes Caddy with automatic TLS)
- [ ] Regular backups of `data/` (experience store) and the key vault
