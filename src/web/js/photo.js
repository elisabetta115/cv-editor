// Photos, their framing, and the signature.
import { $, S, TOKEN } from "./state.js";
import { icon } from "./icons.js";
import { api, ask, checkAllowed, fill, h, L, placeUnder, status, table, toast, togglePanel } from "./util.js";
import { inLanguage } from "./changes.js";
import { changed } from "./sync.js";
import { button, card } from "./fields.js";
import { cardIcon } from "./cards.js";
import { render } from "./nav.js";
import { updateBar } from "./design.js";
import { updatePreview } from "./preview.js";

// the photo button of the bar (and the photo menu, when it is open)
function renderPhotos() {
  const f = S.photoList.find(x => x.name === S.photo);
  fill($("#btn-photo"), h("span", { class: "photo-dot", style: f ? `background-image:url("${f.src}")` : "" }, f ? null : icon("image-off")),
    h("span", { class: "label" }, f ? "Photo" : "No photo"), icon("chevron-down", "chev"));
  $("#btn-frame").hidden = !f;
  if (!$("#photo-panel").hidden) renderPhotoPanel();
  updateBar();
}
const photoPanel = () => togglePanel("photo-panel", renderPhotoPanel);
function renderPhotoPanel() {
  const p = $("#photo-panel");
  const pick = name => { S.photo = name; $("#frame-panel").hidden = true; renderPhotos(); updatePreview(true); };
  fill(p,
    h("div", { class: "panel-head" }, h("strong", {}, "Photo"), button("✕", "Close", () => { p.hidden = true; updateBar(); })),
    h("div", { id: "photos" },
      h("button", { type: "button", class: "no-photo", "aria-pressed": String(S.photo === null), onclick: () => pick(null) }, icon("image-off"), "No photo"),
      S.photoList.map(f => h("div", { class: "photo" },
        h("button", { type: "button", class: "pick", title: f.name, "aria-label": "Preview with " + f.name,
                      "aria-pressed": String(S.photo === f.name), style: `background-image:url("${f.src}")`, onclick: () => pick(f.name) }),
        h("button", { type: "button", class: "x", title: "Delete this photo", "aria-label": "Delete " + f.name, onclick: () => deletePhoto(f.name) }, icon("x")))),
      h("label", { class: "add-photo", title: "Add one or more photos: you get one more PDF for each" }, icon("plus"), "Add",
        h("input", { type: "file", accept: "image/*", multiple: true, hidden: true, onchange: e => uploadPhotos([...e.target.files]) }))),
    h("small", { class: "hint" }, "Each photo gives one more version of the PDF. The one chosen here is the one you see."),
    S.photo ? h("div", { class: "photo-actions" }, h("small", { class: "hint" }, "Which part of the photo, how close, which shape:"),
      h("button", { type: "button", class: "btn", onclick: e => { e.stopPropagation(); framePanel(); } }, icon("crop"), "Frame…")) : null);
  placeUnder(p, $("#btn-photo"));
}
// ---------------------------------------------------------------- the signature
// One signature per CV (cvs/<name>/signature.png): each language, and each copy, chooses whether it is signed.
// It goes at the end of the CV, under the privacy note, on the right.
function signatureCard(d) {
  const sg = table(d, "signature");
  const input = h("input", { type: "file", accept: "image/*,.pdf,application/pdf", hidden: true,
                             onchange: e => { const f = e.target.files[0]; e.target.value = ""; if (f) uploadSignature(f); } });
  return card([cardIcon("pen"), h("span", { class: "fixed-title" }, "Signature")], S.signature ? [
    h("label", { class: "check translate" }, h("input", { type: "checkbox", checked: !!sg.show,
      onchange: e => { if (e.target.checked) sg.show = true; else delete sg.show; changed(); } }), `Sign the CV${inLanguage()}`),
    h("small", { class: "hint" }, "It goes at the end of the CV, under the privacy note, on the right. ",
      "Each language, and each copy, chooses whether it is signed."),
    h("div", { class: "signature-box" }, h("img", { src: S.signature, alt: "Your signature" })),
    h("div", { class: "signature-actions" },
      h("label", { class: "btn", title: "Choose another image or PDF of your signature" }, icon("upload"), "Replace…", input),
      h("button", { type: "button", class: "btn", onclick: deleteSignature }, icon("trash"), "Delete the signature"))
  ] : [
    h("small", { class: "hint" }, "Add your signature to sign the CV, e.g. under the consent to process your personal data: ",
      "a PNG or JPG (a photo or a scan of your signature on white paper is fine) or a PDF. ",
      "The editor cuts it out and makes the paper transparent; then you choose which languages are signed."),
    h("label", { class: "btn primary", style: "justify-self: start" }, icon("upload"), "Add your signature…", input)]);
}
async function uploadSignature(f) {
  status("Adding the signature…", "busy");
  try {
    const j = await api("/api/signature", f, { "X-CV": encodeURIComponent(S.profile), "X-File-Name": encodeURIComponent(f.name) });
    const first = !S.signature;
    S.signature = j.signature;
    if (first) { table(L().data, "signature").show = true; changed(); }  // the first time: the CV on screen is signed
    status(first ? "Signature added" : "Signature replaced", "ok");
    render(); updatePreview(true);
  } catch (e) { status(""); toast(e.message, { error: true }); }
}
async function deleteSignature() {
  if (!(await ask({ title: "Delete your signature?",
      text: ["It is deleted from this CV: no language is signed any more. You can add it again later."], ok: "Delete", danger: true }))) return;
  try {
    S.signature = (await api("/api/signature/delete", { profile: S.profile })).signature;
    render(); updatePreview(true);
    toast("Signature deleted.");
  } catch (e) { toast(e.message, { error: true }); }
}
async function uploadPhotos(files) {
  for (const f of files) {
    status(`Uploading ${f.name}…`, "busy");
    try {
      const r = await fetch("/api/photos", { method: "POST", headers: { "X-Token": TOKEN, "X-CV": encodeURIComponent(S.profile), "X-File-Name": encodeURIComponent(f.name) }, body: f });
      checkAllowed(r);
      const j = await r.json().catch(() => ({ error: `Error ${r.status}` }));
      if (!r.ok || j.error) throw new Error(j.error);
      S.photoList = j.photos; S.photo = j.name; S.photosChanged = true;
    } catch (e) { toast(e.message, { error: true }); }
  }
  status(S.photosChanged ? "Photo added" : "");
  renderPhotos(); updateBar(); updatePreview(true);
}
async function deletePhoto(name) {
  if (!(await ask({ title: "Delete this photo?", text: [`“${name}” is deleted from this CV, in every language.`],
                    ok: "Delete the photo", danger: true }))) return;
  try {
    const j = await api("/api/photos/delete", { profile: S.profile, name });
    S.photoList = j.photos; if (S.photo === name) { S.photo = null; $("#frame-panel").hidden = true; } S.photosChanged = true;
    if (S.settings?.photos?.[name]) { delete S.settings.photos[name]; S.settingsChanged = true; }
    renderPhotos(); updateBar(); updatePreview(true);
  } catch (e) { toast(e.message, { error: true }); }
}
// ---------------------------------------------------------------- framing of a photo
// Which part of the photo the CV shows, and how close: the same in every style and language of this CV
// (saved in its settings.toml). The preview on the right shows it in the style on screen.
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const framePanel = () => togglePanel("frame-panel", () => { renderFramePanel(); renderPhotos(); });
// the photo in the preview: where the style puts it and the shape of its frame
function previewPhoto() {
  const imgs = [...($("#cv").contentDocument?.querySelectorAll(".header-photo img, .sidebar-photo img") || [])];
  return imgs.find(i => i.offsetParent) || imgs[0] || null;
}
// the shapes you can give the photo instead of the one of the style (base.css, .shape-*)
const SHAPES = [[null, "As the style", "The shape this style gives the photo"], ["rect", "Rectangle", "Straight corners"],
                ["rounded", "Rounded", "Rounded corners"], ["square", "Square", "As tall as it is wide"], ["circle", "Circle", "Round"]];
