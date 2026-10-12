#!/usr/bin/env python3
"""Render an AWS architecture diagram (standard white AWS style) from a YAML spec.

    python tools/diagram/render.py render <spec.yml> [--out file.svg]
    python tools/diagram/render.py icons <query> [<query> ...]
    python tools/diagram/render.py selftest

Positions come from the spec (grid), never from auto-layout. Every text, icon,
arrow and border is recorded with a bounding box and the render fails on any
overlap. Spec format and rules: tools/diagram/README.md (agents: read that, not this file).
"""
import argparse
import base64
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

HERE = Path(__file__).resolve().parent
INDEX_FILE = HERE / ".icon-index.json"

INK, SUB, LINE = "#16191F", "#5F6B7A", "#232F3E"
HEAD = (f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
        f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker></defs>'
        f'<style>.lbl{{font-size:15px;fill:{INK};font-weight:600}}.sub{{font-size:13px;fill:{SUB}}}'
        f'.ttl{{font-size:17px;fill:{INK};font-weight:600}}.arr{{fill:none;stroke:{LINE};stroke-width:2}}'
        f'.h1{{font-size:26px;font-weight:700;fill:{INK}}}.h2{{font-size:14px;fill:{SUB}}}'
        f'.cap{{font-size:13px;fill:{SUB};font-style:italic}}</style>')

# class -> (font size, average glyph width as a fraction of the size)
TEXT_METRICS = {"lbl": (15, 0.60), "sub": (13, 0.55), "ttl": (17, 0.60), "cap": (13, 0.55)}
# Minimum clear space in px per pair of kinds. Pairs not listed are not checked
# (an arrow may cross a border, two arrows may share an elbow).
CLEARANCE = {
    ("text", "text"): 0, ("icon", "text"): 4, ("arrow", "text"): 6, ("border", "text"): 6,
    ("icon", "icon"): 6, ("arrow", "icon"): 6, ("border", "icon"): 6,
}
ARROW_END_TRIM = 14   # an arrow may touch the icon it leaves from or points at
GAP_START, GAP_END = 6, 10

# style -> (stroke, fill, group icon file stem, dashed)
STYLES = {
    "cloud": (LINE, "#fff", "AWS-Cloud", False),
    "region": ("#00A4A6", "#fff", "Region", True),
    "vpc": ("#8C4FFF", "#fff", "Virtual-private-cloud-VPC", False),
    "public": ("#7AA116", "#F6FAEC", "Public-subnet", False),
    "private": ("#00A4A6", "#F0FAFA", "Private-subnet", False),
    "dashed": ("#8A97A8", "#F7F8FA", None, True),
}

# short name -> query. A "res:" prefix selects the resource icon set.
ALIASES = {
    "s3": "simple-storage-service", "sqs": "simple-queue-service", "sns": "simple-notification-service",
    "apigw": "api-gateway", "kms": "key-management-service", "secrets": "secrets-manager",
    "acm": "certificate-manager", "route53": "route-53", "ecr": "elastic-container-registry",
    "iam": "identity-and-access-management", "alb": "res:application-load-balancer",
    "igw": "res:internet-gateway", "vpce": "res:vpc-endpoints", "bucket": "res:s3-bucket",
    "queue": "res:simple-queue-service-queue", "function": "res:lambda-function",
}


class DiagramError(Exception):
    pass


# --- icon pack ----------------------------------------------------------------


def find_pack():
    cands = []
    if os.environ.get("AWS_ICON_PACK"):
        cands.append(Path(os.environ["AWS_ICON_PACK"]))
    cfg = HERE / "config.toml"
    if cfg.exists():
        p = tomllib.loads(cfg.read_text("utf-8")).get("pack")
        if p:
            cands.append(Path(os.path.expandvars(os.path.expanduser(p))))
    for base in (Path.home() / "Downloads", Path.home() / "Downloads" / "Compressed"):
        if base.is_dir():
            cands += sorted(base.glob("Icon-package_*"), reverse=True)
    for c in cands:
        if c.is_dir() and any(c.glob("Architecture-Service-Icons_*")):
            return c
    return None


