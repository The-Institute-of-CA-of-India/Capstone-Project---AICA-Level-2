/** Random identifiers. crypto.getRandomValues is available in every browser the app supports. */
export function randomHex(bytes: number): string {
  const a = new Uint8Array(bytes);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => b.toString(16).padStart(2, '0')).join('');
}
/** 40 hex characters - the unguessable key in a public invoice link. */
export const newShareKey = () => randomHex(20);
export const newShortId = () => randomHex(4);
export const pad = (n: number, w: number) => String(n).padStart(w, '0');
