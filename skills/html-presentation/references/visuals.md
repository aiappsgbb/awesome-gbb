# Palette and visual assets

## Exact palette

Source: the user's `Azure-ColorPalette-2026.pdf`, one page. Names retain the
source spelling in this table. CSS uses conventional spelling for identifiers.

| Role | Name | Hex |
| --- | --- | --- |
| Primary | Electric Blue | #1A00E2 |
| Primary | Energy Blue | #0000B3 |
| Secondary | Deep Blue | #000085 |
| Secondary | Navy Blue | #0D0061 |
| Secondary | Pure White | #FFFFFF |
| Secondary | Light Gray 2 | #FAFAFA |
| Secondary | Light Gray | #D9D9D6 |
| Tertiary | Turquoise | #00BBC3 |
| Tertiary | Lavendar | #AAC0F6 |
| Tertiary | Bright Indigo | #5D52EC |
| Tertiary | Plum | #590055 |
| Tertiary | Fuschia | #D12ACA |
| Tertiary | Blue | #0078D4 |
| Tertiary | Sky Blue | #00FFFF |
| Tertiary | Mint | #CFF3E8 |
| Accent | Light Green | #D4EC8E |
| Accent | Light Yellow | #FFE399 |
| Accent | Light Orange | #FFA38B |
| Accent | Light Magenta | #D59ED7 |

Use `assets/palette.css`. Favor White/Navy for body text and Electric Blue/White
for emphasis. Pale accents need dark text; do not put white body text on
Turquoise, Lavender or a pale accent. Test normal text at 4.5:1 and large text
and meaningful non-text controls at 3:1. Do not use color alone for status.

## Supplied illustrations

The skill's `assets/illustrations/` contains selected supplied 512px artwork.
Use this bundled collection in any installation. If the workspace also contains
the original `Microsoft-Azure-Illcon-Illustrations/` collection, inspect it for
additional concepts; that optional folder contains Dark/Light variants at
128px and 512px (232 PNG files). Follow exact filenames: some have irregular
suffixes such as `Compass-512-512.png`.

Copy selected files into the workspace-local authoring folder before referring
to them in HTML. For example, after staging the starter:

```sh
mkdir -p "$AUTHORING_DIR/illustrations"
cp "$SKILL_DIR/assets/illustrations/Azure-Illcon-Light-Apps-512.png" \
  "$AUTHORING_DIR/illustrations/"
```

Use `src="illustrations/Azure-Illcon-Light-Apps-512.png"`. Stage selected product
SVGs in `icons/` in the same way. Keep the copied asset manifest as provenance;
all rendering files then sit within the authoring folder's `--asset-root`.

Prefer 512px for hero compositions, smaller art for compact labels. The supplied
images preserve their native colors; do not recolor them to fake a product logo.
Inspect Light and Dark variants on the actual background. Choose concepts that
explain the subject: Apps, Cloud-Lock, Chart-Up, Connectivity or Tools. Avoid
repeating the same ornamental icon beside every paragraph.

## Product diagrams

Generic illustrations are not product logos. Use authentic local product SVGs
for named Microsoft services. The bundled set comes from official Microsoft
architecture packages; see the manifest for exact source/member names.
If a needed product is absent, first discover an existing local icon collection.
Then use Microsoft Learn's official icon page if available and permitted. Do
not invent an icon, substitute a different service's logo or use an emoji.
Use a plainly labeled neutral node when an authentic icon cannot be obtained,
and record that limitation. A non-Microsoft product can be a
labeled wordmark/node unless an authentic authorized asset is available.

Keep icons undistorted, unrotated, uncropped and unrecolored. Add a readable
product label. Native icon colors are exempt from the presentation palette.
Microsoft permits its architecture icons for diagrams, training and
documentation, not arbitrary marketing-logo uses. Preserve provenance and terms:

- https://learn.microsoft.com/en-us/azure/architecture/icons/
- https://learn.microsoft.com/en-us/entra/architecture/architecture-icons

Prefer semantic HTML nodes with CSS/SVG connectors or a labeled SVG diagram.
Show flow direction, interfaces, relevant trust/tenant boundaries, where data
resides and what is proposed versus implemented. Distinguish control/identity
flow from data flow when material. Provide a concise text alternative.

An architecture should explain one path. Add a second level of detail or a
clickable detail when needed; do not compress a whole platform into unreadable
logo wallpaper. Check connectors and labels at the real presentation size.