function renderFramePanel() {
  const p = $("#frame-panel"), name = S.photo, photo = S.photoList.find(x => x.name === name);
  if (!photo) { p.hidden = true; return; }
  const saved = S.settings?.photos?.[name] || {};
  const shown = previewPhoto(), pos = shown && getComputedStyle(shown).objectPosition.match(/([\d.]+)%\s+([\d.]+)%/);
  let framed = "x" in saved, shape = saved.shape || null;  // framed: you chose the position or the zoom
  let fr = framed ? { x: saved.x, y: saved.y, zoom: saved.zoom ?? 1 } : { x: pos ? +pos[1] : 50, y: pos ? +pos[2] : 12, zoom: 1 };
  const frameRatio = () => { const i = previewPhoto(); return i?.clientHeight ? i.clientWidth / i.clientHeight : 0.8; };  // width / height
  const pic = h("img", { src: photo.src, alt: "", draggable: false });
  const box = h("div", { class: "frame-box" });
  const stage = h("div", { class: "frame-stage", title: "Click or drag where you want the middle of the photo" }, pic, box);
  // the part of the photo the CV shows: the zoom cuts it, then the frame (cover, object-position)
  const visible = () => {
    const ratio = pic.naturalWidth && pic.naturalHeight ? pic.naturalWidth / pic.naturalHeight : frameRatio(), fw = frameRatio();
    const w = (ratio > fw ? fw / ratio : 1) / fr.zoom, hh = (ratio > fw ? 1 : ratio / fw) / fr.zoom;
    return { w, h: hh, left: fr.x / 100 * (1 - w), top: fr.y / 100 * (1 - hh) };
  };
  const sliders = [["Zoom", "zoom", 1, 3, 0.05, v => Math.round(v * 100) + "%"],
                   ["Left ↔ right", "x", 0, 100, 1, v => Math.round(v) + "%"],
                   ["Up ↕ down", "y", 0, 100, 1, v => Math.round(v) + "%"]].map(([label, k, min, max, step, show]) => {
    const input = h("input", { type: "range", min, max, step, disabled: k === "zoom" && !S.canZoom, oninput: () => set({ [k]: +input.value }) });
    const out = h("output", {});
    return { k, input, out, show, el: h("label", { class: "frame-slider" }, h("span", {}, label), input, out) };
  });
  const shapeButtons = SHAPES.map(([id, label, title]) => h("button", { type: "button", class: "shape-btn", title,
    onclick: () => setShape(id) }, h("i", { class: "shape-icon " + (id || "style") }), label));
  const draw = () => {
    const v = visible();
    Object.assign(box.style, { left: v.left * 100 + "%", top: v.top * 100 + "%", width: v.w * 100 + "%", height: v.h * 100 + "%",
                               borderRadius: shape === "circle" ? "50%" : shape === "rounded" ? "10%" : "2px" });
    for (const s of sliders) { s.input.value = fr[s.k]; s.out.textContent = s.show(fr[s.k]); }
    shapeButtons.forEach((b, i) => b.setAttribute("aria-pressed", String(SHAPES[i][0] === shape)));
  };
  const store = () => {
    const entry = { ...(framed ? { x: Math.round(fr.x), y: Math.round(fr.y), zoom: Math.round(fr.zoom * 100) / 100 } : {}),
                    ...(shape ? { shape } : {}) };
    S.settings.photos ??= {};
    if (Object.keys(entry).length) S.settings.photos[name] = entry; else delete S.settings.photos[name];
    S.settingsChanged = true; updateBar();
  };
  const set = change => { fr = { ...fr, ...change }; framed = true; store(); draw(); updatePreview(); };
  const setShape = id => {
    shape = id; store(); draw(); updatePreview(true);
    setTimeout(draw, 800);  // the frame of the new shape (e.g. square) is known once the preview has it
  };
  // click or drag on the photo: that point goes to the middle of what the CV shows
  const aim = e => {
    const r = pic.getBoundingClientRect(), v = visible();
    const px = clamp((e.clientX - r.left) / r.width, 0, 1), py = clamp((e.clientY - r.top) / r.height, 0, 1);
    set({ x: v.w < 1 ? clamp((px - v.w / 2) / (1 - v.w) * 100, 0, 100) : fr.x,
          y: v.h < 1 ? clamp((py - v.h / 2) / (1 - v.h) * 100, 0, 100) : fr.y });
  };
  stage.addEventListener("pointerdown", e => { stage.setPointerCapture(e.pointerId); aim(e); });
  stage.addEventListener("pointermove", e => { if (stage.hasPointerCapture(e.pointerId)) aim(e); });
  pic.addEventListener("load", draw);
  const reset = () => {
    if (S.settings?.photos?.[name]) { delete S.settings.photos[name]; S.settingsChanged = true; updateBar(); }
    updatePreview(true);
    setTimeout(renderFramePanel, 700);  // again, with the framing and shape of the style
  };
  fill(p,
    h("div", { class: "panel-head" }, h("strong", {}, "Frame the photo"), button("✕", "Close", () => { p.hidden = true; renderPhotos(); })),
    h("small", { class: "hint" }, "Click or drag on the photo where you want its middle, or use the sliders. ",
      "The light part is what the ", h("b", {}, S.styles.find(x => x.id === S.style)?.name || "current"), " style shows; ",
      "the preview on the right shows the result."),
    stage,
    sliders.map(s => s.el),
    S.canZoom ? null : h("small", { class: "hint" }, "To zoom in, install Pillow (", h("code", {}, "pip install pillow"), ") and open the editor again."),
    h("div", { class: "subtitle" }, "Shape"),
    h("div", { class: "shape-row" }, shapeButtons),
    h("small", { class: "hint" }, `The same framing and shape are used for “${name}” in every style and language of this CV. `, h("b", {}, "Save"), " keeps them."),
    h("div", { class: "frame-actions" },
      h("button", { type: "button", class: "btn", title: "Back to how the style frames and shapes the photo", onclick: reset }, "Reset"),
      h("button", { type: "button", class: "btn primary", onclick: () => { p.hidden = true; renderPhotos(); } }, "Done")));
  draw();
}

$("#btn-photo").addEventListener("click", e => { e.stopPropagation(); photoPanel(); });
$("#btn-frame").addEventListener("click", e => { e.stopPropagation(); framePanel(); });

export {
  renderPhotos, signatureCard
};
