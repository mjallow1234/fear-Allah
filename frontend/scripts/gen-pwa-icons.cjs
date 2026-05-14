/**
 * Generates minimal PWA PNG icons (no external deps — pure Node + zlib).
 * Run once: node scripts/gen-pwa-icons.js
 *
 * Produces:
 *   public/pwa-192x192.png       — standard icon (dark bg, accent square)
 *   public/pwa-512x512.png       — standard icon
 *   public/maskable-192x192.png  — maskable icon (full-bleed accent bg)
 *   public/maskable-512x512.png  — maskable icon
 *   public/apple-touch-icon.png  — 180x180 for iOS
 *   public/favicon.ico           — 32x32 PNG (browsers accept PNG named .ico)
 */
'use strict';
const zlib = require('zlib');
const fs   = require('fs');
const path = require('path');

// Brand colours
const BG     = [0x31, 0x33, 0x38]; // #313338
const ACCENT = [0x58, 0x65, 0xF2]; // #5865f2

function crc32(buf) {
  let c = 0xFFFFFFFF;
  for (const b of buf) {
    c ^= b;
    for (let i = 0; i < 8; i++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
  }
  return (~c) >>> 0;
}

function makeChunk(type, data) {
  const t   = Buffer.from(type, 'ascii');
  const len = Buffer.allocUnsafe(4);
  len.writeUInt32BE(data.length, 0);
  const crcVal = Buffer.allocUnsafe(4);
  crcVal.writeUInt32BE(crc32(Buffer.concat([t, data])), 0);
  return Buffer.concat([len, t, data, crcVal]);
}

function makeIHDR(w, h) {
  const b = Buffer.allocUnsafe(13);
  b.writeUInt32BE(w, 0);
  b.writeUInt32BE(h, 4);
  b[8]  = 8; // bit depth
  b[9]  = 2; // colour type: RGB
  b[10] = 0; b[11] = 0; b[12] = 0;
  return b;
}

/**
 * Draw icon pixels.
 * style = 'standard'  → dark bg + centred accent rounded-rect (20 % padding)
 * style = 'maskable'  → accent bg + centred white rounded-rect (safe area = 20%)
 */
function makePixels(size, style) {
  const pad    = Math.round(size * 0.2);
  const inner  = size - pad * 2;
  const radius = Math.round(inner * 0.18); // slight corner rounding

  const [fgR, fgG, fgB] = style === 'maskable' ? [0xFF, 0xFF, 0xFF] : ACCENT;
  const [bgR, bgG, bgB] = style === 'maskable' ? ACCENT              : BG;

  const raw = Buffer.allocUnsafe(size * (1 + size * 3));

  for (let y = 0; y < size; y++) {
    raw[y * (1 + size * 3)] = 0; // filter byte = None
    for (let x = 0; x < size; x++) {
      const lx = x - pad;
      const ly = y - pad;

      let inRect = lx >= 0 && lx < inner && ly >= 0 && ly < inner;
      // Corner-radius clipping
      if (inRect) {
        const cx = lx < radius ? radius - lx : (lx >= inner - radius ? lx - (inner - radius - 1) : 0);
        const cy = ly < radius ? radius - ly : (ly >= inner - radius ? ly - (inner - radius - 1) : 0);
        if (cx > 0 && cy > 0 && cx * cx + cy * cy > radius * radius) inRect = false;
      }

      const [r, g, b] = inRect ? [fgR, fgG, fgB] : [bgR, bgG, bgB];
      const off = y * (1 + size * 3) + 1 + x * 3;
      raw[off] = r; raw[off + 1] = g; raw[off + 2] = b;
    }
  }
  return raw;
}

function makePNG(size, style) {
  const sig  = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const raw  = makePixels(size, style);
  const comp = zlib.deflateSync(raw, { level: 9 });
  return Buffer.concat([
    sig,
    makeChunk('IHDR', makeIHDR(size, size)),
    makeChunk('IDAT', comp),
    makeChunk('IEND', Buffer.alloc(0)),
  ]);
}

const outDir = path.join(__dirname, '..', 'public');
fs.mkdirSync(outDir, { recursive: true });

const icons = [
  ['pwa-192x192.png',      192, 'standard'],
  ['pwa-512x512.png',      512, 'standard'],
  ['maskable-192x192.png', 192, 'maskable'],
  ['maskable-512x512.png', 512, 'maskable'],
  ['apple-touch-icon.png', 180, 'maskable'],
  ['favicon-32x32.png',     32, 'standard'],
];

for (const [name, size, style] of icons) {
  const p = path.join(outDir, name);
  fs.writeFileSync(p, makePNG(size, style));
  console.log(`  ✓  ${name}  (${size}x${size}, ${style})`);
}

console.log('\nPWA icons generated in frontend/public/');
