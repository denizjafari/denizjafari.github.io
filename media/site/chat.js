/**
 * chat.js — minimal client for the deniz-chat Cloudflare Worker.
 *
 * Reads the API URL from <meta name="chat-api" content="...">.
 * Opens a HUD-styled modal, sends messages, renders replies, and gracefully
 * surfaces the topic-gate refusals coming back from the Worker.
 *
 * No keys, no PII, no localStorage. History lives in memory until the modal
 * closes, then it's discarded.
 */

(() => {
  const apiMeta = document.querySelector('meta[name="chat-api"]');
  const API_URL = apiMeta ? apiMeta.getAttribute("content") : "";

  const modal = document.getElementById("chat-modal");
  if (!modal) return;

  const log = modal.querySelector("[data-chat-log]");
  const form = modal.querySelector("[data-chat-form]");
  const input = modal.querySelector("[data-chat-input]");
  const sendBtn = modal.querySelector("[data-chat-send]");
  const statusText = modal.querySelector("[data-chat-status-text]");
  const statusEl = modal.querySelector("[data-chat-status]");

  const history = []; // [{role:'user'|'assistant', content:string}]
  let busy = false;

  // ---------- modal open/close ----------
  function openChat() {
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    setTimeout(() => input.focus(), 80);
    if (!log.children.length) {
      addMessage(
        "assistant",
        "Hi — ask me about Deniz's research, projects, papers, teaching, or consulting. " +
        "I'll only answer professional questions. Try \"What was your MSc thesis about?\" or \"What are you building right now?\""
      );
    }
  }

  function closeChat() {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  document.querySelectorAll("[data-open-chat]").forEach((el) => {
    el.addEventListener("click", openChat);
  });
  modal.querySelectorAll("[data-close-chat]").forEach((el) => {
    el.addEventListener("click", closeChat);
  });
  document.addEventListener("keydown", (e) => {
    if (!modal.hidden && e.key === "Escape") closeChat();
  });

  // ---------- rendering ----------
  function addMessage(role, text, opts = {}) {
    const wrap = document.createElement("div");
    wrap.className = `chat-msg chat-msg--${role}`;
    if (opts.refusal) wrap.classList.add("chat-msg--refusal");

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    // Render the text with simple paragraph + line-break support, no HTML.
    text.split(/\n{2,}/).forEach((p, idx) => {
      if (idx > 0) bubble.appendChild(document.createElement("br"));
      const para = document.createElement("p");
      p.split(/\n/).forEach((line, li) => {
        if (li > 0) para.appendChild(document.createElement("br"));
        para.appendChild(document.createTextNode(line));
      });
      bubble.appendChild(para);
    });

    if (opts.sources && opts.sources.length) {
      const meta = document.createElement("div");
      meta.className = "chat-sources";
      const unique = [...new Set(opts.sources)];
      meta.textContent = "// sources: " + unique.join(", ");
      bubble.appendChild(meta);
    }

    wrap.appendChild(bubble);
    log.appendChild(wrap);
    log.scrollTop = log.scrollHeight;
    return wrap;
  }

  function setStatus(text, mode = "idle") {
    statusText.textContent = text;
    statusEl.dataset.mode = mode; // idle | thinking | error
  }

  function setBusy(b) {
    busy = b;
    sendBtn.disabled = b;
    input.disabled = b;
    sendBtn.classList.toggle("is-loading", b);
  }

  // ---------- send ----------
  async function send(message) {
    if (!API_URL || /REPLACE-ME/i.test(API_URL)) {
      setStatus("Chat backend not configured yet.", "error");
      addMessage(
        "assistant",
        "The chatbot isn't wired up yet — the worker URL still needs to be set. " +
        "In the meantime, the contact form below goes straight to the inbox.",
        { refusal: true }
      );
      return;
    }

    addMessage("user", message);
    history.push({ role: "user", content: message });

    const thinking = addMessage("assistant", "thinking…");
    thinking.classList.add("chat-msg--thinking");
    setStatus("Routing through the operator…", "thinking");
    setBusy(true);

    let data;
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message, history }),
      });
      if (res.status === 429) {
        thinking.remove();
        addMessage(
          "assistant",
          "Easy on the trigger — too many messages in a minute. Give it ~30 seconds and try again.",
          { refusal: true }
        );
        setStatus("Rate-limited.", "error");
        setBusy(false);
        return;
      }
      data = await res.json();
      if (!res.ok) throw new Error(data?.error || `HTTP ${res.status}`);
    } catch (err) {
      thinking.remove();
      addMessage(
        "assistant",
        "Connection to the chat backend just dropped. The contact form below still works.",
        { refusal: true }
      );
      setStatus("Connection error.", "error");
      setBusy(false);
      return;
    }

    thinking.remove();

    if (data.on_topic === false) {
      addMessage("assistant", data.reply || "I only answer professional questions.", {
        refusal: true,
      });
      setStatus("Off-topic — try a research/project question.", "idle");
    } else {
      addMessage("assistant", data.reply || "(no reply)", {
        sources: data.sources,
      });
      history.push({ role: "assistant", content: data.reply || "" });
      if (data.lead_recorded) {
        setStatus("Lead recorded — Deniz will follow up.", "idle");
      } else {
        setStatus("Idle. Ask another question.", "idle");
      }
    }

    setBusy(false);
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (busy) return;
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    autoresize();
    send(text);
  });

  // submit on Enter, newline on Shift+Enter
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  // simple textarea autoresize
  function autoresize() {
    input.style.height = "auto";
    input.style.height = Math.min(160, input.scrollHeight) + "px";
  }
  input.addEventListener("input", autoresize);
})();
