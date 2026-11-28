# Converza: Complete UI Spec

> Give this file to the coding agent. It **replaces** the current UI design. Follow it literally: layout, sizes, states, copy and colors are all specified. Backend routes stay as in `CONVERZA_AGENT_GUIDE.md`.

---

## 0. What is wrong with the current UI (remove these)

| Problem in the current build | Fix |
|---|---|
| Landing-page hero ("Convert files on your own hardware") pushes the real action down | Tiny title only, and only while no files are added |
| Two-column desktop layout with sidebar cards ("Conversion options", "Device engines") | Single centered column, no sidebars |
| Empty placeholder card "Relevant settings appear automatically..." | Delete. Options live inside each file card |
| Big "Supported formats" grid on the main screen | Move into the Info bottom sheet |
| Device engine status list on the main screen | Move into the Info bottom sheet, show one status dot in the header |
| "Ctrl+V" paste hint on a phone | Show only on devices with a mouse (`@media (hover:hover)`) |
| Tiny, low-contrast gray text (about 11px) | Minimum 12px, body 14 to 16px, muted text must reach 4.5:1 contrast |
| Near-invisible dashed dropzone border | Visible 2px dashed border, tinted background, clear drag-over state |
| Desktop-first design | Design for 360 to 430px wide phones first, then center it on larger screens |

The goal: the user opens the page and the **only** thing they see is a dropzone. After adding files, the **only** things they see are file cards and one big action button.

---

## 1. Principles

1. **One screen, one job:** add files, pick a format, convert, download.
2. **Mobile first.** Everything is a single column. Max content width 640px, centered on larger screens.
3. **Thumb friendly.** Tap targets at least 48px high. Primary actions are full width. Bulk action bar is fixed at the bottom.
4. **Quiet UI.** One accent color. Category colors appear only on small icon chips. No gradients, no glow, no decorative backgrounds.
5. **Show state, not text.** Every file card clearly shows exactly one state: ready, queued, running, done, error.
6. **Light weight.** System font stack, inline SVG icons, no web fonts, no icon fonts, no extra JS libraries.

---

## 2. Design tokens

### 2.1 Colors

| Token | Dark | Light |
|---|---|---|
| page background (`base-100`) | `#0f1419` | `#f8fafc` |
| card surface (`base-200`) | `#161c24` | `#ffffff` |
| border / divider (`base-300`) | `#222c3a` | `#e2e8f0` |
| text (`base-content`) | `#e6edf3` | `#0f172a` |
| muted text | `#9aa7b4` | `#475569` |
| primary (buttons, selected chip, focus ring) | `#38bdf8` | `#0284c7` |
| text on primary | `#04202e` | `#ffffff` |
| success | `#34d399` | `#059669` |
| error | `#f87171` | `#dc2626` |
| warning | `#fbbf24` | `#d97706` |

**Category icon chip colors** (icon uses the color, chip background is the same color at 15% opacity):

| Category | Color | Icon (Lucide) |
|---|---|---|
| Video | sky `#38bdf8` | `film` |
| Audio | emerald `#34d399` | `music` |
| Image | amber `#fbbf24` | `image` |
| Document | indigo `#818cf8` | `file-text` |
| PDF | rose `#fb7185` | `file` |

### 2.2 Typography

