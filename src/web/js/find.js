// Find and replace in the whole CV.
import { $, CONTACT_TYPES, S, WEB_CONTACTS } from "./state.js";
import { fill, h, L, toast } from "./util.js";
import { isHidden, keyOf, removedFixed } from "./changes.js";
import { changed, isObj, languageName, short } from "./sync.js";
import { ENTRY_TYPES } from "./fields.js";
import { PARTS } from "./cards.js";
import { navKeys, render, renderNav, sectionName } from "./nav.js";
import { TEXT_LINK } from "./links.js";

// ---------------------------------------------------------------- find and replace
// Ctrl+F (or Find, in the top bar) looks for words in every box of the CV in the language on screen, in the order of
// the form. Enter goes from one to the next: its section opens (and its entry), and the words are marked in their box.
// Replace changes the words marked and goes to the next ones; Replace all changes every one (Undo in the message).
// Link addresses are left out unless you ask for them, so that replacing a word does not break a link.
const F = { query: "", matchCase: false, words: false, links: false,
            spots: [], matches: [], current: -1, counts: new Map(), inLinks: 0,
            where: null, dirty: false, shown: false, opened: null };
const findOpen = () => !$("#find").hidden;
const boxes = new WeakMap();  // object -> { key: the box of the form that edits object[key] }
function bindBox(obj, k, el) { let b = boxes.get(obj); if (!b) boxes.set(obj, b = {}); b[k] = el; }
const boxOf = (obj, k) => { const el = boxes.get(obj)?.[k]; return el?.isConnected ? el : null; };
const textOf = v => (Array.isArray(v) ? v.join("\n") : typeof v === "string" ? v : "");  // a list: one item per line, as in its box
// every text of the CV in this language, in the order of the form: the page that shows it, its name, its entry
function findSpots() {
  const d = L().data, out = [];
  const obj = (o, k) => (isObj(o?.[k]) ? o[k] : {}), items = (o, k) => (Array.isArray(o?.[k]) ? o[k].filter(isObj) : []);
  const labels = obj(d, "labels"), p = obj(d, "person");
  const add = (o, k, page, place, x = {}) => {
    const v = o[k];
    if (typeof v === "string" || (Array.isArray(v) && v.every(t => typeof t === "string")))
      out.push({ obj: o, k, page, place, nav: x.nav || page, entry: x.entry || null, hidden: !!x.hidden, address: k === "link" });
  };
  const entries = (arr, kind, page, name, hidden) => {
    const cfg = ENTRY_TYPES[kind];
    for (const v of arr) for (const [k, label] of cfg.fields)
      add(v, k, page, `${name} › ${short(v[cfg.title] || cfg.empty, 40)} › ${label}`, { entry: v, hidden });
  };
  add(p, "first_name", "header", "Header › First name");
  add(p, "last_name", "header", "Header › Last name");
  add(p, "headline", "header", "Header › Line under the name");
  const gone = removedFixed();  // contacts and personal details taken out of the CV are not on screen
  for (const r of gone.includes("contacts") ? [] : items(d, "contacts")) {
    const name = "Contacts › " + (CONTACT_TYPES[r.type] || "Website"), x = { nav: "f:contacts" };
    add(r, "text", "header", name, x);
    if (WEB_CONTACTS.includes(r.type)) add(r, "link", "header", name + " › Link", x);
  }
  for (const r of gone.includes("details") ? [] : items(d, "details")) {
    add(r, "label", "header", "Personal details › Name", { nav: "f:details" });
    add(r, "value", "header", "Personal details › " + short(r.label || "Value", 30), { nav: "f:details" });
  }
  for (const o of L().order) {
    if (o.fixed === "contacts" || o.fixed === "details") continue;
    const page = keyOf(o), name = sectionName(o), hidden = isHidden(o), x = { hidden };  // a hidden section shows only its title
    if (o.section) {
      const s = o.section;
      add(s, "title", page, name + " › Title");
      for (const part of Object.keys(PARTS).filter(k => k in s)) {
        if (part === "entries") entries(items(s, "entries"), "entries", page, name, hidden);
        else if (part === "rows") for (const r of items(s, "rows")) {
          add(r, "label", page, `${name} › Table › Name`, x);
          add(r, "value", page, `${name} › ${short(r.label || "Table", 30)}`, x);
        }
        else add(s, part, page, `${name} › ${PARTS[part].name}`, x);
      }
      continue;
    }
    const k = o.fixed;
    add(labels, k, page, name + " › Title");
    if (k === "profile" || k === "about_me") add(p, k, page, name, x);
    else if (k === "experience" || k === "education") entries(items(d, k), k, page, name, hidden);
    else if (k === "interests") add(obj(d, "interests"), "text", page, name, x);
    else if (k === "skills") {
      add(labels, "languages", page, `${name} › Title of the languages`, x);
      for (const r of items(d, "languages")) {
        add(r, "language", page, `${name} › ${labels.languages || "Languages"}`, x);
        add(r, "level", page, `${name} › ${short(r.language || "Language", 30)} › Level`, x);
      }
      for (const [key, label, title] of [["digital", "digital_skills", "Digital skills"], ["soft", "soft_skills", "Soft skills"]]) {
        add(labels, label, page, `${name} › Title of the ${title.toLowerCase()}`, x);
        add(obj(d, "skills"), key, page, `${name} › ${labels[label] || title}`, x);
      }
    }
  }
  add(obj(d, "privacy"), "text", "privacy", "Privacy note");
  for (const [k, label] of [["contacts", "“Contacts” title"], ["grade", "Word for the grade"], ["thesis", "Word for the thesis"]])
    add(labels, k, "labels", "Other labels › " + label);
  return out;
}
function findRegex() {
  const q = F.query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(F.words ? `(?<![\\p{L}\\p{N}_])${q}(?![\\p{L}\\p{N}_])` : q, "gu" + (F.matchCase ? "" : "i"));
}
// the parts of a text that are link addresses: the (address) of [words](address), and addresses written as they are
const addressRanges = text => [...text.matchAll(TEXT_LINK)].map(m => [m[1] != null ? m.index + 1 + m[1].length : m.index, m.index + m[0].length]);
const matchPlace = m => m && { obj: m.spot.obj, k: m.spot.k, start: m.start };
// Looks for the words again (after a change, or other words); the current match stays at `place` ({obj, k, start}),
// or the one after it. Without a place (null), the first match from the section on screen.
function refreshFind(place) {
  if (F.where !== L()) { F.where = L(); F.shown = false; F.opened = null; place = null; }  // another language or CV
  else if (place === undefined) place = matchPlace(F.matches[F.current]);
  F.spots = L() ? findSpots() : []; F.matches = []; F.inLinks = 0; F.dirty = false;
  if (F.query) {
    const re = findRegex();
    F.spots.forEach((spot, n) => {
      const text = textOf(spot.obj[spot.k]), addresses = spot.address ? [[0, text.length]] : addressRanges(text);
      for (const m of text.matchAll(re)) {
        const start = m.index, end = start + m[0].length;
        if (!F.links && addresses.some(([a, b]) => start < b && end > a)) F.inLinks++;
        else F.matches.push({ spot, n, start, end });
      }
    });
  }
  F.current = placeIndex(place);
  F.counts = new Map();
  for (const m of F.matches) F.counts.set(m.spot.nav, (F.counts.get(m.spot.nav) || 0) + 1);
  updateFindBar();
}
function placeIndex(place) {
  if (!F.matches.length) return -1;
  let n = place ? F.spots.findIndex(s => s.obj === place.obj && s.k === place.k) : -1, from = place?.start ?? 0;
  if (n < 0) {
    const keys = navKeys(), here = keys.indexOf(S.section);
    n = F.spots.findIndex(s => keys.indexOf(s.page) >= here);
    from = 0;
  }
  return Math.max(0, n < 0 ? 0 : F.matches.findIndex(m => m.n > n || (m.n === n && m.start >= from)));
}
let findDirtyTimer = 0;
function findDirty() {  // the CV changed: count again soon (at once when the form is drawn again)
  F.dirty = true;
  if (!findOpen()) return;
  clearTimeout(findDirtyTimer);
  findDirtyTimer = setTimeout(() => { if (findOpen() && F.dirty) { refreshFind(); renderNav(); } }, 300);
}
function updateFindBar() {
  const n = F.matches.length, m = F.matches[F.current], count = $("#find-count"), where = $("#find-where");
  $("#find-query").placeholder = L() ? `Find in the ${languageName(S.language)} CV` : "Find";
  count.textContent = !F.query ? "" : n ? `${F.current + 1} of ${n}` : "No results";
  count.classList.toggle("none", !!F.query && !n);
  for (const id of ["#find-prev", "#find-next", "#find-one", "#find-all"]) $(id).disabled = !n;
  for (const b of document.querySelectorAll(".find-opt")) b.setAttribute("aria-pressed", String(F[b.dataset.opt]));
  const more = F.inLinks ? `${F.inLinks} more in link addresses` : "";
  fill(where, m ? [h("b", {}, m.spot.place), m.spot.hidden ? " · in a hidden section: not in the CV" : "", more && " · " + more]
    : more ? [`Found only in link addresses (${F.inLinks}). `,
              h("button", { type: "button", class: "link", onclick: () => setFindOption("links", true) }, "Search them too")]
    : F.query ? "" : "Enter: next · Shift+Enter: previous · Esc: close");
  where.title = m ? where.textContent : "";
}
// shows the current match: its section, its entry open, the words marked in their box
function showMatch(scroll = true) {
  const m = F.matches[F.current];
  F.shown = !!m;
  updateFindBar();
  if (!m) return unmark();
  const s = m.spot;
  let redraw = false;
  if (S.section !== s.page) { S.section = s.page; $("#add-menu").hidden = true; redraw = true; }
  if (F.opened && F.opened !== s.entry) { if (S.open.delete(F.opened)) redraw = true; F.opened = null; }  // opened for the previous match
  if (s.entry && !S.open.has(s.entry)) { S.open.add(s.entry); F.opened = s.entry; redraw = true; }
  if (redraw) render(); else unmark();
  const el = boxOf(s.obj, s.k), range = el && boxRange(el, m);
  if (range) markBox(el, range[0], range[1], scroll);
}
// where match m is in its box (the box may hold the text a bit differently, e.g. with an empty line)
function boxRange(el, m) {
  const text = textOf(m.spot.obj[m.spot.k]);
  if (el.value === text) return [m.start, m.end];
  const words = text.slice(m.start, m.end);
  let best = -1;
  for (let i = el.value.indexOf(words); i >= 0; i = el.value.indexOf(words, i + 1))
    if (best < 0 || Math.abs(i - m.start) < Math.abs(best - m.start)) best = i;
  return best < 0 ? null : [best, best + words.length];
}
let marked = null;  // the box where the current match is marked
function unmark() {
  if (!marked) return;
  const { el, mirror, observer, follow } = marked;
  marked = null;
  mirror.remove(); observer.disconnect(); el.removeEventListener("scroll", follow);
  el.classList.remove("find-current"); el.parentElement?.classList.remove("find-host");
}
// The words found, marked in their box: over the box, a copy of its text, transparent but for the words.
// The box keeps its text as it is (and the focus stays in the find bar).
function markBox(el, a, b, scroll) {
  unmark();
  el.parentElement.classList.add("find-host");
  const cs = getComputedStyle(el), area = el.tagName === "TEXTAREA", hit = h("mark", {}, el.value.slice(a, b));
  const mirror = h("div", { class: "find-mirror", "aria-hidden": "true" }, el.value.slice(0, a), hit, el.value.slice(b));
  for (const p of ["fontFamily", "fontSize", "fontWeight", "fontStyle", "fontStretch", "fontFeatureSettings", "letterSpacing", "wordSpacing", "textIndent",
                   "textTransform", "tabSize", "lineHeight", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "overflowWrap", "wordBreak"])
    mirror.style[p] = cs[p];
  Object.assign(mirror.style, { left: el.offsetLeft + el.clientLeft + "px", top: el.offsetTop + el.clientTop + "px",
                                width: el.clientWidth + "px", height: el.clientHeight + "px", whiteSpace: area ? "pre-wrap" : "pre" },
                area ? {} : { lineHeight: el.clientHeight + "px", paddingTop: "0", paddingBottom: "0" });  // one line, in the middle
  el.after(mirror);
  el.classList.add("find-current");
  // the words in sight inside the box too: a long line, a text longer than its box
  if (area && (hit.offsetTop < el.scrollTop || hit.offsetTop + hit.offsetHeight > el.scrollTop + el.clientHeight))
    el.scrollTop = hit.offsetTop - el.clientHeight / 3;
  if (!area && (hit.offsetLeft < el.scrollLeft || hit.offsetLeft + hit.offsetWidth > el.scrollLeft + el.clientWidth - parseFloat(cs.paddingRight)))
    el.scrollLeft = hit.offsetLeft - el.clientWidth / 3;
  const follow = () => { mirror.scrollTop = el.scrollTop; mirror.scrollLeft = el.scrollLeft; };
  follow();
  const w = el.clientWidth, ht = el.clientHeight;  // a box of another size (the window, the text): the words are marked again
  const observer = new ResizeObserver(() => { if (marked?.el === el && el.isConnected && (el.clientWidth !== w || el.clientHeight !== ht)) markBox(el, a, b, false); });
  observer.observe(el);
  el.addEventListener("scroll", follow);
  el.addEventListener("input", () => { if (marked?.el === el) unmark(); }, { once: true });  // you write in it: the mark goes
  marked = { el, mirror, observer, follow };
  if (scroll) reveal(hit);
}
// scrolls the form, only if needed, so that el is well in sight
function reveal(el) {
  let box = el.parentElement;
  while (box && !(/auto|scroll/.test(getComputedStyle(box).overflowY) && box.scrollHeight > box.clientHeight)) box = box.parentElement;
  if (!box) return el.scrollIntoView({ block: "center" });
  const r = el.getBoundingClientRect(), b = box.getBoundingClientRect();
  if (r.top >= b.top + 16 && r.bottom <= b.bottom - 16) return;
  box.scrollTo({ top: box.scrollTop + r.top - b.top - Math.max(16, (b.height - r.height) / 3), behavior: "smooth" });
}
let findTimer = 0;
// the words in the box were changed: look for them (true), and show the first match from where you are
function applyQuery() {
  clearTimeout(findTimer);
  const q = $("#find-query").value;
  if (q === F.query) return false;
  F.query = q;
  refreshFind(F.shown ? undefined : null);
  if (F.matches.length) showMatch(); else { F.shown = false; unmark(); }
  renderNav();
  return true;
}
function findStep(d) {
  if (applyQuery()) return;  // other words: their first match is already shown
  if (F.dirty) refreshFind();
  if (!F.matches.length) return;
  if (F.shown) F.current = (F.current + d + F.matches.length) % F.matches.length;
  showMatch();
}
function setFindOption(opt, on = !F[opt]) {
  F[opt] = on;
  refreshFind();
  if (F.matches.length) showMatch(); else { F.shown = false; unmark(); }
  renderNav();
  $("#find-query").focus();
}
// the text of a box with the ranges [start, end] replaced by `by`; in a list, line by line (a line left empty goes)
function writeSpot(spot, ranges, by) {
  const { obj, k } = spot, v = obj[k];
  const put = (text, at) => {  // the ranges that fall in text, which starts at `at`
    let out = "", last = 0;
    for (const [a, b] of ranges) if (a >= at && b <= at + text.length) { out += text.slice(last, a - at) + by; last = b - at; }
    return out + text.slice(last);
  };
  if (!Array.isArray(v)) {
    const out = put(v, 0);
    if (k === "link" && !out.trim()) delete obj[k]; else obj[k] = out;
    return;
  }
  let at = 0;
  const lines = v.map(x => { const out = put(x, at); at += x.length + 1; return out; }).filter(x => x.trim());
  if (k === "description" && !lines.length) delete obj[k];
  else obj[k] = k === "description" && lines.length === 1 && v.length > 1 ? lines[0] : lines;  // one line left: a sentence, as in its box
}
function replaceOne() {
  if (applyQuery()) return;  // other words: first see which ones
  if (F.dirty) refreshFind();
  const m = F.matches[F.current];
  if (!m) return;
  if (!F.shown || S.section !== m.spot.page) return showMatch();  // first see which words are replaced
  const by = $("#find-replace").value;
  writeSpot(m.spot, [[m.start, m.end]], by);
  changed();
  refreshFind({ obj: m.spot.obj, k: m.spot.k, start: m.start + by.length });  // then the next ones
  render();
  if (F.matches.length) showMatch(); else { F.shown = false; updateFindBar(); }
}
function replaceAll() {
  applyQuery();
  refreshFind();
  if (!F.matches.length) return;
  const l = S.language, by = $("#find-replace").value, n = F.matches.length, what = F.query, undo = [], bySpot = new Map();
  for (const m of F.matches) { if (!bySpot.has(m.spot)) bySpot.set(m.spot, []); bySpot.get(m.spot).push([m.start, m.end]); }
  for (const [spot, ranges] of bySpot) { undo.push([spot.obj, spot.k, spot.k in spot.obj, spot.obj[spot.k]]); writeSpot(spot, ranges, by); }
  changed();
  refreshFind();
  F.shown = false;
  render(); updateFindBar();
  toast(`“${short(what, 40)}” ${by ? `replaced with “${short(by, 40)}”` : "deleted"} ${n === 1 ? "once" : n + " times"} in ${languageName(l)}: ` +
        "check and press Save.", { undo: () => {
    for (const [o, k, had, v] of undo.reverse()) { if (had) o[k] = v; else delete o[k]; }
    changed(false, l);
    if (S.language === l) render();
  } });
}
function openFind(replace = false) {
  if (document.body.classList.contains("empty") || !L()) return;
  const q = $("#find-query"), a = document.activeElement, wasOpen = findOpen();
  // words selected in a box of the form: they are what you look for, from there
  let place = null;
  if ($("#form").contains(a) && /^(INPUT|TEXTAREA)$/.test(a.tagName) && a.selectionEnd > a.selectionStart) {
    const words = a.value.slice(a.selectionStart, a.selectionEnd);
    if (words.trim() && !words.includes("\n") && words.length <= 200) {
      q.value = F.query = words;
      const spot = findSpots().find(s => boxOf(s.obj, s.k) === a);
      place = spot ? { obj: spot.obj, k: spot.k, start: a.value === textOf(spot.obj[spot.k]) ? a.selectionStart : 0 } : null;
    }
  }
  $("#find").hidden = false;
  $("#btn-find").setAttribute("aria-pressed", "true");
  if (place) { F.where = L(); refreshFind(place); showMatch(false); }
  else if (q.value !== F.query) applyQuery();
  else if (!wasOpen || F.dirty || F.where !== L()) { F.shown = false; refreshFind(null); }
  renderNav();
  const box = replace && q.value ? $("#find-replace") : q;
  box.focus(); box.select();
}
// closes the bar; the words found last stay selected in their box, to go on writing there
function closeFind(focusMatch = true) {
  if (!findOpen()) return;
  const m = F.shown && F.matches[F.current], el = m && boxOf(m.spot.obj, m.spot.k), range = el && boxRange(el, m);
  unmark();
  $("#find").hidden = true;
  $("#btn-find").setAttribute("aria-pressed", "false");
  F.opened = null; F.shown = false;
  if (L()) renderNav();
  if (focusMatch && range) { el.focus({ preventScroll: true }); el.setSelectionRange(range[0], range[1]); }
}

