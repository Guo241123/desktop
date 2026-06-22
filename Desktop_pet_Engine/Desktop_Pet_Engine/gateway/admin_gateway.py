"""Gateway — 管理后台（聊天气泡 + 运行指标）"""

import json
import logging
from pathlib import Path
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from utils.metrics import get_metrics
from utils.log_capture import get_logs

logger = logging.getLogger(__name__)
admin_router = APIRouter(prefix="/admin", tags=["管理后台"])


@admin_router.get("/api/logs")
def api_logs(
    level: str = Query(""),
    keyword: str = Query(""),
    limit: int = Query(300),
):
    return {"logs": get_logs(level=level, keyword=keyword, limit=limit)}


@admin_router.get("/api/metrics")
def api_metrics():
    return get_metrics()


@admin_router.get("/api/chat-history")
def api_chat_history():
    """读取聊天记录文件"""
    from config.paths import CHAT_MEMORY_DIR
    msgs = []
    for f in sorted(CHAT_MEMORY_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            session = f.stem
            for m in data:
                content = m.get("content", "")
                # 尝试解析 assistant 的 JSON 内容
                if m["role"] == "assistant" and content.startswith("{"):
                    try:
                        parsed = json.loads(content)
                        content = parsed.get("text", content)
                    except json.JSONDecodeError:
                        pass
                msgs.append({
                    "session": session,
                    "role": m["role"],
                    "content": content,
                    "source": "微信" if content.startswith("[微信]") else "桌面" if content.startswith("[桌面]") else "助手",
                })
        except Exception:
            continue
    return {"messages": msgs}


ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guo 助手 · 管理后台</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body {
    font-family: 'Inter', -apple-system, "Microsoft YaHei", sans-serif;
    background: #f8f6f3; color: #2d2a24;
    height:100vh; display:flex; flex-direction:column; overflow:hidden;
}
.header {
    display:flex; align-items:center; gap:16px; padding:16px 28px;
    background:#fff; border-bottom:2px solid #ede8e2; flex-shrink:0; z-index:10;
}
.header h1 {
    font-size:20px; font-weight:700; letter-spacing:-0.5px;
    background: linear-gradient(135deg, #2d2a24, #8a7e72);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
}
.header .status {
    font-size:12px; padding:4px 14px; border-radius:20px;
    background:#e8f5e9; color:#2e7d32; font-weight:500;
}
.header .btn {
    background:#fff; border:1.5px solid #e0d6cc; border-radius:10px;
    color:#5a4d3e; padding:6px 16px; font-size:13px; font-weight:500;
    cursor:pointer; margin-left:auto; transition:all 0.2s;
}
.header .btn:hover { background:#f5f0eb; border-color:#c4b5a2; transform:translateY(-1px); }

.main { display:flex; flex:1; overflow:hidden; background:#f8f6f3; }

.left { width:65%; display:flex; flex-direction:column; background:#fff; border-right:1px solid #ede8e2; }
.chat-header {
    padding:12px 24px; font-size:13px; color:#8a7e72; font-weight:500; letter-spacing:0.3px;
    border-bottom:1px solid #f0ece6; flex-shrink:0; background:#faf8f6;
}
.chat-container {
    flex:1; overflow-y:auto; padding:16px 20px;
    background: linear-gradient(180deg, #faf8f6 0%, #fff 40%);
}
.chat-container::-webkit-scrollbar { width:6px; }
.chat-container::-webkit-scrollbar-track { background:transparent; }
.chat-container::-webkit-scrollbar-thumb { background:#d6cec4; border-radius:3px; }

.bubble-row { display:flex; margin-bottom:10px; align-items:flex-start; }
.bubble-row.user { justify-content:flex-end; }
.bubble-row.assistant { justify-content:flex-start; }

.bubble {
    max-width:72%; padding:10px 18px; border-radius:16px;
    font-size:14px; line-height:1.6; word-break:break-word;
    box-shadow:0 1px 3px rgba(0,0,0,0.04);
}
.bubble.user {
    background: linear-gradient(135deg, #f5a623, #f7c948); color:#fff;
    border-bottom-right-radius:4px;
}
.bubble.assistant {
    background:#f5f2ee; color:#2d2a24; border-bottom-left-radius:4px;
}
.bubble .source-tag {
    display:inline-block; font-size:10px; padding:2px 8px; border-radius:10px;
    margin-bottom:6px; font-weight:500; opacity:0.8;
}
.bubble.user .source-tag { background:rgba(255,255,255,0.2); }
.bubble.assistant .source-tag { background:rgba(0,0,0,0.06); color:#6b5b4e; }

.empty-state { text-align:center; padding:60px 20px; color:#b5a898; }
.empty-state .illus { font-size:64px; margin-bottom:16px; opacity:0.6; }
.empty-state p { font-size:14px; line-height:1.8; }

.right { width:35%; display:flex; flex-direction:column; overflow-y:auto; background:#faf8f6; }
.panel-section { padding:16px 20px; border-bottom:1px solid #ede8e2; }
.panel-section:last-child { border-bottom:none; }
.panel-section h3 {
    font-size:11px; color:#9a8e82; text-transform:uppercase;
    letter-spacing:1px; margin-bottom:12px; font-weight:600;
}
.metric-row {
    display:flex; justify-content:space-between;
    padding:6px 0; font-size:13px; border-bottom:1px dashed #ede8e2;
}
.metric-row:last-child { border-bottom:none; }
.metric-label { color:#8a7e72; }
.metric-value { color:#2d2a24; font-weight:600; font-family:'Inter',monospace; }

.context-bar { height:8px; background:#e8e4de; border-radius:6px; margin:8px 0; overflow:hidden; }
.context-bar-fill {
    height:100%; background:linear-gradient(90deg, #f5a623, #f7c948);
    border-radius:6px; transition:width 0.6s ease;
}

.deco-dots {
    display:flex; gap:6px; padding:12px 20px;
    border-top:1px solid #ede8e2; flex-shrink:0;
}
.deco-dots span { width:8px; height:8px; border-radius:50%; background:#e0d6cc; }
.deco-dots span:nth-child(1) { background:#f5a623; }
.deco-dots span:nth-child(2) { background:#f7c948; }
.deco-dots span:nth-child(3) { background:#e8d5b5; }

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
.pulse { animation:pulse 2s ease-in-out infinite; }
</style>
</head>
<body>

<div class="header">
    <h1>Guo 助手</h1>
    <span class="status pulse" id="status">◉ 运行中</span>
    <button class="btn" onclick="pollAll()">↻ 刷新</button>
</div>

<div class="main">
    <div class="left">
        <div class="chat-header">对话记录</div>
        <div class="chat-container" id="chatContainer">
            <div class="empty-state" id="emptyState">
                <p>等待对话数据...</p>
            </div>
        </div>
        <div class="deco-dots"><span></span><span></span><span></span></div>
    </div>

    <div class="right">
        <div class="panel-section">
            <h3>运行指标</h3>
            <div class="metric-row"><span class="metric-label">运行时长</span><span class="metric-value" id="mRuntime">00:00</span></div>
            <div class="metric-row"><span class="metric-label">请求次数</span><span class="metric-value" id="mRequests">0</span></div>
            <div class="metric-row"><span class="metric-label">Token 入</span><span class="metric-value" id="mTokenIn">0</span></div>
            <div class="metric-row"><span class="metric-label">Token 出</span><span class="metric-value" id="mTokenOut">0</span></div>
            <div class="metric-row"><span class="metric-label">缓存命中</span><span class="metric-value" id="mCache">0%</span></div>
            <div class="metric-row"><span class="metric-label">费用</span><span class="metric-value" id="mCost">¥0</span></div>
        </div>
        <div class="panel-section">
            <h3>模型上下文</h3>
            <div class="context-bar"><div class="context-bar-fill" id="ctxBar" style="width:0%"></div></div>
            <div class="metric-row"><span class="metric-label">已用</span><span class="metric-value" id="ctxUsage">0</span></div>
            <div class="metric-row"><span class="metric-label">消息数</span><span class="metric-value" id="ctxMsgs">0</span></div>
        </div>
    </div>
</div>

<script>
let chatMsgs = []; let chatCount = 0;
function esc(t) { const d=document.createElement('div'); d.textContent=t; return d.innerHTML; }

function appendChat(n) {
    const c = document.getElementById('chatContainer');
    const empty = document.getElementById('emptyState');
    if (empty) empty.remove();
    for (let i = chatCount; i < n; i++) {
        const m = chatMsgs[i]; if (!m) continue;
        const side = m.role === 'user' ? 'user' : 'assistant';
        const src = m.source || (m.role === 'user' ? '用户' : '助手');
        const row = document.createElement('div');
        row.className = 'bubble-row ' + side; row.style.opacity = '0';
        const b = document.createElement('div');
        b.className = 'bubble ' + side;
        b.innerHTML = '<div class="source-tag">' + esc(src) + '</div>' + esc(m.content);
        row.appendChild(b);
        c.appendChild(row);
        gsap.to(row, { opacity:1, y:0, duration:0.4, ease:'back.out(1.4)', delay:Math.min((i-chatCount)*0.05,0.3) });
    }
    chatCount = n;
    if (n > 0) gsap.to(c, { scrollTop: c.scrollHeight, duration: 0.3 });
}

function renderMetrics(m) {
    document.getElementById('mRuntime').textContent = m.runtime_str;
    document.getElementById('mRequests').textContent = m.request_count;
    document.getElementById('mTokenIn').textContent = m.token_input_str;
    document.getElementById('mTokenOut').textContent = m.token_output_str;
    document.getElementById('mCache').textContent = m.cache_hit_rate + '%';
    document.getElementById('mCost').textContent = m.cost_str;
    const ctxMax = 8000, used = Math.min(m.token_input % (ctxMax * 3), ctxMax);
    gsap.to('#ctxBar', { width: Math.min(100, Math.round(used/ctxMax*100))+'%', duration:0.6, ease:'power2.out' });
    document.getElementById('ctxUsage').textContent = used + ' / ' + ctxMax;
    document.getElementById('ctxMsgs').textContent = m.request_count * 2;
}

async function pollAll() {
    try {
        const [cr, mr] = await Promise.all([
            fetch('/admin/api/chat-history'), fetch('/admin/api/metrics'),
        ]);
        const cd = await cr.json(), md = await mr.json();
        if ((cd.messages||[]).length > chatMsgs.length) { chatMsgs = cd.messages||[]; appendChat(chatMsgs.length); }
        renderMetrics(md);
    } catch(e) {
        const s = document.getElementById('status');
        s.textContent = '◉ 断开'; s.style.background = '#fce4e4'; s.style.color = '#c62828';
    }
}

gsap.from('.header', { y:-20, opacity:0, duration:0.5, ease:'power2.out' });
gsap.from('.left', { x:-20, opacity:0, duration:0.5, delay:0.1, ease:'power2.out' });
gsap.from('.right', { x:20, opacity:0, duration:0.5, delay:0.15, ease:'power2.out' });
pollAll();
setInterval(pollAll, 3000);
</script>
</body>
</html>"""



@admin_router.get("", response_class=HTMLResponse)
@admin_router.get("/", response_class=HTMLResponse)
def admin_page():
    return ADMIN_HTML
