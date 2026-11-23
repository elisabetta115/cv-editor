// The CVs (one per person): opening, creating, duplicating, importing, exporting, deleting, saving.
import { $, S, TOKEN } from "./state.js";
import { icon } from "./icons.js";
import { api, ask, checkAllowed, fill, h, L, status, toast, togglePanel } from "./util.js";
import { removedFixed, sync } from "./changes.js";
import { isObj, languageName, unsaved } from "./sync.js";
import { button, wrap } from "./fields.js";
import { updateBar } from "./design.js";
import { deleteLanguage } from "./languages.js";
import { start } from "./main.js";

// ---------------------------------------------------------------- CVs (one per person)
const LAST_CV = "cv-editor:last";
function remember(name) { try { localStorage.setItem(LAST_CV, name); } catch {} }
function lastOpened() { try { return localStorage.getItem(LAST_CV); } catch { return null; } }
const discardOk = async () => !unsaved() || ask({ title: "Discard your changes?",
  text: ["You have changes in this CV that are not saved yet.", "Press Cancel and then Save to keep them."],
  ok: "Discard them", danger: true });
// The CV menu (the "CV: name ▾" button): click a name to open that CV; below, new, duplicate, import,
// export and delete. Made of ordinary buttons, so it works the same in every browser.
let cvForm = null;  // the small form open in the menu: "new" or "duplicate"
const cvPanel = () => S.profiles.length && togglePanel("cv-panel", () => { cvForm = null; renderCvPanel(); });
const toggleCvForm = (kind, focus) => { cvForm = cvForm === kind ? null : kind; renderCvPanel(); if (cvForm) $(focus)?.select(); };
const MARKS = { "✓": "check", "＋": "plus", "⬆": "upload", "⬇": "download", "🗑": "trash", "⧉": "copy" };
// a name no CV has yet: "Jane Doe (2)", "Jane Doe (3)"...
function freeCvName(base) {
  for (let n = 2; ; n++) if (!S.profiles.some(x => x.name === `${base} (${n})`)) return `${base} (${n})`;
}
// the form to duplicate the CV on screen: the name of the copy, its languages, with or without the photos
function duplicateForm() {
  const name = h("input", { class: "inp", id: "dup-name", value: freeCvName(S.profile), "aria-label": "Name of the copy",
                            onkeydown: e => { if (e.key === "Enter") go(); } });
  const codes = Object.keys(S.languages);
  const langs = codes.map(l => [l, h("input", { type: "checkbox", checked: true })]);
  const photos = h("input", { type: "checkbox", checked: true });
  const go = () => duplicateCv(name.value, langs.filter(([, box]) => box.checked).map(([l]) => l), photos.checked);
  return h("div", { class: "menu-form" },
    wrap("Name of the copy", name, { hint: "Only for you, in this menu: e.g. “" + S.profile + " – Marketing”. The name in the CV stays the same." }),
    codes.length > 1 ? h("div", { class: "dup-langs" }, h("span", { class: "subtitle" }, "Languages:"),
      langs.map(([l, box]) => h("label", { class: "check" }, box, languageName(l)))) : null,
    h("label", { class: "check" }, photos, "include the photos"),
    h("button", { type: "button", class: "btn primary", style: "justify-self: start", onclick: go }, icon("copy"), "Duplicate and open the copy"));
}
// a copy of this CV (as saved: unsaved changes are saved first), opened at once to change it
async function duplicateCv(name, languages, photos) {
  if (!name.trim()) return toast("Write a name for the copy.", { error: true });
  if (!languages.length) return toast("Choose at least one language to copy.", { error: true });
  if (unsaved() && !(await save())) return;
  const from = S.profile;
  try {
    const r = await api("/api/cvs/duplicate", { profile: from, name, languages, photos });
    $("#cv-panel").hidden = true;
    cvForm = null;
    await start(r.profile);
    toast(`You are editing the copy “${r.profile}”: what you change here does not touch “${from}”.`);
  } catch (e) { toast(e.message, { error: true }); }
}
function menuItem(mark, text, onclick, o = {}) {
  return h("button", { type: "button", class: "menu-item" + (o.cls ? " " + o.cls : ""), disabled: !!o.disabled, title: o.title || "",
                       onclick: e => { e.stopPropagation(); onclick(); } }, h("span", { class: "mark" }, MARKS[mark] ? icon(MARKS[mark]) : mark), text);
}
function renderCvPanel(extra) {
  const p = $("#cv-panel");
  const others = S.profiles.filter(x => x.name !== S.profile);
  let newForm = null;
  if (cvForm === "new") {
    const first = h("input", { class: "inp", placeholder: "First name", id: "new-first" });
    const last = h("input", { class: "inp", placeholder: "Last name" });
    const language = h("select", { class: "inp" }, S.templates.map(t => h("option", { value: t.code }, t.name)));
    language.value = "en";
    newForm = h("div", { class: "menu-form" }, h("div", { class: "grid" }, first, last), wrap("Language", language, {}),
      h("button", { type: "button", class: "btn primary", style: "justify-self: start",
                    onclick: () => createCv(first.value, last.value, language.value) }, "Create"));
  }
  fill(p,
    extra || null,
    h("div", { class: "menu-title" }, "Open a CV"),
    S.profiles.map(x => h("div", { class: "menu-row" },
      x.name === S.profile
        ? menuItem("✓", x.name, () => (p.hidden = true), { cls: "current", title: "This is the CV you are editing" })
        : menuItem("", x.name, () => openCv(x.name), { title: `Open the CV of ${x.name}` }),
      button("🗑", `Delete the CV of ${x.name}`, () => deleteCvNamed(x.name), { cls: "danger" }))),
    others.length ? null : h("p", { class: "hint", style: "margin: 2px 8px 4px 32px" },
      "This is your only CV. Create, duplicate or import another one to switch between them."),
    h("div", { class: "menu-sep" }),
    menuItem("＋", "New empty CV", () => toggleCvForm("new", "#new-first")),
    newForm,
    menuItem("⧉", "Duplicate this CV…", () => toggleCvForm("duplicate", "#dup-name"),
             { title: "A copy of this CV with the same languages, colours and photos, to change it (e.g. for another job) without touching this one" }),
    cvForm === "duplicate" ? duplicateForm() : null,
    h("label", { class: "menu-item", title: IMPORT_TITLE }, h("span", { class: "mark" }, icon("upload")), "Import a CV (.zip)…", importInput()),
    exportItems(),
    h("div", { class: "menu-sep" }),
    Object.keys(S.languages).length > 1
      ? menuItem("🗑", `Delete only the ${languageName(S.language)} version…`, () => { p.hidden = true; deleteLanguage(S.language); },
                 { cls: "danger", title: `Delete the ${languageName(S.language)} version of this CV: the other languages stay` }) : null,
    menuItem("🗑", "Delete this CV…", deleteCv, { cls: "danger", title: "Delete this CV with every language, its photos and PDFs" }));
}
async function openCv(name) {
  if (!(await discardOk())) return;
  $("#cv-panel").hidden = true;
  await start(name);
}
async function createCv(first, last, language) {
  if (!first.trim() && !last.trim()) return toast("Write at least a first or a last name.", { error: true });
  if (!(await discardOk())) return;
  try {
    const r = await api("/api/cvs/new", { first_name: first, last_name: last, language });
    $("#cv-panel").hidden = true;
    await start(r.profile);
    toast(`Empty CV created for ${r.profile}: fill it in and press Save.`);
  } catch (e) { toast(e.message, { error: true }); }
}
// deletes any CV (the open one or another); after the last one the welcome screen appears
async function deleteCvNamed(name) {
  const last = S.profiles.length === 1;
  if (!(await ask({ title: `Delete the CV of ${name}?`,
      text: ["The whole CV is deleted from this computer: every language, the photos and the PDFs.",
             last ? "It is your last CV: the editor will start empty." : "",
             name === S.profile && Object.keys(S.languages).length > 1
               ? `To delete only one language, use “Delete only the ${languageName(S.language)} version” instead.` : ""],
      ok: "Delete the whole CV", danger: true }))) return;
  try {
    S.profiles = (await api("/api/cvs/delete", { profile: name })).profiles;
    if (name === S.profile) {
      $("#cv-panel").hidden = true;
      S.changed = {}; S.photosChanged = S.settingsChanged = S.languagesChanged = false;
      S.profile = null;
      await start();
    } else renderCvPanel();
    toast(`The CV of ${name} was deleted.`);
  } catch (e) { toast(e.message, { error: true }); }
}
const deleteCv = () => deleteCvNamed(S.profile);
// export items, in the CV menu
function exportItems() {
  const withPhotos = h("input", { type: "checkbox", checked: true, onclick: e => e.stopPropagation() });
  return [
    menuItem("⬇", "Export this CV (.zip)", () => exportCv(withPhotos.checked),
             { title: "Download this CV as a .zip file with its folder, as in the cvs folder: content files, colours and photos" }),
    S.profiles.length > 1 ? menuItem("⬇", "Export every CV (.zip)", () => exportCv(withPhotos.checked, true),
                                     { title: "Download all the CVs in one .zip file, as in the cvs folder" }) : null,
    h("label", { class: "check", style: "padding: 0 10px 6px 38px; font-size: 12px" }, withPhotos, "include the photos")];
}
// a .zip with the CV's folder, as in the cvs folder; every: all the CVs in one .zip
async function exportCv(withPhotos, every = false) {
  $("#cv-panel").hidden = true;
  if (unsaved() && !(await save())) return;
  const which = every ? "" : `cv=${encodeURIComponent(S.profile)}&`;
  try {
    const r = await fetch(`/api/export-zip?${which}photos=${withPhotos ? 1 : 0}`, { headers: { "X-Token": TOKEN } });
    checkAllowed(r);
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `Error ${r.status}`);
    const name = decodeURIComponent(/filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") || "")?.[1] || "cv.zip");
    const a = h("a", { href: URL.createObjectURL(await r.blob()), download: name });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    toast(`Exported as ${name}: you find it in your downloads.`);
  } catch (e) { toast(e.message, { error: true }); }
}
// the file chooser of every "Import" button: a .zip file exported from this editor
const IMPORT_TITLE = "Add CVs from a .zip file exported from this editor (yours or someone else's), or from a .zip of the cvs folder. " +
                     "You can also drag the .zip onto the editor.";
