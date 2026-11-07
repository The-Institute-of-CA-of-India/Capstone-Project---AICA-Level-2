/* Service workers need https:// or localhost. On plain http over a LAN the browser exposes no
   navigator.serviceWorker, so the app simply runs without offline mode (see the docs for --https). */
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js').catch(err => console.warn('Service worker not registered:', err));
  });
}
