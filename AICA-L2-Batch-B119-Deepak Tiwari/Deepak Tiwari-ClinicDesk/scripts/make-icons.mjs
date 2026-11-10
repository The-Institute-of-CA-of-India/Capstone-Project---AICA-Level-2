// Regenerates the PWA icons from a logo.   Usage:  npm run icons -- path/to/logo.png
// Use a PNG with a TRANSPARENT background (a "checkerboard" in a picture is not transparency).
// The installed-app icon is static, so re-run this and redeploy if you change the logo for the installed app.
import sharp from 'sharp';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = process.argv[2] ? path.resolve(process.argv[2]) : path.join(root, 'scripts/source-logo.png');
const out = path.join(root, 'public/icons');
mkdirSync(out, { recursive: true });

const BG = { r: 240, g: 247, b: 250, alpha: 1 };
async function tile(size, frac, name, bg = BG) {
  const inner = Math.round(size * frac);
  const logo = await sharp(src).trim().resize(inner, inner, { fit: 'inside' }).toBuffer();
  await sharp({ create: { width: size, height: size, channels: 4, background: bg } }).composite([{ input: logo, gravity: 'center' }]).png().toFile(path.join(out, name));
  console.log('wrote', name);
}
await tile(192, 0.74, 'icon-192.png');
await tile(512, 0.74, 'icon-512.png');
await tile(512, 0.52, 'maskable-512.png');                       // stays inside the maskable safe zone
await tile(180, 0.76, 'apple-touch-icon.png', { r: 255, g: 255, b: 255, alpha: 1 });
await sharp(src).trim().resize(256, 256, { fit: 'inside' }).png().toFile(path.join(out, 'logo.png'));
await sharp(src).trim().resize(32, 32, { fit: 'inside' }).png().toFile(path.join(out, 'favicon-32.png'));
console.log('done');
