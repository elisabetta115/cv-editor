// Links in the text: [words](address), and the dialog that adds or changes one.
import { $ } from "./state.js";
import { icon } from "./icons.js";
import { fill, h } from "./util.js";
import { button, webAddress } from "./fields.js";

// ---------------------------------------------------------------- links in the text
// [words](address): the CV shows the words, and clicking them opens the address; an address written as it is
// (https://…, www.…) is a link too. "Add a link" under a text box, or Ctrl+K in it, turns the selected words into
// a link; with the cursor in a link it changes or removes it. The same rules as MARKDOWN_LINK in generate_cv.py.
const MD_LINK = /\[([^\[\]\n]+)\]\(\s*((?:[^\s()]|\([^\s()]*\))+)\s*\)/g;
const TEXT_LINK = new RegExp(MD_LINK.source + String.raw`|(?<![\w@/.\-])(?:https?:\/\/|www\.)[^\s<>\[\]()*"']+`, "gi");
const isEmail = a => /^[^@\s/:]+@[^@\s/]+\.[^@\s/]+$/.test(a);
const linkAddress = a => (a = a.trim()) ? (isEmail(a) ? "mailto:" + a : webAddress(a)) : "";
function linkButton(el) {
  return h("button", { type: "button", class: "link add-link", title: "Make the selected words a link (or press Ctrl+K in the box)",
    onmousedown: e => e.preventDefault(),  // the words selected in the box stay selected
    onclick: e => { e.preventDefault(); linkDialog(el); } }, icon("chain"), "Add a link");
}
function linkDialog(el) {
  const dlg = $("#link-dialog"), v = el.value;
  let start = el.selectionStart ?? v.length, end = el.selectionEnd ?? v.length;
  // the cursor in a link, or the link selected: change it
  const old = [...v.matchAll(MD_LINK)].find(m => start === end ? m.index < start && start < m.index + m[0].length
                                                               : m.index <= start && end <= m.index + m[0].length);
  if (old) [start, end] = [old.index, old.index + old[0].length];
  else {
    while (start < end && /\s/.test(v[start])) start++;
    while (end > start && /\s/.test(v[end - 1])) end--;
  }
  const selected = v.slice(start, end).replace(/\s+/g, " ");
  const isAddress = /^(https?:\/\/|www\.)\S+$/i.test(selected) || isEmail(selected);
  const words = h("input", { class: "inp", placeholder: "e.g. my portfolio", value: old ? old[1] : selected });
  const address = h("input", { class: "inp", placeholder: "https://…, or an e-mail address", value: old ? old[2] : isAddress ? selected : "" });
  address.spellcheck = false;
  const test = h("a", { class: "ico", target: "_blank", rel: "noopener", title: "Open the link to check it" }, icon("external"));
  const updateTest = () => { const url = linkAddress(address.value); test.href = url || "#"; test.style.visibility = url ? "" : "hidden"; };
  address.addEventListener("input", () => { address.setCustomValidity(""); updateTest(); });
  updateTest();
  // a new link written where the cursor is, right after a word: a space between them
  const space = !old && start === end && start > 0 && !/\s/.test(v[start - 1]) ? " " : "";
  const done = text => {
    if (text != null) { el.setRangeText(text && space + text, start, end, "end"); el.dispatchEvent(new Event("input")); }
    dlg.close();
  };
  const submit = e => {
    e.preventDefault();
    const a = address.value.trim();
    if (!linkAddress(a)) {
      address.setCustomValidity(a ? "Write a web address (https://…), an e-mail address or a phone number (tel:…)." : "Write the link.");
      return address.reportValidity();
    }
    // the words cannot hold [ ], and an address is written without spaces or brackets
    const w = words.value.replace(/[\[\]]/g, "").replace(/\s+/g, " ").trim() || a.replace(/[\[\]]/g, "");
    done(`[${w}](${a.replace(/\s/g, "%20").replace(/\(/g, "%28").replace(/\)/g, "%29")})`);
  };
  fill(dlg, h("form", { onsubmit: submit },
    h("div", { class: "panel-head" }, h("strong", {}, old ? "Change the link" : "Add a link"), button("✕", "Close", () => done())),
    h("label", { class: "field" }, h("span", {}, "Words to show"), words),
    h("label", { class: "field" }, h("span", {}, "Link"), h("div", { class: "address" }, address, test)),
    h("p", { class: "more" }, "In the CV the words are underlined, and clicking them in the PDF opens the link. ",
      "Leave the words empty to show the address itself."),
    h("div", { class: "actions" },
      old ? h("button", { type: "button", class: "btn", title: "Keep the words, without the link", onclick: () => done(old[1]) }, "Remove the link") : null,
      h("span", { class: "spacer" }),
      h("button", { type: "button", class: "btn", onclick: () => done() }, "Cancel"),
      h("button", { type: "submit", class: "btn primary" }, old ? "Change" : "Add the link"))));
  dlg.onclose = () => el.focus();
  dlg.showModal();
  (words.value && !address.value ? address : words).focus();
}
// the addresses of the links do not change when a company is renamed in the text (only the words do)
function outsideAddresses(text, fn) {
  let out = "", last = 0;
  for (const m of text.matchAll(TEXT_LINK)) {
    out += fn(text.slice(last, m.index)) + (m[1] != null ? "[" + fn(m[1]) + m[0].slice(1 + m[1].length) : m[0]);
    last = m.index + m[0].length;
  }
  return out + fn(text.slice(last));
}
const withoutAddresses = text => text.replace(TEXT_LINK, (m, words) => (words != null ? words : " "));

export {
  linkButton, linkDialog, outsideAddresses, TEXT_LINK, withoutAddresses
};