def build_index(pack):
    if INDEX_FILE.exists():
        data = json.loads(INDEX_FILE.read_text("utf-8"))
        if data.get("pack") == str(pack):
            return data["icons"]
    idx = {"service": {}, "resource": {}, "group": {}}
    for f in pack.glob("Architecture-Service-Icons_*/Arch_*/64/Arch_*_64.svg"):
        idx["service"][f.stem[len("Arch_"):-len("_64")]] = str(f)
    for f in pack.glob("Resource-Icons_*/Res_*/Res_*_48.svg"):
        idx["resource"][f.stem[len("Res_"):-len("_48")]] = str(f)
    for f in pack.glob("Architecture-Group-Icons_*/*_32.svg"):
        idx["group"][f.stem[:-len("_32")]] = str(f)
    try:
        INDEX_FILE.write_text(json.dumps({"pack": str(pack), "icons": idx}), "utf-8")
    except OSError:
        pass
    return idx


def short(name):
    n = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    for p in ("amazon-", "aws-"):
        if n.startswith(p):
            n = n[len(p):]
    return n


def resolve(idx, query):
    kind, q = "service", query
    q = ALIASES.get(short(q), q)
    if q.startswith("res:"):
        kind, q = "resource", q[4:]
    nq = short(q)
    pool = {short(k): v for k, v in idx[kind].items()}
    if nq in pool:
        return pool[nq]
    hits = sorted(k for k in pool if nq in k)
    if len(hits) == 1:
        return pool[hits[0]]
    shown = ", ".join(hits[:8]) or "no match"
    raise DiagramError(f'icon "{query}": {"ambiguous" if hits else "not found"} ({shown}). '
                       f'Use `render.py icons {query}` or a "res:" prefix for resource icons')


# --- canvas, overlap check ----------------------------------------------------


class Canvas:
    def __init__(self, idx):
        self.items, self.idx, self._uri = [], idx, {}

    def record(self, kind, x0, y0, x1, y1, name, **flags):
        self.items.append(dict(kind=kind, box=(x0, y0, x1, y1), name=name, **flags))

    def uri(self, path):
        if path not in self._uri:
            self._uri[path] = "data:image/svg+xml;base64," + base64.b64encode(Path(path).read_bytes()).decode()
        return self._uri[path]


def find_overlaps(items):
    problems = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            key = tuple(sorted((a["kind"], b["kind"])))
            if key not in CLEARANCE:
                continue
            if "border" in key and (a.get("on_border") or b.get("on_border")):
                continue
            c = CLEARANCE[key]
            ax0, ay0, ax1, ay1 = a["box"]
            bx0, by0, bx1, by1 = b["box"]
            if ax0 - c < bx1 and bx0 - c < ax1 and ay0 - c < by1 and by0 - c < ay1:
                problems.append(f'{a["kind"]} "{a["name"]}" vs {b["kind"]} "{b["name"]}" closer than {c}px '
                                f'(boxes {tuple(round(v) for v in a["box"])} / {tuple(round(v) for v in b["box"])})')
    return problems


# --- drawing ------------------------------------------------------------------


def text(cv, x, y, content, cls="lbl", anchor="middle", on_border=False):
    size, f = TEXT_METRICS[cls]
    w = len(content) * size * f
    x0 = {"middle": x - w / 2, "start": x, "end": x - w}[anchor]
    box = (x0, y - size * 0.8, x0 + w, y + size * 0.25)
    cv.record("text", *box, content, on_border=on_border)
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{escape(content)}</text>', box


def icon(cv, path, cx, cy, size, name, on_border=False):
    box = (cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2)
    cv.record("icon", *box, name, on_border=on_border)
    return (f'<image href="{cv.uri(path)}" x="{box[0]}" y="{box[1]}" width="{size}" height="{size}"/>', box)


def user_glyph(cv, cx, cy):
    box = (cx - 26, cy - 27, cx + 26, cy + 28)
    cv.record("icon", *box, "user")
    svg = (f'<circle cx="{cx}" cy="{cy - 14}" r="13" fill="none" stroke="{LINE}" stroke-width="3"/>'
           f'<path d="M{cx - 26},{cy + 28} Q{cx - 26},{cy + 4} {cx},{cy + 4} Q{cx + 26},{cy + 4} {cx + 26},{cy + 28} Z" '
           f'fill="none" stroke="{LINE}" stroke-width="3" stroke-linejoin="round"/>')
    return svg, box


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def label_lines(label):
    return [label] if isinstance(label, str) else [str(x) for x in label]


