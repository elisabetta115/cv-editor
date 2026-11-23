"""
Automatic translation of a CV, with one of two translators:

- "local": an AI model on this computer, run by Ollama (https://ollama.com, free, MIT licence) with
  Qwen3 (Apache 2.0 licence: free for any use, commercial too). Nothing leaves the computer and
  there is no key nor limit; it needs Ollama installed and the model downloaded (ollama pull qwen3:8b).
- "azure": Microsoft Azure AI Translator. Its free tier (F0) translates 2 million characters a month;
  Microsoft does not keep the text it translates. It needs the user's own key.

Either way only the text of the CV is translated: names, contacts, organisations and links stay as
they are (and are never sent to Microsoft).

The Azure key is kept on this computer, in ~/.config/cv-editor/translator.json (readable only by you):
it never reaches the browser and is never part of an exported CV. Environment variables:
AZURE_TRANSLATOR_KEY and AZURE_TRANSLATOR_REGION are used instead of the saved key,
AZURE_TRANSLATOR_ENDPOINT names another endpoint (e.g. https://api-eur.cognitive.microsofttranslator.com
to have the text processed in Europe), OLLAMA_HOST where Ollama listens and CV_OLLAMA_MODEL another
model than Qwen3 (check its licence).
"""
import copy
import html
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

import generate_cv as cv

KEEP = {"first_name", "last_name", "organization", "link", "type", "id", "builtin", "hidden", "column", "after",
        "copied_from"}
KEEP_TOP = {"contacts", "cv_language"}             # whole parts of the CV that are not translated


# ---------------------------------------------------------------------
#  The AI on this computer (Ollama)
# ---------------------------------------------------------------------
def _ollama_url():
    host = os.environ.get("OLLAMA_HOST", "").strip() or "127.0.0.1:11434"
    host = host if "://" in host else "http://" + host
    return host.rstrip("/").replace("://0.0.0.0", "://127.0.0.1")


# Qwen3 (Apache 2.0): the first of these that is installed is used
MODELS = ["qwen3:8b", "qwen3:latest", "qwen3:14b", "qwen3:4b", "qwen3:30b", "qwen3:32b"]
SUGGESTED_MODEL = "qwen3:8b"
LOCAL_MAX_CHARS, LOCAL_MAX_ITEMS = 2_000, 60       # short lines: many at once, so that the AI sees them together
LONG_LINE = 5                                      # words: longer lines (sentences) are translated one at a time
LOCAL_TIMEOUT = 900                                # seconds: computers without a graphics card are slow
# the sampling Qwen3 recommends without thinking (greedy decoding makes it copy and repeat)
LOCAL_OPTIONS = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "num_ctx": 8192}

RULES = """- Write as in a well-written professional CV in {target}: natural, concise, faithful to the meaning; do not add or remove anything.
- Keep unchanged: names of people, companies, products and technologies (e.g. Figma, HTML), URLs, e-mail addresses,
  numbers and CEFR levels such as B2 or C1. Translate month names and words such as "today".
- Keep **bold** and *italic* markers around the corresponding words.
- A link is written [words](address): translate the words in brackets, copy the address in parentheses exactly.
- The person's gender is not known: where {target} needs it, choose wording that avoids it."""
# a block of short lines (titles, skills, labels): the AI sees what each one is
PROMPT_SHORT = """You translate CVs (résumés) from {source} to {target}.
You receive a JSON object with short lines of one person's CV, in order. Each key is a number followed by what the
line is (job title, language level, soft skill...).
Answer with a JSON object with exactly the same keys, each value translated into {target}.
- Every value must be in {target}: job titles, skills, language names, language levels written in words
  (e.g. "Native"), grades (e.g. "Distinction"), labels and list items.
""" + RULES
# one sentence or paragraph: a model of this size translates long lines better one at a time
PROMPT_LINE = """You translate one part of a CV (résumé) from {source} to {target}: its {kind}.
Answer with the translation only, in {target}.
""" + RULES
ATTEMPTS = 3   # a long line that comes back copied is translated again


