// Changes to bring to the other languages of a CV, and sections still to translate.
import { $, S } from "./state.js";
import { icon } from "./icons.js";
import { api, ask, fill, h, L, table, toast } from "./util.js";
import { hasContent, inLanguage, partners, sync } from "./changes.js";
import { button } from "./fields.js";
import { render } from "./nav.js";
import { updateBar } from "./design.js";
import { findDirty } from "./find.js";
import { updatePreview } from "./preview.js";

// ---------------------------------------------------------------- changes to bring to the other languages
// Every language is remembered as it was when the CV was opened (or when its changes were last brought to
// the others, or left only there). What differs since then is a change: a text, an entry added, an entry
// deleted. The other languages have the same parts in the same places: a change goes to the same place.
// "hidden" is a change only for an item of a list (a detail, a job...); the sections of each language are its own
const NO_DIFF = new Set(["id", "builtin", "hidden", "removed", "column", "after", "copied_from", "type", "icon", "cv_language"]);
const COPY_ONLY = new Set(["first_name", "last_name", "organization", "link", "hidden"]);  // copied as they are, never translated
const isHideChange = c => c.kind === "text" && c.key === "hidden";
const isObj = v => v && typeof v === "object" && !Array.isArray(v);
function snapshot(l) {
  const twins = new WeakMap();
  const clone = v => {
    if (Array.isArray(v)) { const c = v.map(clone); twins.set(v, c); return c; }
    if (isObj(v)) { const c = {}; for (const [k, x] of Object.entries(v)) c[k] = clone(x); twins.set(v, c); return c; }
    return v;
  };
  (S.base ??= {})[l] = { root: clone(L(l).data), twins, clone };
}
// a part of a language changed by the editor itself (a copy, a translation): it is not a change of yours
function rebase(l, obj) {
  const b = S.base?.[l], t = b?.twins.get(obj);
  if (!t) return;
  if (Array.isArray(obj)) t.splice(0, t.length, ...obj.map(b.clone));
  else { for (const k of Object.keys(t)) delete t[k]; for (const [k, v] of Object.entries(obj)) t[k] = b.clone(v); }
}
// what changed in language l: [{kind: "text" | "add" | "remove", path, ...}]; a path is made of keys,
// {i} (the place in a list, as it was) and {id} (an added section: the same id in each language that has it)
function pendingChanges(l) {
  const b = S.base?.[l];
  if (!b || !L(l)) return [];
  const out = [];
  const entryList = a => Array.isArray(a) && a.some(isObj);
  function walk(cur, old, path) {
    const item = isObj(path[path.length - 1]) && "i" in path[path.length - 1];  // an item of a list
    for (const k of new Set([...Object.keys(cur), ...Object.keys(old)])) {
      if (NO_DIFF.has(k) && !(k === "hidden" && item)) continue;
      if (k.endsWith("_hidden")) continue;  // hidden lines of a list: each language hides its own
      const v = cur[k], o = old[k];
      if (k === "signature" && !path.length) continue;  // whether a language is signed: each one chooses
      if (k === "sections" && !path.length) sections(Array.isArray(v) ? v : []);
      else if (entryList(v) || entryList(o)) list(Array.isArray(v) ? v : [], Array.isArray(o) ? o : [], [...path, k]);
      else if (isObj(v) || isObj(o)) walk(isObj(v) ? v : {}, isObj(o) ? o : {}, [...path, k]);
      else if (JSON.stringify(v ?? "") !== JSON.stringify(o ?? "") && (String(v ?? "").trim() || String(o ?? "").trim()))
        out.push({ kind: "text", path: [...path, k], key: k, value: v, old: o, owner: cur });
    }
  }
  function list(arr, old, path) {
    const kept = new Set();
    let last = -1;
    arr.forEach(item => {
      const twin = isObj(item) ? b.twins.get(item) : undefined, i = twin ? old.indexOf(twin) : -1;
      if (i >= 0) { kept.add(i); last = i; walk(item, twin, [...path, { i }]); }
      else if (isObj(item) && Object.values(item).some(x => String(x ?? "").trim())) out.push({ kind: "add", path, item, after: last });
    });
    old.forEach((o, i) => { if (!kept.has(i) && isObj(o) && Object.values(o).some(x => String(x ?? "").trim())) out.push({ kind: "remove", path, i, item: o }); });
  }
  // the added sections: their content, by id (adding, moving, hiding or deleting one stays in its language)
  function sections(arr) {
    for (const s of arr) {
      const twin = isObj(s) && s.id ? b.twins.get(s) : undefined;
      if (twin) walk(s, twin, ["sections", { id: s.id }]);
    }
  }
  walk(L(l).data, b.root, []);
  return out;
}
// the same place in another language (undefined when it has no such place)
function locate(root, path) {
  let x = root;
  for (const seg of path) {
    if (x == null) return undefined;
    x = typeof seg === "string" ? x[seg] : "id" in seg ? (Array.isArray(x) ? x.find(o => o?.id === seg.id) : undefined) : (Array.isArray(x) ? x[seg.i] : undefined);
  }
  return x;
}
// how a change is called in the review: "Experience › Senior Designer › Description"
const FIELD_NAMES = { role: "Role", organization: "Company / school", location: "Location", dates: "Dates", description: "Description",
  title: "Title", grade: "Grade", thesis: "Thesis", text: "Text", list: "List", tags: "Tags", label: "Name", value: "Value", level: "Level",
  language: "Language", headline: "Line under the name", first_name: "First name", last_name: "Last name", profile: "Profile",
  about_me: "About me", link: "Link", digital: "Digital skills", soft: "Soft skills" };