def draw_node(cv, nid, n, cx, cy):
    size = n.get("size", 56)
    on_border = bool(n.get("border"))
    parts, boxes = [], []
    if n["icon"] == "user":
        svg, box = user_glyph(cv, cx, cy)
    else:
        svg, box = icon(cv, resolve(cv.idx, n["icon"]), cx, cy, size, nid, on_border)
    parts.append(svg)
    boxes.append(box)
    lines, pos = label_lines(n.get("label", nid)), n.get("label_pos", "below")
    half = size / 2
    if pos == "below":
        x, y0, anchor, step = cx, cy + half + 22, "middle", 17
    elif pos == "above":
        x, y0, anchor, step = cx, cy - half - 12 - 17 * (len(lines) - 1), "middle", 17
    elif pos == "right":
        x, y0, anchor, step = cx + half + 12, cy + 5 - 8.5 * (len(lines) - 1), "start", 17
    elif pos == "left":
        x, y0, anchor, step = cx - half - 12, cy + 5 - 8.5 * (len(lines) - 1), "end", 17
    else:
        raise DiagramError(f'node "{nid}": label_pos must be below, above, right or left')
    for i, line in enumerate(lines):
        svg, box = text(cv, x, y0 + step * i, line, "lbl" if i == 0 else "sub", anchor, on_border)
        parts.append(svg)
        boxes.append(box)
    bbox = union(boxes)
    if on_border:
        px0, py0, px1, py1 = bbox[0] - 8, bbox[1] - 8, bbox[2] + 8, bbox[3] + 8
        parts.insert(0, f'<rect x="{px0}" y="{py0}" width="{px1 - px0}" height="{py1 - py0}" rx="6" fill="#fff"/>')
    return "".join(parts), bbox, size


def draw_group(cv, gid, g, box):
    stroke, fill, icon_stem, dashed = STYLES[g.get("style", "dashed")]
    x0, y0, x1, y1 = box
    title = g.get("title", gid)
    for side in ((x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1)):
        cv.record("border", side[0] - 1, side[1] - 1, side[2] + 1, side[3] + 1, title)
    out = (f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="6" fill="{fill}" '
           f'stroke="{stroke}" stroke-width="2"' + (' stroke-dasharray="6 5"/>' if dashed else "/>"))
    tx = x0 + 24
    if icon_stem:
        path = cv.idx["group"].get(icon_stem)
        if path:
            out += f'<image href="{cv.uri(path)}" x="{x0}" y="{y0}" width="40" height="40"/>'
            tx = x0 + 52
    svg, _ = text(cv, tx, y0 + 26, title, "ttl", "start")
    return out + svg


def route(pts):
    """Drop repeated points, require axis-aligned segments."""
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    for p, q in zip(pts, pts[1:]):
        if p[0] != q[0] and p[1] != q[1]:
            raise DiagramError(f"segment {p}->{q} is not horizontal or vertical; add a via point")
    return pts


def shift(p, toward, d):
    if p[0] == toward[0]:
        step = d if toward[1] > p[1] else -d
        if abs(toward[1] - p[1]) <= d:
            raise DiagramError("arrow too short for the icon gap; move the nodes apart")
        return (p[0], p[1] + step)
    step = d if toward[0] > p[0] else -d
    if abs(toward[0] - p[0]) <= d:
        raise DiagramError("arrow too short for the icon gap; move the nodes apart")
    return (p[0] + step, p[1])


def draw_arrow(cv, pts, name):
    segs = list(zip(pts, pts[1:]))
    for i, ((x0, y0), (x1, y1)) in enumerate(segs):
        ts = ARROW_END_TRIM if i == 0 else 0
        te = ARROW_END_TRIM if i == len(segs) - 1 else 0
        if y0 == y1:
            a, b = (x0 + ts, x1 - te) if x1 >= x0 else (x1 + te, x0 - ts)
            lo, hi = min(a, b), max(a, b)
            if lo <= hi:
                cv.record("arrow", lo, y0 - 1, hi, y0 + 1, name)
        else:
            a, b = (y0 + ts, y1 - te) if y1 >= y0 else (y1 + te, y0 - ts)
            lo, hi = min(a, b), max(a, b)
            if lo <= hi:
                cv.record("arrow", x0 - 1, lo, x0 + 1, hi, name)
    return '<path d="M' + " L".join(f"{x},{y}" for x, y in pts) + '" class="arr" marker-end="url(#ah)"/>'


# --- spec -> svg --------------------------------------------------------------