- Font: `ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. Monospace only for file extensions: `ui-monospace, monospace`.
- Page title: 24px / 600. Section title: 18px / 600. Card title (file name): 16px / 500. Body and buttons: 16px. Meta text: 14px, muted. Smallest allowed: 12px (badges only).

### 2.3 Spacing, shape, motion

- 4px grid. Page padding: 16px (24px at 768px and up). Card padding: 16px. Gap between cards: 12px. Gap inside a card: 12px.
- Radius: cards 16px, buttons and inputs 12px, chips 999px.
- Borders: 1px solid border color. No heavy shadows (dark theme: none; light theme: `shadow-sm` only).
- Transitions: 150ms ease on color, background and opacity only. Respect `prefers-reduced-motion` (disable the indeterminate animation and use a static striped bar).

### 2.4 DaisyUI theme config (ui-build/tailwind.config.js)

```js
module.exports = {
  content: ['../templates/**/*.html'],
  plugins: [require('daisyui')],
  daisyui: {
    themes: [
      { 'converza-dark': {
          'color-scheme': 'dark',
          'primary': '#38bdf8', 'primary-content': '#04202e',
          'base-100': '#0f1419', 'base-200': '#161c24', 'base-300': '#222c3a',
          'base-content': '#e6edf3',
          'success': '#34d399', 'error': '#f87171', 'warning': '#fbbf24',
          '--rounded-box': '1rem', '--rounded-btn': '0.75rem',
      } },
      { 'converza-light': {
          'color-scheme': 'light',
          'primary': '#0284c7', 'primary-content': '#ffffff',
          'base-100': '#f8fafc', 'base-200': '#ffffff', 'base-300': '#e2e8f0',
          'base-content': '#0f172a',
          'success': '#059669', 'error': '#dc2626', 'warning': '#d97706',
          '--rounded-box': '1rem', '--rounded-btn': '0.75rem',
      } },
    ],
  },
};
```

Theme logic: on load read `localStorage.theme` (inside try/catch). If empty, use `prefers-color-scheme`. Set `<html data-theme="converza-dark|converza-light">`. Default is dark.

---

## 3. Page map

```
Page
├── Header (sticky)
├── Main (single column, max-w 640px)
│   ├── Intro (only when no files)
│   ├── Dropzone (big when empty, slim bar when files exist)
│   ├── File list
│   │   └── File card (one per file, repeated)
│   └── Toast area
├── Bulk action bar (fixed bottom, only when files exist)
├── Info bottom sheet (<dialog>)
└── Footer line
```

---

## 4. Wireframes

### 4.1 Empty state (phone)

```
+----------------------------------+
| [logo] Converza            (o) (m)|   Header 56px
+----------------------------------+
|                                  |
|  Convert any file                |   24px title
|  Private, runs on this device.   |   14px muted
|                                  |
|  +- - - - - - - - - - - - - - -+ |
|  |                             | |
|  |          [ up icon ]        | |
|  |   Drop files here to        | |
|  |   convert                   | |
|  |                             | |
|  |   +---------------------+   | |
|  |   |    Choose files     |   | |   48px primary button
|  |   +---------------------+   | |
|  |    Up to 500 MB per file    | |   12px muted
|  +- - - - - - - - - - - - - - -+ |
|                                  |
|  Files delete after 1 hour       |   14px muted, centered
|  How it works                    |   text button, opens Info sheet
+----------------------------------+
(o) = engine status dot (opens Info sheet)   (m) = theme toggle
```

### 4.2 Files added (phone)

```
+----------------------------------+
| [logo] Converza            (o) (m)|
+----------------------------------+
|  +------------------------------+|
|  |  + Add more files            ||   Slim dropzone, 56px
|  +------------------------------+|
|                                  |
|  +------------------------------+|
|  | [vid]  holiday-trip.mov   [x]||   File card
|  |        MOV  148 MB           ||
|  |                              ||
|  |  Convert to                  ||
|  |  (MP4) (MKV) (WEBM) (GIF)    ||   Format chips
|  |  (MP3) (WAV) (M4A)           ||
|  |                              ||
|  |  > Options                   ||   Collapsible
|  |                              ||
|  |  +------------------------+  ||
|  |  |        Convert         |  ||   48px, full width
|  |  +------------------------+  ||
|  +------------------------------+|
|                                  |
|  +------------------------------+|
|  | [img]  receipt.png        [x]||
|  |  ...                         ||
|  +------------------------------+|
|                                  |
|         (space for bar)          |
+----------------------------------+
| +------------------------------+ |   Fixed bottom bar
| |      Convert all (2)         | |
| +------------------------------+ |
+----------------------------------+
```

### 4.3 File card states (bottom area of the card only)

```
READY      [        Convert         ]

QUEUED     (spinner) Waiting in queue
           [x] Cancel

RUNNING    Converting...   00:12
           [=====>        ]        (indeterminate progress bar)

DONE       (check) Done  12.1 MB
           [     Download     ]  [ Convert again ]

ERROR      (alert) Conversion failed
           Short reason (max 2 lines)
           [   Retry   ]   > Show details
