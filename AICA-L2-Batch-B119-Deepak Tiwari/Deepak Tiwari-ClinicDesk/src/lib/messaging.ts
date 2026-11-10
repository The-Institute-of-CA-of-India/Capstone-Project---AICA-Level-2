/** Links that open the device's own apps. Nothing is sent from the server; a person presses Send. */
export const waLink = (digits: string, text: string) => `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
export const mailtoLink = (to: string, subject: string, body: string) =>
  `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
export const smsLink = (e164: string, body: string) => `sms:${e164}?&body=${encodeURIComponent(body)}`;
export function openExternal(url: string) {
  if (url.startsWith('mailto:') || url.startsWith('sms:')) { window.location.href = url; return; }
  window.open(url, '_blank', 'noopener');
}