const IMPORT_TYPES = ".zip,application/zip,application/x-zip-compressed";
const importInput = () => h("input", { type: "file", accept: IMPORT_TYPES, hidden: true, onchange: importChosen });
function importChosen(e) { const f = e.target.files[0]; e.target.value = ""; if (f) importFile(f); }
async function importFile(f) {
  const head = new Uint8Array(await f.slice(0, 2).arrayBuffer());
  if (head[0] !== 0x50 || head[1] !== 0x4b)  // "PK": a .zip file
    return toast(`${f.name} is not a .zip file: choose a .zip exported by the CV editor (CV menu → Export).`, { error: true });
  if (f.size > 80e6) return toast(`${f.name} is too large (more than 80 MB).`, { error: true });
  const send = mode => api("/api/import-zip", f, { "X-Mode": mode });  // mode "check" | "replace" | "copy"
  try {
    const existing = (await send("check")).cvs.filter(x => x.exists).map(x => x.name);
    if (!existing.length) return importCv(send, "copy");
    const one = existing.length === 1, names = existing.map(n => `“${n}”`).join(", ");
    for (const x of document.querySelectorAll(".panel")) x.hidden = x.id !== "cv-panel";
    renderCvPanel(h("div", { class: "choice" }, h("span", {}, one ? `There is already a CV called ${names}.` : `There are already CVs called ${names}.`),
      h("button", { type: "button", class: "btn", onclick: () => importCv(send, "replace", existing) }, one ? "Replace it" : "Replace them"),
      h("button", { type: "button", class: "btn", onclick: () => importCv(send, "copy") }, "Keep both"),
      h("button", { type: "button", class: "link", onclick: () => renderCvPanel() }, "Cancel")));
  } catch (e) { toast(e.message, { error: true }); }
}
// a .zip file dragged from the computer onto the editor (anywhere, the welcome screen too) is imported like "Import"
const draggingFiles = e => [...(e.dataTransfer?.types || [])].includes("Files");
function showDrop(on) { $("#drop").hidden = !on; }
function watchDrops(doc) {
  doc.addEventListener("dragenter", e => { if (draggingFiles(e)) { e.preventDefault(); showDrop(true); } });
  doc.addEventListener("dragover", e => { if (draggingFiles(e)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; } });
  doc.addEventListener("drop", e => {
    if (!draggingFiles(e)) return;
    e.preventDefault(); showDrop(false);
    const files = [...e.dataTransfer.files];
    if (files.length > 1) return toast("Drop one .zip file at a time.", { error: true });
    if (files.length) importFile(files[0]);
  });
}
watchDrops(document);
// the overlay covers the preview too: leaving it means leaving the window
$("#drop").addEventListener("dragleave", e => { if (e.target === $("#drop")) showDrop(false); });
async function importCv(send, mode, existing = []) {
  const one = existing.length === 1;
  if (mode === "replace" && !(await ask({ title: `Replace the ${one ? "CV" : "CVs"} of ${existing.join(", ")}?`,
      text: [`${one ? "Its" : "Their"} content, photos and PDFs are overwritten by the imported file.`],
      ok: "Replace", danger: true }))) return;
  if (!(await discardOk())) return;
  $("#cv-panel").hidden = true;
  status("Importing…", "busy");
  try {
    const r = await send(mode);
    S.changed = {}; S.photosChanged = S.settingsChanged = S.languagesChanged = false;
    await start(r.profiles[0]);
    status(`Imported ✓ ${r.profiles.join(", ")}`, "ok");
    if (r.profiles.length > 1) toast(`${r.profiles.length} CVs imported: switch between them with the CV menu (top left).`);
  } catch (e) { status("Import failed", "error"); toast(e.message, { error: true }); }
}

