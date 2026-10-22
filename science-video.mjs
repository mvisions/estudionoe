const button = document.querySelector("#load-aristotle-video");
const container = document.querySelector("#aristotle-video");

button.hidden = false;
button.addEventListener("click", () => {
  const player = document.createElement("iframe");
  player.src = "https://www.youtube-nocookie.com/embed/Wr3p0U2_nqU";
  player.title = "ARISTÓTELES para niños | BIOGRAFÍA corta · Quonomy";
  player.allow = "encrypted-media; picture-in-picture; fullscreen";
  player.allowFullscreen = true;
  player.referrerPolicy = "strict-origin-when-cross-origin";
  container.append(player);
  container.hidden = false;
  button.hidden = true;
  player.focus();
});
