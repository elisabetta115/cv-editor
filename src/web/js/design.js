// The design bar above the preview: style (with its picker), colour and sidebar.
import { $, S } from "./state.js";
import { icon } from "./icons.js";
import { api, fill, h, placeUnder, togglePanel } from "./util.js";
import { unsaved } from "./sync.js";
import { hasSidebar, setSidebar } from "./cards.js";
import { render } from "./nav.js";
import { updatePreview, viewRequest } from "./preview.js";

// ---------------------------------------------------------------- bar, photos, PDFs
function updateBar() {
  for (const b of document.querySelectorAll("#languages button[data-l]")) {
    b.setAttribute("aria-pressed", String(b.dataset.l === S.language));
    b.classList.toggle("unsaved", !!S.changed[b.dataset.l]);
    b.title = S.changed[b.dataset.l] ? "Changes not saved yet" : "";
  }
  $("#style-name").textContent = S.styles.find(x => x.id === S.style)?.name || S.style;
  for (const b of document.querySelectorAll("#view-mode button")) b.setAttribute("aria-pressed", String(b.dataset.v === S.view));
  const full = !!document.fullscreenElement, fb = $("#btn-fullscreen");
  fill(fb, icon(full ? "minimize" : "maximize"));
  fb.title = full ? "Leave full screen" : "Show the pages on the whole screen";
  if (S.settings) {
    $("#btn-sidebar").setAttribute("aria-pressed", String(hasSidebar()));
    const color = S.settings.styles[S.style].color, c = S.colors[color];
    if (c) $("#color-dot").style.background = `linear-gradient(135deg, ${c.dark} 0 50%, ${c.light} 50% 100%)`;
    for (const b of document.querySelectorAll("#colors button")) b.setAttribute("aria-pressed", String(b.dataset.c === color));
  }
  for (const [id, panel] of [["btn-color", "color-panel"], ["btn-photo", "photo-panel"], ["btn-frame", "frame-panel"], ["style-btn", "style-panel"], ["btn-cv", "cv-panel"]])
    $("#" + id).setAttribute("aria-expanded", String(!$("#" + panel).hidden));
  const save = $("#btn-save");
  save.classList.toggle("primary", unsaved());
  fill(save, unsaved() ? "Save" : [icon("check"), "Saved"]);
}
// ---------------------------------------------------------------- style picker
// Search by name, group, tags or description; every style shows a thumbnail of this CV, drawn when it
// scrolls into view. Click a style to choose it: next to the preview the panel stays open, to compare.
const thumbs = new Map();                 // style -> { key, doc }: thumbnails already drawn for this content
let styleFilter = { text: "", group: "" }, thumbObserver = null;
const fold = s => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
// a word of the text starts with w ("photo" finds "round photo"; "serif" does not find "sans-serif")
const wordStart = (text, w) => text.startsWith(w) || text.includes(" " + w);
function styleScore(x, words) {           // 0 = no match; higher = better
  const name = fold(x.name), tags = x.tags.map(fold), group = fold(S.styleGroups[x.group] || ""), text = fold(x.description);
  let score = 1;
  for (const w of words) {
    if (name.startsWith(w)) score += 8;
    else if (wordStart(name, w)) score += 5;
    else if (tags.some(t => t.startsWith(w))) score += 4;
    else if (tags.some(t => wordStart(t, w)) || wordStart(group, w)) score += 3;
    else if (wordStart(text, w)) score += 1;
    else return 0;
  }
  return score;
}
function filteredStyles() {
  const words = fold(styleFilter.text).split(/[\s,]+/).filter(Boolean);
  return S.styles.filter(x => !styleFilter.group || x.group === styleFilter.group)
    .map(x => ({ x, score: styleScore(x, words) })).filter(r => r.score)
    .sort((a, b) => b.score - a.score).map(r => r.x);  // stable: same score keeps the group order
}
// side by side with the preview: the panel covers the form, so the preview stays visible
const besidePreview = () => $("#preview").getBoundingClientRect().left > 420;
function placeStylePanel(p) {
  const left = $("#preview").getBoundingClientRect().left;
  if (besidePreview()) {
    const w = Math.min(640, left - 24);
    Object.assign(p.style, { width: w + "px", left: left - w - 10 + "px", top: "66px" });
  } else Object.assign(p.style, { width: "calc(100vw - 28px)", left: "14px", top: $("#style-btn").getBoundingClientRect().bottom + 6 + "px" });
}
function renderStylePanel() {
  const p = $("#style-panel");
  placeStylePanel(p);
  const search = h("input", { class: "inp", type: "search", id: "style-search", value: styleFilter.text, autocomplete: "off",
    placeholder: `Search ${S.styles.length} styles: serif, dark, photo, sidebar, timeline…`, "aria-label": "Search styles",
    oninput: e => { styleFilter.text = e.target.value; renderStyleGrid(); }, onkeydown: styleKeys });
  const count = id => S.styles.filter(x => !id || x.group === id).length;
  fill(p,
    h("div", { class: "style-search" }, search,
      h("div", { class: "style-groups", role: "group", "aria-label": "Groups" },
        [["", "All"], ...Object.entries(S.styleGroups)].map(([id, name]) => h("button", {
          type: "button", "aria-pressed": String(styleFilter.group === id),
          onclick: () => { styleFilter.group = id; renderStylePanel(); } }, `${name} · ${count(id)}`)))),
    h("div", { class: "style-grid", id: "style-grid" }),
    h("div", { class: "style-foot" }, h("span", { id: "style-count" }),
      h("span", {}, "Arrows: browse · Enter: choose · Esc: close")));
  renderStyleGrid();
  search.focus();
}
function renderStyleGrid() {
  const grid = $("#style-grid"), list = filteredStyles();
  thumbObserver?.disconnect();
  thumbObserver = new IntersectionObserver(seen => {
    for (const e of seen) if (e.isIntersecting) { thumbObserver.unobserve(e.target); drawThumb(e.target); }
  }, { root: grid, rootMargin: "400px 0px" });
  $("#style-count").textContent = list.length === S.styles.length ? `${list.length} styles` : `${list.length} of ${S.styles.length} styles`;
  fill(grid, list.length ? list.map(x => {
    const thumb = h("div", { class: "style-thumb", "data-style": x.id, "aria-hidden": "true" });
    thumbObserver.observe(thumb);
    return h("div", { class: "style-card" + (x.id === S.style ? " current" : "") }, thumb,
      h("button", { type: "button", class: "pick", "data-style": x.id, title: x.description, "aria-pressed": String(x.id === S.style),
                    onclick: () => chooseStyle(x.id, !besidePreview()), onkeydown: styleKeys },
        h("span", { class: "style-name" }, x.name), h("span", { class: "style-tags" }, x.tags.slice(0, 3).join(" · "))));
  }) : h("p", { class: "hint", style: "grid-column: 1 / -1; margin: 6px 0" }, `No style matches “${styleFilter.text}”. `,
         h("button", { type: "button", class: "link", onclick: () => { styleFilter = { text: "", group: "" }; renderStylePanel(); } }, "Show them all")));
}
// the CV in one style, scaled down; the same content and the same colour as that style would use
async function drawThumb(box) {
  const id = box.dataset.style;
  const req = { ...viewRequest(), style: id, color: S.settings.styles[id]?.color };
  const key = JSON.stringify(req);
  if (thumbs.get(id)?.key !== key) {
    try { thumbs.set(id, { key, doc: (await api("/api/preview", req)).document }); } catch { return; }
  }
  if (!box.isConnected) return;
  const zoom = box.clientWidth / 794;  // 210 mm
  const frame = h("iframe", { sandbox: "allow-same-origin", tabindex: "-1", title: "" });
  frame.srcdoc = thumbs.get(id).doc.replace("</head>",
    `<style>html{zoom:${zoom};overflow:hidden}body{padding:0!important;margin:0}.page{margin:0!important;box-shadow:none!important}</style></head>`);
  box.append(frame);
}
function chooseStyle(id, close) {
  if (S.style !== id) { S.style = id; updateBar(); render(); updatePreview(true); }
  for (const b of document.querySelectorAll("#style-grid .pick")) {
    b.setAttribute("aria-pressed", String(b.dataset.style === id));
    b.parentElement.classList.toggle("current", b.dataset.style === id);
  }
  if (close) { $("#style-panel").hidden = true; $("#style-btn").focus(); }
}
// arrows move between the styles (and show each in the preview), Enter chooses, Esc closes
function styleKeys(e) {
  const picks = [...document.querySelectorAll("#style-grid .pick")];
  const i = picks.indexOf(e.target), columns = getComputedStyle($("#style-grid")).gridTemplateColumns.split(" ").length;
  const go = j => { const b = picks[Math.max(0, Math.min(picks.length - 1, j))]; if (b) { b.focus(); b.scrollIntoView({ block: "nearest" }); chooseStyle(b.dataset.style, false); } };
  if (e.key === "Escape") { e.preventDefault(); $("#style-panel").hidden = true; $("#style-btn").focus(); }
  else if (i < 0) {  // in the search field
    if (e.key === "ArrowDown") { e.preventDefault(); go(0); }
    else if (e.key === "Enter" && picks.length) { e.preventDefault(); chooseStyle(picks[0].dataset.style, true); }
  }
  else if (e.key === "ArrowRight") { e.preventDefault(); go(i + 1); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); go(i - 1); }
  else if (e.key === "ArrowDown") { e.preventDefault(); go(i + columns); }
  else if (e.key === "ArrowUp") { e.preventDefault(); if (i < columns) $("#style-search").focus(); else go(i - columns); }
  else if (e.key === "Enter") { e.preventDefault(); chooseStyle(e.target.dataset.style, true); }
}

function renderStyles() {
  fill($("#colors"), Object.entries(S.colors).map(([id, c]) => h("button", {
    type: "button", class: "swatch", "data-c": id, title: c.name, "aria-label": "Colour " + c.name,
    onclick: () => { S.settings.styles[S.style].color = id; S.settingsChanged = true; updateBar(); updatePreview(true); } },
    h("i", { style: `background: linear-gradient(135deg, ${c.dark} 0 50%, ${c.light} 50% 100%)` }), c.name)));
}
const colorPanel = () => togglePanel("color-panel", () => placeUnder($("#color-panel"), $("#btn-color")));

$("#btn-sidebar").addEventListener("click", () => setSidebar(!hasSidebar()));
$("#btn-color").addEventListener("click", e => { e.stopPropagation(); colorPanel(); });

$("#style-btn").addEventListener("click", e => { e.stopPropagation(); togglePanel("style-panel", () => renderStylePanel()); });

export {
  renderStyles, updateBar
};
