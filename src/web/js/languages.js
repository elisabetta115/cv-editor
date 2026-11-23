// The languages of a CV: switching, adding, copying and deleting them.
import { $, S } from "./state.js";
import { icon } from "./icons.js";
import { api, ask, fill, h, L, placeUnder, toast, togglePanel } from "./util.js";
import { baseOf, isVersion, sync } from "./changes.js";
import { languageName, snapshot } from "./sync.js";
import { button, wrap } from "./fields.js";
import { render } from "./nav.js";
import { updateBar } from "./design.js";
import { namesDialog } from "./names.js";
import { updatePreview } from "./preview.js";

// ---------------------------------------------------------------- languages
function renderLanguages() {
  fill($("#languages"),
    Object.keys(S.languages).map(l => h("button", { type: "button", "data-l": l, onclick: () => switchLanguage(l) }, languageName(l))),
    h("button", { type: "button", class: "add", id: "btn-copy-language",
                  title: "Make a copy of a language of this CV, in the same language (e.g. English for Ireland), " +
                         "to change it without touching the original",
                  onclick: e => { e.stopPropagation(); copyPanel(); } }, icon("copy"), "Copy"),
    h("button", { type: "button", class: "add", title: "Add a language: the CV copied and translated into another language (or delete one)",
                  onclick: e => { e.stopPropagation(); languagePanel(); } }, icon("plus"), "New language"));
  updateBar();
}
function switchLanguage(l) {
  S.language = l; updateBar(); render(); $("#form").scrollTop = 0; updatePreview(true);
}

