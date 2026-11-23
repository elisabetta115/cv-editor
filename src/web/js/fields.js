// The fields of the form: text boxes, lists, rows, contacts and entries (jobs, degrees...).
import { $, CONTACT_GROUPS, CONTACT_TYPES, DESC_HINT, ICON_NAMES, S, WEB_CONTACTS } from "./state.js";
import { icon } from "./icons.js";
import { fill, h, L, list, move, placeUnder, toast } from "./util.js";
import { baseOf } from "./changes.js";
import { changed, languageName, rebase, remove, short } from "./sync.js";
import { render, renderNav } from "./nav.js";
import { linkButton, withoutAddresses } from "./links.js";
import { arr } from "./names.js";
import { bindBox } from "./find.js";

// ---------------------------------------------------------------- fields
const GLYPHS = { "↑": "arrow-up", "↓": "arrow-down", "🗑": "trash" };
function button(text, title, fn, o = {}) {
  const content = text === "✕" ? icon(/^close/i.test(title) ? "x" : "trash") : GLYPHS[text] ? icon(GLYPHS[text]) : text;
  return h("button", { type: "button", class: "ico" + (o.cls ? " " + o.cls : ""), title, "aria-label": title,
                       disabled: !!o.disabled, onclick: e => { e.stopPropagation(); fn(e); } }, content);
}
// "⇄ EN": copy to the other language; with more languages it opens a menu to pick one
function copyButton(what, fn, others = Object.keys(S.languages).filter(l => l !== S.language)) {
  if (!others.length) return null;
  if (others.length === 1)
    return button([icon("copy"), others[0].toUpperCase()], `Copy ${what} to ${languageName(others[0])} (then translate it)`, () => fn(others[0]), { cls: "text" });
  return button(icon("copy"), `Copy ${what} to another language (then translate it)`,
    e => menu(e, `Copy ${what} to:`, others.map(l => [languageName(l), () => fn(l)])), { cls: "text" });
}
function menu(e, title, items) {
  closeMenu();
  const r = e.currentTarget.getBoundingClientRect();
  const m = h("div", { class: "menu", id: "menu" }, h("span", {}, title),
    items.map(([text, fn]) => h("button", { type: "button", onclick: ev => { ev.stopPropagation(); closeMenu(); fn(); } }, text)));
  m.style.left = Math.min(r.left, innerWidth - 210) + "px";
  m.style.top = r.bottom + 4 + "px";
  document.body.append(m);
}
const closeMenu = () => $("#menu")?.remove();
// links: the text can hold links (Ctrl+K); text areas and wide boxes also show an "Add a link" button
function wrap(label, el, o) {
  if (o.links) el.dataset.links = "";
  const add = o.links && (el.tagName === "TEXTAREA" || o.wide) ? linkButton(el) : null;
  return h("label", { class: "field" + (o.wide ? " wide" : "") }, label ? h("span", {}, label) : null, el,
           add ? h("small", { class: "with-link" }, h("span", {}, o.hint || ""), add) : o.hint ? h("small", {}, o.hint) : null);
}
function field(obj, k, label, o = {}) {
  const el = h(o.multi ? "textarea" : "input", { class: "inp", placeholder: o.ph || "" });
  el.value = obj[k] ?? "";
  if (o.multi) el.rows = Math.min(14, Math.max(3, Math.ceil(el.value.length / 75) + el.value.split("\n").length));
  el.addEventListener("input", () => { obj[k] = el.value; o.then?.(); changed(); });
  bindBox(obj, k, el);
  if (o.focus) S.toFocus ??= el;
  return wrap(label, el, o);
}
// text with one item per line (lists). With desc: one line = string, several lines = list.
// With hide: under the box, each line with an eye to hide it from the CV.
function linesField(obj, k, label, o = {}) {
  const v = obj[k]; const lines = Array.isArray(v) ? v : (v ? [v] : []);
  const el = h("textarea", { class: "inp", placeholder: o.ph || "" });
  el.value = lines.join("\n");
  el.rows = Math.min(14, Math.max(2, lines.length + 1));
  const chips = o.hide ? lineChips(obj, k) : null;
  el.addEventListener("input", () => {
    const r = el.value.split("\n").map(x => x.trim()).filter(Boolean);
    if (!o.desc) obj[k] = r;
    else if (!r.length) delete obj[k];
    else obj[k] = r.length === 1 ? r[0] : r;
    chips?.draw();
    changed();
  });
  bindBox(obj, k, el);
  const box = wrap(label, el, o);
  if (chips) box.append(chips.box);
  return box;
}
// The lines of a list as chips, each with an eye: a hidden line stays in the box but is not in the CV. Hidden lines
// are written, by their text, in "<key>_hidden" (digital_hidden...): a line whose text changes is shown again.
function lineChips(obj, k) {
  const box = h("div", { class: "line-chips" }), hk = k + "_hidden";
  const plain = t => withoutAddresses(t).replace(/\*\*?/g, "").trim();
  const draw = () => {
    const v = obj[k], lines = [...new Set((Array.isArray(v) ? v : v ? [v] : []).map(x => String(x).trim()).filter(Boolean))];
    const hidden = new Set(arr(obj[hk]).filter(x => lines.includes(x)));
    const keep = () => { if (hidden.size) obj[hk] = [...hidden]; else delete obj[hk]; };
    keep();
    fill(box, lines.length ? h("span", { class: "mini" }, "In the CV:") : null, lines.map(t => {
      const off = hidden.has(t);
      return h("button", { type: "button", class: "line-chip" + (off ? " off" : ""),
        title: off ? `Hidden from the CV: click to show it again — ${short(plain(t), 120)}`
                   : `Click to hide it from the CV (it stays here) — ${short(plain(t), 120)}`,
        onclick: e => { e.preventDefault(); off ? hidden.delete(t) : hidden.add(t); keep(); changed(); draw(); } },
        icon(off ? "eye-off" : "eye"), h("span", {}, short(plain(t), 48)));
    }));
  };
  draw();
  return { box, draw };
}
function sectionTitle(obj, k, ph) {
  const el = h("input", { class: "section-title", placeholder: ph || "", title: "Title in the CV: click to change it" });
  el.value = obj[k] ?? "";
  el.addEventListener("input", () => { obj[k] = el.value; changed(); refreshOrder(); });
  bindBox(obj, k, el);
  return el;
}
// redraws the list of sections (e.g. while a section title is being typed)
function refreshOrder() { renderNav(); }
function smallInput(obj, k) {
  const el = h("input", { class: "inp small", title: "Title in the CV: click to change it" });
  el.value = obj[k] ?? "";
  el.addEventListener("input", () => { obj[k] = el.value; changed(); });
  bindBox(obj, k, el);
  return el;
}
function card(head, body) {
  return h("section", { class: "card" }, h("div", { class: "card-head" }, head), h("div", { class: "card-body" }, body));
}