```

While `queued`, `running` or `done`, the format chips and Options become read-only (dimmed, not clickable). "Convert again" resets the card to READY.

### 4.4 Info bottom sheet

```
+----------------------------------+
|  --- (drag handle)               |
|  About Converza             [x]  |
|                                  |
|  Engines on this device          |
|  FFmpeg (video, audio)   Ready   |
|  ImageMagick (images)    Ready   |
|  Pandoc (documents)      Ready   |
|  Poppler (PDF)           Ready   |
|  Tesseract (OCR)         Ready   |
|                                  |
|  Supported formats               |
|  > Video                         |   Accordion, one open at a time
|  > Audio                         |
|  > Image                         |
|  > Document                      |
|  > PDF                           |
|                                  |
|  Known limits                    |
|  No Office or Markdown to PDF,   |
|  no mobi/azw3. Large videos are  |
|  slow on a phone.                |
+----------------------------------+
```

### 4.5 Desktop (768px and up)

Same single column, centered, `max-w-[640px]`. No sidebars. The Info sheet becomes a centered modal (`sm:modal-middle`). The bottom bar becomes a sticky bar at the bottom of the same 640px column.

---

## 5. Component specs

### 5.1 Header
- Sticky top, height 56px, background `base-100` with a 1px bottom border, plus `padding-top: env(safe-area-inset-top)`.
- Left: logo mark (28px SVG, two arrows forming a swap) + "Converza" (18px / 600).
- Right, two icon buttons (44x44, ghost style):
  1. **Status dot button:** 10px dot, green if all engines ready, amber if some missing. Tap opens the Info sheet. `aria-label="Device status"`.
  2. **Theme toggle:** sun or moon icon only, no text. `aria-label="Toggle theme"`.
- Remove the "On-device" badge, the "Private . Auto-cleans in 1h" text and the "Light" text label.

### 5.2 Intro (only when the file list is empty)
- Title: "Convert any file" (24px / 600). Subtitle: "Private, runs on this device." (14px muted).
- Hidden as soon as the first file is added.

### 5.3 Dropzone
- **Empty state:** card with 2px dashed border (`base-300`, becomes primary on hover or drag), padding 32px 16px, centered content: 48px upload icon in a 56px tinted circle, title "Drop files here to convert" (18px / 600), button "Choose files" (primary, 48px high, min-width 200px), note "Up to 500 MB per file" (12px muted).
- **Files-added state:** collapses to a slim 56px bar with a plus icon and "Add more files". Same click and drop behavior.
- **Drag-over state** (whole page listens for `dragenter`): dropzone gets a solid primary border, primary tint background (10%), text changes to "Release to add". A full-page overlay is not needed.
- **Paste:** `paste` event with files adds them. Show the "or paste (Ctrl+V)" hint only under `@media (hover:hover) and (pointer:fine)`.
- The whole dropzone is a `<label for="picker">`, so a tap anywhere opens the file picker. Input: `multiple`, hidden with `class="hidden"`.
- On selecting files: submit via HTMX `hx-post="/upload"`, `hx-target="#file-list"`, `hx-swap="beforeend"`.

### 5.4 File card
Structure (top to bottom):
1. **Header row** (flex, gap 12): category icon chip (40x40, radius 12) | text block (flex-1, min-w-0) | remove button (44x44 ghost, X icon, `aria-label="Remove file"`).
   - File name: 16px / 500, single line, `truncate`. Always show the extension (truncate the middle of the name, not the end, if easy; otherwise truncate normally).
   - Meta line: `MOV  148 MB` (14px muted, extension in monospace and uppercase).
2. **Format chips** (only in READY state, dimmed otherwise):
   - Label: "Convert to" (14px muted).
   - Chips are radio inputs styled as pills: height 40px, padding 0 16px, 1px border, 14px / 500 uppercase text. Selected: primary background and primary-content text. Unselected: transparent with border. Wrap onto multiple lines, gap 8px.
   - `ocr_txt` label is "Text (OCR)". All others are the uppercase extension.
   - A default chip is **pre-selected**: the first target that differs from the input extension (exceptions: video defaults to MP4, or WEBM if the input is MP4; PDF defaults to PNG; image defaults to JPG, or PNG if the input is JPG).
3. **Options** (video, audio and image only): a `<details>` row, 48px high summary "Options" with a chevron. Contents are described in section 6. Closed by default.
4. **Action area:** see the state table in section 7. Always full width, 48px high buttons.

Card: background `base-200`, 1px border, radius 16px, padding 16px, gap 12px. A card enters with a 150ms fade (no sliding).

### 5.5 Bulk action bar
- Appears only when there is at least one file. Fixed to the bottom, full width, background `base-100` with a top border, padding 12px 16px plus `env(safe-area-inset-bottom)`. Inner content is max 640px, centered.
- Button label changes with state:
  - Some cards are READY: **"Convert all (N)"** (primary). N is the number of READY cards.
  - Any card queued or running: **"Converting N of M..."** (disabled, shows spinner).
  - All finished and at least 2 are done: **"Download all (ZIP)"** (primary).
  - Exactly 1 file: hide the bar entirely (the card already has the action).
- Give `<main>` `padding-bottom: 96px` so the last card is never covered.

### 5.6 Info bottom sheet
- Native `<dialog class="modal modal-bottom sm:modal-middle">` (DaisyUI). Max height 85vh, scrollable inside, rounded top corners 24px, drag handle bar on phones, X button top right.
- Opened by the header status dot and the "How it works" text button. Close on backdrop click and Esc.
- Sections: Engines (rows with name and a Ready / Missing badge), Supported formats (accordion per category with `-> targets` list), Known limits.
- Data comes from a `/info` partial (HTMX `hx-get="/info" hx-target="#info-body"` on first open), built from `registry.CATEGORIES`, `registry.TARGETS` and `shutil.which` checks.

### 5.7 Toasts
- DaisyUI `toast toast-top toast-center` with `alert` (max 1 visible, auto-hide after 4s).
- Used for: "2 files skipped: unsupported type", "File too large (max 500 MB)", "Copied" etc.

### 5.8 Footer line
- Below the list, centered, 14px muted: "Files delete automatically after 1 hour".
- Not shown when the bulk bar is visible (the Info sheet already says it).

---

## 6. Options panel (per file card)

Options are collapsed by default. Defaults must give a good result without opening them.

| Category | Option | Values | Default | Command effect |
|---|---|---|---|---|
| Video | Size | Original, 1080p, 720p, 480p | Original | ffmpeg `-vf scale=-2:<h>` |
| Video | Quality | High, Balanced, Small | Balanced | ffmpeg `-crf 20 / 26 / 31` (libx264 targets) |
| Audio (and video to audio) | Bitrate | 320, 192, 128 kbps | 192 | ffmpeg `-b:a <n>k` |
| Image | Quality | slider 60 to 100 | 85 | magick `-quality <n>` |
| Image | Width | Original, 1920, 1280, 800 | Original | magick `-resize <w>x` |
| Document, PDF | none | | | Hide the Options row |

Backend note: extend `build_cmd(category, src, dst_base, target, opts=None)` and read the values from `request.form` in `/convert/<job_id>`. Whitelist every value (never pass raw form text to a command).

---

## 7. File card state machine (HTMX)

| State | Card bottom area | Chips and Options | Polling |
|---|---|---|---|
| `uploaded` (READY) | Primary button "Convert" | Editable | no |
| `queued` | Spinner, "Waiting in queue", Cancel text button | Dimmed | `hx-trigger="every 1s"` |
| `running` | "Converting...", elapsed time, indeterminate `progress` bar | Dimmed | `hx-trigger="every 1s"` |
| `done` | Success row with result size, **Download** (primary) and **Convert again** (outline) | Dimmed | stops |
| `error` | Error row with short message, **Retry** (primary), "Show details" disclosure with stderr tail | Editable | stops |

Rules:
- The card root has `id="job-{{ job.id }}"`. Polling swaps only the card (`hx-swap="outerHTML"`), so scroll position and focus are preserved.
- Add `aria-live="polite"` on the status row so screen readers hear state changes.
- The bulk bar is refreshed with an out-of-band swap (`hx-swap-oob="true"` on `#bulk-bar`) whenever a card partial is returned.
- "Remove" (X) calls `DELETE /jobs/<id>` (or `POST /jobs/<id>/delete`), removes the card and deletes its files. Disabled while `running`.
- "Convert again" calls `POST /jobs/<id>/reset` and returns the card in READY state.

