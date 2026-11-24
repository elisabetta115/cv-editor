// The Adjust panel: the style on screen fitted to this CV (text size, spacing, line spacing, long entries), to fit it
// on fewer pages or give it more air. Each style keeps its own adjustments, saved with the CV (settings.toml).
import { $, S } from "./state.js";
import { api, fill, h, placeUnder, togglePanel } from "./util.js";
import { button } from "./fields.js";
import { updateBar } from "./design.js";
import { updatePreview, viewRequest } from "./preview.js";

// name, label, smallest and largest in % (as ADJUSTMENTS in styles.py), step, what it changes
const ADJUST = [
  ["text", "Text size", 80, 120, 1, "Every text of the style, from the name to the dates"],
  ["spacing", "Spacing", 50, 150, 5, "The space between sections and between entries"],
  ["lines", "Line spacing", 85, 115, 1, "The space between the lines of a paragraph or a list (names and titles keep theirs)"],
];
const SPLIT_HINT = "Normally a job or a degree never starts on one page and ends on the next: when it does not fit, it moves to "
                 + "the next page whole, leaving a gap. With this, it may continue on the next page (each bullet point stays whole).";
let countTimer, countRequest = 0;

const adjustOf = () => S.settings.styles[S.style].adjust || {};
const adjusted = () => Object.keys(adjustOf()).length > 0;

function setAdjust(name, value) {
  const st = S.settings.styles[S.style], a = { ...(st.adjust || {}) };
  if (value === 100 || value === false) delete a[name]; else a[name] = value;
  if (Object.keys(a).length) st.adjust = a; else delete st.adjust;
  S.settingsChanged = true;
  $("#adjust-reset").disabled = !adjusted();
  updateBar(); updatePreview(); countPages();
}
function resetAdjust() {
  delete S.settings.styles[S.style].adjust;
  S.settingsChanged = true;
  renderAdjustPanel(); updateBar(); updatePreview(true); countPages();
}
function renderAdjustPanel() {
  const p = $("#adjust-panel"), a = adjustOf();
  const name = S.styles.find(x => x.id === S.style)?.name || S.style;
  fill(p,
    h("div", { class: "panel-head" }, h("strong", {}, `Adjust ${name} to your CV`),
      button("✕", "Close", () => { p.hidden = true; updateBar(); })),
    ADJUST.map(([key, label, min, max, step, hint]) => {
      const out = h("output", {}, (a[key] ?? 100) + " %");
      const range = h("input", { type: "range", min, max, step, value: a[key] ?? 100, "aria-label": label,
                                 oninput: () => { out.textContent = range.value + " %"; setAdjust(key, Number(range.value)); } });
      return h("label", { class: "adjust-row", title: hint }, h("span", {}, label), range, out);
    }),
    h("label", { class: "check", title: SPLIT_HINT },
      h("input", { type: "checkbox", checked: !!a.split, onchange: e => setAdjust("split", e.target.checked) }),
      "Long entries may continue on the next page"),
    h("div", { class: "adjust-foot" },
      h("strong", { id: "adjust-pages", "aria-live": "polite" }),
      h("button", { type: "button", class: "btn", id: "adjust-reset", disabled: !adjusted(), onclick: resetAdjust,
                    title: `Back to ${name} as it is designed` }, "Reset")),
    h("small", { class: "hint" }, "Only for this style: each style keeps its own adjustments, saved with the CV."));
  placeUnder(p, $("#btn-adjust"));
}
// how many pages the PDF has, asked a moment after the last change (Chrome prints it, which takes a second)
function countPages(now = false) {
  clearTimeout(countTimer);
  if ($("#adjust-panel").hidden || !$("#adjust-pages")) return;
  $("#adjust-pages").textContent = "Counting the pages…";
  countTimer = setTimeout(async () => {
    const n = ++countRequest, show = text => { if (n === countRequest && $("#adjust-pages")) $("#adjust-pages").textContent = text; };
    try {
      const { pages } = await api("/api/pages", viewRequest());
      show(pages === 1 ? "1 page" : `${pages} pages`);
    } catch { show(""); }
  }, now ? 0 : 700);
}
const adjustPanel = () => togglePanel("adjust-panel", () => { renderAdjustPanel(); countPages(true); });

$("#btn-adjust").addEventListener("click", e => { e.stopPropagation(); adjustPanel(); });

export { adjustPanel, renderAdjustPanel };
