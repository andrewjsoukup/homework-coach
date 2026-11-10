// Homework Coach native workspace. Generated from desktop/src/plugin.jsx; run node desktop/build.mjs.

// desktop/src/plugin.jsx
import * as sdk from "@hermes/plugin-sdk";
import { useState, useEffect, useRef } from "react";

// desktop/src/styles.js
var css = `
.hc{color-scheme:dark light;color:var(--ui-text-primary);font-size:14px;line-height:1.5;height:100%;overflow:auto}.hc *{box-sizing:border-box}.hc h1,.hc h2,.hc h3,.hc p{margin:0}.hc h1{font-size:26px;font-weight:650;letter-spacing:-.7px}.hc h2{font-size:19px;font-weight:600}.hc h3{font-size:15px;font-weight:600}.hc button{cursor:pointer}.hc button:disabled{cursor:default;opacity:.5}.hc button:focus-visible,.hc select:focus-visible,.hc input:focus-visible,.hc textarea:focus-visible{outline:2px solid var(--ui-accent);outline-offset:3px}.hc-main{max-width:1190px;margin:auto;padding:28px 32px 60px}.hc-row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.hc-between{justify-content:space-between}.hc-stack{display:flex;flex-direction:column;gap:16px}.hc-small{font-size:12px}.hc-muted{color:var(--ui-text-tertiary)}.hc-eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:1.7px;color:var(--ui-text-tertiary);font-weight:600}.hc-header{margin-bottom:24px}.hc-tabs{display:flex;gap:6px;border-bottom:1px solid var(--ui-stroke-secondary);margin:20px 0 24px;padding-bottom:10px}.hc-tabs button{border-radius:6px;padding:9px 18px;color:var(--ui-text-secondary);background:transparent;border:0}.hc-tabs button[aria-selected=true]{color:var(--ui-accent);background:color-mix(in srgb,var(--ui-accent) 12%,transparent);font-weight:650}.hc-select{padding:7px 10px;border:1px solid var(--ui-stroke-secondary);border-radius:6px;background:var(--ui-surface-secondary,var(--ui-bg-secondary));color:inherit}.hc-select option{color:var(--ui-text-primary);background:var(--ui-bg-primary,var(--ui-surface-primary))}.hc-card{border:1px solid var(--ui-stroke-secondary);border-radius:12px;padding:22px;background:color-mix(in srgb,var(--ui-text-primary) 2%,transparent)}.hc-card.active{border-color:var(--ui-accent)}.hc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.hc-hero{padding:26px;border-left:3px solid var(--ui-accent);margin-bottom:22px;background:color-mix(in srgb,var(--ui-accent) 6%,transparent);border-radius:0 10px 10px 0}.hc-pill{font-size:11px;display:inline-flex;align-items:center;gap:6px;padding:4px 9px;border-radius:20px;border:1px solid var(--ui-stroke-secondary);color:var(--ui-text-secondary);white-space:nowrap}.hc-accent{color:var(--ui-accent)}.hc-source{font-size:11px;padding:4px 9px;border:1px solid var(--ui-stroke-secondary);border-radius:20px;background:transparent;color:var(--ui-text-secondary)}.hc-split{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(290px,1fr);gap:24px;align-items:start}.hc-detail{position:sticky;top:12px;max-height:78vh;overflow:auto}.hc-timeline{border-left:2px solid var(--ui-stroke-secondary);margin-left:8px;padding-left:22px}.hc-unit{position:relative;margin-bottom:12px}.hc-unit:before{content:'';position:absolute;left:-29px;top:21px;width:10px;height:10px;background:var(--ui-text-quaternary,var(--ui-stroke-secondary));border-radius:50%}.hc-unit.current:before{background:var(--ui-accent);box-shadow:0 0 0 4px color-mix(in srgb,var(--ui-accent) 16%,transparent)}.hc-unit button{width:100%;text-align:left;border:1px solid var(--ui-stroke-secondary);border-radius:9px;padding:15px 18px;background:transparent;color:inherit}.hc-unit.current button,.hc-unit button[aria-pressed=true]{border-color:var(--ui-accent);background:color-mix(in srgb,var(--ui-accent) 6%,transparent)}.hc-unit .hc-small{margin-top:5px}.hc-today-marker{color:var(--ui-accent);font-size:11px;font-weight:650;letter-spacing:1px;margin:20px 0 12px}.hc-list{margin:8px 0;padding-left:19px}.hc-list li{margin:5px 0}.hc-rule{border:0;border-top:1px solid var(--ui-stroke-secondary);margin:16px 0}.hc-photo{max-width:100%;height:auto;display:block;border:1px solid var(--ui-stroke-secondary);border-radius:7px}.hc-photo-wrap{max-height:74vh;overflow:auto;background:color-mix(in srgb,var(--ui-text-primary) 3%,transparent);padding:8px;border-radius:10px}.hc-drop{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;border:1px dashed var(--ui-stroke-secondary);border-radius:10px;padding:26px;text-align:center}.hc-drop.dragging{border-color:var(--ui-accent);background:color-mix(in srgb,var(--ui-accent) 9%,transparent)}.hc-callout{padding:12px 15px;border-radius:8px;background:color-mix(in srgb,var(--ui-accent) 8%,transparent);border-left:2px solid var(--ui-accent);font-size:13px}.hc-error{border:1px solid var(--ui-stroke-secondary);padding:14px;border-radius:8px;color:var(--ui-text-primary)}.hc-field{display:flex;flex-direction:column;gap:6px;font-size:12px;min-width:0}.hc-field input,.hc-field textarea{width:100%}.hc-field input[type=time]{max-width:180px}.hc-form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.hc-form-grid .wide{grid-column:1/-1}.hc-rate-row{display:flex;gap:12px;align-items:center;padding:12px 8px;border-bottom:1px solid var(--ui-stroke-secondary);border-left:3px solid transparent}.hc-rate-row.selected{border-left-color:var(--ui-accent);background:color-mix(in srgb,var(--ui-accent) 6%,transparent)}.hc-rating{border:1px solid var(--ui-stroke-secondary);border-radius:6px;min-width:44px;min-height:44px;height:44px;background:transparent;color:inherit;font-weight:650}.hc-rating[aria-pressed=true]{border-color:var(--ui-accent);color:var(--ui-bg-primary,#111);background:var(--ui-accent)}.hc-wrap{overflow-wrap:anywhere}.hc-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}@media(max-width:850px){.hc-stats{grid-template-columns:repeat(2,1fr)}}.hc-problem-label{flex:1;text-align:left;background:none;border:0;color:inherit;min-width:0}.hc-tip{margin:8px 0 12px 8px}.hc-table-wrap{overflow:auto}.hc-table{width:100%;border-collapse:collapse;font-size:12px}.hc-table td,.hc-table th{padding:12px;border-bottom:1px solid var(--ui-stroke-secondary);text-align:left;vertical-align:top}.hc-table th{font-weight:500;color:var(--ui-text-tertiary);white-space:nowrap}.hc-mark{min-width:26px;height:28px;border-radius:5px;margin:2px;padding:2px 5px;border:1px solid var(--ui-stroke-secondary);background:transparent;color:var(--ui-text-primary);font-size:11px}.hc-mark[data-rating=I]{background:color-mix(in srgb,var(--ui-accent) 16%,transparent);color:var(--ui-accent)}.hc-mark[data-rating=S]{border-style:dashed}.hc-mark[data-rating=N]{border-width:2px}.hc-stat{font-size:28px;font-weight:600;letter-spacing:-.7px}.hc-event{display:grid;grid-template-columns:85px 1fr auto;gap:16px;padding:20px 0;border-bottom:1px solid var(--ui-stroke-secondary)}.hc-coach-card{max-width:640px;margin:12px 0}.hc-keyboard{font-family:monospace;font-size:11px;padding:2px 5px;border:1px solid var(--ui-stroke-secondary);border-radius:4px}.hc-preview-bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}.hc-days{display:flex;gap:6px;flex-wrap:wrap}.hc-days .hc-rating{min-width:48px;padding:0 10px}.hc-empty{text-align:center;padding:42px 22px;border:1px dashed var(--ui-stroke-secondary);border-radius:10px}.hc-inline-link{color:var(--ui-accent);background:none;border:0;text-align:left;padding:0;text-decoration:underline;text-underline-offset:3px}.hc-read-row{border-bottom:1px solid var(--ui-stroke-secondary);padding:16px 0}.hc-read-row.uncertain{border-left:2px solid var(--ui-accent);padding-left:12px}.hc-metric{padding:18px;min-width:140px}.hc-progress-log{display:grid;grid-template-columns:90px 1fr;gap:14px;padding:12px 0;border-bottom:1px solid var(--ui-stroke-secondary)}
@media(max-width:850px){.hc-main{padding:20px 16px}.hc-split{grid-template-columns:1fr}.hc-detail{position:static;max-height:none}.hc-tabs{overflow:auto}.hc-tabs button{white-space:nowrap;padding:8px 12px}.hc-form-grid{grid-template-columns:1fr}.hc-event{grid-template-columns:70px 1fr}.hc-event>:last-child{grid-column:2}.hc h1{font-size:23px}}
`;

