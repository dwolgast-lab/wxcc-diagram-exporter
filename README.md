# WxCC Diagram Exporter

Post-processing for Webex Contact Center flow diagrams exported to draw.io by the
Cloverhound browser extension, plus a patched copy of the Cloverhound shape library.

Flow Designer draws a dot at every connection handle on an activity. The exported
diagrams have the connection points but no dots, so a line arrives at a box edge with
nothing marking which output it left from. This repo adds those dots and fixes edge
z-order, and it does it in a way that survives a Cloverhound library update.

## Layout

- `upstream/` — untouched Cloverhound exports. Never edit these. Currently `WxCC-FlowBuilder-Activities.xml`.
- `library/` — the transformed shape library loaded into draw.io. Currently `WxCC-FlowBuilder-Activities-dots.xml`.
- `tools/` — `wxcc_port_dots.py`, the transformer.
- `samples/` — `Customer_Service_Queue.xml` is a raw extension export, `Customer_Service_Queue-dots.xml` is the same file after processing. Regression check.
- `plugin/` — draw.io plugin (on hold, see Planned).
- `doc/` — user- and admin-facing documentation.

## Requirements

Python 3.8 or newer. The script imports only the standard library.

## Usage

```
python tools\wxcc_port_dots.py <file.xml>                    writes <file>-dots.xml
python tools\wxcc_port_dots.py <file.xml> --in-place         overwrites, keeps a .bak
python tools\wxcc_port_dots.py <file.xml> --dot-align inside
python tools\wxcc_port_dots.py <file.xml> --size 10 --stroke "#0b6bcb"
python tools\wxcc_port_dots.py <file.xml> --keep-z-order
```

The script auto-detects whether it was handed a shape library or a diagram, and it
accepts several files in one call. Running it twice on the same file changes nothing,
because rows already carrying the `wxccDot=1` marker only get their dot recolored.

Useful flags:

- `--dot-align edge` puts the dot astride the border, matching Flow Designer. This is the default and the setting we shipped.
- `--dot-align inside` pulls the dot fully within the row. Tested, and it does not change when draw.io offers a connection point, so there is no reason to use it beyond taste.
- `--size`, `--fill`, `--stroke`, `--stroke-width` control the dot itself.
- `--keep-z-order` leaves edge ordering alone.
- `--inputs-only`, `--outputs-only` limit which dots get added.

## What the transform does

Output ports change shape. Each port row switches from `text` to `label` and paints its
own circle through an inline SVG data URI. No extra cell is involved, so the row keeps
its own hover, selection and drag behavior, and the connection arrow still appears.
mxLabel places a right-aligned image at `x + w - imageWidth - (spacing + 5)`, so
`spacing` positions the circle: `-size/2 - 5` straddles the border and `-5` sits flush
inside it. That same value feeds the text renderer, so `spacingLeft` and `spacingRight`
absorb it and the label text does not move.

An earlier version made the dot a separate child cell. That version is the reason the
script strips leftovers. A separate cell always wins the mouse in mxGraph, the
`pointerEvents` style key never reaches shape hit-testing, and `part=1` handed the drag
to the row underneath, so the row popped out of the section stack on any click.

Input ports get one child ellipse centered on the left edge of the activity header. The
style carries `movable=0`, which removes the cell from `getLayoutCells` in mxStackLayout
and keeps the section stack from treating the dot as another row. `part=1` sends clicks
to the activity, so dragging the dot moves the whole box. Entry-point activities get no
header dot at all.

Edges move ahead of vertices inside each `<root>`, the same result as Edit then Send to
Back. Lines paint behind the activity boxes and behind the dots, so a connection
disappears under its circle instead of crossing over it.

Dots follow Flow Designer. An unconnected handle is white with a ring in its color: blue,
or red for a row labelled `Error` or `Undefined Errors`. In a diagram, a port row with an
edge leaving it fills solid in that color, and the edge goes to 2pt in the matching line
color. Every dot in the library is unconnected, since a library has no edges. Re-running
repaints every dot, header dots included, so a row whose edge was deleted goes back to
a ring and a palette change reaches files processed earlier. Any custom color on an
edge leaving a port row is overwritten on each run.

The colors were sampled from Flow Designer's computed styles with its default Link color
(Blue) and Error path color (Red). Flow Designer draws the dot darker than its line:

| | Dot (ring or fill) | Line |
| --- | --- | --- |
| Normal | `#0353a8` | `#1170cf` |
| Error | `#ab0a15` | `#ab0a15` |

They live in `DOT_STROKE`, `CONNECTED_COLOR`, `CONNECTED_EDGE_COLOR` and `ERROR_COLOR` at
the top of the script. Flow Designer's dot is 12px with a 2px ring on a pale 20px halo
when connected; ours stays 8px with a 1pt ring and no halo.

## The style contract

The script recognizes Cloverhound output by four markers. Any of them changing upstream
will make dots land in the wrong place or stop appearing.

- `points=[[1,0.5]]` on a 230 by 30 cell identifies an output port row.
- `swimlane` plus `startSize=56` plus `childLayout=stackLayout` identifies an activity container.
- Fill `#f0fdf4` is Start Flow. Fill `#f0fefb` is the eleven event triggers. Both are entry points and take no incoming connection, so both are listed in `NO_INPUT_FILLS` and get no header dot.
- Header connection points sit at `startSize / 2`, which is y=28 on every shape in the set.

Current counts, useful as a sanity check after an upstream change: the library yields
100 port dots and 41 header dots across 53 shapes. The sample diagram yields 30 port
dots, 8 header dots, 13 edges sent back and 13 edges colored, one of them red.

## Updating after a Cloverhound release

1. Save the new library export into `upstream/` with its version in the filename.
2. Run the script against it, writing the result into `library/`.
3. Open the result in draw.io, drag out Menu and Business Hours, and confirm the dots line up.
4. Re-run the script against `samples/Customer_Service_Queue.xml` and diff against the stored output. Compare the library by decompressed cells rather than bytes, because a different zlib build can produce different compressed bytes for the same content.
5. Commit both the upstream file and the generated one.

Keeping the upstream copy is the whole point. Regenerating takes one command, so a
Cloverhound update costs a few minutes rather than a rebuild.

## Known behavior

Connection points appear only after the cursor enters the row from inside the activity
box. Approaching a dot from the canvas side does not raise the green marker, and a click
there grabs the row instead. Dot alignment does not affect this, so it is draw.io hover
handling rather than dot geometry. Work around it by approaching from inside.

Dragging a port row pulls it out of the section stack. The rows are movable cells in the
original Cloverhound library and always have been. Setting `movable=0` would stop it and
would also remove the rows from the stack layout, which breaks adding Menu options, so
Ctrl+Z remains the fix.

## Planned

A draw.io plugin, so the fix runs from a menu item on the open diagram instead of a
shell command. This is on hold. draw.io Desktop removed custom plugin support in
v31.1.5 (jgraph/drawio-desktop commit `92d25a17`, 2026-07-27), and the web app loads a
custom plugin only from its own domain with `ALLOW_CUSTOM_PLUGINS` set, which means
self-hosting.
