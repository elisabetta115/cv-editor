// The list of sections on the left, the page of the form on screen, adding a section.
import { $, S } from "./state.js";
import { icon } from "./icons.js";
import { ask, fill, h, L, table, toast } from "./util.js";
import {
   baseOf, copyFlags, hasContent, inLanguage, isHidden, isSide, keyOf, newId, privacyHidden, privacyRemoved,
   removedFixed, removePrivacy, restorePrivacy, setHidden, setPrivacyHidden, setSide,
} from "./changes.js";
import { changed, languageName, rebase, updateSyncBar } from "./sync.js";
import { button, card, field } from "./fields.js";
import { cardIcon, extraCard, fixedCard, headerCards, PARTS, restoreSection } from "./cards.js";
import { namesDialog } from "./names.js";
import { F, findOpen, refreshFind, unmark } from "./find.js";
import { signatureCard } from "./photo.js";

// ---------------------------------------------------------------- the list of sections (left)
// Click a section to edit it; drag to reorder; the small buttons put it in the sidebar or hide it.
// Contacts and personal details are edited in the header. Changes apply to every language.
const SECTION_ICONS = { contacts: "at", details: "id", profile: "text", about_me: "smile", experience: "briefcase",
                        education: "cap", skills: "star", interests: "heart" };
const sectionIcon = o => (o.fixed ? SECTION_ICONS[o.fixed] || "text" : "layers");
const sectionName = o => (o.fixed ? table(L().data, "labels")[o.fixed] || o.fixed : o.section.title || "Untitled section");
const OTHER_PAGES = { header: "Header", privacy: "Privacy note", signature: "Signature", labels: "Other labels" };
// what the middle column can show, in order: the header, the sections, the privacy note and the labels
const navKeys = () => ["header", ...L().order.filter(o => o.fixed !== "contacts" && o.fixed !== "details").map(keyOf),
                        ...(privacyRemoved() ? [] : ["privacy"]), "signature", "labels"];
