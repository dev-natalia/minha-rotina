// JS mínimo do minha-rotina. Comportamentos de cada tela entram aqui, sem framework.
"use strict";

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  });
}

// Rotina: sem preferência salva, computador abre na Grade e celular na vista Dia.
document.addEventListener("DOMContentLoaded", () => {
  const rotina = document.querySelector(".rotina");
  if (!rotina) return;

  if (rotina.dataset.temCookie === "nao" && window.matchMedia("(min-width: 900px)").matches) {
    const url = new URL(location.href);
    url.searchParams.set("vista", "grade");
    location.replace(url);
    return;
  }

  // Vista Dia: deslizar para o lado troca de dia.
  const area = rotina.querySelector("[data-deslizar]");
  if (!area) return;
  let inicioX = null;
  area.addEventListener("pointerdown", (e) => { inicioX = e.clientX; });
  area.addEventListener("pointerup", (e) => {
    if (inicioX === null) return;
    const delta = e.clientX - inicioX;
    inicioX = null;
    if (Math.abs(delta) < 50) return;
    const links = [...rotina.querySelectorAll(".seletor-dias a")];
    const atual = links.findIndex((a) => a.getAttribute("aria-current") === "date");
    const destino = links[atual + (delta < 0 ? 1 : -1)];
    if (destino) location.href = destino.href;
  });
});
