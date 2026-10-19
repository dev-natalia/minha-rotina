// JS mínimo do minha-rotina. Comportamentos de cada tela entram aqui, sem framework.
"use strict";

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  });
}