// the eye of a detail, contact, language, row or entry: hidden = it stays here but is not in the CV
function hideToggle(r) {
  return button(icon(r.hidden ? "eye-off" : "eye"),
    r.hidden ? "Hidden from the CV: click to show it again" : "Hide it from the CV (it stays here: you can show it again)",
    () => { if (r.hidden) delete r.hidden; else r.hidden = true; changed(true); }, { cls: r.hidden ? "is-off" : "" });
}
// simple rows: personal details, languages
function rows(arr, columns, addLabel, o = {}) {
  const box = h("div", { class: "rows" });
  arr.forEach((r, i) => {
    const row = h("div", { class: "row" + (r.hidden ? " is-hidden" : "") });
    for (const [k, ph] of columns) {
      const el = h("input", { class: "inp", placeholder: ph || "" });
      el.value = r[k] ?? "";
      if (o.links?.includes(k)) { el.dataset.links = ""; el.title = "Ctrl+K: make the selected words a link"; }
      el.addEventListener("input", () => { r[k] = el.value; changed(); });
      bindBox(r, k, el);
      if (S.focus === r) S.toFocus ??= el;
      row.append(el);
    }
    row.append(hideToggle(r),
      button("↑", "Move up", () => { move(arr, i, -1); changed(true); }, { disabled: i === 0 }),
      button("↓", "Move down", () => { move(arr, i, 1); changed(true); }, { disabled: i === arr.length - 1 }),
      button("✕", "Delete", () => remove(arr, i, o.removed || "Row deleted"), { cls: "danger" }));
    box.append(row);
  });
  box.append(h("button", { type: "button", class: "add-btn",
    onclick: () => { const r = {}; arr.push(r); S.focus = r; changed(true); } }, icon("plus"), addLabel));
  return box;
}

