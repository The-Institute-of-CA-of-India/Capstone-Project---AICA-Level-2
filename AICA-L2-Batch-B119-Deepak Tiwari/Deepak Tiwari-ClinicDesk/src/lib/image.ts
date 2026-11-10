/** Shrinks a logo/photo in the browser before upload (also strips EXIF metadata). */
export const ALLOWED_IMAGE = ['image/png', 'image/jpeg', 'image/webp'];
export async function resizeImage(file: File, max = 512): Promise<Blob> {
  if (!ALLOWED_IMAGE.includes(file.type)) throw new Error('Please choose a PNG, JPG or WebP image.');
  if (file.size > 8 * 1024 * 1024) throw new Error('That image is larger than 8 MB.');
  const bmp = await createImageBitmap(file);
  const scale = Math.min(1, max / Math.max(bmp.width, bmp.height));
  const w = Math.max(1, Math.round(bmp.width * scale)), h = Math.max(1, Math.round(bmp.height * scale));
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Your browser cannot process images.');
  ctx.drawImage(bmp, 0, 0, w, h);
  bmp.close?.();
  return await new Promise<Blob>((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error('Could not process the image.'))), 'image/png'));
}
