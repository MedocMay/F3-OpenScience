// F3-OpenScience 桌面壳 UI。通过 Tauri 命令调 Rust bridge → orchestrator server(ipc.schema)。
// 三块:① 运行工作区(方向+自主度+事件流)② gate 确认 ③ 用户主权面板。
import { useEffect, useState, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

type Ev = { stage: string; type: string; data: any };
type Contribution = { id: string; kind: string; scope: string; reuse_count: number; status: string };

export default function App() {
  const [direction, setDirection] = useState("efficient transformers for battery health");
  const [autonomy, setAutonomy] = useState(1);
  const [model, setModel] = useState("anthropic:claude-haiku-4-5-20251001");
  const [events, setEvents] = useState<Ev[]>([]);
  const [gate, setGate] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [contribs, setContribs] = useState<Contribution[]>([]);
  const [backendDown, setBackendDown] = useState<{message:string}|null>(null);

  // 订阅 orchestrator 流式事件 + gate 请求(Rust bridge 通过 Tauri event 转发)
  useEffect(() => {
    const un1 = listen<Ev>("run.event", (e) => setEvents((prev) => [...prev, e.payload]));
    const un2 = listen<{ gate_id: string }>("gate.request", (e) => setGate(e.payload.gate_id));
    // 后端未就绪(看门狗兜底):提示用户,而不是静默失败
    const un3 = listen<{ message: string }>("backend.unavailable", (e) => setBackendDown(e.payload));
    return () => { un1.then((f) => f()); un2.then((f) => f()); un3.then((f) => f()); };
  }, []);

  const start = useCallback(async () => {
    setEvents([]); setStatus("running");
    const r = await invoke<{ status: string }>("run_start", { direction, autonomy, model });
    setStatus(r.status);
  }, [direction, autonomy, model]);

  const resolveGate = useCallback(async (decision: string) => {
    const g = gate; setGate(null);
    await invoke("gate_resolve", { gateId: g, decision });
  }, [gate]);

  const loadPanel = useCallback(async () => {
    const rows = await invoke<{ contributions: Contribution[] }>("sovereignty_list", {});
    setContribs(rows.contributions ?? []);
  }, []);
  const revoke = useCallback(async (id: string) => { await invoke("sovereignty_revoke", { lessonId: id }); loadPanel(); }, [loadPanel]);

  return (
    <div style={S.app}>
      <h1 style={S.h1}>F3-OpenScience · <span style={{color:"#D9A441"}}>可署名</span>的科研工作台</h1>

      {backendDown && (
        <div style={S.banner}>
          <b>后端未连接</b> — {backendDown.message}
          <div style={{color:"#9CB1B7",fontSize:12,marginTop:6}}>
            请确认已安装 Node ≥18 与 Python ≥3.11;可先在终端运行 <code>bash demo.sh</code> 排查。
          </div>
        </div>
      )}

      <section style={S.card}>
        <div style={S.row}>
          <input style={S.input} value={direction} onChange={(e)=>setDirection(e.target.value)} placeholder="研究方向"/>
          <select style={S.select} value={model} onChange={(e)=>setModel(e.target.value)}>
            <optgroup label="云">
              <option value="anthropic:claude-haiku-4-5-20251001">Claude</option>
              <option value="openai:gpt-5">GPT</option>
              <option value="gemini:gemini-2.0">Gemini</option>
              <option value="deepseek:deepseek-chat">DeepSeek</option>
              <option value="kimi:moonshot-v1-8k">Kimi</option>
              <option value="qwen:qwen-max">Qwen</option>
            </optgroup>
            <optgroup label="本地(数据不出域)">
              <option value="ollama:qwen2.5">Ollama · Qwen2.5</option>
              <option value="local:my-model">OpenAI-兼容 / vLLM</option>
            </optgroup>
          </select>
          <label style={S.auto}>自主度 L{autonomy}
            <input type="range" min={0} max={6} value={autonomy} onChange={(e)=>setAutonomy(+e.target.value)}/>
          </label>
          <button style={S.btn} onClick={start} disabled={status==="running" || !!backendDown}>运行</button>
        </div>
        <div style={S.status}>状态:<b style={{color: status==="signed"?"#3FAE8C":status==="blocked_pre_signoff"?"#E36A48":"#9CB1B7"}}>{status}</b></div>
      </section>

      <section style={S.card}>
        <div style={S.eyebrow}>运行事件流</div>
        <div style={S.log}>
          {events.map((e,i)=>(
            <div key={i} style={S.logline}><span style={{color:"#6B848C"}}>{e.stage}</span> <span style={{color:"#5FA8E0"}}>{e.type}</span> {JSON.stringify(e.data)}</div>
          ))}
        </div>
      </section>

      <section style={S.card}>
        <div style={S.eyebrow}>用户主权面板 <span style={{color:"#6B848C",fontWeight:400}}>· private-by-default</span>
          <button style={S.linkbtn} onClick={loadPanel}>刷新</button></div>
        {contribs.length===0 ? <div style={{color:"#6B848C"}}>(无贡献 — 你的经验默认仅本地,未共享)</div> :
          contribs.map((c)=>(
            <div key={c.id} style={S.crow}>
              <span>{c.id.slice(0,10)} <span style={{color:"#8A8FE6"}}>[{c.kind}]</span> scope=<b>{c.scope}</b> reuse={c.reuse_count}</span>
              <button style={S.revoke} onClick={()=>revoke(c.id)}>撤回</button>
            </div>
          ))}
      </section>

      {gate && (
        <div style={S.modal}><div style={S.modalCard}>
          <div style={S.eyebrow}>GATE · {gate==="pre_signoff"?"署名前(不可跳过)":gate}</div>
          <p style={{color:"#E9E5D9"}}>{gate==="pre_signoff"?"校验全绿,确认署名并产出可复现包?":gate==="share_consent"?"是否把本次校验经验贡献到 global?(脱敏后)":"确认进入下一阶段?"}</p>
          <div style={S.row}>
            <button style={S.btn} onClick={()=>resolveGate("approve")}>确认</button>
            <button style={S.ghost} onClick={()=>resolveGate("reject")}>拒绝</button>
          </div>
        </div></div>
      )}
    </div>
  );
}

const S: Record<string, React.CSSProperties> = {
  app:{background:"#09141A",minHeight:"100vh",color:"#E9E5D9",fontFamily:"'IBM Plex Sans',system-ui,sans-serif",padding:"28px 32px"},
  h1:{fontSize:24,fontWeight:600,marginBottom:20},
  card:{background:"#0E1A20",border:"1px solid #22414C",borderRadius:12,padding:18,marginBottom:16},
  row:{display:"flex",gap:10,alignItems:"center",flexWrap:"wrap"},
  input:{flex:1,minWidth:260,background:"#09141A",border:"1px solid #22414C",borderRadius:8,color:"#E9E5D9",padding:"9px 12px"},
  select:{background:"#09141A",border:"1px solid #22414C",borderRadius:8,color:"#E9E5D9",padding:"9px 10px"},
  auto:{display:"flex",flexDirection:"column",fontSize:12,color:"#9CB1B7"},
  btn:{background:"#D9A441",color:"#09141A",border:0,borderRadius:8,padding:"9px 18px",fontWeight:600,cursor:"pointer"},
  ghost:{background:"transparent",color:"#9CB1B7",border:"1px solid #22414C",borderRadius:8,padding:"9px 18px",cursor:"pointer"},
  status:{marginTop:12,color:"#9CB1B7"},
  eyebrow:{fontFamily:"monospace",fontSize:12,color:"#9CB1B7",letterSpacing:".08em",marginBottom:10,textTransform:"uppercase"},
  log:{fontFamily:"monospace",fontSize:12,maxHeight:220,overflow:"auto",lineHeight:1.7},
  logline:{whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"},
  crow:{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"6px 0",borderBottom:"1px solid #16262d",fontSize:13},
  revoke:{background:"transparent",color:"#E36A48",border:"1px solid #E36A48",borderRadius:6,padding:"3px 12px",cursor:"pointer",fontSize:12},
  linkbtn:{marginLeft:12,background:"transparent",color:"#5FA8E0",border:0,cursor:"pointer",fontSize:12},
  banner:{background:"#2A1A16",border:"1px solid #E36A48",borderRadius:10,padding:"12px 16px",marginBottom:16,color:"#F0C4B4",fontSize:14},
  modal:{position:"fixed",inset:0,background:"rgba(0,0,0,.6)",display:"flex",alignItems:"center",justifyContent:"center"},
  modalCard:{background:"#0E1A20",border:"1px solid #D9A441",borderRadius:12,padding:24,maxWidth:420},
};
