import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';

type Kind = 'ok' | 'err' | 'info';
interface T { id: number; msg: string; kind: Kind }
const Ctx = createContext<(msg: string, kind?: Kind) => void>(() => {});
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<T[]>([]);
  const n = useRef(0);
  const push = useCallback((msg: string, kind: Kind = 'ok') => {
    const id = ++n.current;
    setItems((x) => [...x.slice(-3), { id, msg, kind }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), kind === 'err' ? 7000 : 3500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={'toast ' + t.kind}>{t.msg}</div>)}
      </div>
    </Ctx.Provider>
  );
}
