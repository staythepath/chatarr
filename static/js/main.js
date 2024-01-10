import { sendMessage, updateChat, handleKeyPress } from "./chat.js";

import {
  toggleConfigPanel,
  fetchRadarrRootFolders,
  handleRefresh,
  refreshDiscordChannels,
  loadChannels,
} from "./config.js";

$.fn.popover.Constructor.Default.whiteList.button = [];
$.fn.popover.Constructor.Default.whiteList.button.push("type");
$.fn.popover.Constructor.Default.whiteList.button.push("class");
$.fn.popover.Constructor.Default.whiteList.dl = [];
$.fn.popover.Constructor.Default.whiteList.dt = [];
$.fn.popover.Constructor.Default.whiteList.dd = [];

console.log("main.js loaded");

document.addEventListener("DOMContentLoaded", (event) => {
  const configPanel = document.getElementById("config-panel");
  const configToggle = document.getElementById("config-toggle");
  const radarrApiKeyInput = document.getElementById("radarr_api_key");
  const radarrUrlInput = document.getElementById("radarr_url");
  const refreshButton = document.getElementById("refresh-button");

  configToggle.addEventListener("click", toggleConfigPanel);

  document.addEventListener("click", function (event) {
    var isClickInsideConfigPanel = configPanel.contains(event.target);
    var isClickInsideConfigToggle = configToggle.contains(event.target);

    if (
      !isClickInsideConfigPanel &&
      !isClickInsideConfigToggle &&
      configPanel.style.left === "0px"
    ) {
      toggleConfigPanel(); // Close the panel
    }

    const sendMessageButton = document.getElementById("send-message-btn");
    if (sendMessageButton) {
      sendMessageButton.addEventListener("click", sendMessage);
    }

    // Add event listener for messageInput
    const messageInput = document.getElementById("message-input");
    if (messageInput) {
      messageInput.addEventListener("keypress", handleKeyPress);
    }

    // Event delegation for dynamically generated movie links
    if (event.target.classList.contains("movie-link")) {
      const tmdbId = event.target.getAttribute("data-tmdb-id");
      if (tmdbId) {
        addMovieToRadarr(tmdbId); // Call your function with tmdbId
      }
    }
  });

  if (radarrApiKeyInput) {
    radarrApiKeyInput.addEventListener("blur", fetchRadarrRootFolders);
  }

  if (radarrUrlInput) {
    radarrUrlInput.addEventListener("blur", fetchRadarrRootFolders);
  }

  if (refreshButton) {
    refreshButton.addEventListener("click", handleRefresh);
  }

  // Event listener for Discord Token input
  const discordTokenInput = document.getElementById("discord_token");
  if (discordTokenInput) {
    discordTokenInput.addEventListener("change", loadChannels);
  }

  // Event listener for Refresh Channels button
  const refreshChannelsButton = document.getElementById(
    "refresh-channels-button"
  );
  if (refreshChannelsButton) {
    refreshChannelsButton.addEventListener("click", refreshDiscordChannels);
  }
});

// Function to add a movie to Radarr and update the chat
export function addMovieToRadarr(tmdbId) {
  fetch(`/add_movie_to_radarr/${tmdbId}`)
    .then((response) => response.json())
    .then((data) => {
      updateChat("bot", data.message);
    })
    .catch((error) => console.error("Error:", error));
}