// contacts: for GitHub, LinkedIn and websites the name shown and the link are separate (WEB_CONTACTS)
const FROM_NAME = "Leave it empty: it is made from the user name";
const CONTACT_EXAMPLES = {
  phone: ["+39 …"], email: ["name@email.com"], address: ["Street …, City"], whatsapp: ["Number, e.g. +39 333 …"],
  orcid: ["Your ORCID iD, e.g. 0000-0002-1825-0097"],
  web: ["Name to show, e.g. My website", "https://…"],
  linkedin: ["Name to show, e.g. Jane Doe", "https://www.linkedin.com/in/…"],
  github: ["User name, e.g. janedoe", FROM_NAME], gitlab: ["User name, e.g. janedoe", FROM_NAME],
  x: ["@username", FROM_NAME], instagram: ["@username", FROM_NAME], telegram: ["@username", FROM_NAME],
  stackoverflow: ["Name to show", "https://stackoverflow.com/users/…"], behance: ["Name to show", "https://www.behance.net/…"],
  dribbble: ["Name to show", "https://dribbble.com/…"], scholar: ["Name to show, e.g. Jane Doe", "https://scholar.google.com/citations?user=…"],
  researchgate: ["Name to show, e.g. Jane Doe", "https://www.researchgate.net/profile/…"],
  facebook: ["Name to show", "https://www.facebook.com/…"], youtube: ["Channel name", "https://www.youtube.com/@…"],
};
// an icon of the CV (the same drawings as in the PDF)
function cvIcon(name) {
  const svg = icon("");
  svg.innerHTML = S.icons?.[name] || S.icons?.web || "";
  return svg;
}
const contactIcon = r => (r.icon === "none" ? icon("image-off", "no-icon") : cvIcon(S.icons?.[r.icon] ? r.icon : r.type));
// the icon of a contact: automatic (the one of its type), none, or any other
function iconMenu(anchor, r) {
  const p = $("#icon-panel");
  for (const x of document.querySelectorAll(".panel")) x.hidden = true;
  const pick = v => { if (v === null) delete r.icon; else r.icon = v; p.hidden = true; changed(true); };
  const current = S.icons?.[r.icon] || r.icon === "none" ? r.icon : null;
  const choice = (v, label, content, cls) => h("button", { type: "button", class: cls, title: label, "aria-label": label,
    "aria-pressed": String(current === v), onclick: () => pick(v) }, content);
  fill(p, h("div", { class: "panel-head" }, h("strong", {}, "Icon of this contact"), button("✕", "Close", () => (p.hidden = true))),
    h("div", { class: "icon-presets" },
      choice(null, `Automatic: the ${CONTACT_TYPES[r.type] || "website"} icon`, [cvIcon(r.type), "Automatic"], "btn"),
      choice("none", "No icon", [icon("image-off"), "No icon"], "btn")),
    h("div", { class: "icon-grid" }, Object.keys(S.icons || {}).map(k => choice(k, ICON_NAMES[k] || k, cvIcon(k), "icon-choice"))));
  p.hidden = false;
  placeUnder(p, anchor);
}
// web, email and phone addresses only ("" for javascript:, data: and the like)
const webAddress = l => { l = l.trim(); return /^(https?|mailto|tel):/i.test(l) ? l : /^[a-z][a-z0-9+.-]*:(?!\d)/i.test(l) ? "" : "https://" + l; };
function contactRows(arr) {
  const box = h("div", { class: "rows" });
  arr.forEach((r, i) => {
    const web = WEB_CONTACTS.includes(r.type), examples = CONTACT_EXAMPLES[r.type] || CONTACT_EXAMPLES.web;
    const sel = h("select", { class: "inp", "aria-label": "Contact type" },
      CONTACT_GROUPS.map(([group, types]) => h("optgroup", { label: group },
        Object.entries(types).map(([val, name]) => h("option", { value: val }, name)))));
    sel.value = r.type || "web";
    sel.addEventListener("change", () => { r.type = sel.value; if (!WEB_CONTACTS.includes(r.type)) delete r.link; changed(true); });
    const text = h("input", { class: "inp", placeholder: examples[0], "aria-label": web ? "Name shown in the CV" : "Contact" });
    text.value = r.text ?? "";
    // for email and phone the link comes from the text
    text.addEventListener("input", () => { r.text = text.value; if (!web) delete r.link; changed(); });
    bindBox(r, "text", text);
    if (S.focus === r) S.toFocus ??= text;
    const iconButton = h("button", { type: "button", class: "ico contact-icon", title: "The icon of this contact: click to choose another one",
      "aria-label": "Choose the icon", onclick: e => { e.stopPropagation(); iconMenu(e.currentTarget, r); } }, contactIcon(r));
    const contact = h("div", { class: "contact" + (r.hidden ? " is-hidden" : "") }, h("div", { class: "row" }, iconButton, sel, text, hideToggle(r),
      button("↑", "Move up", () => { move(arr, i, -1); changed(true); }, { disabled: i === 0 }),
      button("↓", "Move down", () => { move(arr, i, 1); changed(true); }, { disabled: i === arr.length - 1 }),
      button("✕", "Delete", () => remove(arr, i, "Contact deleted"), { cls: "danger" })));
    if (web) {
      const link = h("input", { class: "inp", placeholder: examples[1], "aria-label": "Link" });
      link.value = r.link ?? "";
      const test = h("a", { class: "ico", target: "_blank", rel: "noopener", title: "Open the link to check it" }, icon("external"));
      const updateTest = () => { const url = r.link ? webAddress(r.link) : ""; test.href = url || "#"; test.style.visibility = url ? "" : "hidden"; };
      link.addEventListener("input", () => { if (link.value.trim()) r.link = link.value.trim(); else delete r.link; updateTest(); changed(); });
      bindBox(r, "link", link);
      updateTest();
      contact.append(h("div", { class: "row link-row" }, h("span", { class: "mini" }, "Link"), link, test));
    }
    box.append(contact);
  });
  box.append(h("button", { type: "button", class: "add-btn",
    onclick: () => { const r = { type: "email" }; arr.push(r); S.focus = r; changed(true); } }, icon("plus"), "Add contact"));
  return box;
}