def render(spec, idx):
    cv = Canvas(idx)
    cw, ch = spec.get("cell", [200, 150])
    ox, oy = spec.get("origin", [100, 150])
    width, height = spec.get("canvas", [1600, 1000])
    nodes, groups = spec.get("nodes") or {}, spec.get("groups") or {}

    def px(pt):
        return (ox + pt[0] * cw, oy + pt[1] * ch)

    geo, node_svg = {}, []
    for nid, n in nodes.items():
        if "at" not in n or "icon" not in n:
            raise DiagramError(f'node "{nid}" needs "icon" and "at"')
        cx, cy = px(n["at"])
        svg, bbox, size = draw_node(cv, nid, n, cx, cy)
        geo[nid] = dict(cx=cx, cy=cy, size=size, bbox=bbox)
        node_svg.append(svg)

    gbox = {}

    def group_box(gid, stack=()):
        if gid in gbox:
            return gbox[gid]
        if gid in stack:
            raise DiagramError(f'group "{gid}" contains itself')
        g = groups[gid]
        boxes = []
        for m in g.get("members", []):
            if m in groups:
                boxes.append(group_box(m, stack + (gid,)))
            elif m in geo:
                boxes.append(geo[m]["bbox"])
            else:
                raise DiagramError(f'group "{gid}": unknown member "{m}"')
        if not boxes:
            raise DiagramError(f'group "{gid}" has no members')
        pad = g.get("pad", 28)
        x0, y0, x1, y1 = union(boxes)
        gl, gt, gr, gb = g.get("grow", [0, 0, 0, 0])
        box = [x0 - pad - gl, y0 - pad - 44 - gt, x1 + pad + gr, y1 + pad + gb]
        need = 52 + len(g.get("title", gid)) * TEXT_METRICS["ttl"][0] * TEXT_METRICS["ttl"][1] + 24
        if box[2] - box[0] < need:
            box[2] = box[0] + need
        gbox[gid] = tuple(box)
        return gbox[gid]

    for gid in groups:
        group_box(gid)
    group_svg = []
    for gid in sorted(groups, key=lambda k: -(gbox[k][2] - gbox[k][0]) * (gbox[k][3] - gbox[k][1])):
        group_svg.append(draw_group(cv, gid, groups[gid], gbox[gid]))

    arrow_svg = []
    for e in spec.get("edges") or []:
        if isinstance(e, list):
            e = dict(zip(("from", "to", "route"), e))
        a, b = e.get("from"), e.get("to")
        if a not in geo or b not in geo:
            raise DiagramError(f"edge {a}->{b}: unknown node")
        for end in (a, b):
            if nodes[end].get("support"):
                raise DiagramError(f'edge {a}->{b}: "{end}" is a supporting service (support: true); '
                                   f"house style rule 4 allows no arrows to it")
        ga, gb = geo[a], geo[b]
        via = [px(p) for p in e.get("via", [])]
        if not via and ga["cx"] != gb["cx"] and ga["cy"] != gb["cy"]:
            via = [(gb["cx"], ga["cy"])] if e.get("route", "hv") == "hv" else [(ga["cx"], gb["cy"])]
        try:
            pts = route([(ga["cx"], ga["cy"])] + via + [(gb["cx"], gb["cy"])])
            pts[0] = shift(pts[0], pts[1], ga["size"] / 2 + GAP_START)
            pts[-1] = shift(pts[-1], pts[-2], gb["size"] / 2 + GAP_END)
        except DiagramError as err:
            raise DiagramError(f"edge {a}->{b}: {err}") from None
        arrow_svg.append(draw_arrow(cv, pts, f"{a}->{b}"))

    problems = find_overlaps(cv.items)
    if problems:
        raise DiagramError("overlap check failed (hint: label_pos, via, or move nodes):\n  " + "\n  ".join(problems))

    sub = "Prototype design. Not deployed."
    if spec.get("source"):
        sub += f' Source of truth: {spec["source"]}'
    head = (f'<text x="48" y="58" class="h1">{escape(spec.get("title", "Architecture"))}</text>'
            f'<text x="48" y="84" class="h2">{escape(spec.get("subtitle", sub))}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
           f'height="{height}" font-family="Helvetica, Arial, sans-serif">{HEAD}'
           f'<rect width="{width}" height="{height}" fill="#fff"/>{head}'
           + "".join(group_svg) + "".join(node_svg) + "".join(arrow_svg) + "</svg>")
    extent = union([i["box"] for i in cv.items]) if cv.items else (0, 0, 0, 0)
    if extent[2] > width or extent[3] > height or extent[0] < 0 or extent[1] < 0:
        raise DiagramError(f"content spills outside the {width}x{height} canvas {tuple(round(v) for v in extent)}; "
                           f"change origin/cell/canvas")
    return svg, dict(nodes=len(nodes), edges=len(spec.get("edges") or []), groups=len(groups))


