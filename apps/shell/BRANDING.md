# 视觉资产

品牌标识:FrontierFirm.Fund 金色方形标(金底 `#C9A85C` + 墨色 `#0A1220` 字标)。

## 应用图标 `src-tauri/icons/`
从 `icon.svg` 以 1024×1024 光栅化后降采样生成,共 17 个文件:
- `icon.ico`(Windows,内嵌 16/24/32/48/64/128/256 七档)
- `icon.icns`(macOS)
- `32x32.png` · `128x128.png` · `128x128@2x.png` · `icon.png`(512)
- Windows Store 徽标 10 个(Square30…310、StoreLogo)
- `icon.svg` 矢量原件

> 重新生成:改 `icon.svg` 后按 `packaging/` 的方式用 cairosvg 光栅化再降采样(LANCZOS)。

## DMG 安装背景 `src-tauri/dmg/`
- `background.png`(660×400)+ `background@2x.png`(1320×800)
- 布局与 `tauri.conf.json` 的 `bundle.macOS.dmg` 坐标对齐:App 位 (160,150),Applications 位 (500,150)
- 含拖拽引导箭头与图标位虚线框

## 启动画面
- `splash.html` —— **实际使用的启动窗**(无边框、居中、置顶),带进度条与阶段提示动画
- `src-tauri/dmg/splash.png` —— 静态版(文档/备用)

**联动机制(非装饰)**:壳启动时先显示 splash、主窗口隐藏;`src-tauri/src/lib.rs` 收到 orchestrator 的 `ready` 通知后关闭 splash 并显示主窗口。冷启动需拉起 orchestrator + 3 个 sidecar,这几秒由 splash 覆盖。

## Web UI
`public/favicon.svg` · `public/favicon.png`,`index.html` 已引用。

## 配色(与产品文档一致)
| 用途 | 色值 |
|---|---|
| 品牌金 | `#C9A85C` |
| 深墨底 | `#09141A` / 面板 `#0E1A20` |
| 正文 | `#E9E5D9` / 次级 `#9CB1B7` / 弱化 `#6B848C` |
| 边框 | `#22414C` |