def _copied(line, out):
    """The model sometimes copies the original line, or its beginning, instead of translating it."""
    first = lambda text: re.findall(r"[^\W\d_]{3,}", text.lower())[:2]
    return out.strip() == line.strip() or (len(first(line)) == 2 and first(line) == first(out))


def _ollama(path, body=None, timeout=LOCAL_TIMEOUT):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(_ollama_url() + path, data=data, headers={"Content-Type": "application/json"},
                                     method="POST" if body is not None else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return json.load(r)


def local_status():
    """{"running": Ollama answers, "model": the model that will be used (None: no suitable model installed)}"""
    try:
        tags = _ollama("/api/tags", timeout=2)
    except (urllib.error.URLError, OSError, ValueError):
        return {"running": False, "model": None, "suggested": SUGGESTED_MODEL}
    names = [str(m.get("name") or m.get("model")) for m in tags.get("models", []) if isinstance(m, dict)]
    wanted = os.environ.get("CV_OLLAMA_MODEL", "").strip()
    model = next((m for m in ([wanted] if wanted else MODELS) if m in names), None)
    if not model and not wanted:
        model = next((m for m in names if m.startswith("qwen3:")), None)
    return {"running": True, "model": model, "suggested": wanted or SUGGESTED_MODEL}


def _chat(model, system, user, keys):
    """Asks the model; its answer is a JSON object with exactly these keys (Ollama keeps it to the schema)."""
    schema = {"type": "object", "properties": {k: {"type": "string"} for k in keys}, "required": keys,
              "additionalProperties": False}
    body = {"model": model, "stream": False, "think": False, "format": schema, "options": LOCAL_OPTIONS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        out = json.loads(_ollama("/api/chat", body)["message"]["content"])
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read() or b"{}").get("error") or e.reason
        except (ValueError, OSError):
            detail = e.reason
        raise RuntimeError(f"The AI on this computer (Ollama) stopped: {detail}") from None
    except TimeoutError:
        raise RuntimeError("The AI on this computer is taking too long: try Microsoft Translator.") from None
    except (urllib.error.URLError, OSError):
        raise RuntimeError("The AI on this computer is not running: start Ollama (or install it from ollama.com).") from None
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("The AI on this computer gave an unexpected answer: try again.") from None
    if not isinstance(out, dict):
        raise RuntimeError("The AI on this computer gave an unexpected answer: try again.")
    return out


def _translate_local(lines, kinds, r):
    status = local_status()
    if not status["running"]:
        raise RuntimeError("The AI on this computer needs Ollama: install it from ollama.com and start it.")
    if not status["model"]:
        raise RuntimeError(f"Download the AI model first: open a terminal and run   ollama pull {status['suggested']}")
    model = status["model"]
    names = {"source": _language_name(r.get("from_name"), r["from"]), "target": _language_name(r.get("to_name"), r["to"])}
    translated = {}
    # a line the model leaves empty keeps its original text
    for line in (x for x in lines if len(x.split()) >= LONG_LINE):
        for _ in range(ATTEMPTS):
            out = _chat(model, PROMPT_LINE.format(**names, kind=kinds[line]), line, ["translation"])
            translated[line] = _keep_links(line, str(out.get("translation") or "").strip()) or line
            if not _copied(line, translated[line]):
                break
    short = [x for x in lines if len(x.split()) < LONG_LINE]
    for batch in _batches(short, LOCAL_MAX_CHARS, LOCAL_MAX_ITEMS):
        keys = [f"{i + 1}: {kinds[line]}" for i, line in enumerate(batch)]
        out = _chat(model, PROMPT_SHORT.format(**names), json.dumps(dict(zip(keys, batch)), ensure_ascii=False, indent=1), keys)
        translated.update((line, _keep_links(line, str(out.get(k) or "").strip()) or line) for k, line in zip(keys, batch))
    return translated, 0


def _language_name(name, code):
    name = str(name or cv.KNOWN_LANGUAGES.get(code, {}).get("name") or "").strip()[:40]
    return f"{name} ({code})" if name else code


# ---------------------------------------------------------------------
#  Microsoft Azure AI Translator
# ---------------------------------------------------------------------
AZURE_ENDPOINT = os.environ.get("AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com").rstrip("/")
CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "cv-editor" / "translator.json"
MEMORY = None   # the demo keeps the key in memory only: a dict instead of the file
AZURE_CODES = {"zh": "zh-Hans", "no": "nb"}        # where Azure's code differs from the editor's
AZURE_MAX_CHARS, AZURE_MAX_ITEMS = 10_000, 100     # per request (Azure: 50 000 and 1000; free tier: ~33 000 a minute)
KEY = re.compile(r"[A-Za-z0-9]{20,200}")
REGION = re.compile(r"[a-z0-9]{0,40}")


def _config():
    if MEMORY is not None:
        return MEMORY
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def credentials():
    if os.environ.get("AZURE_TRANSLATOR_KEY"):
        return os.environ["AZURE_TRANSLATOR_KEY"].strip(), os.environ.get("AZURE_TRANSLATOR_REGION", "").strip().lower()
    c = _config()
    return str(c.get("key") or ""), str(c.get("region") or "")


def azure_status():
    """What the editor may know: whether there is a key (never the key itself)."""
    key, region = credentials()
    return {"configured": bool(key), "region": region, "from_environment": bool(os.environ.get("AZURE_TRANSLATOR_KEY"))}


def status():
    return {"local": local_status(), "azure": azure_status()}


def set_key(r):
    """r = {"key", "region"}: checks the Azure key with a one-word translation, then keeps it. An empty key removes it."""
    key = str(r.get("key") or "").strip()
    region = re.sub(r"[\s_-]+", "", str(r.get("region") or "")).lower()
    if key:
        if not KEY.fullmatch(key):
            raise RuntimeError("This does not look like a Microsoft Translator key: copy KEY 1 from "
                               "“Keys and Endpoint” in the Azure portal.")
        if not REGION.fullmatch(region):
            raise RuntimeError("The region is written like westeurope or northeurope (see “Keys and Endpoint”).")
        _azure_batch(["Hello"], "en", "it", key, region)  # a wrong key or region stops here
    data = {"key": key, "region": region} if key else {}
    if MEMORY is not None:
        MEMORY.clear()
        MEMORY.update(data)
    elif data:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        CONFIG_FILE.chmod(0o600)
    else:
        CONFIG_FILE.unlink(missing_ok=True)
    return status()


def _azure_error(e):
    try:
        err = json.loads(e.read() or b"{}").get("error") or {}
    except (ValueError, AttributeError, OSError):
        err = {}
    detail = str(err.get("message") or "").strip() if isinstance(err, dict) else ""
    code = err.get("code") if isinstance(err, dict) else None
    if e.code == 401:
        return ("Microsoft Translator did not accept the key: check the key and the region "
                "(“Keys and Endpoint” in the Azure portal).")
    if e.code == 403:
        return ("Microsoft Translator refused the translation: the free characters of this month are probably "
                f"used up (they come back next month). {detail}").strip()
    if e.code == 429:
        return "Too much text at once for the free tier of Microsoft Translator: wait a minute and try again."
    if e.code == 400 and code in (400035, 400036):
        return "Microsoft Translator does not translate this language."
    return f"Microsoft Translator error {e.code}: {detail or e.reason}"


def _azure_batch(texts, source, target, key, region):
    query = urlencode({"api-version": "3.0", "from": AZURE_CODES.get(source, source),
                       "to": AZURE_CODES.get(target, target), "textType": "html"})
    headers = {"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/json; charset=UTF-8"}
    if region and region != "global":
        headers["Ocp-Apim-Subscription-Region"] = region
    body = json.dumps([{"Text": x} for x in texts], ensure_ascii=False).encode()
    request = urllib.request.Request(f"{AZURE_ENDPOINT}/translate?{query}", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as r:
            result = json.load(r)
        out = [str(x["translations"][0]["text"]) for x in result]
    except urllib.error.HTTPError as e:
        raise RuntimeError(_azure_error(e)) from None
    except (urllib.error.URLError, OSError):
        raise RuntimeError("Microsoft Translator cannot be reached: check the internet connection.") from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise RuntimeError("Microsoft Translator gave an unexpected answer: try again later.") from None
    if len(out) != len(texts):
        raise RuntimeError("Microsoft Translator gave an unexpected answer: try again later.")
    return out


def _keep_links(line, out):
    """The translation of a line with links ([words](address)) with their addresses as in the line: the AI
    may change an address while translating the words. None when the translation lost or added a link."""
    addresses = [m.group(2) for m in cv.MARKDOWN_LINK.finditer(line)]
    found = [m.group(2) for m in cv.MARKDOWN_LINK.finditer(out)]
    if not out or len(found) != len(addresses):
        return None
    if sorted(found) == sorted(addresses):  # copied right (the words may have moved, with their links)
        return out
    rest = iter(addresses)
    return cv.MARKDOWN_LINK.sub(lambda m: f"[{m.group(1)}]({next(rest)})", out)


# **bold**, *italic* and the words of links travel as HTML tags, so that the translation keeps them around
# the right words. The address of a link is not sent: <a id="0">words</a>, _from_html puts it back.
LINK_TAG = re.compile(r"""<a\b[^>]*?\bid\s*=\s*["']?(\d+)["']?[^>]*>(.*?)</a>""", re.S | re.I)


def _to_html(line):
    """(the line as HTML, the addresses of its links)"""
    addresses = []

    def link(m):
        addresses.append(m.group(2))
        return f"\ue000{len(addresses) - 1}\ue001{m.group(1)}\ue002"
    s = cv.MARKDOWN_LINK.sub(link, line.replace("\ue000", "").replace("\ue001", "").replace("\ue002", ""))
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    return re.sub("\ue000(\\d+)\ue001(.*?)\ue002", r'<a id="\1">\2</a>', s), addresses


def _from_html(s, addresses=()):
    """The translation back as text, with its links; None when a link was lost."""
    back = {}

    def link(m):
        i = int(m.group(1))
        if i >= len(addresses) or i in back:
            return m.group(2)
        back[i] = addresses[i]
        return f"\ue000{i}\ue001{m.group(2)}\ue002"
    s = LINK_TAG.sub(link, s)
    if len(back) != len(addresses):
        return None
    s = re.sub(r"<b>\s*(.*?)\s*</b>", r"**\1**", s, flags=re.S)
    s = re.sub(r"<i>\s*(.*?)\s*</i>", r"*\1*", s, flags=re.S)
    s = html.unescape(re.sub(r"<[^>]*>", "", s)).strip()
    words = lambda w: " ".join(w.replace("[", "").replace("]", "").split()) or "link"
    return re.sub("\ue000(\\d+)\ue001(.*?)\ue002", lambda m: f"[{words(m.group(2))}]({back[int(m.group(1))]})", s, flags=re.S)


def _translate_azure(lines, kinds, r):
    key, region = credentials()
    if not key:
        raise RuntimeError("Add your Microsoft Translator key first.")
    translated, characters = {}, 0
    for batch in _batches(lines, AZURE_MAX_CHARS, AZURE_MAX_ITEMS):
        sent = [_to_html(x) for x in batch]
        texts = [text for text, _ in sent]
        characters += sum(map(len, texts))
        out = _azure_batch(texts, r["from"], r["to"], key, region)
        # a line whose translation lost a link keeps its original text
        translated.update((x, _from_html(o, addresses) or x) for x, o, (_, addresses) in zip(batch, out, sent))
    return translated, characters


# ---------------------------------------------------------------------
#  The CV
# ---------------------------------------------------------------------
def _batches(texts, max_chars, max_items):
    batch, size = [], 0
    for x in texts:
        if batch and (len(batch) >= max_items or size + len(x) > max_chars):
            yield batch
            batch, size = [], 0
        batch.append(x)
        size += len(x)
    if batch:
        yield batch


# what a line is, from the key that holds it (for the AI: "Native" as a language level)
FIELDS = {"role": "job title", "location": "place", "grade": "final grade", "thesis": "thesis title",
          "language": "language name", "level": "language level", "digital": "digital skill", "soft": "soft skill",
          "list": "list item", "tags": "tag", "profile": "profile text"}
TOP_FIELDS = {"labels": "section title", "privacy": "privacy note", "interests": "interests"}


def _texts(data):
    """(table or list, key, what it is) of every text of the CV to translate. Names of organisations stay as
    they are written: an official name (Sapienza Università di Roma) is always right, a translated one may not be."""
    found = []

    def walk(node, field=None, fixed=False, top=False):
        for k, v in (node.items() if isinstance(node, dict) else enumerate(node)):
            if isinstance(node, dict) and (k in KEEP or (top and k in KEEP_TOP)):
                continue
            if top and k in TOP_FIELDS:
                f, fx = TOP_FIELDS[k], True
            elif fixed or not isinstance(node, dict):
                f, fx = field, fixed
            else:
                f, fx = FIELDS.get(k, str(k).replace("_", " ")), False
            if isinstance(v, str):
                if v.strip():
                    found.append((node, k, f or "text"))
            elif isinstance(v, (dict, list)):
                walk(v, f, fx)

    walk(data, top=True)
    return found


ENGINES = {"local": _translate_local, "azure": _translate_azure}


def _paragraphs(text):
    """The CV shows an empty line as a new paragraph and a single line break as a space (lists are lists):
    so a paragraph is translated as a whole, even when its sentences are split over several lines."""
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def translate_cv(r):
    """r = {"data": content of a language, "from": code, "to": code, "engine": "local" | "azure",
            "from_name", "to_name": names of the languages}  ->  {"data": translated content, "characters"}.
    Every paragraph is translated as a whole (titles, list items and sentences are paragraphs too), each
    different one once. Section titles known for the new language come from the editor."""
    for code in (r.get("from"), r.get("to")):
        if not isinstance(code, str) or not cv.VERSION_CODE.fullmatch(code):
            raise RuntimeError(f"Invalid language code: {code!r}.")
    # another version in a language (en-ireland) is translated as its language (en)
    r = {**r, "from": cv.base_language(r["from"]), "to": cv.base_language(r["to"])}
    engine = ENGINES.get(r.get("engine") or "azure")
    if not engine:
        raise RuntimeError("Unknown translator.")
    data = copy.deepcopy(r.get("data")) if isinstance(r.get("data"), dict) else {}
    template = cv.KNOWN_LANGUAGES.get(r["to"], {}).get("labels") or {}
    labels = data.get("labels") if isinstance(data.get("labels"), dict) else {}
    data["labels"] = {k: v for k, v in labels.items() if k not in template}

    places = _texts(data)
    kinds = {}  # every different paragraph, and what it is
    for node, k, kind in places:
        for part in _paragraphs(node[k]):
            kinds.setdefault(part, kind)
    parts = list(kinds)
    translated, characters = engine(parts, kinds, r) if parts else ({}, 0)
    for node, k, _ in places:
        node[k] = "\n\n".join(translated.get(part, part) for part in _paragraphs(node[k]))
    data["labels"].update(template)
    return {"data": data, "characters": characters}
