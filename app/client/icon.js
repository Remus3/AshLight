"use strict";
/* DESKTOP-CLIENT (decision 0041): AshLight's own generic icon, drawn in code
   so no binary art is tracked and no game art, logo or trademark is used:
   a warm ember dot on a dark rounded square. PNG for the tray and window,
   ICO (PNG entries) for the Start Menu shortcut (scripts\setup.ps1 runs
   `node app/client/icon.js <out.ico>`). Node built-ins only. */

const zlib = require("zlib");

const SIZES = [16, 24, 32, 48, 64, 256];
const BG = [32, 36, 44];
const EMBER_IN = [255, 214, 128];
const EMBER_OUT = [226, 118, 40];

function mix(a, b, t) {
  return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * t));
}

/* One pixel sample at (u, v) in 0..1: [r, g, b, a] with a in 0..1. */
function sample(u, v) {
  const r = 0.2; // corner radius of the plate
  const cx = Math.min(Math.max(u, r), 1 - r);
  const cy = Math.min(Math.max(v, r), 1 - r);
  if (Math.hypot(u - cx, v - cy) > r) { return [0, 0, 0, 0]; }
  const d = Math.hypot(u - 0.5, v - 0.54);
  const core = 0.24;
  if (d <= core) { return mix(EMBER_IN, EMBER_OUT, d / core).concat(1); }
  const glow = Math.max(0, 1 - (d - core) / 0.16) * 0.45; // soft halo
  return mix(BG, EMBER_OUT, glow).concat(1);
}

/* RGBA bytes of a size x size icon, 4x4 supersampled. */
function rgba(size) {
  const out = Buffer.alloc(size * size * 4);
  const n = 4;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let r = 0, g = 0, b = 0, a = 0;
      for (let sy = 0; sy < n; sy++) {
        for (let sx = 0; sx < n; sx++) {
          const p = sample((x + (sx + 0.5) / n) / size, (y + (sy + 0.5) / n) / size);
          r += p[0] * p[3]; g += p[1] * p[3]; b += p[2] * p[3]; a += p[3];
        }
      }
      const o = (y * size + x) * 4;
      out[o] = a ? Math.round(r / a) : 0;
      out[o + 1] = a ? Math.round(g / a) : 0;
      out[o + 2] = a ? Math.round(b / a) : 0;
      out[o + 3] = Math.round((a / (n * n)) * 255);
    }
  }
  return out;
}

let CRC_TABLE = null;
function crc32(buf) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Int32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) { c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1); }
      CRC_TABLE[i] = c;
    }
  }
  let c = -1;
  for (let i = 0; i < buf.length; i++) { c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8); }
  return (c ^ -1) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

/* A PNG file (8-bit RGBA) of the icon at this size. */
function png(size) {
  const px = rgba(size);
  const raw = Buffer.alloc(size * (size * 4 + 1));
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0; // filter: none
    px.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 6; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0))
  ]);
}

/* A Windows .ico holding one PNG entry per size. */
function ico(sizes) {
  const list = sizes || SIZES;
  const images = list.map(png);
  const head = Buffer.alloc(6 + 16 * list.length);
  head.writeUInt16LE(0, 0);
  head.writeUInt16LE(1, 2);
  head.writeUInt16LE(list.length, 4);
  let offset = head.length;
  list.forEach((s, i) => {
    const e = 6 + 16 * i;
    head[e] = s >= 256 ? 0 : s;
    head[e + 1] = s >= 256 ? 0 : s;
    head[e + 2] = 0; head[e + 3] = 0;
    head.writeUInt16LE(1, e + 4);
    head.writeUInt16LE(32, e + 6);
    head.writeUInt32LE(images[i].length, e + 8);
    head.writeUInt32LE(offset, e + 12);
    offset += images[i].length;
  });
  return Buffer.concat([head].concat(images));
}

/* CLI for setup.ps1: write the .ico only when its bytes changed (a re-run
   is a no-op). Prints "written" or "unchanged". */
function main(argv) {
  const fs = require("fs");
  const out = argv[2];
  if (!out) { process.stderr.write("usage: node icon.js <out.ico>\n"); return 2; }
  const data = ico();
  let same = false;
  try { same = fs.readFileSync(out).equals(data); } catch (e) { same = false; }
  if (!same) { fs.writeFileSync(out, data); }
  process.stdout.write(same ? "unchanged\n" : "written\n");
  return 0;
}

if (require.main === module) { process.exitCode = main(process.argv); }

module.exports = { png, ico, rgba, crc32, SIZES };