New or changed partials:

| Partial | Purpose |
|---|---|
| `partials/file_card.html` | One full card (replaces `file_rows.html` and `job_row.html`; renders the right bottom area for the job's status) |
| `partials/bulk_bar.html` | The bottom bar, rendered out-of-band |
| `partials/info.html` | Content of the Info sheet |
| `partials/toast.html` | One toast message |

---

## 8. Microcopy

| Place | Text |
|---|---|
| Page title | Convert any file |
| Subtitle | Private, runs on this device. |
| Dropzone title | Drop files here to convert |
| Dropzone button | Choose files |
| Dropzone note | Up to 500 MB per file |
| Dropzone (drag over) | Release to add |
| Slim dropzone | Add more files |
| Chips label | Convert to |
| Ready button | Convert |
| Queued | Waiting in queue |
| Running | Converting... |
| Done | Done |
| Done buttons | Download, Convert again |
| Error | Conversion failed |
| Error button | Retry |
| Bulk | Convert all (N), Converting N of M..., Download all (ZIP) |
| Unsupported file toast | N file(s) skipped: unsupported type |
| Too large toast | File too large (max 500 MB) |
| Footer | Files delete automatically after 1 hour |

Tone: short, plain, no marketing words.

---

## 9. Icons

Inline SVG from Lucide, 20px by default (24px in the dropzone circle). Needed: `upload`, `plus`, `x`, `film`, `music`, `image`, `file-text`, `file`, `check-circle`, `alert-circle`, `download`, `chevron-down`, `sun`, `moon`, `loader`, `info`. Put them in one Jinja macro file `templates/_icons.html` so each icon is defined once. No icon font and no CDN.

---

## 10. Responsive and accessibility rules

**Breakpoints:** design at 360px. Verify at 360, 390, 430, 768 and 1280px. Never allow horizontal scroll at any width.

**Accessibility**
- Text contrast 4.5:1 or better in both themes. Use the muted colors from section 2.1, never lighter.
- All interactive elements are real `<button>`, `<label>`, `<input>` or `<summary>`; visible focus ring: 2px primary with 2px offset.
- Chips are real radio inputs inside a `<fieldset>` with a `<legend>` ("Convert to").
- Icon-only buttons have `aria-label`.
- Do not rely on color alone: states always include an icon and text.
- `prefers-reduced-motion`: no animation except a static bar.

**Safe areas:** `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`, with padding using `env(safe-area-inset-*)` on the header and the bottom bar.

---

## 11. Acceptance checklist

The UI is done only when every line is true:

- [ ] Opening the page on a 390px phone shows header, title, dropzone and nothing else. No scrolling needed.
- [ ] There are no sidebars, no hero, no formats grid and no engine list on the main screen.
- [ ] Adding 3 files shows 3 cards and a "Convert all (3)" bar; the last card is not hidden behind the bar.
- [ ] Each card has a pre-selected format, so a single tap on "Convert" works.
- [ ] Format chips and buttons are at least 40px and 48px high respectively.
- [ ] All five states (ready, queued, running, done, error) look different and each has an icon plus text.
- [ ] Polling cards do not make the page jump or lose scroll position.
- [ ] Both themes pass the contrast rule. Theme choice persists after reload.
- [ ] The Info sheet opens from the header dot and "How it works", closes with Esc and backdrop.
- [ ] Nothing scrolls horizontally at 360, 390, 430, 768 and 1280px.
- [ ] Final `app.css` is under 100 KB and the page loads no external resources.

---

## 12. Suggested work order for the agent

1. Add the two DaisyUI themes and rebuild `app.css`. Add the theme toggle.
2. Rebuild `base.html`: header, single column `<main>`, footer line, Info dialog shell.
3. Rebuild `index.html`: intro and dropzone (empty and slim states), drag-over and paste handling.
4. Create `partials/file_card.html` with all five states and the chips.
5. Add the Options panel and extend `build_cmd` with `opts`.
6. Add `bulk_bar.html` with out-of-band updates and the new routes (`reset`, `delete`, `/info`).
7. Add toasts, empty and error handling, accessibility pass.
8. Check every item in section 11 at the five widths and fix what fails.
