# TODO

## Next up

- [ ] **draw.io plugin, on hold.** Move dots, z-order and coloring into `plugin/` so the whole fix runs from a menu item on the open diagram. Blocked: draw.io Desktop v31.1.5 and later (installed: 31.5.3) removed custom plugins (jgraph/drawio-desktop `92d25a17`, 2026-07-27). Remaining routes: a userscript that injects the plugin into app.diagrams.net, a self-hosted draw.io with `ALLOW_CUSTOM_PLUGINS` and the plugin served from the same domain, or pinning Desktop at v31.0.2, which would miss the September 2026 security fixes.

## Later

- [ ] Send Cloverhound a feature request. They own the emitter, and dots at generation time is the only fix that needs no post-processing at all.
- [ ] Add the Cloverhound version to the `upstream/` filename, and record which version the current `library/` file was built from.
- [ ] Decide whether entry-point activities should also lose their `points=[[0,...]]` left connection point. Right now Start Flow and the eleven event triggers show no header dot but still accept an inbound edge on the header, so geometry and behavior disagree.
- [ ] Consider a folder watcher so a fresh export gets processed without a manual run. Lower priority once the plugin exists.
- [ ] Write the `doc/` page covering how to load the library and what the dots mean, for anyone else on the team who picks up these diagrams.

## Open questions

- Does the transformed library survive a draw.io scratchpad round trip, meaning drag a shape out, edit it, save it back to a custom library?
- What happens to dots on a Menu shape after adding several options and letting the stack layout re-run? Duplicating a row should carry the style, and the style is where the dot lives now, so this should hold. Worth confirming once.

- Keep the header (input) dot? Flow Designer keeps its input ports at `visibility: hidden`, connected or not, so it draws no input dot at rest (sampled 2026-10-02 on BasicQueueFlow). Ours always shows one.
- Flow Designer draws a 12px dot with a 2px ring, and a pale 20px halo when connected (`#dbf0ff` blue, `#ffe8ea` error). Ours is 8px with a 1pt ring and no halo. Match the size, or leave it?

## Done

- [x] Connected output dots fill solid (red for `Error` and `Undefined Errors`), unconnected stay hollow, and re-runs repaint after rewiring.
- [x] Edges leaving a port row take the dot's color at 2pt.
- [x] Output written with LF on Windows so it diffs cleanly against `samples/`.
- [x] Palette sampled from Flow Designer computed styles: dot `#0353a8`, line `#1170cf`, error dot and line `#ab0a15`. Unconnected dots ring in the same blue or red, header dots included. Sample and library regenerated.
- [x] Re-runs restyle existing header dots, so palette changes reach files processed earlier.

- [x] Hollow dot on every output handle, painted by the row itself rather than a child cell.
- [x] Hollow dot on the left of each activity header, skipping flow entry points.
- [x] Edges sent behind vertices so lines route under the activity boxes and under the dots.
- [x] Idempotent script that also strips the child-cell dots left by the first version.
- [x] Repo, README and the current library and sample pair.
