// Service worker do minha-rotina.
// Só guarda arquivos estáticos e a página "sem conexão": dados nunca vêm do cache.
const CACHE = "rotina-v1";
const ESTATICOS = [
  "/offline",
  "/static/css/app.css",
  "/static/js/app.js",
  "/static/vendor/htmx.min.js",
  "/static/icons/icon-192.png",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ESTATICOS)));
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches.keys().then((nomes) =>
      Promise.all(nomes.filter((nome) => nome !== CACHE).map((nome) => caches.delete(nome)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (evento) => {
  const pedido = evento.request;
  if (pedido.method !== "GET") return;
  const url = new URL(pedido.url);
  if (url.origin !== self.location.origin) return;

  if (pedido.mode === "navigate") {
    // Rede primeiro; só sem rede mostra a página offline.
    evento.respondWith(fetch(pedido).catch(() => caches.match("/offline")));
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    // Rede primeiro, para que atualizações de CSS/JS cheguem logo; cache só sem rede.
    evento.respondWith(fetch(pedido).catch(() => caches.match(pedido)));
  }
});
