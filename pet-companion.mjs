const storageKey = "noe-pet-companion-v1";
const pets = Object.freeze({
  loro: { label: "Loro", image: new URL("./pets/parrot.svg?v=2d2", import.meta.url).href },
  gato: {
    label: "Gato",
    image: new URL("./pets/cat-preview.jpg?v=2", import.meta.url).href,
  },
  perro: {
    label: "Perro",
    image: new URL("./pets/dog-preview.jpg?v=1", import.meta.url).href,
  },
});
let companion;
let dock;
let dialog;
let status;
let image;
let nameLabel;
let celebrationTimer;
let fireworksTimer;

function validName(name) {
  return typeof name === "string" && name.trim().length > 0 && name.trim().length <= 30
    && !/[\u0000-\u001f\u007f<>]/.test(name);
}

function validProfile(profile) {
  return Boolean(profile && typeof profile === "object" && validName(profile.petName)
    && Object.hasOwn(pets, profile.animalType));
}

export function getPetProfile() {
  try {
    const stored = localStorage.getItem(storageKey);
    if (!stored) return null;
    const profile = JSON.parse(stored);
    return validProfile(profile) ? { petName: profile.petName.trim(), animalType: profile.animalType } : null;
  } catch (error) {
    console.error("No se pudo leer la mascota guardada.", error);
    return null;
  }
}

export function setPetProfile(profile) {
  if (!validProfile(profile)) throw new Error("Elige un nombre y una mascota válidos.");
  const saved = { petName: profile.petName.trim(), animalType: profile.animalType };
  localStorage.setItem(storageKey, JSON.stringify(saved));
  companion = saved;
  renderCompanion();
  return { ...saved };
}

export function petCelebrationForGrade(grade) {
  if (typeof grade !== "number" || !Number.isFinite(grade)) return { dance: false, fireworks: false };
  return { dance: grade > 5, fireworks: grade > 7 };
}

function petDescription(profile) {
  return `${pets[profile.animalType].label.toLocaleLowerCase("es")}`;
}

function renderCompanion() {
  if (!dock) return;
  const profile = companion ?? getPetProfile();
  companion = profile;
  dock.classList.toggle("pet-companion-empty", !profile);
  nameLabel.textContent = profile?.petName ?? "Tu compañero de estudio";
  image.src = profile ? pets[profile.animalType].image : pets.loro.image;
  image.alt = profile ? `${profile.petName}, tu ${petDescription(profile)}` : "Mascotas para elegir";
  dock.querySelector("[data-pet-change]").textContent = profile ? "Cambiar" : "Elegir mascota";
  dock.querySelector("[data-pet-change]").setAttribute("aria-label",
    profile ? `Cambiar mascota, ahora ${profile.petName}` : "Elegir una mascota");
}

function createDialog() {
  dialog = document.createElement("dialog");
  dialog.className = "pet-picker";
  dialog.innerHTML = `<form method="dialog" data-pet-form>
    <span class="eyebrow">Tu compañero de estudio</span>
    <h2>Elige tu mascota</h2>
    <p>Estará contigo por la web y celebrará tus buenos resultados.</p>
    <div class="pet-picker-options" role="radiogroup" aria-label="Elige entre loro, gato y perro">
      ${Object.entries(pets).map(([type, pet]) => `<label class="pet-choice">
        <input type="radio" name="animalType" value="${type}" required>
        <img src="${pet.image}" alt="" aria-hidden="true"><span>${pet.label}${type === "loro" ? " · 2D" : " · 3D"}</span>
      </label>`).join("")}
    </div>
    <p class="pet-picker-credits">
      Modelos 3D: <a href="https://sketchfab.com/3d-models/sitting-cat-48ff148440734e4b99465d899cf80506" target="_blank" rel="noopener noreferrer">Sitting Cat</a>
      de Weiting Ke y <a href="https://sketchfab.com/3d-models/shiba-faef9fe5ace445e7b2989d1c1ece361c" target="_blank" rel="noopener noreferrer">Shiba</a>
      de zixisun02, con licencia <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>.
      Loro 2D: <a href="https://openmoji.org/library/emoji-1F99C/" target="_blank" rel="noopener noreferrer">OpenMoji</a>,
      <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a>.
    </p>
    <label class="input-label" for="pet-companion-name">¿Cómo se llamará?</label>
    <input id="pet-companion-name" name="petName" maxlength="30" required autocomplete="off" placeholder="Por ejemplo: Luna">
    <p class="pet-picker-error" role="alert"></p>
    <div class="result-actions"><button class="secondary" type="button" data-pet-cancel>Cerrar</button>
      <button class="primary" type="submit">Guardar mi mascota</button></div>
  </form>`;
  document.body.append(dialog);
  const form = dialog.querySelector("[data-pet-form]");
  const name = dialog.querySelector("#pet-companion-name");
  const error = dialog.querySelector(".pet-picker-error");
  const cancel = dialog.querySelector("[data-pet-cancel]");
  cancel.addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", event => {
    if (event.target === dialog && companion) dialog.close();
  });
  dialog.addEventListener("close", () => {
    if (!companion) status.textContent = "Elige una mascota para tenerla contigo mientras estudias.";
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    const data = new FormData(form);
    const profile = {
      petName: String(data.get("petName") ?? "").trim(),
      animalType: String(data.get("animalType") ?? ""),
    };
    if (!validProfile(profile)) {
      error.textContent = "Escribe un nombre de hasta 30 caracteres y elige loro, gato o perro.";
      return;
    }
    try {
      setPetProfile(profile);
      dialog.close();
      status.textContent = `${profile.petName} ya te acompañará por la web.`;
    } catch (saveError) {
      console.error("No se pudo guardar tu mascota.", saveError);
      error.textContent = `No se ha podido guardar tu mascota: ${saveError.message}`;
    }
  });
  return { dialog, name, error };
}

