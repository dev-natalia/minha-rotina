// JS mínimo do minha-rotina. Comportamentos de cada tela entram aqui, sem framework.
"use strict";

// HTMX: respostas 400 trazem o cartão com a mensagem de erro e também devem ser trocadas.
if (window.htmx) {
  htmx.config.responseHandling = [
    { code: "204", swap: false },
    { code: "[23]..", swap: true },
    { code: "400", swap: true, error: false },
    { code: "[45]..", swap: false, error: true },
  ];
}

// Contadores: tocar no número abre o diálogo para lançar outra quantidade.
document.addEventListener("click", (evento) => {
  const abrir = evento.target.closest("[data-abrir-dialogo]");
  if (abrir) {
    const dialogo = document.getElementById(abrir.dataset.abrirDialogo);
    dialogo.showModal();
    dialogo.querySelector("input[name=quantidade]").focus();
    return;
  }
  const fechar = evento.target.closest("[data-fechar-dialogo]");
  if (fechar) fechar.closest("dialog").close();
});

// Depois de trocar um cartão, o foco volta para o mesmo botão (quem usa teclado não se perde).
let focoNoCartao = null; // { cartao: id, classe: "botao-mais" | "botao-menos" | "contador-valor" }
document.addEventListener("htmx:beforeRequest", () => {
  const ativo = document.activeElement;
  const cartao = ativo && ativo.closest(".contador");
  const classe = ativo && ["botao-mais", "botao-menos", "contador-valor"].find((c) => ativo.classList.contains(c));
  // Envio pelo diálogo de quantidade: o foco volta para o número.
  focoNoCartao = cartao ? { cartao: cartao.id, classe: classe || "contador-valor" } : null;
});
document.addEventListener("htmx:afterSettle", () => {
  if (!focoNoCartao) return;
  const { cartao: id, classe } = focoNoCartao;
  focoNoCartao = null;
  const cartao = document.getElementById(id);
  if (!cartao) return;
  const alvo = cartao.querySelector("." + classe);
  // Se o "−" ficou desabilitado (nada mais a desfazer), o foco vai para o "+".
  (alvo && !alvo.disabled ? alvo : cartao.querySelector(".botao-mais"))?.focus();
});

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
