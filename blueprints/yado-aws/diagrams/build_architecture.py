"""Build the architecture diagram SVG from the local AWS icon pack.

    python diagrams/build_architecture.py                          # docs/img/architecture.svg
    python diagrams/build_architecture.py --out <another path>      # e.g. the portfolio's static/projects/
    python diagrams/build_architecture.py --selftest                # prove the overlap check works

One white, 1600 x 1000 (16:10) diagram in the standard AWS style, used by both
this repo's README and the portfolio site. AWS diagrams are always white, so
they match real AWS architecture diagrams; never recolour them to a site theme.

The layout follows the House style in docs/diagrams.md. Icons are embedded
unmodified, so the SVG is self-contained. Keep this file in step with
envs/prototype/main.tf: every label and detail must trace to the Terraform.

Rule 12 (nothing overlaps) is enforced here: every text, icon, arrow and border
is recorded with its bounding box, and the build fails if two of them cover,
touch or come closer than the clearance for that pair. Text widths are
estimates, so the check does not replace looking at the render at full size.
"""
import argparse
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "assets" / "aws-icons"
S = ICONS / "Architecture-Service-Icons_07312026"
G = ICONS / "Architecture-Group-Icons_07312026"
RS = ICONS / "Resource-Icons_07312026"

WIDTH, HEIGHT = 1600, 1000
SHIFT = (35, 70)  # moves the drawing below the header and centres it on the page

IC = dict(
    r53=S / "Arch_Networking-Content-Delivery/64/Arch_Amazon-Route-53_64.svg",
    igw=RS / "Res_Networking-Content-Delivery/Res_Amazon-VPC_Internet-Gateway_48.svg",
    alb=RS / "Res_Networking-Content-Delivery/Res_Elastic-Load-Balancing_Application-Load-Balancer_48.svg",
    farg=S / "Arch_Containers/64/Arch_AWS-Fargate_64.svg",
    rds=S / "Arch_Databases/64/Arch_Amazon-RDS_64.svg",
    ecr=S / "Arch_Containers/64/Arch_Amazon-Elastic-Container-Registry_64.svg",
    sec=S / "Arch_Security-Identity/64/Arch_AWS-Secrets-Manager_64.svg",
    s3=S / "Arch_Storage/64/Arch_Amazon-Simple-Storage-Service_64.svg",
    cw=S / "Arch_Management-Tools/64/Arch_Amazon-CloudWatch_64.svg",
    sns=S / "Arch_Application-Integration/64/Arch_Amazon-Simple-Notification-Service_64.svg",
    cloud=G / "AWS-Cloud_32.svg",
    vpc=G / "Virtual-private-cloud-VPC_32.svg",
    pub=G / "Public-subnet_32.svg",
    priv=G / "Private-subnet_32.svg",
)

INK, SUB, LINE = "#16191F", "#5F6B7A", "#232F3E"
HEAD = (f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
        f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker></defs>'
        f'<style>.lbl{{font-size:15px;fill:{INK};font-weight:600}}.sub{{font-size:13px;fill:{SUB}}}'
        f'.ttl{{font-size:17px;fill:{INK};font-weight:600}}.arr{{fill:none;stroke:{LINE};stroke-width:2}}'
        f'.h1{{font-size:26px;font-weight:700;fill:{INK}}}.h2{{font-size:14px;fill:{SUB}}}'
        f'.cap{{font-size:13px;fill:{SUB};font-style:italic}}</style>')

# --- overlap check (rule 12) -------------------------------------------------

# class -> (font size, average glyph width as a fraction of the size)
TEXT_METRICS = {"lbl": (15, 0.60), "sub": (13, 0.55), "ttl": (17, 0.60), "cap": (13, 0.55)}
# Minimum clear space in px for each pair of kinds. Pairs not listed are not checked
# (an arrow may cross a border, and two arrows may share an elbow).
CLEARANCE = {
    ("text", "text"): 0, ("icon", "text"): 4, ("arrow", "text"): 6, ("border", "text"): 6,
    ("icon", "icon"): 6, ("arrow", "icon"): 6, ("border", "icon"): 6,
}
ARROW_END_TRIM = 14  # an arrow may touch the icon it points at or leaves from

ITEMS = []


def record(kind, x0, y0, x1, y1, name, **flags):
    ITEMS.append(dict(kind=kind, box=(x0, y0, x1, y1), name=name, **flags))


