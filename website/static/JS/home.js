// ===== CHAT TOGGLE =====
function toggleChat() {
  const fab = document.getElementById('chat-fab');
  const box = document.getElementById('chat-box');
  const badge = document.getElementById('chat-badge');

  fab.classList.toggle('open');
  box.classList.toggle('open');

  if (box.classList.contains('open')) {
    if (badge) badge.style.display = 'none';
    const input = document.getElementById('user-input');
    if (input) input.focus();
  }
}


// ===== SEND MESSAGE =====
function sendMessage() {
  const input = document.getElementById("user-input");
  const msg = input.value.trim();

  if (!msg) return;

  const messages = document.getElementById("chat-messages");

  // 👉 show user message
  const userDiv = document.createElement('div');
  userDiv.className = 'msg user';
  userDiv.textContent = msg;
  messages.appendChild(userDiv);

  input.value = "";
  messages.scrollTop = messages.scrollHeight;

  // 👉 show typing indicator
  const typingDiv = document.createElement('div');
  typingDiv.className = 'msg bot';
  typingDiv.textContent = "Typing...";
  messages.appendChild(typingDiv);
  messages.scrollTop = messages.scrollHeight;

  // 👉 API call
  fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: msg })
  })
  .then(res => res.text())   // 🔥 FIX: avoid JSON crash
  .then(data => {
    console.log("RAW:", data);

    let reply = "Something went wrong";

    try {
      const json = JSON.parse(data);
      reply = json.reply;
    } catch (e) {
      reply = data; // fallback if not JSON
    }

    // remove typing
    typingDiv.remove();

    // show bot reply
    const botDiv = document.createElement('div');
    botDiv.className = 'msg bot';
    botDiv.textContent = reply;

    messages.appendChild(botDiv);
    messages.scrollTop = messages.scrollHeight;
  })
  .catch(err => {
    typingDiv.remove();

    const errorDiv = document.createElement('div');
    errorDiv.className = 'msg bot';
    errorDiv.textContent = "Error connecting to server";

    messages.appendChild(errorDiv);
    console.error(err);
  });
}


// ===== ENTER KEY SUPPORT =====
document.addEventListener("DOMContentLoaded", function () {
  const input = document.getElementById("user-input");

  if (input) {
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        sendMessage();
      }
    });
  }
});