// What the whole editor shares: the state of the CV on screen (S), the secret token, the kinds of contact.

const TOKEN = document.querySelector('meta[name="cv-editor-token"]').content;  // put in the page by the server
const $ = s => document.querySelector(s);
// the kinds of contact, in groups, with their names: they come with the CV (CONTACT_GROUPS in contacts.py)
let CONTACT_GROUPS = [], CONTACT_TYPES = {}, ICON_NAMES = {}, WEB_CONTACTS = [];
// names of the other icons a contact can have
const OTHER_ICON_NAMES = { address: "Place", web: "Globe", mobile: "Mobile phone", chat: "Chat", chain: "Link", home: "Home",
                           calendar: "Calendar", user: "Person", briefcase: "Work", star: "Star", heart: "Heart" };
function setContactKinds(groups) {
  CONTACT_GROUPS = groups;
  CONTACT_TYPES = Object.assign({}, ...groups.map(g => g[1]));
  ICON_NAMES = { ...CONTACT_TYPES, ...OTHER_ICON_NAMES };
  // the contacts with a link of their own (the others make it from the text: email, phone, WhatsApp, ORCID iD)
  WEB_CONTACTS = Object.keys(CONTACT_TYPES).filter(k => !["phone", "email", "address", "whatsapp", "orcid"].includes(k));
}
const DESC_HINT = "Each line is a bullet point in the CV. You can use **bold**, *italic* and links.";

const S = {
  profile: null, profiles: [],   // the CV that is open, and every CV (one per person)
  languages: {},         // code -> { name, data, order: [{fixed: "experience"} | {section: {...}}] }
  language: "it", style: "formal", photo: null, photoList: [],
  changed: {}, photosChanged: false, version: 0,
  styles: [], colors: {}, settings: null, settingsChanged: false,   // styles, palettes, choice per style
  templates: [],                     // known languages (name and translated section titles)
  saved: new Set(), deleted: new Set(), languagesChanged: false,
  open: new WeakSet(),   // entries open in the form
  focus: null, toFocus: null,
  fixedSections: [],                 // the fixed sections (experience, education...): those not in "order" were removed
  sideSuggested: [],                 // sections put in the sidebar when it is switched on
  lastSide: null,                    // what was in the sidebar before it was switched off
  view: "live",                      // "live" preview or the real "pages"
};

export {
  $, CONTACT_GROUPS, CONTACT_TYPES, DESC_HINT, ICON_NAMES, S, setContactKinds, TOKEN, WEB_CONTACTS
};
