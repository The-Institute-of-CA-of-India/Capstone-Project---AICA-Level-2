import { useEffect, useState } from 'react';

/** Registers the service worker (production only, never inside an iframe/preview). */
export function registerServiceWorker() {
  if (!('serviceWorker' in navigator) || import.meta.env.DEV) return;
  if (window.self !== window.top) return; // embedded preview: skip
  window.addEventListener('load', () => {
    navigator.serviceWorker.register(import.meta.env.BASE_URL + 'sw.js').catch(() => { /* PWA install is optional */ });
  });
}

interface BIPEvent extends Event { prompt(): Promise<void>; userChoice: Promise<{ outcome: string }> }

export function useInstall() {
  const [evt, setEvt] = useState<BIPEvent | null>(null);
  const [installed, setInstalled] = useState(
    window.matchMedia?.('(display-mode: standalone)').matches || (navigator as unknown as { standalone?: boolean }).standalone === true
  );
  useEffect(() => {
    const onBip = (e: Event) => { e.preventDefault(); setEvt(e as BIPEvent); };
    const onInst = () => { setInstalled(true); setEvt(null); };
    window.addEventListener('beforeinstallprompt', onBip);
    window.addEventListener('appinstalled', onInst);
    return () => { window.removeEventListener('beforeinstallprompt', onBip); window.removeEventListener('appinstalled', onInst); };
  }, []);
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  return {
    installed,
    canPrompt: !!evt,
    showIosHint: ios && !installed,
    install: async () => { if (evt) { await evt.prompt(); await evt.userChoice; setEvt(null); } }
  };
}
