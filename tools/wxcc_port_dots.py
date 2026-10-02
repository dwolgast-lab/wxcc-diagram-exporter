#!/usr/bin/env python3
"""
wxcc_port_dots.py - connection dots and edge z-order for Cloverhound WxCC
draw.io exports.

Works on a draw.io shape library (<mxlibrary>) or a diagram (<mxfile>).

Three changes per file:

1. Output ports.  Each port row (points=[[1,0.5]]) switches from the "text"
   shape to the "label" shape and paints a small circle as part of itself,
   using an inline SVG data URI.  No extra cell is involved, so the row keeps
   its own hover, selection and drag behaviour and the connection arrow still
   appears when you hover it.

2. Input ports.  Each activity that accepts an incoming connection gets one
   child ellipse centred on the left edge of its header.  Dragging that dot
   moves the whole activity, which is what dragging a header does anyway.
   Entry points (Start Flow, the eleven event triggers) get nothing.

3. Z-order.  Every edge moves ahead of every vertex inside <root>, so lines
   paint behind the activity boxes and behind the dots.

4. Color.  A port row with an edge leaving it gets a solid dot, red when the
   row is an error handle, and that edge takes the same color at 2pt.  Ports
   with nothing attached keep the hollow dot.  Libraries have no edges, so
   every library dot stays hollow.

Usage:
    python3 wxcc_port_dots.py FILE [FILE ...]     -> writes FILE-dots.xml
    python3 wxcc_port_dots.py FILE --in-place     -> overwrites, keeps .bak
    python3 wxcc_port_dots.py FILE --size 10 --stroke "#0b6bcb"
    python3 wxcc_port_dots.py FILE --dot-align inside
    python3 wxcc_port_dots.py FILE --keep-z-order

Re-running is safe.  Rows already carrying wxccDot=1 only have their dot
recolored, so a re-run after rewiring a diagram brings the colors up to date.
"""

import argparse
import base64
import html
import json
import re
import shutil
import sys
import urllib.parse
import zlib
from pathlib import Path

# ---------------------------------------------------------------- appearance

DOT_SIZE = 8
DOT_FILL = "#ffffff"
DOT_STROKE = "#0353a8"
DOT_STROKE_WIDTH = 1

# Sampled from Flow Designer computed styles (default Link color "Blue",
# Error path color "Red").  An unconnected handle is white with a ring in
# its color; a connected one fills solid and its edge takes the matching
# color.  The blue dot is darker than the blue link; the reds are one red.
CONNECTED_COLOR = "#0353a8"
CONNECTED_EDGE_COLOR = "#1170cf"
ERROR_COLOR = "#ab0a15"
EDGE_WIDTH = 2

# Port rows whose label marks them as an error handle.
ERROR_LABELS = {"error", "undefined errors"}

# Header dot, still a child cell.  movable=0 keeps it out of the stackLayout
# that arranges Details and Connections; part=1 sends clicks to the activity.
CHILD_DOT_STYLE = (
    "ellipse;html=1;fillColor={fill};strokeColor={stroke};strokeWidth={sw};"
    "movable=0;resizable=0;rotatable=0;deletable=0;editable=0;connectable=0;part=1;"
)

DOT_ID_SUFFIX = "-dot"
DOT_MARKER = "wxccDot=1"

# Flow entry points take no incoming connection, so they get no header dot.
# Cloverhound gives Start Flow one fill and the eleven event triggers another.
NO_INPUT_FILLS = {"#f0fdf4", "#f0fefb"}

# ---------------------------------------------------------------- xml helpers

CHUNK_RE = re.compile(r"<mxCell\b(?:[^>]*?/>|.*?</mxCell>)", re.S)
ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def attrs_of(chunk):
    head = chunk[: chunk.index(">") + 1]
    return dict(ATTR_RE.findall(head))


def is_output_port(style):
    return "points=[[1,0.5]]" in style.replace(" ", "")


def is_activity_container(style):
    flat = style.replace(" ", "")
    return (
        flat.startswith("swimlane;")
        and "startSize=56" in flat
        and "childLayout=stackLayout" in flat
        and "points=[[0," in flat
    )


def takes_input(style):
    m = re.search(r"fillColor=(#[0-9a-fA-F]{6})", style)
    return m is None or m.group(1).lower() not in NO_INPUT_FILLS


def start_size(style):
    m = re.search(r"startSize=(\d+)", style)
    return int(m.group(1)) if m else 56


def is_error_row(value):
    text = re.sub(r"<[^>]*>", "", html.unescape(value))
    return " ".join(text.split()).lower() in ERROR_LABELS


def set_style_key(style, key, value):
    pattern = rf"(?<![a-zA-Z]){key}=[^;]*"
    if re.search(pattern, style):
        return re.sub(pattern, f"{key}={value}", style, count=1)
    return style.rstrip(";") + f";{key}={value};"


# ------------------------------------------------------------ the port circle


