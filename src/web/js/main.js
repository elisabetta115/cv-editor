// The start of the editor, and the keys and clicks that concern the whole page.
import "./state.js";
import "./icons.js";
import "./util.js";
import "./changes.js";
import "./sync.js";
import "./fields.js";
import "./cards.js";
import "./nav.js";
import "./design.js";
import "./links.js";
import "./names.js";
import "./find.js";
import "./languages.js";
import "./photo.js";
import "./preview.js";
import "./cvs.js";
import { $, S, setContactKinds } from "./state.js";
import { api, fill, h, L, toast } from "./util.js";
import { sync, tagSections } from "./changes.js";
import { snapshot, unsaved } from "./sync.js";
import { card, closeMenu, wrap } from "./fields.js";
import { render } from "./nav.js";
import { renderStyles, updateBar } from "./design.js";
import { linkDialog } from "./links.js";
import { closeFind, findOpen, findStep, openFind } from "./find.js";
import { renderLanguages } from "./languages.js";
import { renderPhotos } from "./photo.js";
import { forgetPreview, updatePreview } from "./preview.js";
import { createCv, importCv, importInput, lastOpened, remember, save } from "./cvs.js";

// ---------------------------------------------------------------- start
// no CV yet: create one, import a file or try the example
function welcome() {
  closeFind(false);
  document.body.classList.add("empty");
  document.title = "CV Editor";
  const first = h("input", { class: "inp", placeholder: "First name" });
  const last = h("input", { class: "inp", placeholder: "Last name" });
  const language = h("select", { class: "inp" }, S.templates.map(t => h("option", { value: t.code }, t.name)));
  language.value = S.templates.some(t => t.code === "en") ? "en" : S.templates[0]?.code;
  fill($("#form"), h("div", { class: "welcome" },
    h("h1", {}, "Welcome to CV Editor"),
    h("p", {}, `Write your CV once and get it as PDF in several languages, ${S.styles.length || 50} styles and ${Object.keys(S.colors).length || 16} colours. Everything stays on this computer.`),
    card(h("span", { class: "fixed-title" }, "Start your CV"), [
      h("div", { class: "grid" }, first, last),
      wrap("Language of the CV", language, { hint: "You can add more languages later." }),
      h("button", { type: "button", class: "btn primary", style: "justify-self: start",
                    onclick: () => createCv(first.value, last.value, language.value) }, "Create my CV")]),
    card(h("span", { class: "fixed-title" }, "Already have a CV file?"), [
      h("p", { class: "hint", style: "margin: 0" }, "A .zip file exported from this editor, yours or someone else's, or a .zip of the cvs folder. ",
        "You can also drag it onto this window."),
      h("label", { class: "btn", style: "justify-self: start" }, "Import a CV (.zip)…", importInput())]),
    card(h("span", { class: "fixed-title" }, "Just looking?"), [
      h("p", { class: "hint", style: "margin: 0" }, "Open the CV of a fictional person to see what the editor can do."),
      h("button", { type: "button", class: "btn", style: "justify-self: start", onclick: async () => {
        try {
          const data = await api("/api/example");
          await importCv(mode => api("/api/import", { data, mode }), "copy");
        } catch (e) { toast(e.message, { error: true }); }
      } }, "Try the example")])));
  $("#cv").srcdoc = `<body style="margin:0;background:#e4e7ec;font:15px system-ui,sans-serif;display:grid;place-items:center;height:100vh">
    <div style="width:60%;aspect-ratio:210/297;background:#fff;border-radius:4px;box-shadow:0 10px 30px rgba(16,24,40,.15);display:grid;place-items:center;color:#98a1ad">
    Your CV will appear here</div></body>`;
  forgetPreview();
}
async function start(name) {
  try {
    const cvs = await api("/api/cvs");
    S.profiles = cvs.profiles;
    $("#demo-badge").hidden = !cvs.demo;
    if (!S.profiles.length) {
      if (!S.templates.length) S.templates = (await api("/api/templates")).templates;
      return welcome();
    }
    document.body.classList.remove("empty");
    name = [name, lastOpened()].find(n => n && S.profiles.some(x => x.name === n)) || S.profiles[0].name;
    const r = await api("/api/data?cv=" + encodeURIComponent(name));
    Object.assign(S, { profile: r.profile, languages: {}, changed: {}, photosChanged: false, settingsChanged: false,
                       languagesChanged: false, deleted: new Set() });
    S.version++;
    forgetPreview();
    remember(r.profile);
    document.title = `${r.profile} · CV Editor`;
    $("#cv-name").textContent = r.profile;
    $("#cv-avatar").textContent = r.profile.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join("");
    S.section = "header"; S.sectionPos = 0; S.rendered = null;
    S.fixedSections = r.fixed_sections || [];
    for (const [l, x] of Object.entries(r.languages)) {
      const sections = x.data.sections || [];
      S.languages[l] = { data: x.data, name: x.name,
        order: x.order.map(o => (typeof o === "number" ? { section: sections[o] } : { fixed: o.builtin, hidden: !!o.hidden, side: !!o.side })) };
      sync(l);
    }
    S.photoList = r.photos; S.signature = r.signature;
    S.photo = r.photos[0]?.name ?? null;
    S.styles = r.styles; S.styleGroups = r.style_groups; S.colors = r.colors; S.settings = r.settings; S.templates = r.templates;
    S.canZoom = r.can_zoom; S.icons = r.icons; setContactKinds(r.contact_groups);
    if (!S.styles.some(x => x.id === S.style)) S.style = S.styles[0].id;
    S.sideSuggested = r.sidebar_suggested; S.lastSide = null;
    tagSections();
    S.base = {};
    for (const l of Object.keys(S.languages)) { sync(l); snapshot(l); }
    S.saved = new Set(Object.keys(r.languages));
    if (!S.languages[S.language]) S.language = Object.keys(S.languages)[0];
    renderStyles();
    renderLanguages();
    updateBar(); renderPhotos(); render(); updatePreview(true);
  } catch (e) {
    fill($("#form"), h("p", { class: "note" }, "Could not read the CV: " + e.message));
  }
}

// clicks inside a panel stay in the panel (its content may be redrawn while clicking)
for (const p of document.querySelectorAll(".panel")) p.addEventListener("click", e => { e.stopPropagation(); closeMenu(); });
document.addEventListener("click", e => {
  let closed = false;
  for (const p of document.querySelectorAll(".panel")) if (!p.hidden && !p.contains(e.target)) { p.hidden = true; closed = true; }
  if (!$("#menu")?.contains(e.target)) closeMenu();
  if (closed && S.settings) updateBar();
});
document.addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); } });

document.addEventListener("keydown", e => {
  const key = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (key === "f" || key === "h")) {
    if (document.body.classList.contains("empty") || !L() || document.querySelector("dialog[open]")) return;
    e.preventDefault(); openFind(key === "h");
  } else if (e.key === "F3" && findOpen()) { e.preventDefault(); findStep(e.shiftKey ? -1 : 1); }
});
// Ctrl+K in a text box that can hold links: the selected words become a link
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "k" && e.target.dataset?.links != null) { e.preventDefault(); linkDialog(e.target); }
});
window.addEventListener("beforeunload", e => { if (unsaved()) { e.preventDefault(); e.returnValue = ""; } });
start();

export {
  start
};
