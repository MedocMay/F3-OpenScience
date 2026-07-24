# 操作系统适配矩阵

## 后端(网关 + sidecars,Python 3.11+)
| OS | 状态 | 说明 |
|---|---|---|
| **Linux**(x86_64 / arm64) | ✅ 完全支持 | 全部特性,含沙箱资源限额 + 网络隔离(`unshare`) |
| **macOS**(Intel / Apple Silicon) | ✅ 完全支持 | 沙箱资源限额可用;`unshare` 无 → 网络隔离降级(用容器后端可补) |
| **Windows** 10/11 | ✅ 支持(沙箱降级) | 环境擦除 + 目录 jail + 超时终止均生效;**无 setrlimit 内存/进程限额** → 多租户公开服务建议 `OPENSCI_SANDBOX=container` 或部署到 Linux |
| **WSL2** | ✅ 完全支持 | 等同 Linux,Windows 用户的推荐路径 |

## 桌面 App(Tauri 2)
| OS | 安装包格式 | 构建要求 |
|---|---|---|
| **Windows** 10/11 | `.msi` / `.exe`(NSIS) | Rust + MSVC Build Tools + WebView2(系统自带) |
| **macOS** 11+ | `.dmg` / `.app` | Rust + Xcode CLT;分发需签名 + 公证 |
| **Linux** | `.AppImage` / `.deb` / `.rpm` | Rust + webkit2gtk + libayatana-appindicator |

> Apple Silicon 与 Intel 需分别构建(或用 universal target)。

## 容器 / 服务器
| 目标 | 状态 |
|---|---|
| Docker(linux/amd64, linux/arm64) | ✅ compose 三套(local / cloud / prod) |
| Kubernetes | 🟡 可用 compose 转 manifest(kompose),未提供官方 chart |

## 已知平台差异(代码已处理)
- **沙箱**:POSIX 用 `setrlimit` + `setsid`;Windows 自动降级为新进程组 + 超时(`cloud/sandbox.py` 内 `IS_WIN` 分支)。
- **临时目录**:统一 `tempfile.gettempdir()`,不再硬编码 `/tmp`。
- **网络隔离**:仅 Linux(`unshare -n`);其它平台建议容器后端。
- **外部 API 抖动**:arXiv 检索带指数退避重试;测试含网络可达性守卫。

## 安装产物形态
| 形态 | 命令 | 适用 | 状态 |
|---|---|---|---|
| **Python wheel / sdist** | `bash packaging/build-installers.sh backend` | 任何 OS(需 Python 3.11+) | ✅ 实测构建 |
| **单文件可执行** | 同上(需先 `pip install pyinstaller`) | 免装 Python 的服务器/工作站 | ✅ 实测构建并运行(Linux 9MB) |
| **桌面安装包** | `bash packaging/build-installers.sh desktop` | 终端用户 | 脚手架就绪,需目标 OS + Rust |
| **容器镜像** | `docker build -f deploy/docker/Dockerfile .` | 服务器/云 | compose 三套就绪 |

> 单文件可执行必须显式声明 hidden-import(冻结后 sys.path 失效)——参数已固化在
> `packaging/build-installers.sh` 与 `packaging/opensci.spec`,可直接用。

## CI 自动出包
`.github/workflows/release.yml`:打 tag 即触发
- **backend**:wheel + sdist(一次构建,全平台通用)
- **desktop**:ubuntu-22.04 / macos-latest(ARM)/ macos-13(Intel)/ windows-latest 四矩阵 → .AppImage/.deb/.dmg/.msi
- **docker**:linux/amd64 + linux/arm64 多架构镜像