def find_overlaps(items):
    problems = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            key = tuple(sorted((a["kind"], b["kind"])))
            if key not in CLEARANCE:
                continue
            if "border" in key and (a.get("on_border") or b.get("on_border")):
                continue  # the internet gateway sits on the VPC border on purpose
            c = CLEARANCE[key]
            ax0, ay0, ax1, ay1 = a["box"]
            bx0, by0, bx1, by1 = b["box"]
            if ax0 - c < bx1 and bx0 - c < ax1 and ay0 - c < by1 and by0 - c < ay1:
                problems.append(f'{a["kind"]} "{a["name"]}" and {b["kind"]} "{b["name"]}" '
                                f'are closer than {c}px (boxes {tuple(round(v) for v in a["box"])} and '
                                f'{tuple(round(v) for v in b["box"])})')
    return problems


class OverlapError(Exception):
    pass


# --- drawing helpers ---------------------------------------------------------


def uri(key):
    return "data:image/svg+xml;base64," + base64.b64encode(IC[key].read_bytes()).decode()


def img(key, cx, cy, size=48, on_border=False):
    record("icon", cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2, key, on_border=on_border)
    return f'<image href="{uri(key)}" x="{cx - size / 2}" y="{cy - size / 2}" width="{size}" height="{size}"/>'


def text(x, y, content, cls="lbl", anchor="middle", on_border=False):
    size, factor = TEXT_METRICS[cls]
    width = len(content) * size * factor
    x0 = x - width / 2 if anchor == "middle" else x
    record("text", x0, y - size * 0.8, x0 + width, y + size * 0.25, content, on_border=on_border)
    return f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{content}</text>'


def label(cx, y, name, sub=None):
    out = text(cx, y, name, "lbl")
    if sub:
        out += text(cx, y + 17, sub, "sub")
    return out


def arrow(points, name=""):
    segments = list(zip(points, points[1:]))
    for i, ((x0, y0), (x1, y1)) in enumerate(segments):
        lo_x, hi_x, lo_y, hi_y = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        trim_start = ARROW_END_TRIM if i == 0 else 0
        trim_end = ARROW_END_TRIM if i == len(segments) - 1 else 0
        if y0 == y1:  # horizontal
            first, last = (lo_x + trim_start, hi_x - trim_end) if x1 >= x0 else (lo_x + trim_end, hi_x - trim_start)
            lo_x, hi_x = min(first, last), max(first, last)
        else:  # vertical
            first, last = (lo_y + trim_start, hi_y - trim_end) if y1 >= y0 else (lo_y + trim_end, hi_y - trim_start)
            lo_y, hi_y = min(first, last), max(first, last)
        record("arrow", lo_x - 1, lo_y - 1, hi_x + 1, hi_y + 1, name or f"{points[0]}->{points[-1]}")
    return '<path d="M' + " L".join(f"{x},{y}" for x, y in points) + '" class="arr" marker-end="url(#ah)"/>'


def box(x, y, w, h, stroke, fill, icon, title, dashed=False):
    for side in ((x, y, x + w, y), (x, y + h, x + w, y + h), (x, y, x, y + h), (x + w, y, x + w, y + h)):
        record("border", side[0] - 1, side[1] - 1, side[2] + 1, side[3] + 1, title)
    out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="2"'
    out += ' stroke-dasharray="6 5"/>' if dashed else "/>"
    if icon:
        out += f'<image href="{uri(icon)}" x="{x}" y="{y}" width="40" height="40"/>'
    out += text(x + (52 if icon else 24), y + 26, title, "ttl", anchor="start")
    return out


def user(x, y):
    record("icon", x - 28, y - 15, x + 28, y + 50, "user")
    return (f'<circle cx="{x}" cy="{y}" r="15" fill="none" stroke="{LINE}" stroke-width="3"/>'
            f'<path d="M{x - 28},{y + 50} Q{x - 28},{y + 24} {x},{y + 24} Q{x + 28},{y + 24} {x + 28},{y + 50} Z" '
            f'fill="none" stroke="{LINE}" stroke-width="3" stroke-linejoin="round"/>')