def load_index():
    pack = find_pack()
    if not pack:
        raise DiagramError("AWS icon pack not found. Set AWS_ICON_PACK or tools/diagram/config.toml (see README)")
    return build_index(pack)


def default_out(spec_path):
    if spec_path.parent.name == "diagrams":
        return spec_path.parent.parent / "docs" / "img" / (spec_path.stem + ".svg")
    return spec_path.with_suffix(".svg")


def cmd_render(args):
    spec_path = Path(args.spec)
    spec = yaml.safe_load(spec_path.read_text("utf-8")) or {}
    svg, stats = render(spec, load_index())
    out = Path(args.out) if args.out else default_out(spec_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"OK {out} ({stats['nodes']} nodes, {stats['edges']} edges, {stats['groups']} groups)")


def cmd_icons(args):
    idx = load_index()
    for q in args.query:
        target = ALIASES.get(short(q), q)
        nq = short(target[4:] if target.startswith("res:") else target)
        found = [(kind, name) for kind, pool in idx.items() for name in sorted(pool) if nq in short(name)]
        found.sort(key=lambda kn: (short(kn[1]) != nq, kn[0] != ("resource" if target.startswith("res:") else "service")))
        try:
            print(f"{q}: use `icon: {q}`" if resolve(idx, q) else "")
        except DiagramError:
            print(f"{q}: no single match, {len(found)} candidate(s)")
        for kind, name in found[:10]:
            prefix = {"service": "", "resource": "res:", "group": "group:"}[kind]
            print(f"  {prefix}{short(name)}")


def selftest():
    def case(*items):
        return find_overlaps([dict(kind=k, box=b, name=n) for k, b, n in items])

    border = ("border", (219, 110, 221, 810), "AWS Cloud")
    assert case(border, ("text", (110, 528, 230, 543), "Route 53 + ACM")), "label over a border not caught"
    assert case(("arrow", (569, 469, 571, 561), "a"), ("text", (395, 504, 575, 519), "label")), "arrow through label"
    assert case(("text", (0, 0, 100, 16), "a"), ("text", (50, 8, 150, 24), "b")), "text over text not caught"
    assert not case(border, ("text", (134, 528, 206, 543), "Route 53")), "false positive on a clean label"
    assert short("Amazon-Simple-Queue-Service") == "simple-queue-service"
    assert route([(0, 0), (0, 0), (5, 0)]) == [(0, 0), (5, 0)]
    try:
        route([(0, 0), (3, 4)])
        raise SystemExit("selftest failed: diagonal segment accepted")
    except DiagramError:
        pass
    # layout without any icon file: user glyph + groups only
    spec = dict(nodes={"u": dict(icon="user", at=[0, 0]), "v": dict(icon="user", at=[2, 0])},
                edges=[["u", "v"]], groups={"g": dict(style="dashed", members=["u", "v"])})
    svg, stats = render(spec, {"service": {}, "resource": {}, "group": {}})
    assert stats == dict(nodes=2, edges=1, groups=1) and svg.startswith("<svg")
    # a label under a node that an arrow leaves downward must be reported
    bad = dict(nodes={"u": dict(icon="user", at=[0, 0]), "v": dict(icon="user", at=[0, 2])}, edges=[["u", "v"]])
    try:
        render(bad, {"service": {}, "resource": {}, "group": {}})
        raise SystemExit("selftest failed: arrow through a label not reported")
    except DiagramError:
        pass
    example = HERE / "examples" / "mini.yml"
    if find_pack():
        render(yaml.safe_load(example.read_text("utf-8")), load_index())
        print("selftest ok: overlaps are caught, example spec renders clean")
    else:
        print("selftest ok (icon pack not found: example spec skipped)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render a spec to SVG")
    r.add_argument("spec")
    r.add_argument("--out")
    i = sub.add_parser("icons", help="search icon keys")
    i.add_argument("query", nargs="+")
    sub.add_parser("selftest", help="test the overlap check and the example")
    args = ap.parse_args()
    try:
        {"render": cmd_render, "icons": cmd_icons, "selftest": lambda a: selftest()}[args.cmd](args)
    except DiagramError as err:
        print(f"ERROR {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
