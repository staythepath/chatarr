import { setupPopoverHideWithDelay, showPersonPopover } from "./popovers.js";

function markdownToHTML(text) {
  // Convert names wrapped in # into clickable links
  let htmlText = text.replace(
    /#([^#]+)#/g,
    "<a href='#' class='person-link' (\"$1\")'>$1</a>"
  );

  // Convert italics
  htmlText = htmlText.replace(/\*([^\*]+)\*/g, "<em>$1</em>");

  // Convert bullet points with indentation
  htmlText = htmlText.replace(
    /^- (.+)$/gm,
    "<li style='margin-left: 20px;'>$1</li>"
  );
  htmlText = "<ul>" + htmlText + "</ul>"; // Wrap with <ul> tag

  return htmlText;
}

function displayChatLoadingMessage() {
  let chatBox = document.getElementById("chat-box");
  let loadingDiv = document.createElement("div");
  loadingDiv.id = "chatLoadingMessage";
  loadingDiv.classList.add("message");

  let botLabelSpan = document.createElement("span");
  botLabelSpan.classList.add("sender-bot");
  botLabelSpan.textContent = "Bot:";
  botLabelSpan.style.marginRight = "12px"; // Set right margin for spacing

  let loadingAnimationSpan = document.createElement("span");
  loadingAnimationSpan.classList.add("loading-animation");

  loadingDiv.appendChild(botLabelSpan);
  loadingDiv.appendChild(loadingAnimationSpan);

  chatBox.appendChild(loadingDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function hideChatLoadingMessage() {
  let loadingDiv = document.getElementById("chatLoadingMessage");
  if (loadingDiv) {
    loadingDiv.remove();
  }
}

export function handleKeyPress(event) {
  if (event.keyCode === 13) {
    // 13 is the Enter key
    event.preventDefault(); // Prevent default to avoid form submit
    sendMessage();
  }
}

export function sendMessage() {
  let messageInput = document.getElementById("message-input");
  let message = messageInput.value;

  // Update chat with user's message
  updateChat("user", message);

  // Show loading message in chat
  displayChatLoadingMessage();

  fetch("/send_message", {
    method: "POST",
    body: JSON.stringify({ message: message }),
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      // Hide loading message and update chat with bot's response
      hideChatLoadingMessage();
      updateChat("bot", data.response);
    })
    .catch((error) => {
      console.error("Error:", error);
      hideChatLoadingMessage();
    });

  // Clear the input box right after sending the message
  messageInput.value = "";
}

export function updateChat(sender, text) {
  let chatBox = document.getElementById("chat-box");
  let messageDiv = document.createElement("div");
  messageDiv.classList.add("message");

  let senderSpan = document.createElement("span");
  senderSpan.classList.add(sender === "user" ? "sender-user" : "sender-bot");
  senderSpan.textContent = sender === "user" ? "You: " : "Bot: ";

  let textDiv = document.createElement("div");
  textDiv.classList.add("text-content");
  let htmlContent = markdownToHTML(text);
  textDiv.innerHTML = htmlContent;

  messageDiv.appendChild(senderSpan);
  messageDiv.appendChild(textDiv);
  chatBox.appendChild(messageDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  let movieTitleElement = document.createElement("span");
  movieTitleElement.className = "movie-title";
  movieTitleElement.textContent = "Your Movie Title Here";

  $(messageDiv)
    .find('[data-toggle="popover"]')
    .each(function () {
      setupPopoverHideWithDelay(this);
    });

  $(messageDiv)
    .find(".person-link")
    .each(function () {
      showPersonPopover(this);
    });
}

export function sendPredefinedMessage(message) {
  updateChat("user", message); // Display the message as if the user has sent it
  displayChatLoadingMessage();

  fetch("/send_message", {
    method: "POST",
    body: JSON.stringify({ message: message }),
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => response.json())
    .then((data) => {
      hideChatLoadingMessage();
      updateChat("bot", data.response); // Display the bot's response in chat
    })
    .catch((error) => {
      hideChatLoadingMessage();
      console.error("Error:", error);
    });
}