// ---------------------------------------------------------------- saving
// where the content of each fixed section is: [table, key] (no table = the top of the content)
const FIXED_CONTENT = { contacts: [[null, "contacts"]], details: [[null, "details"]], profile: [["person", "profile"]],
  about_me: [["person", "about_me"]], experience: [[null, "experience"]], education: [[null, "education"]],
  skills: [[null, "languages"], [null, "skills"]], interests: [[null, "interests"]] };
// When saving: the fixed sections taken out of the CV lose their content, in every language (until then Undo
// brings them back as they were). It is forgotten as a change too: there is nothing to bring to the other languages.
function dropRemovedContent() {
  for (const l of Object.keys(S.languages)) {
    const d = L(l).data;
    for (const k of removedFixed(l)) for (const [t, key] of FIXED_CONTENT[k] || []) {
      const owner = t ? d[t] : d;
      if (!isObj(owner) || !(key in owner)) continue;
      delete owner[key];
      delete S.base?.[l]?.twins.get(owner)?.[key];
    }
  }
}
let saving = false;
async function save() {
  if (saving) return false;
  saving = true;
  const version = S.version;
  $("#btn-save").disabled = true;
  status("Saving…", "busy");
  try {
    dropRemovedContent();
    for (const l in S.languages) sync(l);
    const r = await api("/api/save", { profile: S.profile, languages: Object.fromEntries(Object.entries(S.languages).map(([l, x]) => [l, x.data])),
                                       delete: [...S.deleted], settings: S.settings });
    if (S.version === version) S.changed = {};
    S.photosChanged = false; S.settingsChanged = false; S.languagesChanged = false;
    S.deleted.clear(); S.saved = new Set(Object.keys(S.languages));
    status("");  // the Save button says it
    return true;
  } catch (e) {
    status("Not saved", "error"); toast(e.message, { error: true });
    return false;
  } finally {
    saving = false; $("#btn-save").disabled = false; updateBar();
  }
}

$("#btn-save").addEventListener("click", save);

$("#btn-cv").addEventListener("click", e => { e.stopPropagation(); cvPanel(); });

export {
  createCv, importCv, importInput, lastOpened, remember, save, watchDrops
};