// desktop/src/portability.js
var MAX_DOC_BYTES = 15 * 1024 * 1024;
var IMAGE_TARGET_BYTES = 2 * 1024 * 1024;
var IMAGE_MAX_EDGE = 2048;
var IMAGE_MIN_EDGE = 900;
var IMAGE_MIMES = { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp" };
var EXT_FOR = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" };
var ScopeChanged = class extends Error {
  constructor(msg) {
    super(msg || "Profile changed. Try again in the new profile.");
    this.name = "ScopeChanged";
  }
};
function guardScope(scopeNow2, scope, msg) {
  if (scopeNow2() !== scope) throw new ScopeChanged(msg);
}
function clientTimezone(intl = globalThis.Intl) {
  try {
    const z = intl?.DateTimeFormat?.().resolvedOptions?.().timeZone;
    return validTimezone(z, intl) ? z : "UTC";
  } catch {
    return "UTC";
  }
}
function validTimezone(z, intl = globalThis.Intl) {
  if (typeof z !== "string" || !z.trim() || /\s/.test(z)) return false;
  try {
    new intl.DateTimeFormat("en-US", { timeZone: z });
    return true;
  } catch {
    return false;
  }
}
function pickTimezone({ existing, familyZone, hasChildren, client }) {
  if (existing) return existing;
  if (hasChildren && familyZone) return familyZone;
  return client || clientTimezone();
}
async function copyText(ctx, text, sdk2 = {}) {
  const doors = [ctx?.os?.writeClipboard && ((t) => ctx.os.writeClipboard(t)), sdk2.writeClipboardText && (async (t) => {
    await sdk2.writeClipboardText(t);
    return true;
  })].filter(Boolean);
  for (const door of doors) {
    try {
      if (await door(text)) return true;
    } catch {
    }
  }
  return false;
}
function cancelled(x) {
  return x?.canceled === true || x?.cancelled === true || /cancel|abort/i.test(String(x?.name || "")) || /cancel|abort/i.test(String(x?.message || ""));
}
function bytesFromB64(b64, atobFn = globalThis.atob) {
  const bin = atobFn(b64);
  const a = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
  return a;
}
function browserDownload(file, env = {}) {
  const doc = env.document || globalThis.document, URLo = env.URL || globalThis.URL, Blobo = env.Blob || globalThis.Blob;
  if (!doc?.createElement || !URLo?.createObjectURL || !Blobo) throw new Error("This browser cannot download files here.");
  const blob = new Blobo([bytesFromB64(file.data_b64 || "", env.atob)], { type: file.content_type || "application/octet-stream" });
  const url = URLo.createObjectURL(blob), a = doc.createElement("a");
  a.href = url;
  a.download = file.name || "download";
  a.rel = "noopener";
  a.style.display = "none";
  doc.body.appendChild(a);
  a.click();
  a.remove?.();
  setTimeout(() => URLo.revokeObjectURL(url), 3e4);
}
function makeSaver({ native, ctx, scopeNow: scopeNow2, scope, notify, env = {} }) {
  const stale = "Profile changed. Reopen this file in the new profile.";
  async function direct(path, name) {
    guardScope(scopeNow2, scope, stale);
    const r = await ctx.rest("/download", { method: "POST", body: { path }, timeoutMs: 6e4 });
    if (r?.ok === false) throw new Error(r.error || "The file could not be downloaded.");
    guardScope(scopeNow2, scope, stale);
    if (!r?.data_b64) throw new Error("The file could not be downloaded.");
    browserDownload({ ...r, name: r.name || name }, env);
    notify?.({ kind: "info", message: `Download started: ${r.name || name}. Check your browser's downloads.` });
    return { status: "fallback" };
  }
  async function save(path, name) {
    if (typeof native === "function") {
      try {
        await native(path, name);
        return { status: "native" };
      } catch (err) {
        if (cancelled(err)) return { status: "cancelled" };
      }
    }
    return direct(path, name);
  }
  save.direct = direct;
  save.hasNative = typeof native === "function";
  return save;
}
var PRINT_WIDTH = 1700;
var PRINT_FRAME_ID = "hc-print-frame";
var PAGE_IMAGE = /^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/;
var NO_PRINT = "This sheet could not be opened for printing. Use Save sheet and print the PDF.";
function printDocument(images, title = "Practice sheet") {
  const safe = String(title).replace(/[<>&"']/g, "");
  for (const src of images) if (!PAGE_IMAGE.test(src)) throw new Error(NO_PRINT);
  return `<!doctype html><html><head><meta charset="utf-8"><title>${safe}</title><style>@page{margin:0}html,body{margin:0;padding:0;background:#fff}img{display:block;margin:0 auto;max-width:100%;max-height:99vh;break-after:page;page-break-after:always}img:last-child{break-after:auto;page-break-after:auto}</style></head><body>${images.map((s) => `<img src="${s}" alt="">`).join("")}</body></html>`;
}
async function printPages({ load, scopeNow: scopeNow2, scope, title, env = {} }) {
  const stale = "Profile changed. Reopen this sheet in the new profile.";
  const images = [];
  let pages = 1;
  for (let i = 0; i < pages; i++) {
    guardScope(scopeNow2, scope, stale);
    const r = await load(i);
    guardScope(scopeNow2, scope, stale);
    if (!r?.image) throw new Error(NO_PRINT);
    images.push(r.image);
    if (i === 0) pages = Math.max(1, Math.min(50, Number(r.pages) || 1));
  }
  const html = printDocument(images, title);
  const doc = env.document || globalThis.document;
  if (!doc?.createElement || !doc.body) throw new Error(NO_PRINT);
  doc.getElementById?.(PRINT_FRAME_ID)?.remove?.();
  const frame = doc.createElement("iframe");
  frame.id = PRINT_FRAME_ID;
  frame.setAttribute?.("aria-hidden", "true");
  frame.tabIndex = -1;
  frame.style.cssText = "position:fixed;left:-9999px;top:0;width:1px;height:1px;border:0;opacity:0";
  await new Promise((res, rej) => {
    const timer = (env.setTimeout || setTimeout)(() => rej(new Error(NO_PRINT)), 2e4);
    frame.onload = () => {
      (env.clearTimeout || clearTimeout)(timer);
      res();
    };
    frame.srcdoc = html;
    doc.body.appendChild(frame);
  });
  const win = frame.contentWindow;
  if (typeof win?.print !== "function") {
    frame.remove?.();
    throw new Error(NO_PRINT);
  }
  await Promise.all(Array.from(win.document?.images || []).map((img) => img.decode?.().catch(() => {
  })));
  win.addEventListener?.("afterprint", () => frame.remove?.());
  win.focus?.();
  win.print();
  return { status: "printing", pages: images.length };
}
async function runJobScoped({ request: request2, scopeNow: scopeNow2, expectedScope, path, body, onTick, sleep = (ms) => new Promise((r) => setTimeout(r, ms)), maxPolls = 180 }) {
  const scope = expectedScope ?? scopeNow2(), fence = () => guardScope(scopeNow2, scope, "Profile changed while working. Reopen the previous profile to see the result.");
  fence();
  const start = await request2(path, { method: "POST", body, timeoutMs: 6e4 });
  fence();
  if (!start.job) return start;
  for (let n = 0; n < maxPolls; n++) {
    await sleep(n < 5 ? 1e3 : 2e3);
    fence();
    onTick?.(n);
    const j = await request2(`/jobs/${encodeURIComponent(start.job)}`);
    fence();
    if (j.status === "done") {
      if (j.result?.ok === false) throw new Error(j.result.error || "That did not work.");
      return j.result;
    }
    if (j.status === "error") throw new Error(j.error || "That did not work.");
  }
  throw new Error("Still working after 6 minutes. Check History shortly.");
}
function extOf(name) {
  return String(name || "").split(".").pop().toLowerCase();
}
function swapExt(name, mime) {
  const base = String(name || "upload").replace(/\.[^./\\]+$/, "");
  return `${base}.${EXT_FOR[mime]}`;
}
function readB64(file, env = {}) {
  return new Promise((res, rej) => {
    const R = env.FileReader || globalThis.FileReader, r = new R();
    r.onload = () => res(String(r.result).split(",", 2)[1] || "");
    r.onerror = () => rej(new Error("Could not read that file."));
    r.readAsDataURL(file);
  });
}
function browserCodec(env) {
  const w = globalThis;
  return {
    async decode(file) {
      if (!w.createImageBitmap) throw new Error("unsupported");
      return w.createImageBitmap(file);
    },
    async encode(bmp, width, height, mime, quality) {
      const canvas = w.OffscreenCanvas ? new w.OffscreenCanvas(width, height) : Object.assign(w.document.createElement("canvas"), { width, height });
      const g = canvas.getContext("2d");
      if (mime === "image/jpeg") {
        g.fillStyle = "#fff";
        g.fillRect(0, 0, width, height);
      }
      g.drawImage(bmp, 0, 0, width, height);
      if (canvas.convertToBlob) return canvas.convertToBlob({ type: mime, quality });
      return new Promise((ok, no) => canvas.toBlob((b) => b ? ok(b) : no(new Error("encode failed")), mime, quality));
    }
  };
}
async function prepareUpload(file, { teacher = false, env = {} } = {}) {
  const ext = extOf(file?.name), declared = IMAGE_MIMES[ext];
  const isImage = Boolean(declared) || /^image\//.test(file?.type || "");
  if (!isImage) {
    if (file.size > MAX_DOC_BYTES) throw new Error("That file is larger than 15 MB. Choose a smaller PDF or text file.");
    return { filename: file.name, mime: file.type || "application/octet-stream", data_b64: await readB64(file, env), resized: false };
  }
  if (!declared || file.type && !Object.values(IMAGE_MIMES).includes(file.type)) throw new Error("Use a JPG, PNG or WEBP image. Other image types such as HEIC are not supported here; export as JPG first.");
  const codec = env.codec || browserCodec(env), target = env.targetBytes ?? IMAGE_TARGET_BYTES, maxEdge = env.maxEdge ?? IMAGE_MAX_EDGE;
  let bmp;
  try {
    bmp = await codec.decode(file);
  } catch {
    throw new Error("That image could not be read. Choose a different JPG, PNG or WEBP file.");
  }
  try {
    const { width, height } = bmp;
    if (!(width > 0 && height > 0)) throw new Error("That image could not be read. Choose a different JPG, PNG or WEBP file.");
    if (file.size <= target && Math.max(width, height) <= maxEdge) return { filename: file.name, mime: declared, data_b64: await readB64(file, env), resized: false };
    const attempts = [];
    let edge = Math.min(maxEdge, Math.max(width, height));
    const minEdge = Math.min(IMAGE_MIN_EDGE, edge);
    while (true) {
      const s = edge / Math.max(width, height), w = Math.max(1, Math.round(width * s)), h = Math.max(1, Math.round(height * s));
      const mimes = declared === "image/png" ? ["image/png", "image/jpeg"] : [declared];
      for (const mime of mimes) {
        for (const q of mime === "image/png" ? [void 0] : [0.85, 0.7, 0.55]) {
          const blob = await codec.encode(bmp, w, h, mime, q);
          attempts.push(blob.size);
          if (blob.size <= target) return { filename: swapExt(file.name, blob.type || mime), mime: blob.type || mime, data_b64: await readB64(blob, env), resized: true, width: w, height: h };
        }
      }
      if (edge <= minEdge) break;
      edge = Math.max(minEdge, Math.round(edge * 0.75));
    }
    throw new Error("That image is still too large after shrinking. Retake it closer or at lower quality.");
  } finally {
    bmp.close?.();
  }
}

// desktop/src/plugin.jsx
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
var { host, Button, Input, Textarea, useQuery, useMutation, useQueryClient } = sdk;
var ID = "homework-coach";
var ROUTE = "/homework-coach";
var MARKS = ["I", "S", "N"];
var HELP = { I: "On their own", S: "With support", N: "Not yet" };
var DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
var navigation = sdk.atom({ tab: "today" });
var e = encodeURIComponent;
function errorText(err) {
  const d = err?.detail ?? err?.body?.detail ?? err?.data?.detail;
  return typeof d === "string" ? d : d && typeof d === "object" ? [d.error, ...d.details || []].filter(Boolean).join("; ") : String(err?.message || err || "");
}
function ratingsPayload(items, picks) {
  return Object.fromEntries((items || []).filter((it) => MARKS.includes(picks?.[it.id])).map((it) => [it.id, picks[it.id]]));
}
function levelBar(level) {
  const n = Math.max(1, Math.min(5, Number(level) || 1));
  return "\u25CF".repeat(n) + "\u25CB".repeat(5 - n);
}
function mimeFor(name) {
  return { jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp", pdf: "application/pdf", txt: "text/plain" }[String(name).split(".").pop().toLowerCase()] || "application/octet-stream";
}
function scopeNow() {
  return `${host.state.connectionId.get() || "local"}:${host.state.profile.get() || "default"}`;
}
function useScope() {
  const c = sdk.useValue(host.state.connectionId), p = sdk.useValue(host.state.profile);
  return `${c || "local"}:${p || "default"}`;
}
function goto(tab = "today", args = {}) {
  navigation.set({ scope: scopeNow(), tab, ...args });
  host.navigate(ROUTE);
}
function familyLink() {
  host.navigate(sdk.pluginSettingsHref(ID));
}
function request(ctx, path, opts) {
  return ctx.rest(path, opts).then((r) => {
    if (r?.ok === false) throw new Error(r.error || "The change was not saved.");
    return r;
  });
}
function useData(ctx, path, options = {}) {
  const scope = useScope();
  return useQuery({ queryKey: [ID, scope, path], queryFn: async () => {
    const native = sdk.captureGatewayFileDownload?.();
    const data = await request(ctx, path);
    if (scopeNow() !== scope) throw new Error("Profile changed. Reload this view.");
    return { ...data, _save: makeSaver({ native, ctx, scopeNow, scope, notify: host.notify }) };
  }, staleTime: 15e3, retry: 1, ...options });
}
function useWrite(ctx, onSuccess) {
  const qc = useQueryClient(), scope = useScope();
  return useMutation({ mutationFn: async ({ path, body = {} }) => {
    if (scopeNow() !== scope) throw new Error("Profile changed. Try again in the new profile.");
    const r = await request(ctx, path, { method: "POST", body, timeoutMs: 6e4 });
    if (scopeNow() !== scope) throw new Error("Saved in the previous profile. Reopen that profile to review.");
    return r;
  }, onSuccess: (r) => {
    qc.invalidateQueries({ queryKey: [ID, scope] });
    onSuccess?.(r);
  }, onError: (err) => host.notify({ kind: "error", message: errorText(err) }) });
}
function Notice({ error }) {
  return error ? /* @__PURE__ */ jsx("div", { className: "hc-error", role: "alert", children: errorText(error) }) : null;
}
function Empty({ title, children }) {
  return /* @__PURE__ */ jsxs("div", { className: "hc-empty hc-stack", children: [
    /* @__PURE__ */ jsx("h3", { children: title }),
    /* @__PURE__ */ jsx("div", { className: "hc-muted", children })
  ] });
}
function Loading() {
  return /* @__PURE__ */ jsxs("div", { className: "hc-row", role: "status", children: [
    /* @__PURE__ */ jsx(sdk.Loader, {}),
    /* @__PURE__ */ jsx("span", { children: "Loading\u2026" })
  ] });
}
function State({ q, children }) {
  if (q.isLoading) return /* @__PURE__ */ jsx(Loading, {});
  if (q.error) return /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
    /* @__PURE__ */ jsx(Notice, { error: q.error }),
    /* @__PURE__ */ jsx(Button, { variant: "secondary", onClick: () => q.refetch(), children: "Try again" })
  ] });
  if (!q.data) return /* @__PURE__ */ jsx(Empty, { title: "No information yet" });
  return children(q.data);
}
function Field({ label, children, wide = false }) {
  return /* @__PURE__ */ jsxs("label", { className: "hc-field" + (wide ? " wide" : ""), children: [
    /* @__PURE__ */ jsx("span", { children: label }),
    children
  ] });
}
function Back({ onClick, label = "Back" }) {
  return /* @__PURE__ */ jsxs(Button, { variant: "ghost", size: "sm", onClick, children: [
    "\u2190 ",
    label
  ] });
}
function Wrap({ children }) {
  return /* @__PURE__ */ jsxs("div", { className: "hc", children: [
    /* @__PURE__ */ jsx("style", { children: css }),
    children
  ] });
}
function canFollowSource(p) {
  return p.steered_by !== "homework photo" || p.photo_index != null;
}
function navigationView(s) {
  return s.packet ? { kind: "packet", ...s.packet } : s.observation ? { kind: "observation", ...s.observation } : null;
}
function Source({ packet, onSource }) {
  const src = packet.steered_by;
  const label = src === "homework photo" ? `Photo${packet.photo_label ? " \xB7 " + packet.photo_label : ""}` : src === "class curriculum" ? `Class \xB7 ${packet.class_unit || "current unit"}` : src === "grade default" ? "Grade default" : src?.includes("class") ? `Class \xB7 ${packet.class_unit || "current unit"}` : "Source not recorded";
  return /* @__PURE__ */ jsxs("button", { type: "button", className: "hc-source", disabled: !canFollowSource(packet), title: "Practice follows a fresh homework photo (up to 14 days), then the current class unit, then the grade default.", onClick: onSource, children: [
    label,
    " \u2197"
  ] });
}
async function saveFile(save, path, name, direct = false) {
  try {
    if (!save || !path) throw new Error("This file is not available to download on this connection.");
    await (direct ? save.direct : save)(path, name);
  } catch (err) {
    host.notify({ kind: "error", message: errorText(err) });
  }
}
function PrintButton({ ctx, date, childId, kind = "practice", children, ...rest }) {
  const [busy, setBusy] = useState(false);
  return /* @__PURE__ */ jsx(Button, { ...rest, disabled: busy, onClick: async () => {
    const scope = scopeNow();
    setBusy(true);
    try {
      await printPages({ load: (n) => request(ctx, `/packet/${e(date)}/${e(childId)}/preview?page=${n}&kind=${kind}&width=${PRINT_WIDTH}`, { timeoutMs: 6e4 }), scopeNow, scope, title: `${date} ${childId} ${kind === "key" ? "parent key" : "practice"}` });
    } catch (err) {
      host.notify({ kind: "error", message: errorText(err) });
    } finally {
      setBusy(false);
    }
  }, children: busy ? "Opening print\u2026" : children || "Print" });
}
async function draftInChat(ctx, prompt) {
  try {
    if (!ctx.runAction) throw new Error("Open a chat and paste this prompt.");
    await ctx.runAction("session.new");
    host.navigate("/");
    let ok = false;
    for (let n = 0; n < 12 && !ok; n++) {
      await new Promise((r) => setTimeout(r, 100));
      ok = await host.composer.insertText(null, prompt, { mode: "block" });
    }
    if (!ok) throw new Error("The new chat is not ready. Copy this prompt instead.");
  } catch (err) {
    host.notify({ kind: "info", message: errorText(err), detail: prompt });
    const ok = await copyText(ctx, prompt, sdk);
    host.notify({ kind: ok ? "info" : "error", message: ok ? "Prompt copied to the clipboard." : "Copy was not available. Select the prompt text from the notification and paste it into a chat.", detail: prompt });
  }
}
function HomeworkPage({ ctx }) {
  const scope = useScope();
  return /* @__PURE__ */ jsx(Workspace, { ctx }, scope);
}
function Workspace({ ctx }) {
  const q = useData(ctx, "/today", { refetchInterval: 6e4 }), nav = sdk.useValue(navigation);
  const state = nav.scope && nav.scope !== scopeNow() ? { tab: "today" } : nav;
  const [childId, setChild] = useState(state.childId || ""), [view, setView] = useState(navigationView(state));
  useEffect(() => {
    setView(navigationView(state));
    if (state.childId) setChild(state.childId);
  }, [state]);
  const child = q.data?.children?.find((c) => c.id === childId) || q.data?.children?.[0];
  const tab = state.tab || "today";
  const open = (kind, data = {}) => setView({ kind, childId: child?.id, ...data });
  const changeTab = (t) => {
    setView(null);
    goto(t, { childId: child?.id });
  };
  return /* @__PURE__ */ jsx(Wrap, { children: /* @__PURE__ */ jsxs("main", { className: "hc-main", children: [
    /* @__PURE__ */ jsxs("header", { className: "hc-header hc-row hc-between", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: "A little practice. A clearer picture." }),
        /* @__PURE__ */ jsx("h1", { children: "Homework Coach" }),
        /* @__PURE__ */ jsxs("p", { className: "hc-muted hc-small", children: [
          q.data?.today_label || "Your family workspace",
          " \xB7 Print, practise, understand."
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
        /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", onClick: familyLink, children: "Family & settings" }),
        /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", onClick: () => q.refetch(), children: "Refresh" })
      ] })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
      /* @__PURE__ */ jsx("div", { role: "tablist", "aria-label": "Homework views", className: "hc-tabs", children: [["today", "Today"], ["plan", "Class plan"], ["progress", "Progress"], ["history", "History"]].map(([id, label]) => /* @__PURE__ */ jsx("button", { type: "button", role: "tab", "aria-selected": tab === id, onClick: () => changeTab(id), children: label }, id)) }),
      /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
        /* @__PURE__ */ jsx("label", { className: "hc-small hc-muted", htmlFor: "hc-child", children: "Child" }),
        /* @__PURE__ */ jsx("select", { id: "hc-child", className: "hc-select", value: child?.id || "", onChange: (ev) => {
          setChild(ev.target.value);
          goto(tab, { childId: ev.target.value });
          setView(null);
        }, children: (q.data?.children || []).map((c) => /* @__PURE__ */ jsxs("option", { value: c.id, children: [
          c.name,
          " \xB7 Grade ",
          c.grade
        ] }, c.id)) }),
        /* @__PURE__ */ jsx(Button, { size: "sm", variant: "ghost", onClick: familyLink, children: "+ Add child" })
      ] })
    ] }),
    q.error ? /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
      /* @__PURE__ */ jsx(Notice, { error: q.error }),
      /* @__PURE__ */ jsxs(Empty, { title: "Let's set up your family", children: [
        /* @__PURE__ */ jsx("p", { children: "Choose the profile with Homework Coach enabled, or add your first child." }),
        /* @__PURE__ */ jsx(Button, { onClick: familyLink, children: "Open family setup" })
      ] })
    ] }) : q.isLoading ? /* @__PURE__ */ jsx(Loading, {}) : !child ? /* @__PURE__ */ jsx(Empty, { title: "Add your first child", children: /* @__PURE__ */ jsx(Button, { onClick: familyLink, children: "Family setup" }) }) : view ? /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
      /* @__PURE__ */ jsx(Back, { onClick: () => setView(null), label: tab === "plan" ? "Class plan" : tab === "history" ? "History" : "workspace" }),
      view.kind === "upload" ? /* @__PURE__ */ jsx(UploadView, { ctx, child: q.data.children.find((c) => c.id === view.childId) || child, teacher: view.teacher, initialFile: view.file, onDone: (r) => {
        q.refetch();
        setView(r ? { kind: "observation", childId: view.childId, index: r.index ?? -1 } : null);
      } }) : view.kind === "observation" ? /* @__PURE__ */ jsx(Readback, { ctx, childId: view.childId, index: view.index ?? -1 }) : view.kind === "packet" ? /* @__PURE__ */ jsx(RateDesk, { ctx, childId: view.childId, date: view.date, selectedItem: view.item, onSource: (p) => {
        if (p.steered_by === "homework photo") open("observation", { index: p.photo_index ?? -1 });
        else changeTab("plan");
      }, onDone: (next) => next ? goto(tab, { childId: next.id, packet: { childId: next.id, date: view.date } }) : setView(null) }) : null
    ] }) : tab === "today" ? /* @__PURE__ */ jsx(TodayView, { ctx, data: q.data, open, onPlan: (id) => goto("plan", { childId: id }) }) : tab === "plan" ? /* @__PURE__ */ jsx(ClassPlan, { ctx, childId: child.id, open }) : tab === "progress" ? /* @__PURE__ */ jsx(ProgressView, { ctx, childId: child.id, open }) : /* @__PURE__ */ jsx(HistoryView, { ctx, childId: child.id, open })
  ] }) });
}
function TodayView({ ctx, data, open, onPlan }) {
  const m = useWrite(ctx, (r) => {
    if (r.date) open("packet", { date: r.date, childId: r.child_ids?.[0] || data.children[0].id });
  });
  return /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
    /* @__PURE__ */ jsxs("div", { className: "hc-hero", children: [
      /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: "Today" }),
      /* @__PURE__ */ jsx("h2", { children: data.to_rate ? `${data.to_rate} ${data.to_rate === 1 ? "sheet is" : "sheets are"} waiting for your feedback.` : "Small steps, built around school." }),
      /* @__PURE__ */ jsx("p", { className: "hc-muted", children: "A photo tells us what class is doing. Your feedback tells us what to practise next." })
    ] }),
    /* @__PURE__ */ jsx(Notice, { error: m.error }),
    /* @__PURE__ */ jsx("div", { className: "hc-grid", children: data.children.map((c) => /* @__PURE__ */ jsxs("section", { className: "hc-card hc-stack", onDragOver: (ev) => ev.preventDefault(), onDrop: (ev) => {
      ev.preventDefault();
      if (ev.dataTransfer.files[0]) open("upload", { childId: c.id, file: ev.dataTransfer.files[0] });
    }, children: [
      /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h2", { children: c.name }),
          /* @__PURE__ */ jsxs("p", { className: "hc-small hc-muted", children: [
            "Grade ",
            c.grade,
            " \xB7 ",
            c.minutes,
            " minutes"
          ] })
        ] }),
        /* @__PURE__ */ jsx("span", { className: "hc-pill", children: { needs_rating: "Your feedback", packet_ready: "Ready to print", needs_photo: "Add homework", make_packet: "Ready to make", off: "Rest day", done: "All done" }[c.status] || c.status })
      ] }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h3", { children: c.headline }),
        /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: c.class_unit || "Aligned to the next bit of schoolwork" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
        /* @__PURE__ */ jsx(Button, { disabled: m.isPending, onClick: () => {
          if (c.action === "rate" || c.action === "open") open("packet", { childId: c.id, date: c.packet_date });
          else if (c.action === "generate") m.mutate({ path: "/generate", body: { date: c.packet_date, child_ids: [c.id] } });
          else if (c.action === "settings") familyLink();
          else open("upload", { childId: c.id });
        }, children: m.isPending ? "Making practice\u2026" : { rate: "Rate this sheet", open: "Open practice", generate: "Make practice", photo: "Add homework", settings: "Set practice days" }[c.action] || "Add homework" }),
        c.packet_date && (c.action === "rate" || c.action === "open") && /* @__PURE__ */ jsx(PrintButton, { ctx, date: c.packet_date, childId: c.id, variant: "outline", children: "Print sheet" }),
        /* @__PURE__ */ jsxs(Button, { variant: "ghost", size: "sm", onClick: () => onPlan(c.id), children: [
          c.has_plan ? "See class plan" : "Set up class plan",
          " \u2192"
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
        /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", onClick: () => open("upload", { childId: c.id }), children: "Add homework" }),
        /* @__PURE__ */ jsx("span", { className: "hc-small hc-muted", children: "or drop a photo here" })
      ] })
    ] }, c.id)) })
  ] });
}
function PendingStatus({ ctx }) {
  const q = useData(ctx, "/today", { refetchInterval: 6e4 });
  if (!q.data?.to_rate) return null;
  return /* @__PURE__ */ jsxs("button", { title: "Open Homework Coach", onClick: () => goto("today"), children: [
    "Homework \xB7 ",
    q.data.to_rate,
    " to rate"
  ] });
}
function ClassPlan({ ctx, childId, open }) {
  const q = useData(ctx, `/children/${e(childId)}/class-plan`), [selected, setSelected] = useState(null), [material, setMaterial] = useState(null), marker = useRef(null);
  const undo = useWrite(ctx), research = async () => {
    try {
      const r = await request(ctx, `/children/${e(childId)}/research-prompt`);
      await draftInChat(ctx, r.prompt);
    } catch (err) {
      host.notify({ kind: "error", message: errorText(err) });
    }
  };
  return /* @__PURE__ */ jsx(State, { q, children: (d) => {
    const unit = d.units?.find((u) => u.index === selected) || d.units?.find((u) => u.phase === "now") || d.units?.[0];
    return /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
      /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h2", { children: d.curriculum || "Class plan" }),
          /* @__PURE__ */ jsxs("p", { className: "hc-muted hc-small", children: [
            d.child.name,
            " \xB7 ",
            d.school_year,
            " \xB7 Research and teacher updates, together."
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
          /* @__PURE__ */ jsx(Button, { variant: "secondary", onClick: () => open("upload", { teacher: true, childId }), children: "Add teacher material" }),
          /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", onClick: research, children: "Research this program" }),
          /* @__PURE__ */ jsx(Button, { size: "sm", variant: "outline", onClick: () => marker.current?.scrollIntoView({ behavior: "smooth", block: "center" }), children: "Jump to today" })
        ] })
      ] }),
      /* @__PURE__ */ jsx(Notice, { error: undo.error }),
      !d.has_plan ? /* @__PURE__ */ jsxs(Empty, { title: "Bring the school year into view", children: [
        /* @__PURE__ */ jsx("p", { children: "Research the program in chat, or add a unit letter from the teacher." }),
        /* @__PURE__ */ jsxs(Button, { onClick: research, children: [
          "Set up ",
          d.child.name,
          "'s year in chat"
        ] })
      ] }) : /* @__PURE__ */ jsxs("div", { className: "hc-split", children: [
        /* @__PURE__ */ jsx("section", { className: "hc-timeline", "aria-label": "School year timeline", children: ["earlier", "now", "next"].map((phase) => /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("div", { ref: phase === "now" ? marker : null, className: "hc-today-marker", children: phase === "earlier" ? "EARLIER" : phase === "now" ? `TODAY \xB7 ${d.today}` : "COMING NEXT" }),
          d.units.filter((u) => u.phase === phase).map((u) => /* @__PURE__ */ jsx("div", { className: "hc-unit" + (u.phase === "now" ? " current" : ""), children: /* @__PURE__ */ jsxs("button", { type: "button", "aria-pressed": u.index === unit?.index, onClick: () => {
            setSelected(u.index);
            setMaterial(null);
          }, children: [
            /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
              /* @__PURE__ */ jsx("strong", { children: u.title }),
              /* @__PURE__ */ jsx("span", { className: "hc-pill", children: u.source === "teacher" ? "Teacher update" : "Researched" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "hc-small hc-muted", children: [
              u.start_label || u.start,
              " \u2014 ",
              u.end_label || u.end
            ] }),
            u.materials?.length > 0 && /* @__PURE__ */ jsxs("div", { className: "hc-small", children: [
              u.materials.length,
              " teacher ",
              u.materials.length === 1 ? "material" : "materials",
              " \xB7 ",
              u.packets?.length || 0,
              " practice sheets"
            ] })
          ] }) }, u.index))
        ] }, phase)) }),
        unit && /* @__PURE__ */ jsxs("aside", { className: "hc-card hc-stack hc-detail", children: [
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: "Inside this unit" }),
            /* @__PURE__ */ jsx("h2", { children: unit.title }),
            /* @__PURE__ */ jsxs("p", { className: "hc-small hc-muted", children: [
              unit.start,
              " \u2192 ",
              unit.end
            ] })
          ] }),
          unit.shifted && /* @__PURE__ */ jsxs("div", { className: "hc-callout", children: [
            /* @__PURE__ */ jsx("strong", { children: "Teacher-updated dates" }),
            /* @__PURE__ */ jsxs("div", { children: [
              "Was ",
              unit.researched_start,
              " \u2192 ",
              unit.researched_end
            ] }),
            /* @__PURE__ */ jsxs("div", { children: [
              "Now ",
              unit.start,
              " \u2192 ",
              unit.end
            ] }),
            /* @__PURE__ */ jsx("div", { className: "hc-small", children: unit.shift_note })
          ] }),
          unit.undo && /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", disabled: undo.isPending, onClick: () => undo.mutate({ path: `/children/${e(childId)}/units/${unit.index}/undo` }), children: "Undo latest date change" }),
          unit.goals?.length > 0 && /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsxs("h3", { children: [
              "What ",
              d.child.name,
              " is learning"
            ] }),
            /* @__PURE__ */ jsx("ul", { className: "hc-list", children: unit.goals.map((g, i) => /* @__PURE__ */ jsx("li", { children: g }, i)) })
          ] }),
          unit.vocabulary?.length > 0 && /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("h3", { children: "Words used in class" }),
            /* @__PURE__ */ jsx("div", { className: "hc-row", children: unit.vocabulary.map((v) => /* @__PURE__ */ jsx("span", { className: "hc-pill", children: v }, v)) })
          ] }),
          unit.standards?.length > 0 && /* @__PURE__ */ jsxs("p", { className: "hc-small hc-muted", children: [
            "Standards: ",
            unit.standards.join(" \xB7 ")
          ] }),
          unit.notes && /* @__PURE__ */ jsx("p", { className: "hc-small", children: unit.notes }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("h3", { children: "From the teacher" }),
            unit.materials?.length ? unit.materials.map((m) => /* @__PURE__ */ jsxs("div", { className: "hc-read-row", children: [
              /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
                /* @__PURE__ */ jsx("strong", { children: m.title }),
                m.has_file && /* @__PURE__ */ jsx(Button, { size: "sm", variant: "outline", onClick: () => setMaterial(m.index), children: "Open original \u2197" })
              ] }),
              /* @__PURE__ */ jsxs("p", { className: "hc-small hc-muted", children: [
                m.date_label,
                " \xB7 ",
                m.kind
              ] }),
              /* @__PURE__ */ jsx("p", { className: "hc-small", children: m.summary })
            ] }, m.index)) : /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "No teacher material pinned to these dates yet." })
          ] }),
          material !== null && /* @__PURE__ */ jsx(MaterialOriginal, { ctx, childId, index: material }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("h3", { children: "Practice from this unit" }),
            /* @__PURE__ */ jsx("div", { className: "hc-row", children: unit.packets?.length ? unit.packets.map((date) => /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", onClick: () => open("packet", { date, childId }), children: date }, date)) : /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "Practice sheets will appear here." }) })
          ] }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("h3", { children: "Research sources" }),
            /* @__PURE__ */ jsx(SourceLinks, { ctx, sources: d.sources })
          ] })
        ] })
      ] }),
      d.unmatched_materials?.length > 0 && /* @__PURE__ */ jsxs("section", { className: "hc-card hc-stack", children: [
        /* @__PURE__ */ jsx("h3", { children: "Other teacher materials" }),
        d.unmatched_materials.map((m) => /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
          /* @__PURE__ */ jsxs("span", { children: [
            m.title,
            " \xB7 ",
            m.date_label
          ] }),
          /* @__PURE__ */ jsx(Button, { size: "sm", variant: "ghost", onClick: () => setMaterial(m.index), children: "Open original" })
        ] }, m.index)),
        material !== null && !unit?.materials?.some((m) => m.index === material) && /* @__PURE__ */ jsx(MaterialOriginal, { ctx, childId, index: material })
      ] })
    ] });
  } });
}
function SourceLinks({ ctx, sources = [] }) {
  return /* @__PURE__ */ jsx("ul", { className: "hc-list hc-small", children: sources.map((s, i) => {
    const raw = typeof s === "string" ? s : s.url || "";
    const m = raw.match(/^(.*?)\s*\((https?:\/\/[^)\s]+)\)\s*$/) || raw.match(/^(https?:\/\/\S+)\s*\((.*)\)$/);
    const url = m ? m[1].startsWith("http") ? m[1] : m[2] : /^https?:/.test(raw) ? raw : s.url;
    let host2 = "";
    try {
      host2 = new URL(url).hostname.replace(/^www\./, "");
    } catch {
    }
    ;
    const label = typeof s === "object" && (s.title || s.label) || (m ? m[1].startsWith("http") ? m[2] : m[1] : "") || (url ? host2 : raw);
    return /* @__PURE__ */ jsx("li", { children: /^https?:\/\//i.test(url || "") ? /* @__PURE__ */ jsxs("button", { className: "hc-inline-link hc-wrap", onClick: () => ctx.os?.openExternal?.(url), children: [
      label,
      host2 && label !== host2 ? /* @__PURE__ */ jsxs("span", { className: "hc-muted", children: [
        " \xB7 ",
        host2
      ] }) : null,
      " \u2197"
    ] }) : /* @__PURE__ */ jsx("span", { children: label || "Source recorded without a URL" }) }, i);
  }) });
}
function MaterialOriginal({ ctx, childId, index }) {
  const q = useData(ctx, `/children/${e(childId)}/materials/${index}/file`);
  return /* @__PURE__ */ jsx(State, { q, children: (d) => /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
    d.image && /* @__PURE__ */ jsx("img", { className: "hc-photo", src: d.image, alt: "Original teacher material" }),
    /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", onClick: () => saveFile(d._save, d.path, d.name), children: "Save original file" }),
    /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", onClick: () => saveFile(d._save, d.path, d.name, true), children: "Direct download" })
  ] }) });
}
function FamilyPage({ ctx, scheduleOnly = false }) {
  const scope = useScope();
  return /* @__PURE__ */ jsx(FamilySettings, { ctx, scheduleOnly }, scope);
}
function FamilySettings({ ctx, scheduleOnly }) {
  const q = useData(ctx, "/family"), [editing, setEditing] = useState(null), [confirm, setConfirm] = useState(null);
  const m = useWrite(ctx, () => setConfirm(null));
  return /* @__PURE__ */ jsx(Wrap, { children: /* @__PURE__ */ jsxs("main", { className: "hc-main hc-stack", children: [
    /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: "Family settings" }),
        /* @__PURE__ */ jsx("h1", { children: scheduleOnly ? "Practice schedule" : "Your children" }),
        /* @__PURE__ */ jsx("p", { className: "hc-muted", children: "Change a profile without losing its learning history." })
      ] }),
      /* @__PURE__ */ jsx(Button, { variant: "outline", onClick: () => goto("today"), children: "Open workspace" })
    ] }),
    /* @__PURE__ */ jsx(Notice, { error: m.error }),
    q.isLoading ? /* @__PURE__ */ jsx(Loading, {}) : q.error ? /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx(Notice, { error: q.error }),
      /* @__PURE__ */ jsx(ChildForm, { ctx, child: {}, onDone: () => q.refetch() })
    ] }) : q.data && /* @__PURE__ */ jsxs(Fragment, { children: [
      !scheduleOnly && /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx("div", { className: "hc-row", children: /* @__PURE__ */ jsx(Button, { onClick: () => setEditing({}), children: "+ Add child" }) }),
        editing && /* @__PURE__ */ jsx(ChildForm, { ctx, child: editing, familyZone: q.data.timezone, hasChildren: (q.data.children || []).length > 0, grades: q.data.grades, onDone: () => {
          setEditing(null);
          q.refetch();
        } }, editing.id || "new"),
        /* @__PURE__ */ jsx("div", { className: "hc-grid", children: q.data.children.map((c) => /* @__PURE__ */ jsxs("section", { className: "hc-card hc-stack", children: [
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("h2", { children: c.name }),
            /* @__PURE__ */ jsxs("p", { className: "hc-muted hc-small", children: [
              "Grade ",
              c.grade,
              " \xB7 ",
              c.minutes_per_day,
              " minutes \xB7 Math"
            ] }),
            /* @__PURE__ */ jsx("p", { className: "hc-small", children: c.curriculum })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
            /* @__PURE__ */ jsx(Button, { size: "sm", variant: "secondary", onClick: () => setEditing(c), children: "Edit profile" }),
            /* @__PURE__ */ jsx(Button, { size: "sm", variant: "ghost", onClick: async () => {
              try {
                const r = await request(ctx, `/children/${e(c.id)}/research-prompt`);
                await draftInChat(ctx, r.prompt);
              } catch (err) {
                host.notify({ kind: "error", message: errorText(err) });
              }
            }, children: "Research program" }),
            /* @__PURE__ */ jsx(Button, { size: "sm", variant: "ghost", onClick: () => setConfirm(c.id), children: "Archive" })
          ] }),
          confirm === c.id && /* @__PURE__ */ jsxs("div", { className: "hc-callout", children: [
            /* @__PURE__ */ jsxs("p", { children: [
              "Archive ",
              c.name,
              "? Their practice history stays here and can be restored."
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
              /* @__PURE__ */ jsx(Button, { size: "sm", disabled: m.isPending, onClick: () => m.mutate({ path: `/family/children/${e(c.id)}/archive` }), children: "Confirm archive" }),
              /* @__PURE__ */ jsx(Button, { size: "sm", variant: "ghost", onClick: () => setConfirm(null), children: "Keep active" })
            ] })
          ] })
        ] }, c.id)) }),
        q.data.archived?.length > 0 && /* @__PURE__ */ jsxs("section", { className: "hc-card hc-stack", children: [
          /* @__PURE__ */ jsx("h3", { children: "Archived \xB7 history preserved" }),
          q.data.archived.map((c) => /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
            /* @__PURE__ */ jsxs("span", { children: [
              c.name,
              " \xB7 Grade ",
              c.grade
            ] }),
            /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", disabled: m.isPending, onClick: () => m.mutate({ path: `/family/children/${e(c.id)}/restore` }), children: "Restore" })
          ] }, c.id))
        ] })
      ] }),
      /* @__PURE__ */ jsx(ScheduleForm, { ctx, schedule: q.data.schedule, timezone: q.data.timezone }, JSON.stringify(q.data.schedule))
    ] })
  ] }) });
}
function DayPicker({ value, onChange }) {
  return /* @__PURE__ */ jsx("div", { className: "hc-days", "aria-label": "Practice days", children: DAYS.map((d) => /* @__PURE__ */ jsx("button", { type: "button", className: "hc-rating", "aria-label": d, "aria-pressed": value.includes(d), onClick: () => onChange(value.includes(d) ? value.filter((x) => x !== d) : [...value, d]), children: d.slice(0, 1).toUpperCase() + d.slice(1) }, d)) });
}
function ChildForm({ ctx, child = {}, familyZone, hasChildren = false, grades = ["PK", "K", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], onDone }) {
  const [form, setForm] = useState({ name: child.name || "", grade: child.grade || "3", minutes_per_day: child.minutes_per_day || 15, curriculum: child.curriculum || "", days: child.schedule?.days || [], time: child.schedule?.time || "09:00", timezone: pickTimezone({ existing: child.schedule?.timezone || child.timezone, familyZone, hasChildren, client: clientTimezone() }) });
  const [custom, setCustom] = useState(Boolean(child.schedule)), m = useWrite(ctx, onDone);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  return /* @__PURE__ */ jsxs("form", { className: "hc-card hc-stack", onSubmit: (ev) => {
    ev.preventDefault();
    m.mutate({ path: child.id ? `/family/children/${e(child.id)}` : "/family/children", body: { ...form, days: custom ? form.days : [] } });
  }, children: [
    /* @__PURE__ */ jsx("h2", { children: child.id ? `Edit ${child.name}` : "Add a child" }),
    /* @__PURE__ */ jsxs("div", { className: "hc-form-grid", children: [
      /* @__PURE__ */ jsx(Field, { label: "Name", children: /* @__PURE__ */ jsx(Input, { value: form.name, required: true, maxLength: 40, onChange: (ev) => set("name", ev.target.value) }) }),
      /* @__PURE__ */ jsx(Field, { label: "Grade", children: /* @__PURE__ */ jsx("select", { className: "hc-select", value: form.grade, onChange: (ev) => set("grade", ev.target.value), children: grades.map((g) => /* @__PURE__ */ jsx("option", { value: g, children: g === "PK" ? "Pre-K" : g === "K" ? "Kindergarten" : `Grade ${g}` }, g)) }) }),
      /* @__PURE__ */ jsx(Field, { label: "Minutes per day", children: /* @__PURE__ */ jsx(Input, { type: "number", min: 5, max: 60, required: true, value: form.minutes_per_day, onChange: (ev) => set("minutes_per_day", Number(ev.target.value)) }) }),
      /* @__PURE__ */ jsx(Field, { label: "School math program", children: /* @__PURE__ */ jsx(Input, { value: form.curriculum, placeholder: "e.g. enVision Math, Eureka Math", maxLength: 120, onChange: (ev) => set("curriculum", ev.target.value) }) })
    ] }),
    /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "Math \xB7 Practice stays on paper; the parent key stays separate. Saved history is kept when you change grades." }),
    /* @__PURE__ */ jsxs("label", { className: "hc-row hc-small", children: [
      /* @__PURE__ */ jsx("input", { type: "checkbox", checked: custom, onChange: (ev) => setCustom(ev.target.checked) }),
      "Use different practice days for this child"
    ] }),
    custom && /* @__PURE__ */ jsx(DayPicker, { value: form.days, onChange: (v) => set("days", v) }),
    /* @__PURE__ */ jsx(Notice, { error: m.error }),
    /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
      /* @__PURE__ */ jsx(Button, { type: "submit", disabled: m.isPending || !form.name.trim() || custom && !form.days.length, children: m.isPending ? "Saving\u2026" : child.id ? "Save profile" : "Add child" }),
      /* @__PURE__ */ jsx(Button, { type: "button", variant: "ghost", onClick: () => onDone?.(), children: "Cancel" })
    ] })
  ] });
}
function ScheduleForm({ ctx, schedule = {}, timezone }) {
  const [days, setDays] = useState(schedule.days || DAYS.slice(0, 6)), [time, setTime] = useState(schedule.time || "09:00"), [saved, setSaved] = useState(false), [tz, setTz] = useState(timezone || clientTimezone());
  const m = useWrite(ctx, () => setSaved(true));
  const tzOk = validTimezone(tz);
  return /* @__PURE__ */ jsxs("form", { className: "hc-card hc-stack", onSubmit: (ev) => {
    ev.preventDefault();
    m.mutate({ path: "/family/schedule", body: { days, time, timezone: tz } });
  }, children: [
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("h2", { children: "Practice schedule" }),
      /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "Default for children without their own schedule" })
    ] }),
    /* @__PURE__ */ jsx(DayPicker, { value: days, onChange: (v) => {
      setDays(v);
      setSaved(false);
    } }),
    /* @__PURE__ */ jsx(Field, { label: "Preferred time", children: /* @__PURE__ */ jsx(Input, { type: "time", required: true, value: time, onChange: (ev) => {
      setTime(ev.target.value);
      setSaved(false);
    } }) }),
    /* @__PURE__ */ jsx(Field, { label: "Time zone (IANA name, e.g. America/Chicago)", children: /* @__PURE__ */ jsx(Input, { value: tz, required: true, onChange: (ev) => {
      setTz(ev.target.value.trim());
      setSaved(false);
    }, "aria-invalid": !tzOk }) }),
    !tzOk && /* @__PURE__ */ jsx("p", { className: "hc-small", role: "alert", children: "Enter a valid time zone such as America/Chicago." }),
    /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "These preferences guide packet dates. Automatic delivery requires the Daily homework practice packet blueprint using this timezone. Changing these preferences does not reschedule existing jobs." }),
    /* @__PURE__ */ jsx(Notice, { error: m.error }),
    /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
      /* @__PURE__ */ jsx(Button, { type: "submit", disabled: m.isPending || !days.length || !tzOk, children: "Save schedule" }),
      saved && /* @__PURE__ */ jsx("span", { role: "status", children: "Schedule saved." })
    ] })
  ] });
}
function ratingKey(ev) {
  if (ev.ctrlKey || ev.metaKey || ev.altKey || ev.target?.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(ev.target?.tagName)) return null;
  const k = String(ev.key || "").toUpperCase();
  return MARKS.includes(k) ? k : null;
}
function RateDesk({ ctx, childId, date, selectedItem, onDone, onSource }) {
  const q = useData(ctx, `/packet/${e(date)}/${e(childId)}`);
  return /* @__PURE__ */ jsx(State, { q, children: (d) => /* @__PURE__ */ jsx(RateSession, { ctx, packet: d, selectedItem, onDone, onSource }, `${childId}:${date}`) });
}
function RateSession({ ctx, packet: p, selectedItem, onDone, onSource }) {
  const [picks, setPicks] = useState(Object.fromEntries(p.items.filter((i) => i.rating).map((i) => [i.id, i.rating]))), [cursor, setCursor] = useState(Math.max(0, p.items.findIndex((i) => i.id === selectedItem))), [undo, setUndo] = useState([]), [note, setNote] = useState(""), [saved, setSaved] = useState(null), [keyView, setKeyView] = useState(false);
  const root = useRef(null), m = useWrite(ctx, setSaved);
  const mark = (idx, r) => {
    setUndo((u) => [...u, { picks: { ...picks }, cursor }]);
    setPicks((x) => ({ ...x, [p.items[idx].id]: r }));
    setCursor(Math.min(p.items.length - 1, idx + 1));
  };
  useEffect(() => {
    root.current?.focus();
  }, []);
  const keyboard = (ev) => {
    const r = ratingKey(ev);
    if (r) {
      ev.preventDefault();
      mark(cursor, r);
    } else if (!["INPUT", "TEXTAREA", "SELECT"].includes(ev.target?.tagName) && ["ArrowUp", "ArrowDown"].includes(ev.key)) {
      ev.preventDefault();
      setCursor((i) => Math.max(0, Math.min(p.items.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1))));
    }
  };
  const required = p.items.filter((i) => !i.optional), count = required.filter((i) => picks[i.id]).length;
  if (saved) return /* @__PURE__ */ jsxs("div", { className: "hc-card hc-stack", children: [
    /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: "Feedback saved" }),
    /* @__PURE__ */ jsxs("h2", { children: [
      "Thanks. ",
      p.child.name,
      "'s next practice has a clearer starting point."
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "hc-callout", children: [
      /* @__PURE__ */ jsx("strong", { children: saved.applies_label ? `Next practice \xB7 ${saved.applies_label}` : "What changes next" }),
      saved.plain_changes?.length ? /* @__PURE__ */ jsx("ul", { className: "hc-list", children: saved.plain_changes.map((c, i) => /* @__PURE__ */ jsxs("li", { children: [
        c.label,
        ": ",
        c.plain,
        "."
      ] }, i)) }) : /* @__PURE__ */ jsx("p", { children: "The current difficulty stays steady. One round is useful evidence, not a verdict." })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
      /* @__PURE__ */ jsx(Button, { onClick: () => onDone(saved.next_child || null), children: saved.next_child ? `Next: ${saved.next_child.name}` : "Done for now" }),
      /* @__PURE__ */ jsx(Button, { variant: "ghost", onClick: () => setSaved(null), children: "Review ratings" })
    ] })
  ] });
  return /* @__PURE__ */ jsxs("div", { ref: root, tabIndex: 0, onKeyDown: keyboard, className: "hc-stack", "aria-label": "Rate practice desk", children: [
    /* @__PURE__ */ jsxs("header", { className: "hc-row hc-between", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsxs("div", { className: "hc-eyebrow", children: [
          "Rate desk \xB7 ",
          p.label
        ] }),
        /* @__PURE__ */ jsxs("h2", { children: [
          p.child.name,
          " \xB7 ",
          p.focus
        ] }),
        /* @__PURE__ */ jsx(Source, { packet: p, onSource: () => onSource(p) })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
        /* @__PURE__ */ jsx(PrintButton, { ctx, date: p.date, childId: p.child.id, kind: keyView ? "key" : "practice", size: "sm", children: keyView ? "Print key" : "Print sheet" }),
        /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", onClick: () => saveFile(p._save, p.practice_pdf, `${p.date}_${p.child.id}_practice.pdf`), children: "Save sheet" }),
        /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", onClick: () => saveFile(p._save, p.practice_pdf, `${p.date}_${p.child.id}_practice.pdf`, true), children: "Direct download" }),
        /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", onClick: () => setKeyView(!keyView), children: keyView ? "Practice sheet" : "Parent key" }),
        keyView && /* @__PURE__ */ jsxs(Fragment, { children: [
          /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", onClick: () => saveFile(p._save, p.key_pdf, `${p.date}_parent_key.pdf`), children: "Save key" }),
          /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", onClick: () => saveFile(p._save, p.key_pdf, `${p.date}_parent_key.pdf`, true), children: "Direct download" })
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "hc-split", children: [
      /* @__PURE__ */ jsx(PacketPreview, { ctx, date: p.date, childId: p.child.id, kind: keyView ? "key" : "practice" }),
      /* @__PURE__ */ jsxs("section", { className: "hc-card hc-stack", children: [
        /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
          /* @__PURE__ */ jsxs("h3", { children: [
            count,
            " of ",
            required.length,
            " core problems rated"
          ] }),
          /* @__PURE__ */ jsx("span", { className: "hc-pill", children: "Optional challenge stays optional" })
        ] }),
        /* @__PURE__ */ jsxs("p", { className: "hc-small hc-muted", children: [
          /* @__PURE__ */ jsx("kbd", { className: "hc-keyboard", children: "I" }),
          " On their own \xB7 ",
          /* @__PURE__ */ jsx("kbd", { className: "hc-keyboard", children: "S" }),
          " With support \xB7 ",
          /* @__PURE__ */ jsx("kbd", { className: "hc-keyboard", children: "N" }),
          " Not yet",
          /* @__PURE__ */ jsx("br", {}),
          "Use \u2191 \u2193 to move. Ratings save only when you choose Save ratings."
        ] }),
        /* @__PURE__ */ jsx("div", { children: p.items.map((it, idx) => /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsxs("div", { className: "hc-rate-row" + (idx === cursor ? " selected" : ""), children: [
            /* @__PURE__ */ jsxs("button", { type: "button", className: "hc-problem-label", onClick: () => setCursor(idx), children: [
              /* @__PURE__ */ jsxs("strong", { children: [
                it.id,
                ". ",
                it.prompt
              ] }),
              /* @__PURE__ */ jsxs("div", { className: "hc-small hc-muted", children: [
                it.optional ? "Optional \xB7 " : "",
                String(it.format_label || it.skill_label || "").replace(/->/g, "\u2192")
              ] })
            ] }),
            /* @__PURE__ */ jsx("div", { className: "hc-row", style: { gap: 4 }, children: MARKS.map((r) => /* @__PURE__ */ jsx("button", { type: "button", className: "hc-rating", "aria-label": `${it.id}: ${HELP[r]}`, title: HELP[r], "aria-pressed": picks[it.id] === r, onClick: () => mark(idx, r), children: r }, r)) })
          ] }),
          ["S", "N"].includes(picks[it.id]) && /* @__PURE__ */ jsxs("div", { className: "hc-callout hc-tip", children: [
            /* @__PURE__ */ jsx("strong", { children: "How to explain this" }),
            /* @__PURE__ */ jsx("p", { children: it.tip }),
            /* @__PURE__ */ jsx("button", { type: "button", className: "hc-inline-link hc-small", onClick: () => draftInChat(ctx, `Help me explain problem ${it.id} from ${p.child.name}'s ${p.date} practice: ${it.prompt}. Use the current class vocabulary and give a short parent coaching example.`), children: "Ask Hermes for another explanation" })
          ] }),
          idx === cursor && /* @__PURE__ */ jsxs("details", { className: "hc-small hc-muted", style: { padding: "8px 12px" }, children: [
            /* @__PURE__ */ jsx("summary", { children: "Parent answer & explanation" }),
            /* @__PURE__ */ jsx("strong", { children: it.answer }),
            /* @__PURE__ */ jsx("p", { children: it.worked })
          ] })
        ] }, it.id)) }),
        /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
          /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", disabled: !undo.length, onClick: () => {
            const last = undo.at(-1);
            setPicks(last.picks);
            setCursor(last.cursor);
            setUndo((u) => u.slice(0, -1));
          }, children: "Undo last rating" }),
          /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", disabled: count === required.length, onClick: () => {
            setUndo((u) => [...u, { picks: { ...picks }, cursor }]);
            setPicks((x) => ({ ...Object.fromEntries(required.filter((it) => !x[it.id]).map((it) => [it.id, "I"])), ...x }));
          }, children: "Mark rest independent" })
        ] }),
        /* @__PURE__ */ jsx(Field, { label: "Optional note", children: /* @__PURE__ */ jsx(Textarea, { rows: 2, maxLength: 1e3, value: note, onChange: (ev) => setNote(ev.target.value), placeholder: "What helped? What was hard?" }) }),
        /* @__PURE__ */ jsx(Notice, { error: m.error }),
        /* @__PURE__ */ jsx(Button, { disabled: m.isPending || !Object.keys(ratingsPayload(p.items, picks)).length, onClick: () => m.mutate({ path: "/rate", body: { child_id: p.child.id, packet_date: p.date, ratings: ratingsPayload(p.items, picks), note } }), children: m.isPending ? "Saving\u2026" : "Save ratings" })
      ] })
    ] })
  ] });
}
function PacketPreview({ ctx, date, childId, kind = "practice" }) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [kind, date, childId]);
  const q = useData(ctx, `/packet/${e(date)}/${e(childId)}/preview?page=${page}&kind=${kind}`);
  return /* @__PURE__ */ jsxs("section", { className: "hc-detail", children: [
    /* @__PURE__ */ jsxs("div", { className: "hc-preview-bar", children: [
      /* @__PURE__ */ jsx("strong", { children: kind === "key" ? "Parent key \xB7 keep separate" : "Practice sheet \xB7 exactly as printed" }),
      /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
        /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", disabled: page === 0, onClick: () => setPage((p) => p - 1), children: "\u2190" }),
        /* @__PURE__ */ jsxs("span", { className: "hc-small", children: [
          page + 1,
          " / ",
          q.data?.pages || 1
        ] }),
        /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "sm", disabled: !q.data?.pages || page + 1 >= q.data.pages, onClick: () => setPage((p) => p + 1), children: "\u2192" })
      ] })
    ] }),
    q.isLoading ? /* @__PURE__ */ jsx(Loading, {}) : q.error ? /* @__PURE__ */ jsxs("div", { className: "hc-callout", children: [
      "Preview unavailable. Use Save sheet or Save key to open the original PDF.",
      /* @__PURE__ */ jsx(Notice, { error: q.error })
    ] }) : q.data?.image ? /* @__PURE__ */ jsx("div", { className: "hc-photo-wrap", children: /* @__PURE__ */ jsx("img", { className: "hc-photo", src: q.data.image, alt: `${kind === "key" ? "Parent key" : "Practice sheet"} page ${page + 1}` }) }) : /* @__PURE__ */ jsx(Empty, { title: "PDF preview unavailable", children: "Save the original PDF to view or print it." })
  ] });
}
function packetReference(attrs) {
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(attrs?.child || "") || !/^\d{4}-\d{2}-\d{2}$/.test(attrs?.date || "")) return null;
  return { childId: attrs.child, date: attrs.date };
}
function ChatPacket({ ctx, attrs, sessionId }) {
  const ref = packetReference(attrs);
  if (!ref) return /* @__PURE__ */ jsx("span", { children: "Packet reference unavailable." });
  return /* @__PURE__ */ jsx(PacketCardData, { ctx, ...ref, sessionId });
}
function PacketCardData({ ctx, childId, date }) {
  const q = useData(ctx, `/packet/${e(date)}/${e(childId)}`);
  return /* @__PURE__ */ jsx(Wrap, { children: /* @__PURE__ */ jsx("div", { className: "hc-card hc-coach-card", children: /* @__PURE__ */ jsx(State, { q, children: (p) => /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
    /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsxs("div", { className: "hc-eyebrow", children: [
          "Practice ready \xB7 ",
          p.label
        ] }),
        /* @__PURE__ */ jsx("h2", { children: p.child.name }),
        /* @__PURE__ */ jsx("p", { children: p.focus })
      ] }),
      p.verified === true && /* @__PURE__ */ jsx("span", { className: "hc-pill", children: "\u2713 Answer checks passed" })
    ] }),
    /* @__PURE__ */ jsx(Source, { packet: p, onSource: () => goto(p.steered_by === "homework photo" ? "history" : "plan", { childId, ...p.steered_by === "homework photo" ? { observation: { childId, index: p.photo_index } } : {} }) }),
    /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
      /* @__PURE__ */ jsx(Button, { size: "sm", onClick: () => goto("today", { childId, packet: { date, childId } }), children: "Open sheet" }),
      /* @__PURE__ */ jsx(PrintButton, { ctx, date, childId, size: "sm", variant: "outline", children: "Print" }),
      /* @__PURE__ */ jsx(Button, { size: "sm", variant: "outline", onClick: () => saveFile(p._save, p.practice_pdf, `${date}_${childId}_practice.pdf`), children: "Save" }),
      /* @__PURE__ */ jsx(Button, { size: "sm", variant: "outline", onClick: () => saveFile(p._save, p.key_pdf, `${date}_parent_key.pdf`), children: "Parent key" }),
      /* @__PURE__ */ jsx(Button, { size: "sm", variant: "secondary", onClick: () => goto("today", { childId, packet: { date, childId } }), children: "Rate \u2192" })
    ] })
  ] }) }) }) });
}
function PacketMedia({ ctx, file, args, result, fallback, sessionId }) {
  let r = result;
  try {
    if (typeof r === "string") r = JSON.parse(r);
  } catch {
    return fallback;
  }
  const childId = Object.keys(r?.files || {}).find((k) => !k.startsWith("parent_key") && r.files[k] === file?.path);
  const date = r?.date || args?.date || String(file?.path || "").match(/(?:^|[\/\\])(\d{4}-\d{2}-\d{2})(?:[\/\\])/)?.[1];
  const ref = packetReference({ child: childId, date });
  return ref ? /* @__PURE__ */ jsx(ChatPacket, { ctx, attrs: { child: childId, date }, sessionId }) : fallback;
}
function ProgressView({ ctx, childId, open }) {
  const [days, setDays] = useState(30), q = useData(ctx, `/children/${e(childId)}/progress?days=${days}`);
  return /* @__PURE__ */ jsx(State, { q, children: (d) => /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
    /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsxs("h2", { children: [
          "How ",
          d.child.name,
          " is doing"
        ] }),
        /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "Each square is one problem on a practice sheet, with your rating. Nothing here is estimated." })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "hc-row", role: "group", "aria-label": "Time window", children: [14, 30, 90].map((n) => /* @__PURE__ */ jsxs(Button, { size: "sm", variant: days === n ? "secondary" : "ghost", onClick: () => setDays(n), children: [
        n,
        " days"
      ] }, n)) })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "hc-stats", children: [
      /* @__PURE__ */ jsxs("div", { className: "hc-card hc-metric", children: [
        /* @__PURE__ */ jsx("div", { className: "hc-stat", children: d.rated_problems }),
        /* @__PURE__ */ jsx("div", { className: "hc-small hc-muted", children: "problems rated" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "hc-card hc-metric", children: [
        /* @__PURE__ */ jsx("div", { className: "hc-stat", children: d.totals.I }),
        /* @__PURE__ */ jsx("div", { className: "hc-small hc-muted", children: "done on their own" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "hc-card hc-metric", children: [
        /* @__PURE__ */ jsx("div", { className: "hc-stat", children: d.totals.S }),
        /* @__PURE__ */ jsx("div", { className: "hc-small hc-muted", children: "with support" })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: "hc-card hc-metric", children: [
        /* @__PURE__ */ jsx("div", { className: "hc-stat", children: d.totals.N }),
        /* @__PURE__ */ jsx("div", { className: "hc-small hc-muted", children: "not yet" })
      ] })
    ] }),
    /* @__PURE__ */ jsxs("p", { className: "hc-small hc-muted", children: [
      /* @__PURE__ */ jsx("span", { className: "hc-mark", "data-rating": "I", children: "I" }),
      " on their own \xB7 ",
      /* @__PURE__ */ jsx("span", { className: "hc-mark", "data-rating": "S", children: "S" }),
      " with support \xB7 ",
      /* @__PURE__ */ jsx("span", { className: "hc-mark", "data-rating": "N", children: "N" }),
      " not yet \xB7 ",
      /* @__PURE__ */ jsx("span", { className: "hc-mark", children: "\xB7" }),
      " not rated (optional or skipped)"
    ] }),
    !d.enough_data && /* @__PURE__ */ jsx("div", { className: "hc-callout", children: "Rate two practice sheets and this view fills in. One sheet is a snapshot, not a trend." }),
    d.skills.map((s) => /* @__PURE__ */ jsxs("section", { className: "hc-card hc-stack", children: [
      /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h3", { children: s.label }),
          /* @__PURE__ */ jsxs("p", { className: "hc-small hc-muted", children: [
            "Level ",
            s.level,
            " of 5 ",
            /* @__PURE__ */ jsx("span", { className: "hc-accent", "aria-hidden": "true", children: levelBar(s.level) })
          ] })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "hc-row hc-small hc-muted", children: Object.entries(s.dims || {}).map(([k, v]) => /* @__PURE__ */ jsxs("span", { className: "hc-pill", children: [
          { scaffold: "Hints", steps: "Steps", representation: "Pictures", number_range: "Number size" }[k] || k,
          " ",
          v
        ] }, k)) })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "hc-table-wrap", children: /* @__PURE__ */ jsxs("table", { className: "hc-table", children: [
        /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsx("tr", { children: s.cells.map((c) => /* @__PURE__ */ jsx("th", { children: d.columns.find((x) => x.date === c.date)?.label || c.date }, c.date)) }) }),
        /* @__PURE__ */ jsx("tbody", { children: /* @__PURE__ */ jsx("tr", { children: s.cells.map((c) => /* @__PURE__ */ jsx("td", { children: c.marks.length ? c.marks.map((m) => /* @__PURE__ */ jsx("button", { type: "button", className: "hc-mark", "data-rating": m.rating || "", title: `${m.prompt} \xB7 ${m.rating ? HELP[m.rating] : "not rated"}`, onClick: () => open("packet", { childId, date: c.date, item: m.id }), children: m.rating || "\xB7" }, m.id)) : /* @__PURE__ */ jsx("span", { className: "hc-muted", children: "\u2014" }) }, c.date)) }) })
      ] }) }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h3", { className: "hc-small", children: "What changed, and why" }),
        s.changes.length ? s.changes.map((c, i) => /* @__PURE__ */ jsxs("div", { className: "hc-progress-log hc-small", children: [
          /* @__PURE__ */ jsx("span", { className: "hc-muted", children: c.label }),
          /* @__PURE__ */ jsxs("span", { children: [
            c.plain,
            c.why ? ` \u2014 ${c.why}` : ""
          ] })
        ] }, i)) : /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "No difficulty change in this window." })
      ] })
    ] }, s.skill)),
    d.homework?.length > 0 && /* @__PURE__ */ jsxs("section", { className: "hc-card hc-stack", children: [
      /* @__PURE__ */ jsx("h3", { children: "From school homework" }),
      /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "Shown separately: homework is read from a photo, not rated by you." }),
      d.homework.map((h, i) => /* @__PURE__ */ jsxs("div", { className: "hc-progress-log hc-small", children: [
        /* @__PURE__ */ jsx("span", { className: "hc-muted", children: h.label }),
        /* @__PURE__ */ jsxs("span", { children: [
          h.lesson || "Homework",
          " \xB7 ",
          h.items,
          " problems read \xB7 ",
          h.slips,
          " to check"
        ] })
      ] }, i))
    ] })
  ] }) });
}
function HistoryView({ ctx, childId, open }) {
  const q = useData(ctx, `/children/${e(childId)}/history`);
  const icon = { teacher: "From the teacher", homework: "Homework photo", practice: "Practice sheet" };
  return /* @__PURE__ */ jsx(State, { q, children: (d) => /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsxs("h2", { children: [
        d.child.name,
        "'s history"
      ] }),
      /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "Teacher notes, homework photos and practice, newest first." })
    ] }),
    d.events.length ? /* @__PURE__ */ jsx("div", { children: d.events.map((ev, i) => /* @__PURE__ */ jsxs("div", { className: "hc-event", children: [
      /* @__PURE__ */ jsx("span", { className: "hc-small hc-muted", children: ev.label }),
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: icon[ev.type] }),
        /* @__PURE__ */ jsx("strong", { children: ev.title }),
        /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: ev.detail }),
        ev.type === "practice" && ev.steered_by && /* @__PURE__ */ jsx("span", { className: "hc-pill", children: ev.steered_by === "homework photo" ? "Followed a homework photo" : ev.steered_by === "grade default" ? "Grade default" : `Class \xB7 ${ev.class_unit || "current unit"}` })
      ] }),
      /* @__PURE__ */ jsx("div", { children: ev.type === "homework" ? /* @__PURE__ */ jsx(Button, { size: "sm", variant: "outline", onClick: () => open("observation", { index: ev.index }), children: "See what was read" }) : ev.type === "practice" ? /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
        /* @__PURE__ */ jsx(PrintButton, { ctx, date: ev.date, childId, size: "sm", variant: "outline", children: "Print" }),
        /* @__PURE__ */ jsx(Button, { size: "sm", variant: "ghost", onClick: () => open("packet", { date: ev.date }), children: ev.rated ? "Review" : "Rate" })
      ] }) : null })
    ] }, i)) }) : /* @__PURE__ */ jsx(Empty, { title: "Nothing yet", children: "Add a homework photo to get started." })
  ] }) });
}
var STATUS_LABEL = { correct: "Correct", incorrect: "Incorrect", slip: "Small slip", checking_target: "Worth checking", beyond_grade: "Beyond grade", unattempted: "Not attempted", not_assigned: "Not assigned", needs_recheck: "Unclear \u2014 check" };
function Readback({ ctx, childId, index }) {
  const q = useData(ctx, `/children/${e(childId)}/observations/${index}`);
  return /* @__PURE__ */ jsx(State, { q, children: (d) => /* @__PURE__ */ jsx(ReadbackBody, { ctx, childId, d }, d.index) });
}
function ReadbackBody({ ctx, childId, d }) {
  const [edit, setEdit] = useState(null), m = useWrite(ctx, () => setEdit(null));
  const unsure = d.items.filter((i) => i.status === "needs_recheck" || i.confidence != null && i.confidence < 0.7 && !i.corrected).length;
  return /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsxs("div", { className: "hc-eyebrow", children: [
        "Homework read-back \xB7 ",
        d.label
      ] }),
      /* @__PURE__ */ jsx("h2", { children: d.lesson || "Homework photo" }),
      /* @__PURE__ */ jsxs("p", { className: "hc-small hc-muted", children: [
        "Check what Hermes read before it steers practice. ",
        !d.items.length ? "No problems could be read. Add a clearer photo before making practice." : unsure ? `${unsure} unclear ${unsure === 1 ? "reading" : "readings"} to confirm.` : "Every reading looks confident."
      ] })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "hc-split", children: [
      /* @__PURE__ */ jsx("div", { className: "hc-photo-wrap", children: d.photo ? /* @__PURE__ */ jsx("img", { className: "hc-photo", src: d.photo, alt: "Homework photo" }) : /* @__PURE__ */ jsx(Empty, { title: "Photo not available", children: "The reading is saved, but the original photo is not available on this gateway." }) }),
      /* @__PURE__ */ jsxs("section", { className: "hc-card", children: [
        /* @__PURE__ */ jsx(Notice, { error: m.error }),
        d.items.map((it) => {
          const low = it.status === "needs_recheck" || it.confidence != null && it.confidence < 0.7;
          return /* @__PURE__ */ jsxs("div", { className: "hc-read-row" + (low && !it.corrected ? " uncertain" : ""), children: [
            /* @__PURE__ */ jsxs("div", { className: "hc-row hc-between", children: [
              /* @__PURE__ */ jsxs("strong", { children: [
                it.n + 1,
                ". ",
                it.prompt
              ] }),
              /* @__PURE__ */ jsx("span", { className: "hc-pill", children: it.corrected ? "Corrected by you" : STATUS_LABEL[it.status] || it.status })
            ] }),
            /* @__PURE__ */ jsxs("p", { className: "hc-small", children: [
              "Answer written: ",
              /* @__PURE__ */ jsx("strong", { children: it.child_answer ?? "\u2014" }),
              " \xB7 Expected: ",
              /* @__PURE__ */ jsx("strong", { children: it.expected_answer ?? "\u2014" }),
              it.confidence != null && /* @__PURE__ */ jsxs("span", { className: "hc-muted", children: [
                " \xB7 ",
                Math.round(it.confidence * 100),
                "% sure"
              ] })
            ] }),
            edit?.n === it.n ? /* @__PURE__ */ jsxs("form", { className: "hc-form-grid", onSubmit: (ev) => {
              ev.preventDefault();
              m.mutate({ path: `/children/${e(childId)}/observations/${d.index}/items/${it.n}`, body: { fields: { status: edit.status, child_answer: edit.child_answer, expected_answer: edit.expected_answer } } });
            }, children: [
              /* @__PURE__ */ jsx(Field, { label: "Answer written", children: /* @__PURE__ */ jsx(Input, { value: edit.child_answer || "", onChange: (ev) => setEdit({ ...edit, child_answer: ev.target.value }) }) }),
              /* @__PURE__ */ jsx(Field, { label: "Expected answer", children: /* @__PURE__ */ jsx(Input, { value: edit.expected_answer || "", onChange: (ev) => setEdit({ ...edit, expected_answer: ev.target.value }) }) }),
              /* @__PURE__ */ jsx(Field, { label: "Result", wide: true, children: /* @__PURE__ */ jsx("select", { className: "hc-select", value: edit.status, onChange: (ev) => setEdit({ ...edit, status: ev.target.value }), children: Object.entries(STATUS_LABEL).map(([k, v]) => /* @__PURE__ */ jsx("option", { value: k, children: v }, k)) }) }),
              /* @__PURE__ */ jsxs("div", { className: "hc-row wide", children: [
                /* @__PURE__ */ jsx(Button, { type: "submit", size: "sm", disabled: m.isPending, children: "Save correction" }),
                /* @__PURE__ */ jsx(Button, { type: "button", size: "sm", variant: "ghost", onClick: () => setEdit(null), children: "Cancel" })
              ] })
            ] }) : /* @__PURE__ */ jsx("button", { type: "button", className: "hc-inline-link hc-small", onClick: () => setEdit({ n: it.n, status: it.status, child_answer: it.child_answer, expected_answer: it.expected_answer }), children: "Fix this reading" })
          ] }, it.n);
        })
      ] })
    ] })
  ] });
}
function runJob(ctx, path, body, onTick, expectedScope) {
  return runJobScoped({ request: (p, o) => request(ctx, p, o), scopeNow, expectedScope, path, body, onTick });
}
function UploadView({ ctx, child, teacher = false, initialFile = null, onDone }) {
  const qc = useQueryClient(), scope = useScope(), input = useRef(null), [file, setFile] = useState(initialFile), [note, setNote] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState(null), [drag, setDrag] = useState(false), [review, setReview] = useState(null), [tick, setTick] = useState(0);
  const accept = teacher ? ".png,.jpg,.jpeg,.webp,.pdf,.txt,.md" : ".png,.jpg,.jpeg,.webp";
  const go = async () => {
    setBusy(true);
    setErr(null);
    try {
      const prep = await prepareUpload(file, { teacher });
      const data_b64 = prep.data_b64, filename = prep.filename;
      if (teacher) {
        const r = await runJob(ctx, `/children/${e(child.id)}/materials/read`, { filename, data_b64, note }, setTick, scope);
        setReview(r);
      } else {
        const r = await runJob(ctx, "/intake64", { child_id: child.id, filename, data_b64, note }, setTick, scope);
        qc.invalidateQueries({ queryKey: [ID, scope] });
        host.notify({ kind: "success", message: `Homework read for ${child.name}. Check the reading.` });
        onDone({ index: -1, ...r });
      }
    } catch (x) {
      setErr(x);
    } finally {
      setBusy(false);
    }
  };
  if (review) return /* @__PURE__ */ jsx(MaterialReview, { ctx, child, review, onDone: () => {
    qc.invalidateQueries({ queryKey: [ID, scope] });
    onDone(null);
  } });
  return /* @__PURE__ */ jsxs("div", { className: "hc-card hc-stack", style: { maxWidth: 720 }, children: [
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: teacher ? "From the teacher" : "Homework photo" }),
      /* @__PURE__ */ jsx("h2", { children: teacher ? `Add something from ${child.name}'s teacher` : `Add ${child.name}'s homework` }),
      /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: teacher ? "A newsletter, unit letter or study guide. You review any plan change before it is saved." : "A clear photo of finished homework. You can check and fix what was read." })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "hc-drop" + (drag ? " dragging" : ""), onDragOver: (ev) => {
      ev.preventDefault();
      setDrag(true);
    }, onDragLeave: () => setDrag(false), onDrop: (ev) => {
      ev.preventDefault();
      setDrag(false);
      if (ev.dataTransfer.files[0]) setFile(ev.dataTransfer.files[0]);
    }, children: [
      /* @__PURE__ */ jsx("input", { ref: input, type: "file", accept, style: { display: "none" }, onChange: (ev) => setFile(ev.target.files?.[0] || null) }),
      /* @__PURE__ */ jsx("strong", { children: file ? file.name : "Drop a file here" }),
      /* @__PURE__ */ jsx(Button, { variant: "secondary", size: "sm", onClick: () => input.current?.click(), children: file ? "Choose a different file" : "Choose file" })
    ] }),
    /* @__PURE__ */ jsx(Field, { label: "Note (optional)", children: /* @__PURE__ */ jsx(Textarea, { rows: 2, maxLength: 500, value: note, onChange: (ev) => setNote(ev.target.value), placeholder: teacher ? "e.g. came home Monday" : "e.g. Lesson 3-2, she rushed the last row" }) }),
    /* @__PURE__ */ jsx("p", { className: "hc-small hc-muted", children: "The file goes to your configured model provider to be read. Copies stay in this profile's Homework Coach folder." }),
    /* @__PURE__ */ jsx(Notice, { error: err }),
    /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
      /* @__PURE__ */ jsx(Button, { disabled: !file || busy, onClick: go, children: busy ? `Reading\u2026 ${tick > 3 ? "(careful reads take a minute)" : ""}` : teacher ? "Read it" : "Read homework" }),
      /* @__PURE__ */ jsx(Button, { variant: "ghost", disabled: busy, onClick: () => onDone(null), children: "Cancel" })
    ] })
  ] });
}
function MaterialReview({ ctx, child, review, onDone }) {
  const [mat, setMat] = useState(review.material), [prop, setProp] = useState(review.proposal), [dirty, setDirty] = useState(false), [err, setErr] = useState(null), [busy, setBusy] = useState(false), [done, setDone] = useState(null);
  const set = (k, v) => {
    setMat((x) => ({ ...x, [k]: v }));
    setDirty(true);
  };
  const recheck = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await request(ctx, `/children/${e(child.id)}/materials/propose`, { method: "POST", body: { material: mat } });
      setProp(r.proposal);
      setDirty(false);
    } catch (x) {
      setErr(x);
    } finally {
      setBusy(false);
    }
  };
  const apply = async (shift) => {
    setBusy(true);
    setErr(null);
    try {
      const r = await request(ctx, `/children/${e(child.id)}/materials/apply`, { method: "POST", body: { token: review.token, material: mat, apply_shift: shift, expected: prop ? { unit_index: prop.unit_index, delta_days: prop.delta_days } : null } });
      setDone(r);
    } catch (x) {
      setErr(x);
    } finally {
      setBusy(false);
    }
  };
  if (done) return /* @__PURE__ */ jsxs("div", { className: "hc-card hc-stack", children: [
    /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: "Saved" }),
    /* @__PURE__ */ jsxs("h2", { children: [
      done.material?.title || "Teacher material",
      " is in ",
      child.name,
      "'s class plan."
    ] }),
    done.shift ? /* @__PURE__ */ jsxs("div", { className: "hc-callout", children: [
      "Moved ",
      done.shift.moved.length,
      " ",
      done.shift.moved.length === 1 ? "unit" : "units",
      " to match the teacher. You can undo this from the Class plan."
    ] }) : /* @__PURE__ */ jsx("p", { className: "hc-muted", children: "The plan dates were left as they were." }),
    /* @__PURE__ */ jsx(Button, { onClick: onDone, children: "See the class plan" })
  ] });
  return /* @__PURE__ */ jsxs("div", { className: "hc-stack", children: [
    /* @__PURE__ */ jsxs("div", { children: [
      /* @__PURE__ */ jsx("div", { className: "hc-eyebrow", children: "Review before saving" }),
      /* @__PURE__ */ jsx("h2", { children: "Here's what the teacher's note says" })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "hc-split", children: [
      review.preview ? /* @__PURE__ */ jsx("div", { className: "hc-photo-wrap", children: /* @__PURE__ */ jsx("img", { className: "hc-photo", src: review.preview, alt: "Teacher material" }) }) : /* @__PURE__ */ jsx("div", { className: "hc-card hc-muted", children: "Preview not available for this file type." }),
      /* @__PURE__ */ jsxs("section", { className: "hc-card hc-stack", children: [
        /* @__PURE__ */ jsxs("div", { className: "hc-form-grid", children: [
          /* @__PURE__ */ jsx(Field, { label: "Title", wide: true, children: /* @__PURE__ */ jsx(Input, { value: mat.title || "", onChange: (ev) => set("title", ev.target.value) }) }),
          /* @__PURE__ */ jsx(Field, { label: "Dated", children: /* @__PURE__ */ jsx(Input, { type: "date", value: mat.date || "", onChange: (ev) => set("date", ev.target.value) }) }),
          /* @__PURE__ */ jsx(Field, { label: "Unit named", children: /* @__PURE__ */ jsx(Input, { value: mat.unit_title || "", onChange: (ev) => set("unit_title", ev.target.value) }) }),
          /* @__PURE__ */ jsx(Field, { label: "Unit ends / quiz", children: /* @__PURE__ */ jsx(Input, { type: "date", value: mat.unit_end || "", onChange: (ev) => set("unit_end", ev.target.value) }) }),
          /* @__PURE__ */ jsx(Field, { label: "Summary", wide: true, children: /* @__PURE__ */ jsx(Textarea, { rows: 2, value: mat.summary || "", onChange: (ev) => set("summary", ev.target.value) }) })
        ] }),
        mat.goals?.length > 0 && /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h3", { className: "hc-small", children: "Goals it lists" }),
          /* @__PURE__ */ jsx("ul", { className: "hc-list hc-small", children: mat.goals.map((g, i) => /* @__PURE__ */ jsx("li", { children: g }, i)) })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "hc-callout", children: dirty ? /* @__PURE__ */ jsxs("span", { children: [
          "You changed the details. ",
          /* @__PURE__ */ jsx("button", { className: "hc-inline-link", onClick: recheck, disabled: busy, children: "Recheck the plan" }),
          " before applying."
        ] }) : prop && prop.delta_days ? /* @__PURE__ */ jsxs(Fragment, { children: [
          /* @__PURE__ */ jsx("strong", { children: "Proposed change" }),
          /* @__PURE__ */ jsx("p", { children: prop.message }),
          /* @__PURE__ */ jsxs("p", { className: "hc-small", children: [
            prop.unit_title,
            ": ",
            prop.from.label,
            " \u2192 ",
            prop.to.label
          ] })
        ] }) : prop ? /* @__PURE__ */ jsx("p", { children: prop.message }) : /* @__PURE__ */ jsx("p", { children: "No date change to propose. The note will be saved with the plan as is." }) }),
        /* @__PURE__ */ jsx(Notice, { error: err }),
        /* @__PURE__ */ jsxs("div", { className: "hc-row", children: [
          prop?.delta_days ? /* @__PURE__ */ jsx(Button, { disabled: busy || dirty, onClick: () => apply(true), children: "Apply date change" }) : null,
          /* @__PURE__ */ jsx(Button, { variant: prop?.delta_days ? "outline" : "default", disabled: busy || dirty, onClick: () => apply(false), children: prop?.delta_days ? "Save note only" : "Save note" }),
          /* @__PURE__ */ jsx(Button, { variant: "ghost", disabled: busy, onClick: onDone, children: "Discard" })
        ] })
      ] })
    ] })
  ] });
}
var plugin_default = { id: ID, name: "Homework Coach", register(ctx) {
  const cs = [{ id: "page", area: sdk.ROUTES_AREA, data: { path: ROUTE }, render: () => /* @__PURE__ */ jsx(HomeworkPage, { ctx }) }, { id: "nav", area: sdk.SIDEBAR_NAV_AREA, data: { path: ROUTE, label: "Homework", codicon: "mortar-board" } }, { id: "open", area: sdk.PALETTE_AREA, data: { id: "homework-coach.open", label: "Homework Coach: Open workspace", keywords: ["homework", "family", "school", "packet"], run: () => goto("today") } }];
  if (sdk.STATUSBAR_AREAS?.right) cs.push({ id: "pending", area: sdk.STATUSBAR_AREAS.right, data: { id: "homework-coach.pending", render: () => /* @__PURE__ */ jsx(PendingStatus, { ctx }) }, render: () => /* @__PURE__ */ jsx(PendingStatus, { ctx }) });
  if (sdk.TRANSCRIPT_DIRECTIVE_AREA) cs.push({ id: "packet-card", area: sdk.TRANSCRIPT_DIRECTIVE_AREA, data: { name: "homework-packet", render: (p) => /* @__PURE__ */ jsx(ChatPacket, { ctx, attrs: p.attrs, sessionId: p.sessionId }) } });
  if (sdk.TOOL_MEDIA_RENDERER_AREA) cs.push({ id: "packet-media", area: sdk.TOOL_MEDIA_RENDERER_AREA, data: { tools: ["homework_coach_generate_packet"], render: (p) => /* @__PURE__ */ jsx(PacketMedia, { ctx, ...p }) } });
  ctx.registerMany(cs);
  ctx.registerSettingsPage?.({ id: "settings", title: "Homework Coach", icon: "mortar-board", render: () => /* @__PURE__ */ jsx(FamilyPage, { ctx }), children: [{ id: "schedule", title: "Practice schedule", render: () => /* @__PURE__ */ jsx(FamilyPage, { ctx, scheduleOnly: true }) }] });
} };
export {
  ChatPacket,
  ChildForm,
  ClassPlan,
  FamilyPage,
  HistoryView,
  HomeworkPage,
  MaterialReview,
  PacketPreview,
  ProgressView,
  RateDesk,
  Readback,
  TodayView,
  UploadView,
  canFollowSource,
  plugin_default as default,
  errorText,
  levelBar,
  mimeFor,
  navigationView,
  packetReference,
  ratingKey,
  ratingsPayload
};