const PLACE_NAMES = { person: "Header", details: "Personal details", contacts: "Contacts", experience: "Experience", education: "Education",
  languages: "Skills › Languages", skills: "Skills", interests: "Interests", privacy: "Privacy note", labels: "Section titles" };
const short = (v, n = 110) => { const t = (Array.isArray(v) ? v.join(" · ") : String(v ?? "")).replace(/\s+/g, " ").trim(); return t.length > n ? t.slice(0, n - 1) + "…" : t; };
const entryName = e => isObj(e) ? short(e.role || e.title || e.language || e.label || e.text || e.organization || "", 50) : "";
function changePlace(l, c) {
  const parts = [];
  let x = S.base[l].root;  // the places of a change are counted as they were
  c.path.forEach((seg, n) => {
    if (typeof seg === "string") {
      if (isHideChange(c) && n === c.path.length - 1) return;  // "Personal details › Nationality": hidden or shown
      if (n === 0 && seg !== "sections") parts.push(PLACE_NAMES[seg] || seg);
      else if (n === c.path.length - 1 && c.kind === "text")
        parts.push(c.path[0] === "labels" ? (table(L(l).data, "labels")[seg] || seg) : FIELD_NAMES[seg] || seg);
      else if (n > 0 && !["entries", "rows"].includes(seg)) parts.push(FIELD_NAMES[seg] || seg);
      x = x?.[seg];
    } else {
      const was = Array.isArray(x) ? ("id" in seg ? x.find(o => o?.id === seg.id) : x[seg.i]) : undefined;
      const now = c.kind === "text" && n === c.path.length - 2 ? c.owner : was;
      if ("id" in seg) parts.push(now?.title || was?.title || "Untitled section");
      else if (entryName(now) || entryName(was)) parts.push(entryName(now) || entryName(was));
      x = was;
    }
  });
  return parts.join(" › ");
}
// is there, in language t, the place where change c goes?
function placeIn(t, c) {
  const data = L(t).data;
  if (c.kind === "text") return isObj(locate(data, c.path.slice(0, -1)));
  if (c.kind === "remove") return isObj(locate(data, [...c.path, { i: c.i }]));
  return Array.isArray(locate(data, c.path)) || isObj(locate(data, c.path.slice(0, -1)));
}
let syncTimer;
function updateSyncBar() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    const bar = $("#sync-bar");
    if (!bar || !partners(S.language).length) { if (bar) bar.hidden = true; return; }
    const l = S.language, mine = pendingChanges(l).length;
    const other = !mine && partners(l).map(x => [x, pendingChanges(x).length]).find(([, n]) => n);
    if (!mine && !other) { bar.hidden = true; return; }
    const n = mine || other[1], from = mine ? l : other[0], things = n === 1 ? "1 thing" : `${n} things`;
    const others = partners(l);
    fill(bar, icon("globe"),
      h("span", {}, mine
        ? [`You changed ${things} in ${languageName(l)}. Also change ${n === 1 ? "it" : "them"} in `,
           h("b", {}, others.length === 1 ? languageName(others[0]) : "the other languages"), "?"]
        : [h("b", {}, languageName(from)), ` has ${n === 1 ? "a change" : n + " changes"} that ${n === 1 ? "is" : "are"} not in this version yet.`]),
      h("button", { type: "button", class: "btn primary", onclick: () => syncDialog(from, mine ? null : l) }, "Review…"),
      h("button", { type: "button", class: "btn ghost", title: `Keep these changes only in ${languageName(from)}: the question goes away`,
                    onclick: () => { snapshot(from); updateSyncBar(); } }, `Only in ${languageName(from)}`));
    bar.hidden = false;
  }, 300);
}
// the review: which changes, into which languages; then translated (or copied as they are) and applied
async function syncDialog(from, only = null) {
  const dlg = $("#sync-dialog"), changes = pendingChanges(from);
  if (!changes.length) return updateSyncBar();
  const targets = partners(from);
  const chosenLangs = new Set(only ? [only] : targets);
  let st = null;
  try { st = S.translator = await api("/api/translator"); } catch { /* copy as is still works */ }
  const engine = st?.local?.model ? "local" : st?.azure?.configured ? "azure" : null;
  const items = changes.map(c => {
    const box = h("input", { type: "checkbox", checked: true });
    const copyOnly = c.path[0] === "contacts" || (c.kind === "text" && COPY_ONLY.has(c.key));
    const now = targets.filter(t => c.kind === "text" && placeIn(t, c)).map(t => [t, locate(L(t).data, c.path)]);
    const missing = !targets.some(t => placeIn(t, c));
    if (missing) { box.checked = false; box.disabled = true; }
    const tag = c.kind === "add" ? h("span", { class: "tag add" }, "new") : c.kind === "remove" ? h("span", { class: "tag remove" }, "deleted") : null;
    const shownOrNot = v => (v ? "hidden from the CV" : "shown in the CV");
    const what = isHideChange(c)
      ? [h("span", {}, h("b", {}, languageName(from) + ": "), shownOrNot(c.value)),
         ...now.map(([t, there]) => h("span", {}, h("b", {}, languageName(t) + " now: "), shownOrNot(there)))]
      : c.kind === "text"
      ? [h("span", {}, h("b", {}, languageName(from) + ": "), short(c.value) || "(empty)"),
         ...now.map(([t, there]) => h("span", {}, h("b", {}, languageName(t) + " now: "), short(there) || "(empty)"))]
      : [h("span", {}, short(Object.values(c.item).filter(v => typeof v === "string" || Array.isArray(v)).map(v => short(v, 60)).join(" · "), 160))];
    if (copyOnly && !isHideChange(c)) what.push(h("span", {}, "Copied as it is (not translated)."));
    if (missing) what.push(h("span", {}, "Not found in the other languages: change it there by hand."));
    return { c, box, copyOnly, el: h("label", { class: "sync-item" + (missing ? " missing" : "") }, box,
      h("span", { class: "where" }, (c.kind === "add" ? "Added to " : c.kind === "remove" ? "Deleted from " : "") + changePlace(from, c), tag),
      h("span", { class: "what" }, what)) };
  });
  const langBoxes = targets.map(t => {
    const box = h("input", { type: "checkbox", checked: chosenLangs.has(t), onchange: () => (box.checked ? chosenLangs.add(t) : chosenLangs.delete(t)) });
    return h("label", { class: "check" }, box, languageName(t));
  });
  const apply = async translate => {
    const chosen = items.filter(x => x.box.checked && !x.box.disabled), langs = targets.filter(t => chosenLangs.has(t));
    if (!chosen.length || !langs.length) return toast("Choose at least one change and one language.", { error: true });
    for (const b of dlg.querySelectorAll(".actions .btn")) b.disabled = true;
    try {
      const undo = [], before = S.base[from];
      for (const t of langs) await applyChanges(from, t, chosen, translate ? engine : null, undo);
      dlg.close();
      snapshot(from);
      for (const t of langs) changed(false, t);
      render(); updateSyncBar();
      toast(`${chosen.length === 1 ? "The change was" : chosen.length + " changes were"} brought to ${langs.map(languageName).join(", ")}` +
            (translate ? ", translated" : "") + ": check and press Save.", { undo: () => {
        for (const [kind, t, a, b, c] of undo.reverse()) {
          if (kind === "set") { if (c === undefined) delete a[b]; else a[b] = c; } else a.splice(0, a.length, ...b);
          rebase(t, a);
        }
        S.base[from] = before;  // the question comes back
        for (const t of langs) changed(false, t);
        render(); updateSyncBar();
      } });
    } catch (e) {
      toast(e.message, { error: true });
      for (const b of dlg.querySelectorAll(".actions .btn")) b.disabled = false;
    }
  };
  fill(dlg, h("form", { onsubmit: e => { e.preventDefault(); apply(!!engine); } },
    h("div", { class: "panel-head" }, h("strong", {}, `Your changes in ${languageName(from)}`), button("✕", "Close", () => dlg.close())),
    h("small", { class: "hint" }, "Tick the changes to bring to the other languages: each one goes to the same place there. ",
      "Names, companies, links and contacts are copied as they are; the rest is translated."),
    targets.length > 1 ? h("div", { class: "sync-targets" }, h("span", { class: "subtitle" }, "Into:"), langBoxes) : null,
    h("div", { class: "sync-list" }, items.map(x => x.el)),
    engine ? null : h("small", { class: "hint" }, "No translator is ready: “Copy as is” brings the text untranslated. ",
      "To translate, set one up in + New language → Translate it automatically."),
    h("div", { class: "actions" },
      h("button", { type: "button", class: "btn ghost", title: `Keep them only in ${languageName(from)}: the question goes away`,
                    onclick: () => { snapshot(from); dlg.close(); updateSyncBar(); } }, `Only in ${languageName(from)}`),
      h("span", { class: "spacer" }),
      h("button", { type: "button", class: "btn", onclick: () => apply(false) }, "Copy as is"),
      h("button", { type: "submit", class: "btn primary", disabled: !engine }, icon("globe"), "Translate and apply"))));
  dlg.showModal();
}
// brings the chosen changes of language "from" to language "to" (undo collects how to put things back)
async function applyChanges(from, to, chosen, engine, undo) {
  const data = L(to).data;
  // what to translate: the texts, and the new entries (except contacts and the fields copied as they are)
  const texts = chosen.filter(x => x.c.kind === "text" && !x.copyOnly && locate(data, x.c.path.slice(0, -1)));
  const adds = chosen.filter(x => x.c.kind === "add");
  let tr = { texts: texts.map(x => x.c.value), items: adds.map(x => structuredClone(x.c.item)) };
  if (engine && (texts.length || adds.some(x => !x.copyOnly))) {
    const payload = { changes: texts.map(x => ({ [x.c.key]: x.c.value })), items: adds.map(x => (x.copyOnly ? {} : structuredClone(x.c.item))) };
    const r = await api("/api/translate", { data: payload, from, to, engine, from_name: languageName(from), to_name: languageName(to) });
    tr = { texts: texts.map((x, n) => r.data.changes?.[n]?.[x.c.key] ?? x.c.value),
           items: adds.map((x, n) => (x.copyOnly ? structuredClone(x.c.item) : r.data.items?.[n] || structuredClone(x.c.item))) };
  }
  // texts
  for (const x of chosen.filter(x => x.c.kind === "text")) {
    const owner = locate(data, x.c.path.slice(0, -1));
    if (!isObj(owner)) continue;
    const n = texts.indexOf(x), value = n >= 0 ? tr.texts[n] : structuredClone(x.c.value);
    undo.push(["set", to, owner, x.c.key, owner[x.c.key]]);
    if (value === undefined || value === "") delete owner[x.c.key]; else owner[x.c.key] = value;
    rebase(to, owner);
  }
  // lists: deleted entries go, new ones go after the entry they follow
  const lists = new Map();
  for (const x of chosen.filter(x => x.c.kind !== "text")) {
    const key = JSON.stringify(x.c.path);
    if (!lists.has(key)) lists.set(key, { path: x.c.path, adds: [], removes: [] });
    lists.get(key)[x.c.kind === "add" ? "adds" : "removes"].push(x);
  }
  for (const { path, adds: add, removes } of lists.values()) {
    let arr = locate(data, path), created = null;
    if (arr === undefined && add.length) {  // e.g. the first entry of a list that is empty there
      created = locate(data, path.slice(0, -1));
      if (!isObj(created)) continue;
      arr = created[path[path.length - 1]] = [];
    }
    if (!Array.isArray(arr)) continue;
    const before = arr.slice();
    undo.push(["list", to, arr, before]);
    const gone = new Set(removes.map(x => before[x.c.i]).filter(Boolean));
    const next = before.filter(o => !gone.has(o)), placed = new Map();
    for (const x of add) {
      const item = tr.items[adds.indexOf(x)];
      let anchor = placed.get(x.c.after) ?? (x.c.after >= 0 ? before[x.c.after] : null);
      for (let k = x.c.after; anchor && !next.includes(anchor) && k >= 0; k--) anchor = before[k - 1] ?? null;
      next.splice(anchor ? next.indexOf(anchor) + 1 : 0, 0, item);
      placed.set(x.c.after, item);
    }
    arr.splice(0, arr.length, ...next);
    rebase(to, arr);
    if (created) rebase(to, created);
  }
}

