"""Build the findings-to-design-answers SVG from the local AWS icon pack.

    python diagrams/build_findings.py                          # docs/img/findings.svg
    python diagrams/build_findings.py --out <another path>      # e.g. the portfolio's static/projects/
    python diagrams/build_findings.py --selftest                # prove the overlap check passes

One white, 1600 x 1000 (16:10) image in the standard AWS style, drawn with the
same helpers as build_architecture.py (official icons, unmodified, and the
rule 12 overlap check). Each row pairs a finding from the real homelab review
with the design answer that addresses it. Keep it in step with the findings
table in README.md and with envs/prototype/main.tf: every line must trace to
one of them.
"""
import argparse
import sys
from pathlib import Path

import build_architecture as ba

ROOT = ba.ROOT

# (finding on the homelab, icon key, answer title, answer detail)
ROWS = [
    ("No scheduled PostgreSQL backups", "rds", "RDS automated backups",
     "7-day retention, final snapshot on destroy, restore test in the runbook"),
    ("SSO down about two weeks, no alert", "cw", "Running-task alarm",
     "Missing data counts as breaching. ECS replaces failed tasks"),
    ("Secrets in per-server .env files", "sec", "Secrets Manager",
     "Injected at task start, never stored on the server"),
    ("Three Postgres containers, one unused", "rds", "One shared RDS instance",
     "A database and a role per service. Single AZ in the prototype"),
    ("Manual pull and compose up deploys", "ecr", "Immutable image tags",
     "Rolling deploys with automatic rollback on failure"),
    ("Routes live only in a dashboard", "alb", "Hostname routing as code",
     "ALB host rules defined in Terraform"),
]

LEFT_X, LEFT_W = 48, 660
RIGHT_X, RIGHT_W = 752, 800
TOP, ROW_H, GAP = 175, 96, 24


def card(x, y, w, h, stroke, fill):
    for side in ((x, y, x + w, y), (x, y + h, x + w, y + h), (x, y, x, y + h), (x + w, y, x + w, y + h)):
        ba.record("border", side[0] - 1, side[1] - 1, side[2] + 1, side[3] + 1, "card")
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'


def build():
    ba.ITEMS.clear()
    p = []
    p.append(ba.text(LEFT_X, 150, "Found on the homelab", "ttl", anchor="start"))
    p.append(ba.text(RIGHT_X, 150, "Design answer", "ttl", anchor="start"))

    for i, (finding, icon, title, detail) in enumerate(ROWS):
        y = TOP + i * (ROW_H + GAP)
        cy = y + ROW_H // 2
        p.append(card(LEFT_X, y, LEFT_W, ROW_H, "#8A97A8", "#F7F8FA"))
        p.append(ba.text(LEFT_X + 24, cy + 5, finding, "lbl", anchor="start"))
        p.append(ba.arrow([(LEFT_X + LEFT_W + 4, cy), (RIGHT_X - 4, cy)], f"finding {i + 1} to answer"))
        p.append(card(RIGHT_X, y, RIGHT_W, ROW_H, "#7AA116", "#F6FAEC"))
        p.append(ba.img(icon, RIGHT_X + 52, cy, 56))
        p.append(ba.text(RIGHT_X + 100, cy - 4, title, "lbl", anchor="start"))
        p.append(ba.text(RIGHT_X + 100, cy + 16, detail, "sub", anchor="start"))

    foot_y = TOP + len(ROWS) * (ROW_H + GAP) - GAP + 44
    p.append(ba.text(LEFT_X, foot_y, "Findings come from a review of the running homelab, listed in README.md.",
                     "cap", anchor="start"))

    problems = ba.find_overlaps(ba.ITEMS)
    if problems:
        raise ba.OverlapError("Overlap check failed (rule 12):\n  " + "\n  ".join(problems))

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ba.WIDTH} {ba.HEIGHT}" width="{ba.WIDTH}" '
            f'height="{ba.HEIGHT}" font-family="Helvetica, Arial, sans-serif">{ba.HEAD}'
            f'<rect width="{ba.WIDTH}" height="{ba.HEIGHT}" fill="#fff"/>'
            '<text x="48" y="58" class="h1">Findings to design answers</text>'
            '<text x="48" y="84" class="h2">Prototype design. Not deployed. '
            'Source of truth: README.md findings and envs/prototype/main.tf</text>'
            + "".join(p) + "</svg>")


def selftest():
    build()
    print("selftest ok: the findings image has no overlaps")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "img" / "findings.svg",
                    help="output file (default: docs/img/findings.svg)")
    ap.add_argument("--selftest", action="store_true", help="run the overlap check, write nothing")
    args = ap.parse_args()
    try:
        if args.selftest:
            selftest()
        else:
            svg = build()
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(svg, encoding="utf-8")
            print(f"wrote {args.out}")
    except ba.OverlapError as err:
        print(err, file=sys.stderr)
        sys.exit(1)
