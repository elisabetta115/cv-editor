// Small helpers used everywhere: building elements, requests to the editor's server, messages, questions, panels.
import { $, S, TOKEN } from "./state.js";
import { icon } from "./icons.js";
import { button } from "./fields.js";
import { updateBar } from "./design.js";

// ---------------------------------------------------------------- utilities
function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k in el && !k.includes("-")) el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) if (c != null && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}
// like replaceChildren, but also accepts lists and skips empty values
function fill(el, ...children) {
  el.replaceChildren(...children.flat(Infinity).filter(c => c != null && c !== false));
  return el;
}
async function api(path, data, headers = {}) {
  const opts = { method: data === undefined ? "GET" : "POST", headers: { "X-Token": TOKEN, ...headers } };
  if (data instanceof Blob) opts.body = data;  // a file, sent as it is
  else if (data !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(data); }
  let r;
  try { r = await fetch(path, opts); }
  catch { throw new Error("The editor is not responding: maybe its terminal window was closed. Open it again."); }
  checkAllowed(r);
  const j = await r.json().catch(() => ({ error: `Error ${r.status}` }));
  if (!r.ok || j.error) throw new Error(j.error || `Error ${r.status}`);
  return j;
}
// 403: the editor was restarted (new secret token) or updated while this page was open
function checkAllowed(r) {
  if (r.status === 403) throw new Error("This page is out of date: reload it (F5). If that does not help, close the editor's terminal window and open CV Editor again.");
}
const list = (o, k) => (Array.isArray(o[k]) ? o[k] : (o[k] = []));
const table = (o, k) => (o[k] && typeof o[k] === "object" && !Array.isArray(o[k]) ? o[k] : (o[k] = {}));
const L = (l = S.language) => S.languages[l];
function move(arr, i, d) { const j = i + d; if (j >= 0 && j < arr.length) [arr[i], arr[j]] = [arr[j], arr[i]]; }

let toastTimer;
function toast(text, o = {}) {
  const box = $("#toast");
  box.className = "visible" + (o.error ? " error" : "");
  fill(box, h("span", {}, text),
    o.undo ? h("button", { type: "button", onclick: () => { box.className = ""; o.undo(); } }, "Undo") : null,
    o.action ? h("button", { type: "button", onclick: () => { box.className = ""; o.action[1](); } }, o.action[0]) : null,
    h("button", { type: "button", title: "Close", onclick: () => (box.className = "") }, icon("x")));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (box.className = ""), o.error ? 15000 : 7000);
}
function status(text, kind = "") { const el = $("#status"); el.textContent = text; el.className = "status " + kind; }

// ---------------------------------------------------------------- questions
// A window in the editor's style instead of the browser's popup: resolves true when the answer is "ok".
// text: one paragraph or a list (the first one is the question, the others smaller); danger: a red button.
function ask({ title, text = [], ok = "OK", cancel = "Cancel", danger = false }) {
  const dlg = $("#ask-dialog");
  return new Promise(resolve => {
    const answer = v => { resolve(v); if (dlg.open) dlg.close(); };
    const no = h("button", { type: "button", class: "btn", onclick: () => answer(false) }, cancel);
    fill(dlg, h("form", { onsubmit: e => { e.preventDefault(); answer(true); } },
      h("div", { class: "panel-head" }, h("strong", {}, title), button("✕", "Close", () => answer(false))),
      [].concat(text).filter(Boolean).map((t, i) => h("p", { class: i ? "more" : "" }, t)),
      h("div", { class: "actions" }, no, h("button", { type: "submit", class: "btn " + (danger ? "danger" : "primary") }, ok))));
    dlg.onclose = () => resolve(false);  // Esc
    dlg.showModal();
    (danger ? no : dlg.querySelector("[type=submit]")).focus();  // before deleting, Enter means "Cancel"
  });
}

function togglePanel(id, render) {
  for (const x of document.querySelectorAll(".panel")) if (x.id !== id) x.hidden = true;
  const p = $("#" + id);
  p.hidden = !p.hidden;
  if (!p.hidden) render();
  updateBar();
}
// a small menu under the button that opens it
function placeUnder(p, anchor) {
  const r = anchor.getBoundingClientRect();
  Object.assign(p.style, { top: r.bottom + 6 + "px", left: Math.max(12, Math.min(r.left, innerWidth - p.offsetWidth - 12)) + "px" });
}

export {
  api, ask, checkAllowed, fill, h, L, list, move, placeUnder, status, table, toast, togglePanel
};
