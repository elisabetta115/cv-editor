// The names of companies and schools, changed everywhere at once.
import { $, S } from "./state.js";
import { fill, h, L, toast } from "./util.js";
import { changed, languageName } from "./sync.js";
import { button } from "./fields.js";
import { render } from "./nav.js";
import { outsideAddresses, withoutAddresses } from "./links.js";

// ---------------------------------------------------------------- names of companies and schools
// Every organisation of the CV in this language (jobs, education, entries of the sections), and a box to
// write it differently: the new name replaces it everywhere in this language, in the text too.
const NOT_TEXT = new Set(["link", "type", "id", "builtin", "column", "hidden", "after", "first_name", "last_name", "contacts", "cv_language"]);
function eachText(node, fn) {
  for (const [k, v] of Object.entries(node)) {
    if (NOT_TEXT.has(k)) continue;
    if (typeof v === "string") fn(node, k, v);
    else if (v && typeof v === "object") eachText(v, fn);
  }
}
const arr = v => (Array.isArray(v) ? v : []);
const nameRe = name => new RegExp(`(?<![\\p{L}\\p{N}])${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\p{L}\\p{N}])`, "gu");
function organisations(d) {
  const names = new Map();  // name -> how many jobs, degrees and other entries have it, how many texts mention it
  const groups = { job: arr(d.experience), degree: arr(d.education), entry: arr(d.sections).flatMap(s => arr(s?.entries)) };
  for (const [kind, entries] of Object.entries(groups))
    for (const e of entries) {
      const n = typeof e?.organization === "string" ? e.organization.trim() : "";
      if (!n) continue;
      if (!names.has(n)) names.set(n, { job: 0, degree: 0, entry: 0, text: 0, re: nameRe(n) });
      names.get(n)[kind]++;
    }
  eachText(d, (o, k, v) => {
    if (k !== "organization") for (const c of names.values()) if (withoutAddresses(v).match(c.re)) c.text++;
  });
  return names;
}
function renameOrganisations(d, changes) {
  const undo = [];
  eachText(d, (o, k, v) => {
    let out = v;
    for (const [from, to] of changes)
      out = k === "organization" ? (out.trim() === from ? to : out) : outsideAddresses(out, x => x.replace(nameRe(from), () => to));
    if (out !== v) { undo.push([o, k, v]); o[k] = out; }
  });
  return undo;
}
function namesDialog() {
  const dlg = $("#names-dialog"), l = S.language, d = L(l).data, names = organisations(d);
  if (!names.size) return toast("There are no companies, universities or schools in this CV yet.");
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const go = h("button", { type: "submit", class: "btn primary" });
  const update = () => {  // the boxes you changed are highlighted, and the button says how many names change
    for (const r of rows) r.input.classList.toggle("changed", !!r.input.value.trim() && r.input.value.trim() !== r.name);
    const n = rows.filter(r => r.input.classList.contains("changed")).length;
    go.disabled = !n;
    go.textContent = n ? `Change ${plural(n, "name", "names")}` : "Change names";
  };
  const rows = [...names].map(([name, c]) => {
    const input = h("input", { class: "inp", value: name, "aria-label": "New name for " + name, oninput: update });
    const used = [c.job && plural(c.job, "job", "jobs"), c.degree && plural(c.degree, "degree", "degrees"),
                  c.entry && plural(c.entry, "entry", "entries")].filter(Boolean).join(", ");
    const said = c.text ? ` · mentioned ${c.text === 1 ? "once" : c.text + " times"} in the text` : "";
    return { name, input, el: h("div", { class: "name-row" },
      h("div", {}, h("strong", {}, name), h("small", {}, `  ·  used in ${used}${said}`)),
      h("label", { class: "new" }, h("span", {}, "New name"), input)) };
  });
  const apply = () => {
    const changes = rows.map(r => [r.name, r.input.value.trim()]).filter(([from, to]) => to && to !== from);
    dlg.close();
    if (!changes.length || S.language !== l) return;
    const undo = renameOrganisations(d, changes);
    changed(); render();
    toast(`${changes.length === 1 ? "Name" : "Names"} changed in ${languageName(l)}: press Save to keep ${changes.length === 1 ? "it" : "them"}.`,
          { undo: () => { for (const [o, k, v] of undo.reverse()) o[k] = v; changed(false, l); if (S.language === l) render(); } });
  };
  fill(dlg, h("form", { onsubmit: e => { e.preventDefault(); apply(); } },
    h("div", { class: "panel-head" }, h("strong", {}, `Company and school names · ${languageName(l)}`), button("✕", "Close", () => dlg.close())),
    h("small", { class: "hint" }, "Write the new name in the box next to the one you want to change. Each name changes everywhere in the ",
      h("b", {}, languageName(l)), " CV: in jobs, education, other sections and the text. The other languages are not changed."),
    h("div", { class: "names-list" }, rows.map(r => r.el)),
    h("div", { class: "actions" }, h("button", { type: "button", class: "btn", onclick: () => dlg.close() }, "Cancel"), go)));
  update();
  dlg.showModal();
  rows[0].input.focus();
}

export {
  arr, namesDialog
};
