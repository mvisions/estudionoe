import { initializeTheme } from "../theme.mjs";

function announce(message) {
  const notice = document.querySelector("#notice");
  if (notice) notice.textContent = message;
}

initializeTheme(announce);
