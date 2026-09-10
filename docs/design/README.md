# Design records

The operator's Claude Design canvases, committed so a build can be checked against the
design it was made from. A canvas is the specification; the build's departures from it are
recorded beside the build, not here.

| Canvas | What it designs | Built |
|:--|:--|:--|
| [`Dispatch Display Redesign.dc.html`](<Dispatch Display Redesign.dc.html>) | The dispatch display (hall display and workstation, 1920×1080) in three turns: 1a–1d a first pass and its TV-mode and expand states, 2a the operator's own sketch with the cadastral tile dropped, **3a / 3b** two answers to "the call card is as big as the header", 3c the expand state on 3a. | **3A**, 2026-09-09, on `KioskView`, `ActiveAlertBanner`, `RouteOverviewPanel`, the two view tiles. What departs from the canvas and why: [`briefings/mobile_accessibility_review.md`](../briefings/mobile_accessibility_review.md) §7. 3C (the expand state) is not built. |

## Reading a canvas

The `.dc.html` is a Claude Design document: the artboards are plain HTML with inline styles,
so the layout, labels and notes are readable in any editor, and every artboard's readme
(`dv-read`) is in the file. Opening it in a browser needs `support.js` beside it (committed)
and **React from unpkg.com, which `support.js` fetches** — the canvas is a design tool's
record, not part of the application, and nothing in the app loads it. The `sc-if` /
`sc-for` tags are the tool's template switches (`bigCall`, `showBanners`, the hydrant states).

**Not committed: the three placeholder images** the canvas references (`assets/aerial.png`,
`assets/route.png`, `assets/streetview.png`). `streetview.png` is a Google Street View capture,
which the Maps Platform terms do not allow to be stored (`docs/standards/README.md`, §3.2.3);
`route.png` is a screenshot of the Carto street basemap (CLAUDE.md §1, the licence caution);
`aerial.png` is a screenshot of the app's own orthophoto tile and is left out with them so
the rule is one rule. The real app renders all three from its own layers. In the canvas those
three slots show as broken images; the layout around them is the specification.

The source canvas lives outside git in `archive/UX_Claude_Design/` on the operator's machine,
and is also readable in Claude Design (project `dbba6af9-4a18-4cc8-a5d8-e096f6f17c1f`). This
copy is the 2026-09-09 state that 3A was built from.
