const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");
const sendButton = document.getElementById("send-button");
const serverListEl = document.getElementById("server-list");
const toolListEl = document.getElementById("tool-list");
const sidebarEl = document.getElementById("sidebar");
const toggleSidebarButton = document.getElementById("toggle-sidebar");

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

function addToolCard(toolCall) {
  const card = document.createElement("div");
  card.className = "tool-card" + (toolCall.error ? " error" : "");

  const name = document.createElement("div");
  name.className = "tool-name";
  name.textContent = (toolCall.error ? "Tool call failed: " : "Tool call: ") + toolCall.tool;
  card.appendChild(name);

  const input = document.createElement("div");
  input.textContent = "input: " + JSON.stringify(toolCall.input);
  card.appendChild(input);

  const output = document.createElement("div");
  output.className = "tool-output";
  output.textContent = toolCall.output;
  card.appendChild(output);

  messagesEl.appendChild(card);
  scrollToBottom();
}

function addTyping() {
  const el = document.createElement("div");
  el.className = "typing";
  el.textContent = "The assistant is thinking…";
  messagesEl.appendChild(el);
  scrollToBottom();
  return el;
}

async function loadSidebar() {
  try {
    const [servers, tools] = await Promise.all([
      fetch("/api/servers").then((r) => r.json()),
      fetch("/api/tools").then((r) => r.json()),
    ]);

    serverListEl.innerHTML = "";
    if (servers.length === 0) {
      serverListEl.innerHTML = '<li class="muted">No server connected</li>';
    } else {
      for (const id of servers) {
        const li = document.createElement("li");
        li.innerHTML = `<span class="server-dot"></span>${id}`;
        serverListEl.appendChild(li);
      }
    }

    toolListEl.innerHTML = "";
    for (const tool of tools) {
      const li = document.createElement("li");
      li.innerHTML = `<b>${tool.id}</b><span>${tool.description}</span>`;
      toolListEl.appendChild(li);
    }
  } catch (err) {
    serverListEl.innerHTML = '<li class="muted">Could not load</li>';
  }
}

async function sendMessage(text) {
  addMessage("user", text);
  inputEl.value = "";
  sendButton.disabled = true;
  const typingEl = addTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    typingEl.remove();

    for (const toolCall of data.tool_calls || []) {
      addToolCard(toolCall);
    }
    addMessage("assistant", data.reply);
  } catch (err) {
    typingEl.remove();
    addMessage("assistant", "Something went wrong talking to the server, please try again.");
  } finally {
    sendButton.disabled = false;
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  sendMessage(text);
});

toggleSidebarButton.addEventListener("click", () => {
  sidebarEl.classList.toggle("open");
});

loadSidebar();
inputEl.focus();
