import { API_BASE } from "./config.mjs";

const button = document.createElement("button");
button.type = "button";
button.className = "secondary";
button.textContent = "Panel de control";
button.setAttribute("aria-haspopup", "dialog");
Object.assign(button.style, {
  position: "fixed", right: "1rem", bottom: "1rem", zIndex: "999",
});

const dialog = document.createElement("dialog");
const form = document.createElement("form");
const title = document.createElement("h2");
title.textContent = "Panel de control";
const label = document.createElement("label");
label.htmlFor = "visitor-panel-pin";
label.textContent = "PIN de cuatro cifras";
const input = document.createElement("input");
input.id = "visitor-panel-pin";
input.type = "password";
input.inputMode = "numeric";
input.pattern = "[0-9]{4}";
input.maxLength = 4;
input.autocomplete = "off";
input.required = true;
const status = document.createElement("p");
status.setAttribute("role", "status");
status.setAttribute("aria-live", "polite");
const submit = document.createElement("button");
submit.type = "submit";
submit.className = "primary";
submit.textContent = "Ver visitas de hoy";
const cancel = document.createElement("button");
cancel.type = "button";
cancel.className = "secondary";
cancel.textContent = "Cerrar";
cancel.addEventListener("click", () => dialog.close());
form.append(title, label, input, status, submit, cancel);
dialog.append(form);
document.body.append(button, dialog);

button.addEventListener("click", () => {
  status.textContent = "";
  input.value = "";
  dialog.showModal();
  input.focus();
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  status.textContent = "Consultando…";
  submit.disabled = true;
  try {
    const response = await fetch(`${API_BASE}/api/admin/visitors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: input.value }),
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Error del servidor (${response.status}).`);
    status.textContent = `Visitantes únicos de hoy (${data.date}): ${new Intl.NumberFormat("es-ES").format(data.uniqueVisitors)}`;
    input.value = "";
  } catch (error) {
    status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