def dot_data_uri(size, fill, stroke, sw):
    """Inline SVG circle, percent-encoded so the style string holds no ';'."""
    r = size / 2 - sw / 2
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {size:g} {size:g}'>"
        f"<circle cx='{size / 2:g}' cy='{size / 2:g}' r='{r:g}' "
        f"fill='{fill}' stroke='{stroke}' stroke-width='{sw:g}'/></svg>"
    )
    return "data:image/svg+xml," + urllib.parse.quote(svg, safe="")


def paint_dot_on_row(style, cfg, fill, stroke):
    """Turn a port row into a label shape carrying the circle at its right edge.

    mxLabel places a right-aligned image at  x + w - imageWidth - (spacing + 5),
    so the spacing value sets where the circle lands:

        align=edge    spacing = -size/2 - 5   circle straddles the border
        align=inside  spacing = -5            circle sits flush inside it

    mxText reads the same spacing value, so spacingLeft and spacingRight absorb
    it and the row text stays exactly where it was.

    A row that already carries the marker only gets its circle repainted.
    """
    uri = dot_data_uri(cfg.size, fill, stroke, cfg.stroke_width)
    if DOT_MARKER in style:
        new_style = re.sub(r"image=data:image/svg\+xml,[^;]*", f"image={uri}", style, count=1)
        return new_style, False

    size = cfg.size
    spacing = (-size / 2 - 5) if cfg.dot_align == "edge" else -5
    shift = -spacing

    if style.startswith("text;"):
        style = "label;" + style[len("text;"):]

    def bump(match):
        return f"{match.group(1)}={float(match.group(2)) + shift:g}"

    style = re.sub(r"(spacingLeft|spacingRight)=(-?[\d.]+)", bump, style)
    style = re.sub(r"(?<![a-zA-Z])spacing=-?[\d.]+;?", "", style)

    new_style = (
        style.rstrip(";")
        + f";image={uri};imageWidth={size:g};imageHeight={size:g};"
        f"imageAlign=right;imageVerticalAlign=middle;spacing={spacing:g};"
        f"{DOT_MARKER};"
    )
    return new_style, True


def replace_style(chunk, attrs, new_style):
    if "style" in attrs:
        return chunk.replace(f'style="{attrs["style"]}"', f'style="{new_style}"', 1)
    return chunk.replace("<mxCell ", f'<mxCell style="{new_style}" ', 1)


def make_child_dot(parent_id, x, y, size, style):
    return (
        f'<mxCell id="{parent_id}{DOT_ID_SUFFIX}" value="" style="{style}" '
        f'vertex="1" parent="{parent_id}">'
        f'<mxGeometry x="{x:g}" y="{y:g}" width="{size:g}" height="{size:g}" as="geometry" />'
        f"</mxCell>"
    )


# ------------------------------------------------------------- model rewrite


def transform_model(model_xml, cfg):
    """Returns (xml, port_dots, header_dots, edges_moved, edges_colored)."""
    start = model_xml.index("<root>") + len("<root>")
    end = model_xml.rindex("</root>")
    body = model_xml[start:end]

    chunks = CHUNK_RE.findall(body)
    existing = {attrs_of(c).get("id", "") for c in chunks}
    # Rows painted their own dot now, so any leftover child dot from an
    # earlier run of this script gets dropped.
    port_ids = {
        attrs_of(c).get("id", "")
        for c in chunks
        if is_output_port(attrs_of(c).get("style", ""))
    }
    child_style = CHILD_DOT_STYLE.format(
        fill=cfg.fill, stroke=cfg.stroke, sw=cfg.stroke_width
    )

    # A port is connected when an edge leaves it.  Edges can sit before or
    # after their source row, so colors are settled before the main pass.
    sources = {
        attrs_of(c).get("source")
        for c in chunks
        if attrs_of(c).get("edge") == "1"
    }
    port_color = {}
    for c in chunks:
        a = attrs_of(c)
        if a.get("id") in port_ids and a.get("id") in sources:
            error = is_error_row(a.get("value", ""))
            port_color[a["id"]] = ERROR_COLOR if error else CONNECTED_COLOR

    head, ordered, added = [], [], []
    ports = inputs = colored = 0

    for chunk in chunks:
        a = attrs_of(chunk)
        cid, cstyle = a.get("id", ""), a.get("style", "")

        if cid.endswith(DOT_ID_SUFFIX) and a.get("parent") in port_ids:
            continue

        # Header dot from an earlier run: restyle so palette changes reach it.
        if cid == a.get("parent", "") + DOT_ID_SUFFIX:
            chunk = replace_style(chunk, a, child_style)

        if cid in ("0", "1") and "style" not in a:
            head.append(chunk)
            continue

        if cfg.do_outputs and is_output_port(cstyle):
            color = port_color.get(cid)
            if color:
                fill, stroke = color, color
            else:
                error = is_error_row(a.get("value", ""))
                fill, stroke = cfg.fill, ERROR_COLOR if error else cfg.stroke
            new_style, added_dot = paint_dot_on_row(cstyle, cfg, fill, stroke)
            chunk = replace_style(chunk, a, new_style)
            ports += added_dot

        elif cfg.do_outputs and a.get("edge") == "1" and a.get("source") in port_color:
            color = port_color[a["source"]]
            if color == CONNECTED_COLOR:
                color = CONNECTED_EDGE_COLOR
            new_style = set_style_key(cstyle, "strokeColor", color)
            new_style = set_style_key(new_style, "strokeWidth", f"{EDGE_WIDTH:g}")
            chunk = replace_style(chunk, a, new_style)
            colored += 1

        elif (
            cfg.do_inputs
            and is_activity_container(cstyle)
            and takes_input(cstyle)
            and cid + DOT_ID_SUFFIX not in existing
        ):
            y = start_size(cstyle) / 2 - cfg.size / 2
            x = -cfg.size / 2 if cfg.dot_align == "edge" else 0
            added.append(make_child_dot(cid, x, y, cfg.size, child_style))
            inputs += 1

        ordered.append((chunk, a.get("edge") == "1"))

    if cfg.reorder:
        edges = [c for c, is_edge in ordered if is_edge]
        vertices = [c for c, is_edge in ordered if not is_edge]
        cells = head + edges + vertices + added
        moved = len(edges)
    else:
        cells = head + [c for c, _ in ordered] + added
        moved = 0

    xml = model_xml[:start] + "\n".join(cells) + model_xml[end:]
    return xml, ports, inputs, moved, colored


