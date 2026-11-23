// The cards of the form: one per section, fixed or added, with their buttons.
import { $, S } from "./state.js";
import { icon } from "./icons.js";
import { ask, h, L, list, move, table, toast } from "./util.js";
import { hasContent, inLanguage, isHidden, isSide, keyOf, setHidden, setSide } from "./changes.js";
import { changed, isObj, keepSection, languageName, translateSection, untranslated } from "./sync.js";
import {
   button, card, contactRows, copyButton, entryList, field, linesField, rows, sectionTitle, smallInput,
} from "./fields.js";
import { copySection, sectionIcon, sectionName } from "./nav.js";
import { namesDialog } from "./names.js";

// ---------------------------------------------------------------- cards
const cardIcon = name => h("span", { class: "card-icon" }, icon(name));
// the header of the CV: name and headline, contacts, personal details (these two are sections too:
// in the sidebar, or hidden, like the others)
function headerCards(d) {
  const p = table(d, "person"), order = L().order, at = k => order.findIndex(o => o.fixed === k);
  const flags = k => [sideToggle(order[at(k)]), h("span", { class: "actions" }, hideButton(order[at(k)]),
    button("✕", `Remove this section from the CV${inLanguage()}`, () => removeSection(at(k)), { cls: "danger" }))];
  const contacts = at("contacts") < 0 ? null : card([cardIcon("at"), h("span", { class: "fixed-title" }, "Contacts"), flags("contacts")], [
    h("small", { class: "hint" }, "Choose the kind of contact: its icon and its link follow it (click the icon to choose another one). ",
      "For pages such as LinkedIn or a website write the name to show and, below it, the link. The eye hides one from the CV without deleting it."),
    contactRows(list(d, "contacts"))]);
  const details = at("details") < 0 ? null : card([cardIcon("id"), h("span", { class: "fixed-title" }, "Personal details"), flags("details")], [
    h("small", { class: "hint" }, "Short facts such as date of birth, nationality or driving licence. The eye hides one from the CV without deleting it."),
    rows(list(d, "details"), [["label", "e.g. Date of birth"], ["value", "Value"]], "Add detail", { removed: "Detail deleted", links: ["value"] })]);
  if (contacts) contacts.id = "card-contacts";
  if (details) details.id = "card-details";
  // contacts or personal details removed: they can come back here
  const gone = ["contacts", "details"].filter(k => at(k) < 0);
  return [
    card([cardIcon("user"), h("span", { class: "fixed-title" }, "Name and headline")],
      h("div", { class: "grid" }, field(p, "first_name", "First name"), field(p, "last_name", "Last name"),
        field(p, "headline", "Line under the name", { wide: true, ph: "e.g. Data engineer · leave empty to remove it" }))),
    contacts, details,
    gone.length ? h("div", { class: "add-parts" }, "Removed from the CV:", gone.map(k => h("button", { type: "button", class: "link",
      onclick: () => restoreSection(k, order.length) }, "+ " + (k === "contacts" ? "Contacts" : "Personal details")))) : null];
}
// "◧ Sidebar" / "Main": where the section goes. The CV has a sidebar, in every style,
// as soon as one section is in it; when none is, there is no sidebar.
function sideToggle(o) {
  const side = isSide(o);
  return h("button", { type: "button", class: "side-toggle" + (side ? " on" : ""),
    title: side ? "In the sidebar. Click to move it to the main column."
                : "In the main column. Click to move it to the sidebar (a sidebar appears in every style).",
    onclick: e => { e.stopPropagation(); setSide(o, !side); } }, icon("sidebar"), side ? "Sidebar" : "Main");
}
function hideButton(o) {
  const hidden = isHidden(o);
  return button([icon(hidden ? "eye-off" : "eye"), hidden ? "Show" : "Hide"],
                hidden ? "Show this section in the CV again" : "Hide this section from the CV (its content is kept)",
                () => setHidden(o, !hidden), { cls: "text" });
}
const hasSidebar = () => L().order.some(o => isSide(o) && !isHidden(o));
// the "sidebar" tick: on = a sidebar in every style with the suggested (or previous) sections, off = everything in the main column
function setSidebar(on) {
  const order = L().order;
  if (!on) {
    S.lastSide = order.filter(isSide).map(keyOf);
    for (const o of order) { if (o.fixed) o.side = false; else delete o.section.column; }
  } else {
    const keys = S.lastSide?.length ? S.lastSide : S.sideSuggested.map(k => "f:" + k);
    for (const o of order) if (keys.includes(keyOf(o))) { if (o.fixed) o.side = true; else o.section.column = "side"; }
  }
  changed(true);
  toast(on ? "Sidebar on, in every style: move sections in or out of it with the sidebar button next to each section, in the list on the left."
           : "No sidebar: every section is in the main column, in every style.");
}
// header controls of every section card: move, sidebar, hide/show, delete, and for extra sections copy
function sectionCard(o, idx, title, body, kind) {
  const order = L().order, hidden = isHidden(o);
  const el = card([cardIcon(sectionIcon(o)), title, kind ? h("span", { class: "kind" }, kind) : null, sideToggle(o), h("span", { class: "actions" },
      button("↑", "Move up", () => { move(order, idx, -1); changed(true); }, { disabled: idx === 0 }),
      button("↓", "Move down", () => { move(order, idx, 1); changed(true); }, { disabled: idx === order.length - 1 }),
      hideButton(o),
      o.section ? copyButton("this section", l2 => copySection(o, l2)) : null,
      button("✕", o.fixed ? `Remove this section from the CV${inLanguage()} (Add section brings it back, empty)` : `Delete the section${inLanguage()}`,
             () => removeSection(idx), { cls: "danger" }))],
    hidden ? h("div", { class: "hidden-note" }, icon("eye-off"), h("span", { style: "flex: 1" }, "This section is hidden: it does not appear in the CV. Its content is kept."),
               h("button", { type: "button", class: "btn", onclick: () => setHidden(o, false) }, "Show it again")) : body);
  el.classList.toggle("hidden-section", hidden);
  el.id = "section-" + idx;
  return el;
}
// deletes a section in every language (Undo puts it back). A fixed section (experience, skills...) is taken out of
// the CV: its content is deleted when you save, and "Add section" can bring the section back.
async function removeSection(idx) {
  const order = L().order, o = order[idx], l = S.language;
  if (!o) return;
  const name = sectionName(o), others = inLanguage(l) ? "The other languages are not changed." : "";
  if ((o.fixed || hasContent(o.section)) && !(await ask({ title: `${o.fixed ? "Remove" : "Delete"} the section “${name}”?`,
      text: o.fixed
        ? [`It is taken out of the CV${inLanguage(l)}, with its content (deleted when you press Save). ` +
           "“Add section” can bring it back, empty.", others, "To keep it but not show it in the CV, use “Hide” instead."]
        : [`It is deleted from the CV${inLanguage(l)}, with its content.`, others, "To keep it but not show it in the CV, use “Hide” instead."],
      ok: o.fixed ? "Remove" : "Delete", danger: true }))) return;
  const at = order.indexOf(o);
  if (at < 0) return;
  order.splice(at, 1);
  changed(true, l);
  toast(o.fixed ? `“${name}” removed from the CV${inLanguage(l)}. Its content is deleted when you save.`
                : `“${name}” deleted${inLanguage(l)}.`, { undo: () => { order.splice(at, 0, o); changed(true, l); } });
}
// a fixed section removed earlier comes back at position pos (empty, once the removal was saved)
function restoreSection(k, pos) {
  $("#add-menu").hidden = true;
  if (L().order.some(o => o.fixed === k)) return;
  L().order.splice(pos, 0, { fixed: k, hidden: false, side: false });
  const inHeader = k === "contacts" || k === "details";
  S.section = inHeader ? "header" : "f:" + k;
  changed(true);
  if (inHeader) $("#card-" + k)?.scrollIntoView({ behavior: "smooth", block: "start" });
}
function fixedCard(o, idx, d) {
  const k = o.fixed, labels = table(d, "labels"), p = table(d, "person");
  return sectionCard(o, idx, sectionTitle(labels, k), fixedBody(k, d, labels, p));
}
function fixedBody(k, d, labels, p) {
  if (k === "profile")
    return field(p, "profile", "", { multi: true, links: true, hint: "You can use **bold**, *italic* and links." });
  if (k === "about_me")
    return field(p, "about_me", "", { multi: true, links: true, hint: "A few lines about you. You can use **bold**, *italic* and links." });
  const rename = what => h("button", { type: "button", class: "link", style: "justify-self: start; display: inline-flex; gap: 6px; align-items: center",
                                     onclick: namesDialog }, icon("building"), `Rename a ${what} everywhere in this CV…`);
  if (k === "experience") return [entryList(list(d, "experience"), "experience", "experience"), rename("company")];
  if (k === "education") return [entryList(list(d, "education"), "education", "education"), rename("school or university")];
  if (k === "skills") {
    const skills = table(d, "skills");
    return [
      h("div", { class: "subtitle" }, smallInput(labels, "languages")),
      rows(list(d, "languages"), [["language", "Language"], ["level", "Level (e.g. C1)"]], "Add language", { removed: "Language deleted", links: ["level"] }),
      h("div", { class: "subtitle" }, smallInput(labels, "digital_skills")),
      linesField(skills, "digital", "", { hint: "One per line. The eye of each one, below, hides it from the CV.", links: true, hide: true }),
      h("div", { class: "subtitle" }, smallInput(labels, "soft_skills")),
      linesField(skills, "soft", "", { hint: "One per line. The eye of each one, below, hides it from the CV.", links: true, hide: true })];
  }
  if (k === "interests")
    return field(table(d, "interests"), "text", "", { multi: true, links: true, hint: "Write normally: an empty line starts a new paragraph." });
  return null;
}
// the kinds of content an extra section can hold (any combination)
const PARTS = {
  text:    { name: "Free text", hint: "Paragraphs, like a profile or a cover note", empty: () => "" },
  list:    { name: "Bullet list", hint: "One point per line", empty: () => [] },
  entries: { name: "Entries with dates", hint: "Like experience: title, where, dates, description", empty: () => [{}] },
  tags:    { name: "Tags", hint: "Short words in a row, e.g. tools, hobbies, certifications", empty: () => [] },
  rows:    { name: "Table", hint: "Name → value rows, e.g. Driving licence → B", empty: () => [{}] },
};
const sectionKind = s => Object.keys(PARTS).filter(k => k in s).map(k => PARTS[k].name.toLowerCase()).join(" + ");
function partEditor(s, k) {
  if (k === "text") return field(s, "text", "", { multi: true, links: true, hint: "An empty line starts a new paragraph. **bold**, *italic* and links work." });
  if (k === "list") return linesField(s, "list", "", { hint: "One point per line.", links: true, hide: true });
  if (k === "entries") return entryList(list(s, "entries"), "entries", null);
  if (k === "tags") return linesField(s, "tags", "", { hint: "One per line. They appear in a row (as chips in the Creative and Modern styles).", links: true, hide: true });
  if (k === "rows") return rows(list(s, "rows"), [["label", "Name, e.g. Driving licence"], ["value", "Value, e.g. B"]], "Add row", { removed: "Row deleted", links: ["value"] });
}
function extraCard(o, idx) {
  const s = o.section;
  const title = sectionTitle(s, "title", "Section title (e.g. Projects)");
  if (S.focus === s) S.toFocus ??= title;
  const body = Object.keys(PARTS).filter(k => k in s).map(k => h("div", { class: "part" },
    h("div", { class: "part-head" }, PARTS[k].name,
      button("✕", `Remove the ${PARTS[k].name.toLowerCase()} from this section`, async () => {
        const v = s[k], l = S.language;
        const filled = Array.isArray(v) ? v.some(x => (isObj(x) ? Object.values(x).some(y => String(y ?? "").trim()) : String(x ?? "").trim()))
                                        : !!String(v ?? "").trim();
        if (filled && !(await ask({ title: `Remove the ${PARTS[k].name.toLowerCase()} from this section?`,
            text: ["What you wrote in it is deleted."], ok: "Remove", danger: true }))) return;
        const before = s[k]; delete s[k];
        changed(true, l);
        toast(`${PARTS[k].name} removed`, { undo: () => { s[k] = before; changed(true, l); } });
      }, { cls: "danger" })),
    partEditor(s, k)));
  const missing = Object.keys(PARTS).filter(k => !(k in s));
  if (missing.length) body.push(h("div", { class: "add-parts" }, "Also add here:",
    missing.map(k => h("button", { type: "button", class: "link", onclick: () => {
      s[k] = PARTS[k].empty();
      if (k === "entries") { S.open.add(s.entries[0]); S.focus = s.entries[0]; }
      changed(true);
    } }, "+ " + PARTS[k].name.toLowerCase()))));
  const todo = untranslated(s);
  if (todo) body.unshift(h("div", { class: "translate-banner" },
    h("span", {}, todo.empty ? `This section is only in ${languageName(todo.from)}.` : `This section is still as in ${languageName(todo.from)}.`,
      ` Translate it into ${languageName(S.language)}?`),
    h("button", { type: "button", class: "btn primary", onclick: e => translateSection(s, todo.from, e.currentTarget) }, "Translate"),
    h("button", { type: "button", class: "link", onclick: () => keepSection(s, todo) }, todo.empty ? "Not now" : "Keep it as it is")));
  return sectionCard(o, idx, title, body, sectionKind(s) || "empty");
}

export {
  cardIcon, extraCard, fixedCard, hasSidebar, headerCards, PARTS, restoreSection, setSidebar
};
