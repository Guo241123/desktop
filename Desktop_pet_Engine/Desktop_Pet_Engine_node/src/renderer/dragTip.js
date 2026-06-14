import { setText } from "./api";

export function createDragTip() {
  const wrap = document.createElement('div');
  wrap.className = 'chat-bubble';
  wrap.style.display = 'none';
  document.body.appendChild(wrap);

  const replyBox = document.createElement('div');
  replyBox.className = 'reply-input-box';
  replyBox.style.display = 'none';
  document.body.appendChild(replyBox);

  replyBox.innerHTML = `<input type="text" class="reply-input" placeholder="输入回复..." />`;
  const replyInput = replyBox.querySelector('.reply-input');

  function openInputBox() {
    const rect = wrap.getBoundingClientRect();
    replyBox.style.left = rect.left + 'px';
    replyBox.style.top = rect.bottom + 6 + 'px';
    replyBox.style.display = 'block';
    replyInput.focus();
  }
  function closeInput() {
    replyBox.style.display = 'none';
  }

  wrap.onclick = openInputBox;

  document.addEventListener('contextmenu', e => {
    e.preventDefault();
    openInputBox();
  });

  document.addEventListener('click', e => {
    if (!wrap.contains(e.target) && !replyBox.contains(e.target)) {
      closeInput();
    }
  })


  replyInput.onkeydown = async (e) => {
    if (e.key === 'Enter') {
      let inputText = replyInput.value.trim();
      if (!inputText) return;

      replyInput.value = '';
      closeInput();

      // 1. 取全局路径
      const paths = window.droppedFilePaths || [];
      let sendText = inputText+"   文件路径:";

      // 2. 路径拼在消息后面
      if (paths.length > 0) {
        sendText += "\n";
        paths.forEach((p, i) => {
          sendText += `文件${i+1}：${p}`;
        });
      }

      // 3. 发送给后端
      try {
        const res = await setText(sendText);
        helloTip(res);
      } catch (err) {
        helloTip("发送失败");
      }
      window.droppedFilePaths = [];
    }
  };

  // 样式完全不变
  const style = document.createElement('style');
  style.textContent = `
    .chat-bubble {
      position: fixed;
      top: 7%; 
      left: 50%;
      transform: translate(-50%, -50%);
      width: 190px;
      min-height: 30px;
      padding: 5px 10px;
      background: #e6e4df;
      border: 2px solid #222222;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      color: #222;
      z-index: 999999 !important;
      box-sizing: border-box;
      pointer-events: auto;
      cursor: pointer;
      word-break: break-all;
      line-height: 1.4;
    }
    .chat-bubble::before {
      content: "";
      position: absolute;
      right: 22px;
      bottom: -7px;
      border-width: 7px 6px 0;
      border-style: solid;
      border-color:#222 transparent transparent;
      z-index: 1;
    }
    .chat-bubble::after {
      content: "";
      position: absolute;
      right: 22px;
      bottom: -4px;
      border-width: 5px 4px 0;
      border-style: solid;
      border-color: #e6e4df transparent transparent;
      z-index: 2;
    }
    .chat-bubble span {
      display: inline-block;
      opacity: 0;
      animation: jump 400ms ease forwards;
      animation-delay: var(--delay);
      margin: 0 1px;
    }
    @keyframes jump {
      0% { opacity: 0; transform: translateY(0); }
      50% { opacity: 1; transform: translateY(-4px); }
      100% { opacity: 1; transform: translateY(0); }
    }
    .reply-input-box {
      position: fixed;
      z-index: 999999;
      display: none;
    }
    .reply-input {
      width: 190px;
      height: 30px;
      background: #e6e4df;
      border: 2px solid #222222;
      border-radius: 8px;
      padding: 0 10px;
      font-size: 11px;
      color: #222;
      outline: none;
      box-sizing: border-box;
    }
  `;
  document.head.appendChild(style);

  const CHAR_DELAY = 90;
  const ANIM_DUR = 400;
  const LINE_STAY = 1000;
  const ALL_END_STAY = 1000;

  function safeReplaceAll(str, search, replacement) {
    if (typeof str !== 'string') return '';
    return str.replace(new RegExp(search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), replacement);
  }

  function splitAutoWrap(text) {
    let sb = '';
    let lineLen = 0;
    for (let i = 0; i < text.length; i++) {
      const c = text.charAt(i);
      sb += c;
      lineLen++;
      if (c === '。' || c === '，' || c === '？' || c === '！') {
        sb += '\n';
        lineLen = 0;
      } else if (lineLen >= 14) {
        sb += '\n';
        lineLen = 0;
      }
    }
    return sb.replace(/\n+/g, '\n').trim();
  }

  function setJumpText(text, cbFinish) {
    if (!text) text = "";
    const arr = safeReplaceAll(text, "\\n", "\n").split("\n").filter(i => i.trim());
    let totalTime = 0;

    function play(idx) {
      if (idx >= arr.length) {
        cbFinish && cbFinish();
        return;
      }
      const s = arr[idx];
      wrap.innerHTML = [...s].map((c, i) =>
        `<span style="--delay:${i * CHAR_DELAY}ms">${c}</span>`
      ).join("");
      const cost = (s.length - 1) * CHAR_DELAY + ANIM_DUR + LINE_STAY;
      totalTime += cost;
      setTimeout(() => play(idx + 1), cost);
    }
    play(0);
    return totalTime;
  }

  function showTip() {}
  function helloTip(resp) {
    wrap.style.display = 'flex';
    try {
      const text = typeof resp === 'object' ? resp.text || resp.msg : String(resp);
      setJumpText(splitAutoWrap(text), () => {
        setTimeout(() => wrap.style.display = 'none', ALL_END_STAY);
      });
    } catch (e) {
      setJumpText('消息解析失败');
    }
  }

  return { showTip, helloTip };
}