def build():
    ITEMS.clear()
    p = []
    # Request path, left to right: user, DNS, internet gateway, ALB, service, database.
    p.append(user(60, 436))
    p.append(label(60, 510, "User"))
    p.append(arrow([(100, 470), (138, 470)], "user to Route 53"))
    p.append(img("r53", 170, 470, 56))
    p.append(text(170, 540, "Route 53") + text(170, 557, "+ ACM"))

    p.append(box(220, 110, 1270, 700, LINE, "#fff", "cloud", "AWS Cloud"))
    p.append(box(320, 165, 810, 580, "#8C4FFF", "#fff", "vpc", "VPC"))
    # The internet gateway sits on the VPC border, on a white patch.
    p.append('<rect x="288" y="440" width="64" height="100" rx="6" fill="#fff"/>')
    p.append(img("igw", 320, 470, 48, on_border=True))
    p.append(text(320, 522, "Internet", on_border=True) + text(320, 539, "gateway", on_border=True))
    # Drawn after the cloud box and the gateway patch, or the white fills paint over it.
    p.append(arrow([(202, 470), (294, 470)], "Route 53 to internet gateway"))

    p.append(box(370, 225, 380, 480, "#7AA116", "#F6FAEC", "pub", "Public subnets, 2 AZs"))
    p.append(arrow([(344, 470), (446, 470)], "internet gateway to ALB"))
    p.append(img("alb", 480, 470, 56))
    p.append(text(480, 516, "Application") + text(480, 533, "Load Balancer")
             + text(480, 550, "host rules, HTTPS", "sub"))
    p.append(arrow([(508, 470), (570, 470), (570, 380), (634, 380)], "ALB to yado"))
    p.append(arrow([(570, 470), (570, 560), (634, 560)], "ALB to sso"))
    for y, name, sub in [(380, "yado", "Fargate, Next.js"), (560, "sso", "Fargate, Laravel")]:
        p.append(img("farg", 660, y))
        p.append(label(660, y + 42, name, sub))

    p.append(box(790, 225, 320, 480, "#00A4A6", "#F0FAFA", "priv", "Private subnets, 2 AZs"))
    p.append(arrow([(686, 560), (922, 560)], "sso to RDS"))
    p.append(img("rds", 950, 560))
    p.append(label(950, 602, "RDS PostgreSQL 16", "single AZ in the prototype"))
    p.append(text(814, 688, "No internet route", "cap", anchor="start"))

    # Supporting services: no arrows, grouped by what they do.
    p.append(box(1160, 165, 300, 300, "#8A97A8", "#F7F8FA", None, "Used by yado and sso", True))
    for y, key, name in [(240, "ecr", "ECR"), (320, "sec", "Secrets Manager"), (400, "s3", "S3")]:
        p.append(img(key, 1210, y))
        p.append(text(1250, y + 5, name, anchor="start"))
    p.append(box(1160, 495, 300, 250, "#8A97A8", "#F7F8FA", None, "Alerting", True))
    p.append(img("cw", 1210, 570))
    p.append(text(1250, 575, "CloudWatch alarms", anchor="start"))
    p.append(img("sns", 1210, 680))
    p.append(text(1250, 685, "SNS email", anchor="start"))
    p.append(arrow([(1210, 596), (1210, 652)], "CloudWatch to SNS"))

    problems = find_overlaps(ITEMS)
    if problems:
        raise OverlapError("Overlap check failed (rule 12):\n  " + "\n  ".join(problems))

    dx, dy = SHIFT
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" '
            f'height="{HEIGHT}" font-family="Helvetica, Arial, sans-serif">{HEAD}'
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#fff"/>'
            '<text x="48" y="58" class="h1">Yado on AWS</text>'
            '<text x="48" y="84" class="h2">Prototype design. Not deployed. Source of truth: envs/prototype/main.tf</text>'
            f'<g transform="translate({dx},{dy})">' + "".join(p) + "</g></svg>")


def selftest():
    """The check must catch the mistakes that were made by hand, and pass clean layouts."""
    def case(*items):
        return find_overlaps([dict(kind=k, box=b, name=n) for k, b, n in items])

    cloud_left = ("border", (219, 110, 221, 810), "AWS Cloud")
    # 1. A label wider than its gap runs into the cloud border.
    assert case(cloud_left, ("text", (110, 528, 230, 543), "Route 53 + ACM")), "label over a border not caught"
    # 2. An arrow runs through the end of a label.
    assert case(("arrow", (569, 469, 571, 561), "ALB to sso"),
                ("text", (395, 504, 575, 519), "Application Load Balancer")), "arrow through a label not caught"
    # 3. Two labels stacked on top of each other.
    assert case(("text", (0, 0, 100, 16), "a"), ("text", (50, 8, 150, 24), "b")), "text over text not caught"
    # 4. A clean layout passes.
    assert not case(cloud_left, ("text", (134, 528, 206, 543), "Route 53")), "false positive on a clean label"
    # 5. A real build passes.
    build()
    print("selftest ok: overlaps are caught, the real diagram is clean")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "img" / "architecture.svg",
                    help="output file (default: docs/img/architecture.svg)")
    ap.add_argument("--selftest", action="store_true", help="test the overlap check, write nothing")
    args = ap.parse_args()
    try:
        if args.selftest:
            selftest()
        else:
            svg = build()
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(svg, encoding="utf-8")
            print(f"wrote {args.out}")
    except OverlapError as err:
        print(err, file=sys.stderr)
        sys.exit(1)