function changed(structureChanged = false, l = S.language) {
  S.changed[l] = true; S.version++;
  findDirty();
  updateSyncBar();
  if (structureChanged) { sync(l); if (l === S.language) render(); }
  updateBar();
  if (l === S.language) updatePreview();
}
const unsaved = () => Object.values(S.changed).some(Boolean) || S.photosChanged || S.settingsChanged || S.languagesChanged;
const languageName = l => S.languages[l]?.name || S.templates.find(t => t.code === l)?.name || l.toUpperCase();
// deletes a row, a contact or an entry, after asking (not for one left empty); Undo puts it back
async function remove(arr, i, message) {
  const item = arr[i], l = S.language;
  const filled = isObj(item) && Object.entries(item).some(([k, v]) => k !== "hidden" && String(v ?? "").trim());
  if (filled && !(await ask({ title: entryName(item) ? `Delete “${entryName(item)}”?` : "Delete it?",
      text: [`It is deleted from the CV${inLanguage(l)}` + (inLanguage(l) ? ": the other languages are not changed." : "."),
             "To keep it but not show it in the CV, use the eye instead."],
      ok: "Delete", danger: true }))) return;
  const at = arr.indexOf(item);
  if (at < 0) return;
  arr.splice(at, 1);
  changed(true, l);
  toast(message, { undo: () => { arr.splice(at, 0, item); changed(true, l); } });
}