# ------------------------------------------------------- library (de)compress


def decompress(data):
    return urllib.parse.unquote(
        zlib.decompress(base64.b64decode(data), -15).decode("utf-8")
    )


def compress(text):
    quoted = urllib.parse.quote(text, safe="!~*'()")
    deflator = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(
        deflator.compress(quoted.encode("utf-8")) + deflator.flush()
    ).decode("ascii")


# ------------------------------------------------------------- file handlers


def process_library(text, cfg):
    entries = json.loads(re.search(r"<mxlibrary>(.*)</mxlibrary>", text, re.S).group(1))
    totals = [0, 0, 0, 0]

    for entry in entries:
        raw = entry.get("xml")
        if not raw:
            continue
        packed = not raw.lstrip().startswith("<")
        model = decompress(raw) if packed else raw
        model, *counts = transform_model(model, cfg)
        entry["xml"] = compress(model) if packed else model
        totals = [t + c for t, c in zip(totals, counts)]

    xml = "<mxlibrary>" + json.dumps(entries, separators=(",", ":")) + "</mxlibrary>"
    return xml, *totals


def process_diagram(text, cfg):
    totals = [0, 0, 0, 0]
    out, last = [], 0

    for m in re.finditer(r"(<diagram\b[^>]*>)(.*?)(</diagram>)", text, re.S):
        body = m.group(2)
        stripped = body.strip()
        packed = bool(stripped) and not stripped.startswith("<")
        model = decompress(stripped) if packed else body
        model, *counts = transform_model(model, cfg)
        totals = [t + c for t, c in zip(totals, counts)]
        out.append(text[last : m.start(2)])
        out.append(compress(model) if packed else model)
        last = m.end(2)

    out.append(text[last:])
    return "".join(out), *totals


def process_file(path, cfg):
    src = Path(path)
    text = src.read_text(encoding="utf-8")
    handler = process_library if "<mxlibrary>" in text[:200] else process_diagram
    result, ports, inputs, moved, colored = handler(text, cfg)

    if cfg.in_place:
        shutil.copy2(src, src.with_suffix(src.suffix + ".bak"))
        dest = src
    else:
        dest = src.with_name(src.stem + "-dots" + src.suffix)
    # newline="" keeps LF on Windows, so output diffs cleanly against samples/.
    dest.write_text(result, encoding="utf-8", newline="")

    kind = "library" if handler is process_library else "diagram"
    print(
        f"{src.name}: {kind}, {ports} port dots, {inputs} header dots, "
        f"{moved} edges sent back, {colored} edges colored -> {dest.name}"
    )


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("files", nargs="+")
    p.add_argument("--size", type=float, default=DOT_SIZE)
    p.add_argument("--fill", default=DOT_FILL)
    p.add_argument("--stroke", default=DOT_STROKE)
    p.add_argument("--stroke-width", type=float, default=DOT_STROKE_WIDTH)
    p.add_argument("--in-place", action="store_true")
    p.add_argument(
        "--dot-align",
        choices=["edge", "inside"],
        default="edge",
        help="edge: dot straddles the border, matching Flow Designer. "
        "inside: dot sits flush within the row. Neither setting changes the "
        "fact that the cursor has to enter the row before draw.io offers a "
        "connection point.",
    )
    p.add_argument("--keep-z-order", action="store_true", help="leave edge order alone")
    p.add_argument("--inputs-only", action="store_true", help="only header dots")
    p.add_argument("--outputs-only", action="store_true", help="only port dots")
    cfg = p.parse_args()

    cfg.do_inputs = not cfg.outputs_only
    cfg.do_outputs = not cfg.inputs_only
    cfg.reorder = not cfg.keep_z_order

    for f in cfg.files:
        if not Path(f).exists():
            print(f"missing: {f}", file=sys.stderr)
            continue
        process_file(f, cfg)


if __name__ == "__main__":
    main()
