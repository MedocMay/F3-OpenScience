// Rust IPC bridge —— 壳与 orchestrator server 的桥。
// 职责:① 启动时 spawn `tsx orchestrator-ts/src/server.ts` 作为子进程(它再拉起 Python sidecars);
//       ② 把 webview 的 Tauri 命令(run_start/gate_resolve/sovereignty_*)转成 JSON-RPC 行写给 server;
//       ③ 读 server 的 notification(run.event/gate.request)→ 通过 Tauri event 转发给 webview。
// 注:本文件为脚手架,需在有 Rust 工具链的桌面上 `cargo tauri dev` 构建运行。
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{Emitter, Manager, State};

/// 启动看门狗超时(秒):后端未就绪也强制进入主界面,避免卡启动页。
const STARTUP_TIMEOUT: u64 = 20;

struct Bridge { stdin: Mutex<ChildStdin>, next_id: Mutex<u64> }

impl Bridge {
    fn send(&self, method: &str, params: serde_json::Value) {
        let mut id = self.next_id.lock().unwrap(); *id += 1;
        let msg = serde_json::json!({ "jsonrpc":"2.0","id":*id,"method":method,"params":params });
        let mut si = self.stdin.lock().unwrap();
        let _ = writeln!(si, "{}", msg.to_string());
        let _ = si.flush();
    }
}

#[tauri::command]
fn run_start(direction: String, autonomy: i64, model: String, state: State<Bridge>) {
    state.send("run.start", serde_json::json!({ "direction": direction, "autonomy": autonomy, "model": model }));
}
#[tauri::command]
fn gate_resolve(gate_id: String, decision: String, state: State<Bridge>) {
    state.send("gate.resolve", serde_json::json!({ "gate_id": gate_id, "decision": decision }));
}
#[tauri::command]
fn sovereignty_list(state: State<Bridge>) { state.send("sovereignty.list", serde_json::json!({})); }
#[tauri::command]
fn sovereignty_revoke(lesson_id: String, state: State<Bridge>) {
    state.send("sovereignty.revoke", serde_json::json!({ "lesson_id": lesson_id }));
}

pub fn run() {
    // 1) 启动 orchestrator server(tsx)。生产打包时可改为编译好的 node 单文件或 Bun 二进制。
    let mut child: Child = Command::new("npx")
        .args(["tsx", "../../orchestrator-ts/src/server.ts"])
        .stdin(Stdio::piped()).stdout(Stdio::piped())
        .spawn().expect("failed to spawn orchestrator server");
    let stdin = child.stdin.take().unwrap();
    let stdout = child.stdout.take().unwrap();

    tauri::Builder::default()
        .manage(Bridge { stdin: Mutex::new(stdin), next_id: Mutex::new(0) })
        .setup(move |app| {
            let handle = app.handle().clone();
            // 后端就绪标记:用于看门狗判断是否需要兜底
            let ready = Arc::new(AtomicBool::new(false));
            let ready_rx = ready.clone();

            // 看门狗:若 STARTUP_TIMEOUT 秒内后端仍未就绪,也要关掉启动页并显示主窗口,
            // 同时通知前端进入「后端未连接」状态 —— 避免用户永远卡在启动画面。
            let wd_handle = handle.clone();
            std::thread::spawn(move || {
                std::thread::sleep(std::time::Duration::from_secs(STARTUP_TIMEOUT));
                if !ready_rx.load(Ordering::SeqCst) {
                    if let Some(w) = wd_handle.get_webview_window("splash") { let _ = w.close(); }
                    if let Some(w) = wd_handle.get_webview_window("main") { let _ = w.show(); let _ = w.set_focus(); }
                    let _ = wd_handle.emit("backend.unavailable", serde_json::json!({
                        "message": "后端未在预期时间内就绪,请检查 Node / Python 运行时",
                        "timeout_secs": STARTUP_TIMEOUT
                    }));
                }
            });
            // 2) 读 server 输出,把 notification 转发给 webview
            std::thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines().flatten() {
                    if let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) {
                        match v.get("method").and_then(|m| m.as_str()) {
                            // orchestrator 就绪 -> 关闭启动画面,显示主窗口
                            Some("ready") => {
                                ready.store(true, Ordering::SeqCst);
                                if let Some(w) = handle.get_webview_window("splash") { let _ = w.close(); }
                                if let Some(w) = handle.get_webview_window("main") { let _ = w.show(); let _ = w.set_focus(); }
                            }
                            Some("run.event")    => { let _ = handle.emit("run.event", v.get("params").cloned()); }
                            Some("gate.request") => { let _ = handle.emit("gate.request", v.get("params").cloned()); }
                            _ => {}
                        }
                    }
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![run_start, gate_resolve, sovereignty_list, sovereignty_revoke])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