// ---------------------------------------------------------------- sections to translate
// A section filled in another language and empty here (added there), or copied from there and not changed
// since: its card asks whether to translate it. "copied_from" marks a copy (made when saving, or with ⇄).
const CONTENT = ["title", "text", "list", "tags", "entries", "rows", "list_hidden", "tags_hidden"];
const contentOf = s => JSON.stringify(CONTENT.map(k => s[k] ?? null));
const notNow = new Set();  // sections left empty for now: "language:id"
function untranslated(s, l = S.language) {
  if (!s.id || notNow.has(`${l}:${s.id}`)) return null;
  const twin = code => L(code)?.order.find(o => o.section?.id === s.id)?.section;
  if (s.copied_from && s.copied_from !== l) {
    const src = twin(s.copied_from);
    return src && contentOf(src) === contentOf(s) ? { from: s.copied_from, empty: false } : null;
  }
  if (hasContent(s)) return null;
  const from = partners(l).filter(code => twin(code) && hasContent(twin(code)))
                     .sort((a, b) => (b === "en") - (a === "en"))[0];
  return from ? { from, empty: true } : null;
}
function keepSection(s, todo) {
  if (todo.empty) notNow.add(`${S.language}:${s.id}`);
  else { delete s.copied_from; changed(); }
  render();
}
async function translateSection(s, from, btn) {
  const l = S.language, src = L(from)?.order.find(o => o.section?.id === s.id)?.section;
  if (!src) return;
  btn.disabled = true; btn.textContent = "Translating…";
  try {
    const st = S.translator = await api("/api/translator");
    const engine = st.local?.model ? "local" : st.azure?.configured ? "azure" : null;
    if (!engine) throw new Error(st.local?.running
      ? `To translate on this computer, download the AI model first: in a terminal run  ollama pull ${st.local.suggested}`
      : "To translate automatically, set up a translator first: + New language → Translate it automatically.");
    const part = Object.fromEntries(CONTENT.filter(k => k in src).map(k => [k, structuredClone(src[k])]));
    const r = await api("/api/translate", { data: { sections: [part] }, from, to: l, engine,
                                            from_name: languageName(from), to_name: languageName(l) });
    const before = structuredClone(s), t = r.data.sections?.[0] || {};
    for (const k of Object.keys(s)) if (!["id", "hidden", "column"].includes(k)) delete s[k];
    for (const k of CONTENT) if (k in t) s[k] = t[k];
    rebase(l, s);
    changed(false, l);
    if (S.language === l) render();
    toast(`“${s.title || "Section"}” translated from ${languageName(from)}: check it and press Save.`, { undo: () => {
      for (const k of Object.keys(s)) delete s[k];
      Object.assign(s, before); rebase(l, s); changed(false, l); if (S.language === l) render();
    } });
  } catch (e) {
    toast(e.message, { error: true });
    btn.disabled = false; btn.textContent = "Translate";
  }
}

export {
  changed, isObj, keepSection, languageName, rebase, remove, short, snapshot, translateSection, unsaved,
  untranslated, updateSyncBar
};
