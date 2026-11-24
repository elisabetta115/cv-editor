// The preview: live while typing, or the real pages (PDF); downloading the PDF; full screen.
import { $, S, TOKEN } from "./state.js";
import { api, checkAllowed, h, L, status, toast } from "./util.js";
import { sync } from "./changes.js";
import { updateBar } from "./design.js";
import { watchDrops } from "./cvs.js";

// ---------------------------------------------------------------- PDF of what is on screen, pages, full screen
function viewRequest() {
  sync(S.language);
  const st = S.settings?.styles[S.style] || {};
  return { profile: S.profile, language: S.language, style: S.style, color: st.color, adjust: st.adjust || null, photo: S.photo,
           frame: S.photo ? S.settings?.photos?.[S.photo] || null : null, data: L().data };
}
async function fetchPdf(inline) {
  const r = await fetch("/api/pdf", { method: "POST", headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
                                      body: JSON.stringify({ ...viewRequest(), inline }) });
  checkAllowed(r);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `Error ${r.status}`);
  const name = decodeURIComponent(/filename\*=UTF-8''([^;]+)/.exec(r.headers.get("Content-Disposition") || "")?.[1] || "CV.pdf");
  return { name, blob: await r.blob() };
}
async function downloadPdf() {
  const b = $("#btn-pdf");
  b.disabled = true; status("Creating the PDF…", "busy");
  try {
    const { name, blob } = await fetchPdf(false);
    const a = h("a", { href: URL.createObjectURL(blob), download: name });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    status(`Downloaded ${name}`, "ok");
  } catch (e) { status("PDF not created", "error"); toast(e.message, { error: true }); }
  finally { b.disabled = false; }
}
let pagesTimer, pagesRequest = 0, pagesUrl = null;
function updatePages(now = false) {
  clearTimeout(pagesTimer);
  pagesTimer = setTimeout(loadPages, now ? 0 : 900);
}
async function loadPages() {
  if (S.view !== "pages") return;
  const n = ++pagesRequest;
  status("Updating the pages…", "busy");
  try {
    const { blob } = await fetchPdf(true);
    if (n !== pagesRequest) return;
    const old = pagesUrl;
    pagesUrl = URL.createObjectURL(blob);
    $("#pages").src = pagesUrl;
    if (old) setTimeout(() => URL.revokeObjectURL(old), 3000);
    status("");
  } catch (e) { status(e.message, "error"); }
}
function setView(v) {
  S.view = v;
  $("#cv").hidden = v !== "live";
  $("#pages").hidden = v !== "pages";
  updateBar();
  if (v === "pages") updatePages(true); else updatePreview(true);
}
let viewBeforeFullscreen = null;
async function toggleFullscreen() {
  if (document.fullscreenElement) return document.exitFullscreen();
  viewBeforeFullscreen = S.view;
  try { await $("#preview").requestFullscreen(); } catch (e) { return toast("Full screen is not available: " + e.message, { error: true }); }
  setView("pages");
}
document.addEventListener("fullscreenchange", () => {
  if (!document.fullscreenElement && viewBeforeFullscreen) { setView(viewBeforeFullscreen); viewBeforeFullscreen = null; }
  updateBar();
});

// ---------------------------------------------------------------- preview
let previewTimer, request = 0, loaded = null, ready = false, pending = null;
// another CV, or the welcome screen: the next preview loads its whole page again
function forgetPreview() { loaded = null; }
function updatePreview(now = false) {
  if (S.view === "pages") return updatePages(now);
  clearTimeout(previewTimer);
  previewTimer = setTimeout(loadPreview, now ? 0 : 250);
}
async function loadPreview() {
  const n = ++request;
  try {
    sync(S.language);
    const req = viewRequest();
    const r = await api("/api/preview", req);
    if (n !== request) return;
    // a new colour, adjustment or sidebar changes the page's stylesheet: the whole page is loaded again
    const frame = $("#cv"), key = [S.profile, S.style, S.language, req.color, JSON.stringify(req.adjust), r.sidebar].join("|");
    if (loaded === key) {
      if (ready) frame.contentDocument.body.innerHTML = r.page; else pending = r.page;
    } else {
      loaded = key; ready = false; pending = null;
      frame.srcdoc = r.document;
    }
  } catch (e) { status(e.message, "error"); }
}
function fitZoom() {
  const frame = $("#cv"), doc = frame.contentDocument;
  if (doc?.documentElement) doc.documentElement.style.zoom = Math.min(1.25, Math.max(0.3, (frame.clientWidth - 24) / 800));
}

$("#cv").addEventListener("load", () => {
  ready = true; fitZoom();
  if ($("#cv").contentDocument) watchDrops($("#cv").contentDocument);  // a .zip dragged in over the preview
  if (pending) { $("#cv").contentDocument.body.innerHTML = pending; pending = null; }
});
new ResizeObserver(fitZoom).observe($("#cv"));

for (const b of document.querySelectorAll("#view-mode button")) b.addEventListener("click", () => setView(b.dataset.v));
$("#btn-fullscreen").addEventListener("click", toggleFullscreen);

$("#btn-pdf").addEventListener("click", downloadPdf);

export {
  forgetPreview, updatePreview, viewRequest
};
