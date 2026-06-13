/* Shinobi Copilot widget — injects a floating editing copilot into any page.
   Calls /api/copilot (server-side proxy) so no API key is exposed client-side. */
(function () {
  'use strict';

  if (document.getElementById('cw-fab')) return; // already injected

  // ---------------------------------------------------------------------
  // Styles
  // ---------------------------------------------------------------------
  var style = document.createElement('style');
  style.textContent = `
  #cw-fab {
    position: fixed;
    bottom: 24px; right: 24px;
    width: 64px; height: 40px;
    border-radius: 8px;
    border: none;
    cursor: pointer;
    z-index: 2147483000;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, #8b5cf6, #ff4d5e, #8b5cf6);
    background-size: 200% 200%;
    animation: cw-gradient-rotate 6s ease infinite;
    box-shadow: 0 4px 24px rgba(139,92,246,0.5);
    padding: 0;
    font-family: 'Molgan', Arial, Helvetica, sans-serif;
  }
  @keyframes cw-gradient-rotate {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  #cw-fab::before {
    content: '';
    position: absolute;
    inset: -6px;
    border-radius: 12px;
    border: 2px solid rgba(139,92,246,0.55);
    animation: cw-pulse-ring 2.2s cubic-bezier(0.4,0,0.6,1) infinite;
  }
  @keyframes cw-pulse-ring {
    0% { transform: scale(0.9); opacity: 0.7; }
    70% { transform: scale(1.35); opacity: 0; }
    100% { transform: scale(1.35); opacity: 0; }
  }
  #cw-fab .cw-icon-wrap { position: relative; width: 22px; height: 22px; }
  #cw-fab svg {
    position: absolute; inset: 0;
    width: 22px; height: 22px;
    transition: opacity 0.18s ease, transform 0.18s ease;
  }
  #cw-fab .cw-icon-close { opacity: 0; transform: rotate(-45deg) scale(0.6); }
  #cw-fab .cw-icon-sparkle { opacity: 1; transform: rotate(0) scale(1); animation: cw-icon-pulse 2s ease-in-out infinite; }
  @keyframes cw-icon-pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.18); opacity: 0.8; }
  }
  #cw-fab.cw-open .cw-icon-close { opacity: 1; transform: rotate(0) scale(1); }
  #cw-fab.cw-open .cw-icon-sparkle { opacity: 0; transform: rotate(45deg) scale(0.6); animation: none; }

  #cw-panel {
    position: fixed;
    bottom: 24px; right: 24px;
    width: 380px; height: 520px;
    background: transparent;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 0px;
    box-shadow: 0 24px 64px rgba(0,0,0,0.6);
    z-index: 2147483000;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    clip-path: inset(calc(100% - 40px) 0px 0px calc(100% - 64px));
    transition: clip-path 320ms cubic-bezier(0.34,1.56,0.64,1);
    pointer-events: none;
    font-family: 'Molgan', Arial, Helvetica, sans-serif;
    max-width: calc(100vw - 24px);
    max-height: calc(100vh - 24px);
  }
  #cw-panel.cw-open {
    clip-path: inset(0px 0px 0px 0px);
    pointer-events: auto;
    background: #0d0d14;
  }
  #cw-panel-content {
    display: flex;
    flex-direction: column;
    height: 100%;
    opacity: 0;
    transition: opacity 180ms ease;
  }
  #cw-panel.cw-content-visible #cw-panel-content { opacity: 1; }

  #cw-header {
    height: 52px;
    flex: 0 0 52px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 14px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    background: linear-gradient(120deg, rgba(139,92,246,0.18), rgba(255,77,94,0.08));
  }
  #cw-header .cw-header-icon {
    width: 22px; height: 22px;
    display: flex; align-items: center; justify-content: center;
    color: #c4b3ff;
    flex-shrink: 0;
  }
  #cw-header .cw-header-title { font-weight: 600; font-size: 14px; flex: 1; color: #f0eefa; }
  #cw-header button {
    background: none; border: none; cursor: pointer;
    color: #b8b4c8;
    width: 28px; height: 28px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    transition: background 0.15s, color 0.15s;
    padding: 0;
  }
  #cw-header button:hover { background: rgba(255,255,255,0.08); color: #fff; }
  #cw-header button svg { width: 16px; height: 16px; }

  #cw-messages {
    flex: 1 1 auto;
    overflow-y: auto;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  #cw-messages::-webkit-scrollbar { width: 4px; }
  #cw-messages::-webkit-scrollbar-track { background: transparent; }
  #cw-messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.15); border-radius: 4px; }

  .cw-msg {
    max-width: 84%;
    padding: 9px 13px;
    font-size: 13.5px;
    line-height: 1.5;
    word-wrap: break-word;
    animation: cw-msg-in 0.22s ease;
  }
  @keyframes cw-msg-in {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .cw-msg.cw-user {
    align-self: flex-end;
    background: linear-gradient(135deg, #8b5cf6, #ff4d5e);
    color: #fff;
    border-radius: 18px 18px 4px 18px;
  }
  .cw-msg.cw-assistant {
    align-self: flex-start;
    background: rgba(255,255,255,0.06);
    color: #e8e6f0;
    border-radius: 18px 18px 18px 4px;
  }
  .cw-msg code {
    background: rgba(0,0,0,0.35);
    padding: 1px 5px;
    border-radius: 4px;
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 12px;
  }
  .cw-msg ul { margin: 4px 0; padding-left: 18px; }
  .cw-msg strong { font-weight: 700; }

  .cw-typing {
    align-self: flex-start;
    display: flex; align-items: center; gap: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 18px 18px 18px 4px;
    padding: 11px 14px;
    animation: cw-msg-in 0.22s ease;
  }
  .cw-typing span {
    width: 6px; height: 6px; border-radius: 50%;
    background: #c4b3ff;
    animation: cw-bounce 1.2s infinite ease-in-out;
  }
  .cw-typing span:nth-child(2) { animation-delay: 0.15s; }
  .cw-typing span:nth-child(3) { animation-delay: 0.3s; }
  @keyframes cw-bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
  }

  #cw-quick-actions { display: flex; gap: 6px; padding: 0 14px 10px; flex-wrap: wrap; }
  .cw-pill-action {
    background: rgba(139,92,246,0.12);
    border: 1px solid rgba(139,92,246,0.35);
    color: #c4b3ff;
    font-size: 12px;
    padding: 6px 12px;
    border-radius: 999px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
    font-family: inherit;
  }
  .cw-pill-action:hover { background: rgba(139,92,246,0.22); border-color: rgba(139,92,246,0.6); }

  #cw-selection-pill {
    display: none;
    align-items: center;
    gap: 8px;
    margin: 0 14px 8px;
    padding: 6px 10px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    font-size: 11.5px;
    color: #b8b4c8;
  }
  #cw-selection-pill.cw-show { display: flex; }
  #cw-selection-pill .cw-sel-label { color: #c4b3ff; font-weight: 600; flex-shrink: 0; }
  #cw-selection-pill .cw-sel-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #cw-selection-pill button { background: none; border: none; color: #b8b4c8; cursor: pointer; font-size: 14px; line-height: 1; padding: 0; flex-shrink: 0; }
  #cw-selection-pill button:hover { color: #fff; }

  #cw-input-area {
    flex: 0 0 auto;
    padding: 10px 12px 12px;
    border-top: 1px solid rgba(255,255,255,0.08);
    display: flex;
    align-items: flex-end;
    gap: 8px;
  }
  #cw-input-wrap {
    flex: 1;
    position: relative;
    display: flex;
    align-items: flex-end;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 14px;
    padding: 8px 44px 8px 12px;
    transition: border-color 0.15s;
  }
  #cw-input-wrap:focus-within { border-color: rgba(139,92,246,0.5); }
  #cw-input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    resize: none;
    color: #f0eefa;
    font-family: inherit;
    font-size: 13.5px;
    line-height: 1.4;
    max-height: 120px;
    min-height: 20px;
  }
  #cw-input::placeholder { color: #6e6b80; }
  #cw-send {
    position: absolute;
    right: 6px; bottom: 6px;
    width: 30px; height: 30px;
    border-radius: 50%;
    border: none;
    cursor: pointer;
    background: linear-gradient(135deg, #8b5cf6, #ff4d5e);
    display: flex; align-items: center; justify-content: center;
    transition: opacity 0.15s, transform 0.1s;
  }
  #cw-send:active { transform: scale(0.92); }
  #cw-send:disabled { opacity: 0.4; cursor: default; }
  #cw-send svg { width: 14px; height: 14px; color: #fff; }

  #cw-preview {
    position: fixed;
    bottom: 30px;
    right: 86px;
    max-width: 220px;
    background: #1a1a2e;
    border: 1px solid rgba(139,92,246,0.35);
    border-radius: 0px;
    padding: 10px 14px;
    font-size: 13px;
    color: #c4b3ff;
    z-index: 2147482999;
    opacity: 0;
    transform: translateX(12px);
    transition: opacity 400ms ease-out, transform 400ms ease-out;
    pointer-events: none;
    font-family: 'Molgan', Arial, Helvetica, sans-serif;
  }
  #cw-preview.cw-show { opacity: 1; transform: translateX(0); pointer-events: auto; }
  #cw-preview.cw-exit { opacity: 0; transform: translateX(-8px); transition: opacity 300ms ease-in, transform 300ms ease-in; }
  #cw-preview-dots { display: flex; gap: 5px; margin-top: 8px; }
  #cw-preview-dots span { width: 6px; height: 6px; border-radius: 999px; background: rgba(255,255,255,0.15); transition: all 300ms ease; }
  #cw-preview-dots span.cw-active { width: 12px; background: #8b5cf6; }

  .cw-model-picker { position: relative; font-family: inherit; }
  .cw-model-btn {
    display: flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.15);
    color: #f0eefa;
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 11px; font-weight: 600;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
    font-family: inherit;
  }
  .cw-model-btn:hover { background: rgba(255,255,255,0.1); border-color: #8b5cf6; }
  .cw-model-dot { width: 7px; height: 7px; border-radius: 50%; background: #8b5cf6; box-shadow: 0 0 8px rgba(139,92,246,0.7); }
  .cw-model-caret { font-size: 9px; color: #9b96a8; margin-left: 1px; }
  .cw-model-menu {
    position: absolute; top: calc(100% + 6px); right: 0;
    width: 250px;
    background: #1a1a26;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    padding: 6px;
    z-index: 2147483001;
    box-shadow: 0 12px 32px -8px rgba(0,0,0,0.6);
  }
  .cw-model-menu.cw-hidden { display: none; }
  .cw-model-menu-section {
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em;
    color: #9b96a8; padding: 8px 10px 4px;
  }
  .cw-model-option { padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: background 0.12s; }
  .cw-model-option:hover { background: rgba(255,255,255,0.06); }
  .cw-model-option.cw-selected { background: rgba(139,92,246,0.15); }
  .cw-model-option-main { display: flex; align-items: center; gap: 8px; }
  .cw-model-name { font-size: 12.5px; font-weight: 600; }
  .cw-model-badge {
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    color: #34d399; border: 1px solid #34d399;
    border-radius: 4px; padding: 1px 5px;
  }
  .cw-model-option-desc { font-size: 11px; color: #9b96a8; margin-top: 2px; line-height: 1.4; }

  @media (max-width: 480px) {
    #cw-panel { width: calc(100vw - 24px); height: 70vh; }
    #cw-preview { display: none; }
  }
  `;
  document.head.appendChild(style);

  // ---------------------------------------------------------------------
  // Markup
  // ---------------------------------------------------------------------
  var wrap = document.createElement('div');
  wrap.innerHTML = `
  <button id="cw-fab" aria-label="Open editing copilot" aria-haspopup="dialog" aria-expanded="false">
    <span class="cw-icon-wrap">
      <svg class="cw-icon-sparkle" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C12 2 12.5 8.5 15.5 11.5C18.5 14.5 22 15 22 15C22 15 18.5 15.5 15.5 18.5C12.5 21.5 12 22 12 22C12 22 11.5 21.5 8.5 18.5C5.5 15.5 2 15 2 15C2 15 5.5 14.5 8.5 11.5C11.5 8.5 12 2 12 2Z" fill="#fff"/>
        </svg>
      <svg class="cw-icon-close" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M6 6L18 18M18 6L6 18" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>
      </svg>
    </span>
  </button>

  <div id="cw-preview" role="status" aria-hidden="true">
    <div id="cw-preview-text"></div>
    <div id="cw-preview-dots"><span></span><span></span><span></span></div>
  </div>

  <div id="cw-panel" role="dialog" aria-label="Editing copilot" aria-modal="false">
    <div id="cw-panel-content">
      <div id="cw-header">
        <span class="cw-header-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C12 2 12.5 8.5 15.5 11.5C18.5 14.5 22 15 22 15C22 15 18.5 15.5 15.5 18.5C12.5 21.5 12 22 12 22C12 22 11.5 21.5 8.5 18.5C5.5 15.5 2 15 2 15C2 15 5.5 14.5 8.5 11.5C11.5 8.5 12 2 12 2Z" fill="currentColor"/>
          </svg>
        </span>
        <span class="cw-header-title">Copilot</span>
        <div class="cw-model-picker">
          <button class="cw-model-btn" id="cw-model-btn" type="button">
            <span class="cw-model-dot"></span>
            <span id="cw-model-label">Katana 5.5</span>
            <span class="cw-model-caret">&#9662;</span>
          </button>
          <div class="cw-model-menu cw-hidden" id="cw-model-menu">
            <div class="cw-model-menu-section">Most capable</div>
            <div class="cw-model-option" data-model="katana-5.5">
              <div class="cw-model-option-main"><span class="cw-model-name">Katana 5.5</span><span class="cw-model-badge">New</span></div>
              <div class="cw-model-option-desc">Sharpest editing — best for nuanced, high-stakes clip selection</div>
            </div>
            <div class="cw-model-option" data-model="wakizashi-4.5">
              <div class="cw-model-option-main"><span class="cw-model-name">Wakizashi 4.5</span></div>
              <div class="cw-model-option-desc">Balanced speed and quality for everyday repurposing</div>
            </div>
            <div class="cw-model-menu-section">Fast</div>
            <div class="cw-model-option" data-model="kunai-4.5">
              <div class="cw-model-option-main"><span class="cw-model-name">Kunai 4.5</span></div>
              <div class="cw-model-option-desc">Quick turnaround for simple, low-stakes clips</div>
            </div>
            <div class="cw-model-option" data-model="shuriken-3.5">
              <div class="cw-model-option-main"><span class="cw-model-name">Shuriken 3.5</span></div>
              <div class="cw-model-option-desc">Lightweight and fast, for quick drafts</div>
            </div>
          </div>
        </div>
        <button id="cw-clear" aria-label="Clear chat" title="Clear chat">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0-1 14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1L5 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <button id="cw-close" aria-label="Close copilot panel" title="Close">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 6L18 18M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>
      </div>

      <div id="cw-messages"></div>

      <div id="cw-quick-actions">
        <button class="cw-pill-action" data-text="Improve my writing">Improve writing</button>
        <button class="cw-pill-action" data-text="Summarise this for me">Summarise</button>
        <button class="cw-pill-action" data-text="Rewrite this">Rewrite this</button>
      </div>

      <div id="cw-selection-pill">
        <span class="cw-sel-label">Selected:</span>
        <span class="cw-sel-text" id="cw-sel-text"></span>
        <button id="cw-sel-clear" aria-label="Dismiss selected text">&times;</button>
      </div>

      <div id="cw-input-area">
        <div id="cw-input-wrap">
          <textarea id="cw-input" rows="1" placeholder="Ask the copilot..." aria-label="Message"></textarea>
          <button id="cw-send" aria-label="Send message" disabled>
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M5 12L19 12M19 12L13 6M19 12L13 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
  `;
  while (wrap.firstChild) document.body.appendChild(wrap.firstChild);

  // ---------------------------------------------------------------------
  // Behavior
  // ---------------------------------------------------------------------
  var fab = document.getElementById('cw-fab');
  var panel = document.getElementById('cw-panel');
  var messagesEl = document.getElementById('cw-messages');
  var input = document.getElementById('cw-input');
  var sendBtn = document.getElementById('cw-send');
  var clearBtn = document.getElementById('cw-clear');
  var closeBtn = document.getElementById('cw-close');
  var quickActions = document.getElementById('cw-quick-actions');
  var selPill = document.getElementById('cw-selection-pill');
  var selText = document.getElementById('cw-sel-text');
  var selClear = document.getElementById('cw-sel-clear');
  var preview = document.getElementById('cw-preview');
  var previewText = document.getElementById('cw-preview-text');
  var previewDots = document.getElementById('cw-preview-dots');

  var isOpen = false;
  var conversation = [];
  var pendingContext = '';
  var firstMessageSent = false;
  var typingEl = null;

  var pageTitle = document.title;
  var pagePreview = (document.body.innerText || '').trim().slice(0, 2000);

  function buildSystemPrompt() {
    var base = 'You are an intelligent editing copilot embedded in a webpage, help users with ' +
      'writing editing summarising rewriting and explaining content, be concise and direct, ' +
      'format responses cleanly, page context: ' + pageTitle + ', page preview: ' + pagePreview;
    if (pendingContext) {
      base = 'Selected text from the page: "' + pendingContext + '"\n\n' + base;
    }
    return base;
  }

  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function inlineMd(text) {
    var escaped = escapeHtml(text);
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return escaped;
  }

  function renderMarkdown(text) {
    var lines = text.split('\n');
    var html = '';
    var inList = false;
    lines.forEach(function (line) {
      var trimmed = line.trim();
      if (/^[-*]\s+/.test(trimmed)) {
        if (!inList) { html += '<ul>'; inList = true; }
        html += '<li>' + inlineMd(trimmed.replace(/^[-*]\s+/, '')) + '</li>';
      } else {
        if (inList) { html += '</ul>'; inList = false; }
        if (trimmed.length) html += '<div>' + inlineMd(trimmed) + '</div>';
        else html += '<div style="height:6px"></div>';
      }
    });
    if (inList) html += '</ul>';
    return html;
  }

  function addMessage(role, text) {
    var el = document.createElement('div');
    el.className = 'cw-msg ' + (role === 'user' ? 'cw-user' : 'cw-assistant');
    if (role === 'user') el.textContent = text;
    else el.innerHTML = renderMarkdown(text);
    messagesEl.appendChild(el);
    scrollToBottom();
    return el;
  }

  function showTyping() {
    typingEl = document.createElement('div');
    typingEl.className = 'cw-typing';
    typingEl.innerHTML = '<span></span><span></span><span></span>';
    messagesEl.appendChild(typingEl);
    scrollToBottom();
  }

  function hideTyping() {
    if (typingEl) { typingEl.remove(); typingEl = null; }
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function saveInstruction(text) {
    try {
      var existing = JSON.parse(localStorage.getItem('shinobi_instructions') || '[]');
      existing.push(text);
      localStorage.setItem('shinobi_instructions', JSON.stringify(existing));
    } catch (e) {
      localStorage.setItem('shinobi_instructions', JSON.stringify([text]));
    }
  }

  function sendMessage(text) {
    text = text.trim();
    if (!text) return;

    if (!firstMessageSent) {
      quickActions.style.display = 'none';
      firstMessageSent = true;
    }

    addMessage('user', text);
    conversation.push({ role: 'user', content: text });
    saveInstruction(text);
    input.value = '';
    autoResize();
    updateSendState();

    pendingContext = '';
    selPill.classList.remove('cw-show');

    showTyping();

    fetch('/api/copilot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        system: buildSystemPrompt(),
        messages: conversation
      })
    })
      .then(function (res) { return res.json(); })
      .then(function (json) {
        hideTyping();
        var reply = '';
        if (json && json.success && json.data && json.data.content && json.data.content[0]) {
          reply = json.data.content[0].text;
        } else {
          reply = '**Error:** ' + (json && json.error ? json.error : 'Something went wrong.');
        }
        addMessage('assistant', reply);
        conversation.push({ role: 'assistant', content: reply });
        maybeApplyEdit(text);
      })
      .catch(function (err) {
        hideTyping();
        addMessage('assistant', '**Error:** ' + err.message);
      });
  }

  // If we're on the repurpose page and a job has finished, let Copilot
  // re-render the clips based on this instruction (e.g. "remove more silence").
  function maybeApplyEdit(instruction) {
    if (typeof currentJobId === 'undefined' || !currentJobId) return;
    if (typeof lastResult === 'undefined' || !lastResult) return;

    fetch('/api/copilot/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: currentJobId, instruction: instruction })
    })
      .then(function (res) { return res.json(); })
      .then(function (json) {
        if (!json || !json.success || !json.data || !json.data.applied) return;
        (json.data.clips || []).forEach(function (c) {
          if (lastResult.clips[c.index]) {
            lastResult.clips[c.index].video_url = c.video_url;
          }
        });
        if (json.data.new_clip) {
          lastResult.clips.push(json.data.new_clip);
        }
        if (typeof renderResults === 'function') renderResults();
        addMessage('assistant', '_' + json.data.reply + '_');
      })
      .catch(function () { /* silent — editing is best-effort */ });
  }

  function autoResize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  }

  function updateSendState() {
    sendBtn.disabled = input.value.trim().length === 0;
  }

  input.addEventListener('input', function () { autoResize(); updateSendState(); });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.value.trim()) sendMessage(input.value);
    }
  });
  sendBtn.addEventListener('click', function () {
    if (input.value.trim()) sendMessage(input.value);
  });
  quickActions.querySelectorAll('.cw-pill-action').forEach(function (btn) {
    btn.addEventListener('click', function () { sendMessage(btn.getAttribute('data-text')); });
  });
  clearBtn.addEventListener('click', function () {
    conversation = [];
    messagesEl.innerHTML = '';
    firstMessageSent = false;
    quickActions.style.display = 'flex';
    localStorage.removeItem('shinobi_instructions');
  });

  document.addEventListener('mouseup', function (e) {
    if (panel.contains(e.target) || fab.contains(e.target)) return;
    var sel = window.getSelection().toString().trim();
    if (sel) {
      pendingContext = sel;
      if (isOpen) showSelectionPill();
      if (showingSelectionPreview === false) { /* handled in cycle */ }
    } else if (showingSelectionPreview) {
      showingSelectionPreview = false;
    }
  });

  function showSelectionPill() {
    if (!pendingContext) { selPill.classList.remove('cw-show'); return; }
    selText.textContent = pendingContext;
    selPill.classList.add('cw-show');
  }

  selClear.addEventListener('click', function () {
    pendingContext = '';
    selPill.classList.remove('cw-show');
  });

  function openPanel() {
    isOpen = true;
    fab.classList.add('cw-open');
    fab.setAttribute('aria-expanded', 'true');
    panel.classList.add('cw-open');
    hidePreviewForever();
    showSelectionPill();
    setTimeout(function () {
      panel.classList.add('cw-content-visible');
      input.focus();
    }, 200);
  }

  function closePanel() {
    isOpen = false;
    fab.classList.remove('cw-open');
    fab.setAttribute('aria-expanded', 'false');
    panel.classList.remove('cw-content-visible');
    setTimeout(function () {
      panel.classList.remove('cw-open');
      fab.focus();
    }, 150);
  }

  fab.addEventListener('click', function () { isOpen ? closePanel() : openPanel(); });
  closeBtn.addEventListener('click', closePanel);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && isOpen) closePanel();
  });

  // -- Preview bubbles --
  var PREVIEW_MESSAGES = [
    'Improve my writing', 'Summarise this page', 'Rewrite more clearly', 'Explain this to me',
    'Make this more concise', 'Make this hook stronger', 'What is the key insight',
    'Rewrite for Twitter', 'Fix the grammar', 'Make this more engaging'
  ];
  var SELECTION_PREVIEW = 'Ask about your selection';
  var previewIndex = 0;
  var previewTimer = null;
  var previewEnabled = true;
  var showingSelectionPreview = false;

  function buildDots() {
    previewDots.innerHTML = '';
    for (var i = 0; i < 3; i++) previewDots.appendChild(document.createElement('span'));
    updateDots();
  }

  function updateDots() {
    previewDots.querySelectorAll('span').forEach(function (d, i) {
      d.classList.toggle('cw-active', i === (previewIndex % 3));
    });
  }

  function showPreview(text) {
    previewText.textContent = text;
    updateDots();
    preview.classList.remove('cw-exit');
    preview.classList.add('cw-show');
    preview.setAttribute('aria-hidden', 'false');
  }

  function hidePreview(cb) {
    preview.classList.remove('cw-show');
    preview.classList.add('cw-exit');
    preview.setAttribute('aria-hidden', 'true');
    setTimeout(function () {
      preview.classList.remove('cw-exit');
      if (cb) cb();
    }, 300);
  }

  function cyclePreview() {
    if (!previewEnabled || isOpen) return;

    if (pendingContext) {
      if (!showingSelectionPreview) {
        showingSelectionPreview = true;
        hidePreview(function () {
          if (!previewEnabled || isOpen) return;
          showPreview(SELECTION_PREVIEW);
        });
      }
      previewTimer = setTimeout(cyclePreview, 600);
      return;
    }
    showingSelectionPreview = false;

    showPreview(PREVIEW_MESSAGES[previewIndex % PREVIEW_MESSAGES.length]);

    previewTimer = setTimeout(function () {
      hidePreview(function () {
        previewIndex++;
        previewTimer = setTimeout(cyclePreview, 500);
      });
    }, 2800);
  }

  function hidePreviewForever() {
    previewEnabled = false;
    if (previewTimer) clearTimeout(previewTimer);
    hidePreview();
  }

  preview.style.pointerEvents = 'auto';
  preview.addEventListener('click', function () { hidePreviewForever(); });

  // -- Model picker --
  var MODEL_LABELS = {
    'katana-5.5': 'Katana 5.5',
    'wakizashi-4.5': 'Wakizashi 4.5',
    'kunai-4.5': 'Kunai 4.5',
    'shuriken-3.5': 'Shuriken 3.5',
  };
  var modelBtn = document.getElementById('cw-model-btn');
  var modelMenu = document.getElementById('cw-model-menu');
  var modelLabel = document.getElementById('cw-model-label');
  var selectedModel = localStorage.getItem('shinobi_model') || 'katana-5.5';
  modelLabel.textContent = MODEL_LABELS[selectedModel] || 'Katana 5.5';
  modelMenu.querySelectorAll('.cw-model-option').forEach(function (el) {
    el.classList.toggle('cw-selected', el.getAttribute('data-model') === selectedModel);
    el.addEventListener('click', function () {
      selectedModel = el.getAttribute('data-model');
      localStorage.setItem('shinobi_model', selectedModel);
      modelLabel.textContent = MODEL_LABELS[selectedModel];
      modelMenu.querySelectorAll('.cw-model-option').forEach(function (o) {
        o.classList.toggle('cw-selected', o === el);
      });
      modelMenu.classList.add('cw-hidden');
    });
  });
  modelBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    modelMenu.classList.toggle('cw-hidden');
  });
  document.addEventListener('click', function (e) {
    if (!modelMenu.contains(e.target) && e.target !== modelBtn) modelMenu.classList.add('cw-hidden');
  });

  buildDots();
  setTimeout(function () {
    if (!isOpen && previewEnabled) cyclePreview();
  }, 2000);
})();