function currentKey() {
  const keys = navKeys();
  if (!keys.includes(S.section)) S.section = keys[Math.min(S.sectionPos ?? 0, keys.length - 1)] || "header";  // e.g. deleted
  S.sectionPos = keys.indexOf(S.section);
  return S.section;
}
function select(key, then) {
  $("#add-menu").hidden = true;
  if (S.section !== key) { S.section = key; render(); }
  then?.();
}
let navDrag = null;
// hide: {hidden, toggle} for a part of the CV that is not a section (the privacy note)
function navItem({ name, iconName, current = false, onclick, o = null, i = -1, key = o && keyOf(o), hide = null }) {
  const found = key && findOpen() && F.counts.get(key);  // how many times the words searched are in it
  const li = h("li", { class: "nav-item" + (current ? " current" : "") + ((o ? isHidden(o) : hide?.hidden) ? " is-hidden" : "") },
    h("button", { type: "button", class: "nav-link", title: name, onclick, "aria-current": current ? "true" : null },
      icon(iconName), h("span", { class: "nav-name" }, name),
      found ? h("span", { class: "nav-count", title: `Found ${found === 1 ? "once" : found + " times"} here` }, found) : null,
      o && isSide(o) ? h("span", { class: "nav-badge", title: "In the sidebar" }, icon("sidebar")) : null),
    o ? h("span", { class: "nav-actions" },
      button(icon("sidebar"), isSide(o) ? "In the sidebar: move it to the main column" : "Move it to the sidebar (a sidebar appears in every style)",
             () => setSide(o, !isSide(o)), { cls: isSide(o) ? "on" : "" }),
      button(icon(isHidden(o) ? "eye-off" : "eye"), isHidden(o) ? "Hidden: show it in the CV again" : "Hide it from the CV (its content is kept)",
             () => setHidden(o, !isHidden(o))))
      : hide ? h("span", { class: "nav-actions" },
        button(icon(hide.hidden ? "eye-off" : "eye"), hide.hidden ? "Hidden: show it in the CV again" : "Hide it from the CV (its text is kept)",
               hide.toggle)) : null);
  if (o) Object.assign(li, { draggable: true,
    ondragstart: e => { navDrag = i; e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(i)); li.classList.add("dragging"); },
    ondragend: () => li.classList.remove("dragging"),
    ondragover: e => { e.preventDefault(); li.classList.add("drop"); },
    ondragleave: () => li.classList.remove("drop"),
    ondrop: e => {
      e.preventDefault(); li.classList.remove("drop");
      const order = L().order;
      if (navDrag === null || navDrag === i) return;
      const [moved] = order.splice(navDrag, 1); order.splice(i, 0, moved); navDrag = null;
      changed(true);
    } });
  return li;
}
function renderNav() {
  const cur = currentKey(), order = L().order;
  const jump = id => () => select("header", () => $(id)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  fill($("#sections"),
    h("div", {}, h("div", { class: "nav-title" }, "Sections"),
      h("ul", { class: "nav-group" },
        navItem({ name: "Header", iconName: "user", current: cur === "header", onclick: () => select("header"), key: "header" }),
        order.map((o, i) => navItem({ name: sectionName(o), iconName: sectionIcon(o), o, i,
          current: cur === keyOf(o), onclick: o.fixed === "contacts" || o.fixed === "details" ? jump("#card-" + o.fixed) : () => select(keyOf(o)) }))),
      h("button", { type: "button", class: "btn ghost nav-add", title: "Add a section (projects, certificates, volunteering…)",
                    onclick: e => { e.stopPropagation(); addMenu(e.currentTarget); } }, icon("plus"), h("span", {}, "Add section"))),
    h("div", {}, h("div", { class: "nav-title" }, "More"),
      h("ul", { class: "nav-group" },
        privacyRemoved() ? null : navItem({ name: "Privacy note", iconName: "shield", current: cur === "privacy", onclick: () => select("privacy"), key: "privacy",
                  hide: { hidden: privacyHidden(), toggle: () => setPrivacyHidden(!privacyHidden()) } }),
        navItem({ name: "Signature", iconName: "pen", current: cur === "signature", onclick: () => select("signature"), key: "signature" }),
        navItem({ name: "Other labels", iconName: "tag", current: cur === "labels", onclick: () => select("labels"), key: "labels" }),
        navItem({ name: "Company & school names", iconName: "building", onclick: namesDialog }))),
    h("p", { class: "nav-foot" }, "Drag the sections to change their order.",
      Object.keys(S.languages).length > 1 ? ` These sections are those of ${languageName(S.language)}: what you change here ` +
        "does not change the other languages (the copy button of a section brings it to another one)." : ""));
}
// "Add section": what the new section contains; it goes after the section on screen
function addMenu(anchor) {
  const p = $("#add-menu");
  if (!p.hidden) { p.hidden = true; return; }
  for (const x of document.querySelectorAll(".panel")) x.hidden = true;
  const order = L().order, at = order.findIndex(o => keyOf(o) === S.section);
  const pos = at >= 0 ? at + 1 : order.length;
  const gone = [...removedFixed(), ...(privacyRemoved() ? ["privacy"] : [])], labels = table(L().data, "labels");
  fill(p, h("div", { class: "panel-head" }, h("strong", {}, "Add a section"), button("✕", "Close", () => (p.hidden = true))),
    h("small", { class: "hint" }, "What should it contain? You can add more kinds of content to it later."),
    h("div", { class: "kinds" }, Object.entries(PARTS).map(([kind, x]) => h("button", { type: "button", class: "btn",
      onclick: () => { p.hidden = true; newSection(pos, kind); } }, preview(kind), h("strong", {}, x.name), h("small", {}, x.hint)))),
    gone.length ? h("small", { class: "hint" }, "Or bring back a section you removed:") : null,
    gone.length ? h("div", { class: "add-parts" }, gone.map(k => k === "privacy"
      ? h("button", { type: "button", class: "btn", onclick: restorePrivacy }, icon("shield"), "Privacy note")
      : h("button", { type: "button", class: "btn", onclick: () => restoreSection(k, pos) }, icon(SECTION_ICONS[k] || "text"), labels[k] || k))) : null);
  p.hidden = false;
  const r = anchor.getBoundingClientRect();
  Object.assign(p.style, { left: Math.min(r.right + 8, innerWidth - p.offsetWidth - 12) + "px",
                           top: Math.max(66, Math.min(r.top - 40, innerHeight - p.offsetHeight - 12)) + "px" });
}
// copies the content of an extra section into the same section of another language
async function copySection(o, l2) {
  const from = S.language, src = L(from).order, dst = L(l2).order;
  let target = dst.find(x => x.section && x.section.id === o.section.id);
  if (target && hasContent(target.section) && !(await ask({ title: `Replace “${sectionName(o)}” in ${languageName(l2)}?`,
      text: [`The section is already in ${languageName(l2)}: what it holds there is replaced by the ${languageName(from)} content.`],
      ok: "Replace", danger: true }))) return;
  if (!target) {  // not in that language yet: it goes after the section that comes before it here
    let at = 0;
    for (let j = src.indexOf(o) - 1; j >= 0; j--) {
      const k = dst.findIndex(x => keyOf(x) === keyOf(src[j]));
      if (k >= 0) { at = k + 1; break; }
    }
    target = { section: { id: o.section.id } };
    copyFlags(o, target);
    dst.splice(at, 0, target);
  }
  for (const k of Object.keys(target.section)) if (!["id", "hidden", "column"].includes(k)) delete target.section[k];
  for (const [k, v] of Object.entries(structuredClone(o.section))) if (!["id", "hidden", "column"].includes(k)) target.section[k] = v;
  const translate = baseOf(l2) !== baseOf(from);
  if (translate) target.section.copied_from = from; else delete target.section.copied_from;
  rebase(l2, target.section);
  changed(true, l2);
  toast(translate ? `“${sectionName(o)}” copied to ${languageName(l2)}: there you can translate it, by hand or automatically.`
                  : `“${sectionName(o)}” copied to ${languageName(l2)}.`);
}
// a tiny drawing of how each kind of content looks
function preview(kind) {
  const line = (w, b) => h("i", { class: b ? "b" : "", style: `width:${w}%` });
  const row = (...c) => h("span", { class: "r" }, c);
  const parts = {
    text: [line(100), line(94), line(70)],
    list: [1, 2, 3].map(n => row(h("b", { class: "dot" }), line(60 + n * 8))),
    entries: [row(line(55, true), h("em", { class: "pill" })), line(40), line(85)],
    tags: [row(h("em", { class: "chip" }), h("em", { class: "chip" }), h("em", { class: "chip" }))],
    rows: [1, 2, 3].map(n => row(line(28, true), line(40 + n * 6))),
  };
  return h("span", { class: "mp", "aria-hidden": "true" }, parts[kind]);
}
function newSection(pos, kind) {
  const s = { id: newId(), title: "", [kind]: PARTS[kind].empty() };
  if (kind === "entries") S.open.add(s.entries[0]);
  L().order.splice(pos, 0, { section: s });
  S.focus = s;
  S.section = "s:" + s.id;
  changed(true);
}

// the section chosen in the list, with "previous" and "next" below it
function render() {
  const form = $("#form"), d = L().data, key = currentKey(), y = form.scrollTop, same = key === S.rendered;
  S.toFocus = null;
  unmark();
  if (findOpen() && (F.dirty || F.where !== L())) refreshFind();
  renderNav();
  let content;
  if (key === "header") content = headerCards(d);
  else if (key === "privacy") {
    const hidden = privacyHidden();
    content = card([cardIcon("shield"), h("span", { class: "fixed-title" }, "Privacy note"), h("span", { class: "actions" },
        button([icon(hidden ? "eye-off" : "eye"), hidden ? "Show" : "Hide"],
               hidden ? "Show the privacy note in the CV again" : "Hide the privacy note from the CV (its text is kept)",
               () => setPrivacyHidden(!hidden), { cls: "text" }),
        button("✕", `Delete the privacy note${inLanguage()} (Add section brings it back, empty)`, removePrivacy, { cls: "danger" }))], [
      hidden ? h("div", { class: "hidden-note" }, icon("eye-off"), h("span", { style: "flex: 1" }, "The privacy note is hidden: it does not appear in the CV. Its text is kept."),
                 h("button", { type: "button", class: "btn", onclick: () => setPrivacyHidden(false) }, "Show it again")) : null,
      h("small", { class: "hint" }, "Printed in small letters at the end of the CV, e.g. the consent to process your personal data. ",
        "Hide it to keep the text without showing it (e.g. for countries that do not use it); the bin deletes it."),
      field(table(d, "privacy"), "text", "", { multi: true, links: true })]);
    content.classList.toggle("hidden-section", hidden);
  }
  else if (key === "signature") content = signatureCard(d);
  else if (key === "labels") {
    const labels = table(d, "labels");
    content = card([cardIcon("tag"), h("span", { class: "fixed-title" }, "Other labels")], [
      h("small", { class: "hint" }, "Words the CV uses besides the section titles (change those by clicking the title of each section)."),
      h("div", { class: "grid" }, field(labels, "contacts", "“Contacts” title (when in the sidebar)"),
        field(labels, "grade", "Word for the grade"), field(labels, "thesis", "Word for the thesis"))]);
  } else {
    const i = L().order.findIndex(o => keyOf(o) === key), o = L().order[i];
    content = o.fixed ? fixedCard(o, i, d) : extraCard(o, i);
  }
  fill(form, h("div", { id: "sync-bar", class: "sync-bar", hidden: true, role: "status" }), h("div", { class: "pane" }, content, pager(key)));
  updateSyncBar();
  form.scrollTop = same ? y : 0;
  S.rendered = key;
  if (S.toFocus) {
    const el = S.toFocus;
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block: "center", behavior: "smooth" });
  }
  S.focus = null;
}
function pager(key) {
  const keys = navKeys(), i = keys.indexOf(key);
  const name = k => OTHER_PAGES[k] || sectionName(L().order.find(o => keyOf(o) === k));
  return h("div", { class: "pager" },
    i > 0 ? h("button", { type: "button", class: "btn ghost", onclick: () => select(keys[i - 1]) }, icon("arrow-left"), h("span", {}, name(keys[i - 1]))) : h("span"),
    i < keys.length - 1 ? h("button", { type: "button", class: "btn", onclick: () => select(keys[i + 1]) }, h("span", {}, name(keys[i + 1])), icon("arrow-right")) : h("span"));
}

export {
  copySection, navKeys, render, renderNav, sectionIcon, sectionName
};
