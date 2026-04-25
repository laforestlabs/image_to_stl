# Future Features

Ideas to consider for future iterations. Each is tagged S/M/L for rough effort.

## Visualization

- **Live 3D STL preview** (L) — Embed a 3D viewer (PyVista's `QtInteractor`, or VTK directly) in a tab next to the 2D processed-image preview. Updates whenever a new mesh is generated. Biggest perceived UX win — users currently have to flip to a slicer to see the mesh.
- **Backlight simulation** (S) — In the "Processed" pane, render the grayscale heightmap as if backlit (gamma curve + soft falloff) so users can preview how the printed lithophane will look with light behind it before exporting.
- **Cross-section overlay** (S) — Show the heightmap as a vertical cross-section along a draggable scan line; helps users tune min/max thickness visually.

## Geometry

- **Cylindrical / curved lithophanes** (L) — Wrap the heightmap around a cylinder (lampshade) or a sphere (ornament). Needs new mesh generators in `core/stl_generator.py`; the rest of the pipeline can stay as is.
- **Frame, stand, and hanging hole** (M) — Procedurally extend the mesh with a base, a slot stand, or an integrated hanging hole. Could be modeled as additional `Operation` types so they live alongside `set_lithophane_parameters` in a process.
- **Magnet pocket** (S) — Add a circular pocket on the back face for a fridge-magnet insert. Parameter: pocket diameter and depth.
- **Tile splitter** (M) — Split lithophanes larger than the user's print bed across multiple tiles with alignment dovetails or pegs. Bed size becomes a per-printer preset.
- **Multi-image parallax stack** (L) — Composite several heightmaps as discrete depth layers — looks like a tiny diorama when backlit. Would need a layered process model in the editor.

## Image Processing

- **Histogram equalization / auto-contrast** (S) — Optional preprocess step before height mapping; huge improvement on typical phone photos with poor contrast.
- **Edge enhancement / sharpening** (S) — Unsharp-mask filter so portraits keep facial features that the current Gaussian blur softens away.
- **Background removal** (M) — Optional rembg integration to isolate a subject before lithophane conversion. Heavy dependency; gate behind a separate optional install.
- **Text or QR engraving overlay** (M) — Composite text/QR onto the heightmap as additional depth — names, dates, "Scan me" links.
- **Color-channel selector** (S) — Today we always grayscale. Optionally extract from R, G, B, or luminance — useful for stylized prints.

## Workflow

- **Batch folder conversion** (M) — Apply a single process to every image in a folder, write all STLs to an output folder. CLI-style + GUI dialog. Uses the existing `Process` JSON format, so presets just work.
- **Print-time / filament-weight estimate** (S) — From mesh volume × density and a printer-speed constant, show estimated grams + minutes. No slicer integration required for a rough number.
- **3MF and OBJ export** (S) — In addition to STL. 3MF carries metadata (color, units), OBJ is broadly accepted. `numpy-stl` doesn't write these; would need `trimesh` (already a test dep) or `lib3mf`.
- **Preset library** (S) — Built-in `processes/presets/` with portrait, landscape, ornament, and lamp configurations selectable from a dropdown. Users today have to load JSONs by hand.
- **mm / inch toggle** (S) — App-wide units switch in a Preferences dialog; the underlying model stays in mm.
- **Dark mode** (S) — Qt has built-in palettes; add a View-menu toggle.

## Robustness / DX

- **Async preview cancellation** (S) — Today rapid slider changes are debounced (Phase 3) but a long-running worker still completes before the next one starts. Cancellation token + early-exit checks would make heavy presets feel snappier.
- **CLI entry point** (S) — `python -m image_to_stl convert input.jpg --process default.json --out out.stl`. Pairs naturally with batch conversion.
- **Test fixtures for mode coverage** (S) — Standardized small images per PIL mode (L, RGB, RGBA, P, CMYK, LA) checked into `tests/fixtures/` to lock down mode handling across the pipeline.