// find and replace: Ctrl+F, Ctrl+H (with the words to replace), F3 / Shift+F3 for the next and previous ones
$("#btn-find").addEventListener("click", () => (findOpen() ? closeFind(false) : openFind()));
$("#find-query").addEventListener("input", () => { clearTimeout(findTimer); findTimer = setTimeout(applyQuery, 150); });
$("#find-query").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); findStep(e.shiftKey ? -1 : 1); } });
$("#find-replace").addEventListener("keydown", e => {
  if (e.key === "Enter") { e.preventDefault(); if (e.ctrlKey || e.metaKey) replaceAll(); else replaceOne(); }
});
$("#find").addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); closeFind(); } });
$("#find-prev").addEventListener("click", () => findStep(-1));
$("#find-next").addEventListener("click", () => findStep(1));
$("#find-one").addEventListener("click", replaceOne);
$("#find-all").addEventListener("click", replaceAll);
$("#find-close").addEventListener("click", () => closeFind());
for (const b of document.querySelectorAll(".find-opt")) b.addEventListener("click", () => setFindOption(b.dataset.opt));
// clicking the buttons of the bar leaves the cursor in the box you were typing in
for (const b of document.querySelectorAll("#find button")) b.addEventListener("mousedown", e => e.preventDefault());

export {
  bindBox, closeFind, F, findDirty, findOpen, findStep, openFind, refreshFind, unmark
};