// before opening: which translators are ready (Ollama may have been installed meanwhile)
async function languagePanel() {
  if ($("#language-panel").hidden) {
    try { S.translator = await api("/api/translator"); } catch { /* the panel works without translators */ }
  }
  togglePanel("language-panel", renderLanguagePanel);
}
// "Copy": another version of the CV in the same language (e.g. English for Ireland), with its own tab at the top
const baseName = l => languageName(baseOf(l));
const copyPanel = () => togglePanel("copy-panel", renderCopyPanel);
function renderCopyPanel() {
  const p = $("#copy-panel"), present = Object.keys(S.languages);
  const from = h("select", { class: "inp" }, present.map(l => h("option", { value: l }, languageName(l))));
  from.value = S.language;
  const what = h("input", { class: "inp", placeholder: "e.g. Ireland" });
  const result = h("small", { class: "hint" });
  const showName = () => {
    const label = what.value.trim().replace(/\s+/g, " ");
    fill(result, "It gets its own tab at the top: ", h("b", {}, `${baseName(from.value)} (${label || "…"})`), ".");
  };
  const create = () => {
    const label = what.value.trim().replace(/\s+/g, " ");
    if (!label) { what.focus(); return toast("Write what the copy is for, for example Ireland.", { error: true }); }
    const base = baseOf(from.value), name = `${baseName(from.value)} (${label})`;
    if (present.some(l => languageName(l).toLowerCase() === name.toLowerCase()))
      return toast(`There is already a version called ${name}.`, { error: true });
    const slug = label.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "").slice(0, 20) || "v";
    let code = `${base}-${slug}`;
    for (let n = 2; S.languages[code]; n++) code = `${base}-${slug}${n}`;
    p.hidden = true;
    addLanguage(code, name, from.value);
  };
  what.addEventListener("input", showName);
  from.addEventListener("change", showName);
  what.addEventListener("keydown", e => { if (e.key === "Enter") create(); });
  showName();
  fill(p,
    h("div", { class: "panel-head" }, h("strong", {}, "Copy a language"), button("✕", "Close", () => (p.hidden = true))),
    h("small", { class: "hint" }, "A copy of the CV in the same language, to change for another country or job: e.g. ",
      h("b", {}, "English"), " and ", h("b", {}, "English (Ireland)"), ". You change the copy as you like; the original is not touched."),
    h("div", { class: "grid" }, wrap("Copy of", from, {}), wrap("What is it for?", what, {})),
    result,
    h("button", { type: "button", class: "btn primary", style: "justify-self: start", onclick: create }, icon("copy"), "Create the copy"));
  placeUnder(p, $("#btn-copy-language"));
  what.focus();
}
function renderLanguagePanel() {
  const p = $("#language-panel"), present = Object.keys(S.languages);
  const choice = h("select", { class: "inp" },
    S.templates.filter(t => !present.includes(t.code)).map(t => h("option", { value: t.code }, t.name)),
    h("option", { value: "*" }, "Other language…"));
  const name = h("input", { class: "inp", placeholder: "e.g. Polski" });
  const code = h("input", { class: "inp", placeholder: "e.g. pl", maxLength: 3 });
  const other = h("div", { class: "grid" }, wrap("Language name", name, {}), wrap("Code (2-3 letters)", code, {}));
  const updateOther = () => (other.hidden = choice.value !== "*");
  choice.addEventListener("change", updateOther);
  updateOther();
  const from = h("select", { class: "inp" }, present.map(l => h("option", { value: l }, languageName(l))));
  from.value = present.includes("en") ? "en" : S.language;
  // automatic translation: the AI on this computer (Ollama) or Microsoft Translator (its key stays on this computer)
  const local = S.translator?.local || {}, azure = S.translator?.azure || {};
  const model = local.suggested || "qwen3:8b";
  const auto = h("input", { type: "checkbox", checked: !!(local.model || azure.configured) });
  const engine = h("select", { class: "inp" },
    h("option", { value: "local" }, "AI on this computer (free, private)"),
    h("option", { value: "azure" }, "Microsoft Translator (free key)"));
  engine.value = local.model || !azure.configured ? "local" : "azure";
  const engineField = wrap("Translator", engine, {});
  const localInfo = h("small", { class: "hint" }, local.model
    ? `Ready (${local.model}). Nothing leaves this computer. Without a graphics card it can take a few minutes.`
    : local.running
      ? ["Download the AI model once (about 5 GB): in a terminal run ", h("code", {}, `ollama pull ${model}`), ", then try again."]
      : ["It needs Ollama, free: install it from ", h("a", { href: "https://ollama.com/download", target: "_blank", rel: "noopener" }, "ollama.com ↗"),
         ", then in a terminal run ", h("code", {}, `ollama pull ${model}`), " (about 5 GB, once) and try again."]);
  const key = h("input", { class: "inp", type: "password", autocomplete: "off", placeholder: "KEY 1" });
  const region = h("input", { class: "inp", placeholder: "e.g. westeurope", value: azure.region || "" });
  const setup = h("div", { class: "grid" }, wrap("Microsoft Translator key", key, {}), wrap("Region", region, {}),
    h("small", { class: "hint wide" }, "Free: 2 million characters a month (a CV uses about 5 000). ",
      h("a", { href: "https://learn.microsoft.com/azure/ai-services/translator/create-translator-resource", target: "_blank", rel: "noopener" },
        "How to get a free key ↗")));
  const saved = h("small", { class: "hint" }, "Key saved on this computer. ",
    azure.from_environment ? "(from AZURE_TRANSLATOR_KEY)" : h("a", { href: "#", onclick: e => { e.preventDefault(); forgetKey(); } }, "Remove the key"));
  const fromHint = h("small", { class: "hint" });
  const go = h("button", { type: "button", class: "btn primary" });
  const update = () => {
    const on = auto.checked, isLocal = engine.value === "local";
    engineField.hidden = !on;
    localInfo.hidden = !on || !isLocal;
    setup.hidden = !on || isLocal || !!azure.configured;
    saved.hidden = !on || isLocal || !azure.configured;
    fromHint.textContent = !on
      ? "All the content is copied, then you translate it. Section titles are already translated for Spanish, " +
        "French, German, Portuguese and Dutch."
      : (isLocal ? "" : "Only the text is sent to Microsoft to be translated (Microsoft does not keep it). ") +
        "Names, contacts, organisations and links stay as they are" + (isLocal ? "." : " and are not sent.") +
        " Check the result before saving.";
    go.textContent = on ? "Translate and create the CV" : "Create the CV in this language";
  };
  auto.addEventListener("change", update);
  engine.addEventListener("change", update);
  update();
  const create = async () => {
    let newCode = choice.value, newName;
    if (newCode === "*") {
      newCode = code.value.trim().toLowerCase(); newName = name.value.trim();
      if (!newName) return toast("Write the name of the language, for example Polski.", { error: true });
      if (!/^[a-z]{2,3}$/.test(newCode)) return toast("The code must have 2 or 3 letters, for example pl.", { error: true });
    } else newName = S.templates.find(t => t.code === newCode).name;
    if (S.languages[newCode]) return toast(`There is already a CV in ${languageName(newCode)}.`, { error: true });
    if (!auto.checked) {
      p.hidden = true;
      return addLanguage(newCode, newName, from.value);
    }
    const isLocal = engine.value === "local";
    if (!isLocal && !azure.configured && !key.value.trim())
      return toast("Paste your Microsoft Translator key, or choose another translator.", { error: true });
    const version = S.version, copy = copyLanguage(from.value), started = Date.now();
    go.disabled = true; go.textContent = "Translating…";
    const timer = setInterval(() => {
      const s = Math.round((Date.now() - started) / 1000);
      go.textContent = `Translating… ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    }, 1000);
    try {
      if (!isLocal && !azure.configured) S.translator = await api("/api/translator", { key: key.value.trim(), region: region.value.trim() });
      const r = await api("/api/translate", { data: copy.data, from: from.value, to: newCode, engine: engine.value,
                                              from_name: languageName(from.value), to_name: newName });
      if (S.version !== version || S.languages[newCode]) return;  // another CV was opened meanwhile
      copy.data = r.data;
      copy.order = copy.order.map((o, i) => (o.fixed ? o : { section: r.data.sections[i] }));
      p.hidden = true;
      addLanguage(newCode, newName, from.value, copy, isLocal ? "the AI on this computer" : "Microsoft Translator");
    } catch (e) {
      toast(e.message, { error: true });
      go.disabled = false; update();
    } finally {
      clearInterval(timer);
    }
  };
  go.addEventListener("click", create);
  fill(p,
    h("div", { class: "panel-head" }, h("strong", {}, "CV languages"), button("✕", "Close", () => (p.hidden = true))),
    h("div", { class: "language-list" }, present.map(l => h("div", { class: "row" }, h("span", {}, languageName(l)),
      button("Delete", `Delete only the ${languageName(l)} version of this CV`, () => deleteLanguage(l), { cls: "text danger", disabled: present.length === 1 })))),
    h("small", { class: "hint" }, "To have another version in the same language (e.g. English for Ireland), use ",
      h("a", { href: "#", onclick: e => { e.preventDefault(); copyPanel(); } }, "Copy"), " instead."),
    h("div", { class: "subtitle" }, "Add a language"),
    wrap("Language", choice, {}), other,
    wrap("Start from the content in", from, {}),
    h("label", { class: "check translate" }, auto, "Translate it automatically"), fromHint,
    engineField, localInfo, setup, saved, go);
}
async function forgetKey() {
  if (!(await ask({ title: "Remove the Microsoft Translator key?", text: ["The key is deleted from this computer.",
                    "You can add it again later in + New language."], ok: "Remove the key", danger: true }))) return;
  try { S.translator = await api("/api/translator", { key: "" }); renderLanguagePanel(); toast("Key removed."); }
  catch (e) { toast(e.message, { error: true }); }
}
// a copy of the content of a language, with its section order
function copyLanguage(from) {
  sync(from);
  const data = structuredClone(L(from).data);
  const order = L(from).order.map((o, i) => (o.fixed ? { fixed: o.fixed, hidden: o.hidden, side: o.side } : { section: data.sections[i] }));
  return { data, order };
}
// translated: who translated it ("" = copied, to be translated by hand)
function addLanguage(code, name, from, { data, order } = copyLanguage(from), translated = "") {
  const template = S.templates.find(t => t.code === code);
  if (translated) for (const s of data.sections || []) delete s.copied_from;
  if (template?.labels) data.labels = { ...data.labels, ...template.labels };
  data.cv_language = { name };
  S.languages[code] = { data, order, name };
  snapshot(code);
  S.deleted.delete(code);
  S.changed[code] = true;
  S.language = code;
  renderLanguages(); render(); $("#form").scrollTop = 0; updatePreview(true);
  const undo = () => deleteLanguage(code, false);  // Undo: the new language goes away
  if (translated) return toast(`The CV in ${name} was translated from ${languageName(from)} by ${translated}: ` +
                               "read it through, correct what is needed and press Save.",
                               { undo, action: ["Change the names", namesDialog] });
  if (isVersion(code)) return toast(`“${name}” is a copy of ${languageName(from)}: change it as you like (e.g. hide the date of birth ` +
                                    "with the eye, remove a section, choose No photo). The other versions are not changed.", { undo });
  toast(`The CV in ${name} was created with the content of ${languageName(from)}: translate it and press Save.` +
        (template?.labels ? " Section titles are already translated." : ""), { undo });
}
// removes one language of the CV (the others stay); confirmFirst = false: right after creating it (Undo)
async function deleteLanguage(l, confirmFirst = true) {
  const name = languageName(l), x = S.languages[l], wasChanged = S.changed[l], saved = S.saved.has(l);
  if (!x || Object.keys(S.languages).length < 2) return;
  if (confirmFirst && !(await ask({ title: `Delete the ${name} version?`,
      text: [`Only the ${name} version of this CV is deleted: the other languages stay as they are.`,
             saved ? `When you press Save, the ${name} file and its PDFs are removed too. Until then you can undo it.` : ""],
      ok: `Delete ${name}`, danger: true }))) return;
  if (S.languages[l] !== x) return;  // already gone
  delete S.languages[l]; delete S.changed[l];
  if (saved) { S.deleted.add(l); S.languagesChanged = true; }
  if (S.language === l) S.language = Object.keys(S.languages)[0];
  renderLanguages(); render(); updatePreview(true); renderLanguagePanel();
  updateBar();
  toast(saved ? `The ${name} version was removed: press Save to confirm.` : `The ${name} version was removed.`, { undo: () => {
    S.languages[l] = x; S.changed[l] = wasChanged; S.deleted.delete(l); S.language = l;
    renderLanguages(); render(); updatePreview(true); updateBar();
  } });
}

export {
  deleteLanguage, renderLanguages
};