export function openPetPicker() {
  if (!dialog) return;
  const { name, error } = dialog.__petControls;
  const current = companion ?? getPetProfile();
  dialog.querySelectorAll('input[name="animalType"]').forEach(input => {
    input.checked = input.value === current?.animalType;
  });
  name.value = current?.petName ?? "";
  error.textContent = "";
  dialog.showModal();
  name.focus();
}

export function celebratePet(grade) {
  const celebration = petCelebrationForGrade(grade);
  if (!Number.isFinite(grade)) return false;
  let celebrated = false;
  if (celebration.dance && companion && dock) {
    window.clearTimeout(celebrationTimer);
    dock.classList.remove("pet-dancing");
    void dock.offsetWidth;
    dock.classList.add("pet-dancing");
    status.textContent = `¡${companion.petName} baila contigo por sacar más de un 5!`;
    celebrationTimer = window.setTimeout(() => dock.classList.remove("pet-dancing"), 3600);
    celebrated = true;
  }
  if (celebration.fireworks) {
    launchFireworks();
    if (status) status.textContent = companion
      ? `¡Cohetes y baile para celebrar tu nota de ${new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 }).format(grade)}!`
      : "¡Cohetes para celebrar que has sacado más de un 7!";
    celebrated = true;
  }
  return celebrated;
}

function launchFireworks() {
  const layer = document.querySelector("[data-pet-fireworks]");
  if (!layer) return;
  window.clearTimeout(fireworksTimer);
  layer.replaceChildren();
  layer.classList.add("pet-fireworks-active");
  for (const [index, left] of [22, 50, 78].entries()) {
    const rocket = document.createElement("span");
    rocket.className = "pet-firework";
    rocket.style.setProperty("--left", `${left}%`);
    rocket.style.setProperty("--launch-delay", `${index * 180}ms`);
    const burst = document.createElement("span");
    burst.className = "pet-firework-burst";
    for (let spark = 0; spark < 12; spark++) {
      const particle = document.createElement("i");
      particle.style.setProperty("--spark-angle", `${spark * 30}deg`);
      particle.style.setProperty("--spark-color", ["#ffcf55", "#ff6d73", "#62d8f3", "#8ade9c"][spark % 4]);
      burst.append(particle);
    }
    rocket.append(burst);
    layer.append(rocket);
  }
  fireworksTimer = window.setTimeout(() => {
    layer.classList.remove("pet-fireworks-active");
    layer.replaceChildren();
  }, 3000);
}

function initializeCompanion() {
  if (!document.body || document.querySelector("[data-pet-companion]")) return;
  companion = getPetProfile();
  dock = document.createElement("aside");
  dock.className = "pet-companion";
  dock.dataset.petCompanion = "";
  dock.setAttribute("aria-label", "Tu mascota de estudio");
  dock.innerHTML = `<div class="pet-companion-stage"><img alt=""></div>
    <div class="pet-companion-info"><span class="pet-companion-kicker">TU COMPAÑERO</span>
      <strong data-pet-name></strong><button class="secondary" type="button" data-pet-change></button></div>
    <p class="pet-companion-status" role="status" aria-live="polite"></p>`;
  document.body.append(dock);
  image = dock.querySelector(".pet-companion-stage img");
  nameLabel = dock.querySelector("[data-pet-name]");
  status = dock.querySelector(".pet-companion-status");
  const controls = createDialog();
  controls.dialog.__petControls = controls;
  const fireworks = document.createElement("div");
  fireworks.className = "pet-fireworks";
  fireworks.dataset.petFireworks = "";
  fireworks.setAttribute("aria-hidden", "true");
  document.body.append(fireworks);
  dock.querySelector("[data-pet-change]").addEventListener("click", openPetPicker);
  renderCompanion();
  if (!companion) {
    status.textContent = "Elige una mascota para tenerla contigo mientras estudias.";
    openPetPicker();
  }
}

if (typeof document !== "undefined") initializeCompanion();