// expandable entries: experience, education, entries of extra sections. With a link, the title is clickable in the CV.
const LINK_PH = "Optional: https://… (the title becomes clickable)";
const ENTRY_TYPES = {
  experience: { title: "role", add: "Add experience", empty: "New experience", removed: "Experience deleted",
    fields: [["role", "Role", { wide: true }], ["organization", "Company / organisation"], ["location", "Location", { ph: "Optional" }],
             ["dates", "Dates", { ph: "e.g. 01/2025 – today" }], ["link", "Link", { ph: LINK_PH }],
             ["description", "Description", { desc: true }]] },
  education: { title: "title", add: "Add qualification", empty: "New qualification", removed: "Entry deleted",
    fields: [["title", "Title", { wide: true }], ["organization", "School / university"], ["location", "Location", { ph: "Optional" }],
             ["dates", "Dates", { ph: "e.g. 09/2021 – 10/2024" }], ["grade", "Grade", { ph: "Optional", links: true }],
             ["thesis", "Thesis", { wide: true, ph: "Optional", links: true }], ["link", "Link", { wide: true, ph: LINK_PH }],
             ["description", "Description", { desc: true }]] },
  entries: { title: "title", add: "Add entry", empty: "New entry", removed: "Entry deleted",
    fields: [["title", "Title", { wide: true }], ["organization", "Organisation / where", { ph: "Optional" }], ["dates", "Dates", { ph: "Optional" }],
             ["location", "Location", { ph: "Optional" }], ["link", "Link", { ph: LINK_PH }],
             ["description", "Description", { desc: true }]] },
};
function entryList(arr, kind, copyKey) {
  const cfg = ENTRY_TYPES[kind];
  const box = h("div", { class: "entries" },
    h("button", { type: "button", class: "add-btn",
      onclick: () => { const v = {}; arr.unshift(v); S.open.add(v); S.focus = v; changed(true); } }, icon("plus"), cfg.add));
  arr.forEach((v, i) => {
    const isOpen = S.open.has(v);
    const main = h("span", { class: "main-text" }), sub = h("span", { class: "sub" });
    const refresh = () => { main.textContent = v[cfg.title] || cfg.empty; sub.textContent = [v.organization, v.dates].filter(Boolean).join(" · "); };
    refresh();
    const head = h("div", { class: "summary", title: isOpen ? "Close" : "Open to edit",
        onclick: () => { isOpen ? S.open.delete(v) : S.open.add(v); render(); } },
      h("span", { class: "arrow" }, icon("chevron-right")), h("span", { class: "texts" }, main, sub),
      v.hidden ? h("span", { class: "hidden-tag", title: "Not in the CV: it stays here. The eye shows it again." }, icon("eye-off"), "Hidden") : null,
      hideToggle(v),
      h("span", { class: "actions" },
        button("↑", "Move up", () => { move(arr, i, -1); changed(true); }, { disabled: i === 0 }),
        button("↓", "Move down", () => { move(arr, i, 1); changed(true); }, { disabled: i === arr.length - 1 }),
        copyKey ? copyButton("the entry", l2 => copyEntry(copyKey, v, i, l2)) : null,
        button("✕", "Delete", () => remove(arr, i, cfg.removed), { cls: "danger" })));
    const el = h("div", { class: "entry" + (isOpen ? " open" : "") + (v.hidden ? " is-hidden" : "") }, head);
    if (isOpen) {
      el.append(h("div", { class: "grid entry-form" }, cfg.fields.map(([k, name, o = {}], n) => o.desc
        ? linesField(v, k, name, { desc: true, wide: true, hint: DESC_HINT, links: true, hide: true })
        : field(v, k, name, { ...o, then: refresh, focus: n === 0 && S.focus === v }))));
    }
    box.append(el);
  });
  return box;
}
function copyEntry(key, v, i, l2) {
  const arr = list(L(l2).data, key);
  const copy = structuredClone(v);
  arr.splice(Math.min(i, arr.length), 0, copy);
  S.open.add(copy);
  rebase(l2, arr);
  changed(false, l2);
  toast(baseOf(l2) === baseOf(S.language) ? `Copied to ${languageName(l2)}.` : `Copied to ${languageName(l2)}: remember to translate it.`);
}

export {
  button, card, closeMenu, contactRows, copyButton, ENTRY_TYPES, entryList, field, linesField, rows,
  sectionTitle, smallInput, webAddress, wrap
};
