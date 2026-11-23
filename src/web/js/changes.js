// Changes to the content: hidden and sidebar sections, the privacy note, the languages of a CV.
import { $, S } from "./state.js";
import { ask, L, table, toast } from "./util.js";
import { changed, languageName, rebase } from "./sync.js";

// ---------------------------------------------------------------- changes
// Every section is saved in the order you see it; fixed ones as {builtin: "experience"}
// (with column = "side" / "main" only when it differs from where that section usually goes).
// The fixed sections taken out of the CV come last, as {builtin: "interests", removed: true}.
function sync(l) {
  const x = L(l);
  x.data.sections = x.order.map(o => {
    if (o.fixed) {
      const entry = { builtin: o.fixed };
      if (o.hidden) entry.hidden = true;
      if (o.side) entry.column = "side";
      return entry;
    }
    delete o.section.after;
    return o.section;
  });
  for (const k of removedFixed(l)) x.data.sections.push({ builtin: k, removed: true });
}
const removedFixed = (l = S.language) => S.fixedSections.filter(k => !L(l).order.some(o => o.fixed === k));
const isHidden = o => (o.fixed ? !!o.hidden : !!o.section.hidden);
const isSide = o => (o.fixed ? !!o.side : o.section.column === "side");
function setHidden(o, hidden) {
  if (o.fixed) o.hidden = hidden;
  else if (hidden) o.section.hidden = true;
  else delete o.section.hidden;
  changed(true);
}
function setSide(o, side) {
  if (o.fixed) o.side = side;
  else if (side) o.section.column = "side";
  else delete o.section.column;
  changed(true);
}
// the privacy note can be hidden too (privacy.hidden = true): its text is kept, the CV does not show it
const privacyHidden = () => !!table(L().data, "privacy").hidden;
// ...or deleted (privacy.removed = true): its text goes, the page leaves the list, "Add section" brings it back
const privacyRemoved = (l = S.language) => !!table(L(l).data, "privacy").removed;
async function removePrivacy() {
  const l = S.language, pr = table(L(l).data, "privacy"), before = structuredClone(pr);
  if (String(pr.text ?? "").trim() && !(await ask({ title: "Delete the privacy note?",
      text: [`Its text is deleted from the CV${inLanguage(l)}.`, inLanguage(l) ? "The other languages are not changed." : "",
             "“Add section” can bring it back, empty. To keep the text but not show it, use “Hide” instead."],
      ok: "Delete", danger: true }))) return;
  for (const k of Object.keys(pr)) delete pr[k];
  pr.removed = true;
  rebase(l, pr);  // taken out here only: nothing to bring to the other languages
  changed(true, l);
  toast(`Privacy note deleted${inLanguage(l)}.`, { undo: () => {
    for (const k of Object.keys(pr)) delete pr[k];
    Object.assign(pr, before); rebase(l, pr); changed(true, l);
  } });
}
function restorePrivacy() {
  $("#add-menu").hidden = true;
  delete table(L().data, "privacy").removed;
  S.section = "privacy";
  changed(true);
}
function setPrivacyHidden(hidden) {
  const pr = table(L().data, "privacy");
  if (hidden) pr.hidden = true; else delete pr.hidden;
  changed(true);
}
const newId = () => "s" + Math.random().toString(36).slice(2, 9);
const keyOf = o => (o.fixed ? "f:" + o.fixed : "s:" + (o.section.id ||= newId()));
function copyFlags(from, to) {
  if (from.fixed) { to.hidden = from.hidden; to.side = from.side; return; }
  for (const k of ["hidden", "column"]) { if (k in from.section) to.section[k] = from.section[k]; else delete to.section[k]; }
}
// Every language has its own sections: what you add, move, hide, put in the sidebar or delete in one language
// stays there (the copy button of a section brings it to another language). Another version in a language
// ("English (Ireland)", code en-ireland) is the CV changed for another country or job, in the same language.
const isVersion = l => l.includes("-");
const baseOf = l => l.split("-")[0];
// the other languages the bar at the top offers to bring your changes to (none for another version)
const partners = l => (isVersion(l) ? [] : Object.keys(S.languages).filter(x => x !== l && !isVersion(x)));
// " in English" when the CV has more languages: where a change happens
const inLanguage = (l = S.language) => (Object.keys(S.languages).length > 1 ? ` in ${languageName(l)}` : "");
// When the CV is opened: give the extra sections an id. Sections without one are paired by position when every
// language has the same number of them: the same section in each language (to bring changes, to translate it).
function tagSections() {
  const codes = Object.keys(S.languages).filter(l => !isVersion(l));
  const untagged = codes.map(l => L(l).order.filter(o => o.section && !o.section.id));
  if (codes.length && untagged.every(u => u.length === untagged[0].length))
    untagged[0].forEach((_, i) => { const id = newId(); untagged.forEach(u => (u[i].section.id = id)); });
  for (const l of Object.keys(S.languages)) for (const o of L(l).order) keyOf(o);
}
const hasContent = s => !!(s.title || s.text || s.list?.length || s.tags?.length || s.entries?.some(e => Object.keys(e).length)
                          || s.rows?.some(r => Object.keys(r).length));

export {
  baseOf, copyFlags, hasContent, inLanguage, isHidden, isSide, isVersion, keyOf, newId, partners, privacyHidden,
  privacyRemoved, removedFixed, removePrivacy, restorePrivacy, setHidden, setPrivacyHidden, setSide, sync,
  tagSections
};
