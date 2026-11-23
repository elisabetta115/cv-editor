# Third-party notices

CV Editor bundles a few works by other people. They keep their own licences, which are listed here.
None of them restricts the CVs and PDFs you make with the editor: those are yours.

## Fonts: SIL Open Font License 1.1

The 33 font families in `src/fonts/` (Inter, Lato, Montserrat, Playfair Display, Source Sans 3 and others)
are licensed under the SIL Open Font License, Version 1.1. Their copyright notices and the full licence
are in [`src/fonts/OFL.txt`](src/fonts/OFL.txt).
The licence allows the fonts to be bundled with any software and embedded in documents such as the PDFs;
they may not be sold by themselves.

## Icons: Lucide (ISC licence; some icons from Feather, MIT licence)

Most of the line icons in `src/editor.html` and `src/generate_cv.py` come from [Lucide](https://lucide.dev);
the others are drawn in the same style for this project.

```
ISC License

Copyright (c) 2026 Lucide Icons and Contributors

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

Some Lucide icons (for example `x`, `plus`, `check`, the arrows and chevrons, `calendar`, `link`, `trash`)
are derived from the [Feather](https://feathericons.com) project:

```
The MIT License (MIT)

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

The icons for LinkedIn, GitHub, X, Instagram and the other sites are simple line drawings that only
show which site a link leads to; the names and logos belong to their owners.

## Used but not included

These programs are not part of this repository. You install them yourself if you want them, under
their own licences: Python, Chrome or Chromium (to print the PDFs), Pillow (optional, to shrink photos),
Ollama and the Qwen3 model (optional, local translation) and Microsoft Azure AI Translator (optional,
with your own key).
