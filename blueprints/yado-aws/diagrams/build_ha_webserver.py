"""Build the HA Web Server architecture SVG from the local AWS icon pack.

    python diagrams/build_ha_webserver.py                          # docs/img/ha-webserver.svg
    python diagrams/build_ha_webserver.py --out <another path>      # e.g. the portfolio's static/projects/
    python diagrams/build_ha_webserver.py --selftest                # run the overlap check, write nothing

One white, 1600 x 1000 (16:10) diagram in the standard AWS style, drawn with the
same helpers as build_architecture.py (official icons, unmodified, and the
rule 12 overlap check).

Source of truth: the README.md (v2.0.0) of the ha-webserver repo
(github.com/samsmon/ha-webserver). Every label traces to it. This was a real
course project built on the AWS Free Tier, so unlike the Yado diagram the header
does not say "not deployed". It states what the README states.

Facts worth knowing before editing:
- Both web servers use ONE RDS MySQL endpoint. There is no database on EC2 and no
  replication. "Replica" in the code means Web2 is read only because PHP returns
  HTTP 403 on writes.
- The database is a single instance, so the web tier is highly available and the
  database tier is not.
"""
import argparse
import sys
from pathlib import Path

import build_architecture as ba

ROOT = ba.ROOT
S = ba.S

ba.IC["ec2"] = S / "Arch_Compute/64/Arch_Amazon-EC2_64.svg"
ba.IC["iam"] = S / "Arch_Security-Identity/64/Arch_AWS-Identity-and-Access-Management_64.svg"

LINE = ba.LINE


def build():
    ba.ITEMS.clear()
    p = []
    text, img, box, arrow = ba.text, ba.img, ba.box, ba.arrow

    # Request path, left to right: user, load balancer, web servers, database.
    p.append(ba.user(90, 490))
    p.append(text(90, 564, "User", "lbl"))

    p.append(box(190, 110, 1370, 800, LINE, "#fff", "cloud", "AWS Cloud, us-east-1"))
    p.append(box(230, 165, 950, 700, "#8C4FFF", "#fff", "vpc", "VPC"))
    # Drawn after the cloud and VPC boxes, or their white fills paint over it.
    p.append(arrow([(132, 515), (278, 515)], "user to ALB"))

    p.append(img("alb", 310, 515, 56))
    p.append(text(310, 576, "Application") + text(310, 594, "Load Balancer")
             + text(310, 614, "ha-web-alb, HTTP 80", "sub")
             + text(310, 631, "round robin", "sub")
             + text(310, 648, "health: /health.php", "sub"))

    p.append(box(440, 230, 360, 250, "#7AA116", "#F6FAEC", None, "Availability Zone us-east-1a", True))
    p.append(box(440, 550, 360, 250, "#7AA116", "#F6FAEC", None, "Availability Zone us-east-1b", True))

    p.append(arrow([(340, 515), (400, 515), (400, 320), (590, 320)], "ALB to Web1"))
    p.append(arrow([(340, 515), (400, 515), (400, 680), (590, 680)], "ALB to Web2"))

    p.append(img("ec2", 620, 320, 56))
    p.append(text(620, 366, "Web1 (EC2)") + text(620, 383, "t3.micro, Ubuntu 22.04", "sub")
             + text(620, 400, "Master: read and write", "sub"))
    p.append(img("ec2", 620, 680, 56))
    p.append(text(620, 726, "Web2 (EC2)") + text(620, 743, "t3.micro, Ubuntu 22.04", "sub")
             + text(620, 760, "Read only: PHP returns 403 on writes", "sub"))

    p.append(arrow([(652, 320), (980, 320), (980, 484)], "Web1 to RDS"))
    p.append(arrow([(652, 680), (980, 680), (980, 546)], "Web2 to RDS"))
    p.append(img("rds", 980, 515, 56))
    p.append(text(1020, 510, "RDS MySQL", "lbl", anchor="start")
             + text(1020, 528, "ha-rds-mysql", "sub", anchor="start")
             + text(1020, 545, "single instance", "sub", anchor="start"))

    # Supporting services: no arrows, grouped by what they do.
    p.append(box(1210, 165, 330, 260, "#8A97A8", "#F7F8FA", None, "Used by the web servers", True))
    p.append(img("s3", 1262, 250))
    p.append(text(1302, 247, "Amazon S3", "lbl", anchor="start") + text(1302, 265, "user photo storage", "sub", anchor="start"))
    p.append(img("iam", 1262, 350))
    p.append(text(1302, 347, "IAM role EC2-S3-Role", "lbl", anchor="start")
             + text(1302, 365, "attached to Web1", "sub", anchor="start"))

    p.append(box(1210, 455, 330, 250, "#8A97A8", "#F7F8FA", None, "Security groups", True))
    p.append(text(1234, 525, "webserver-sg", "lbl", anchor="start")
             + text(1234, 544, "SSH 22 from my IP", "sub", anchor="start")
             + text(1234, 561, "HTTP 80 from anywhere", "sub", anchor="start"))
    p.append(text(1234, 610, "rds-sg", "lbl", anchor="start")
             + text(1234, 629, "MySQL 3306 from webserver-sg", "sub", anchor="start"))

    p.append(text(48, 955, "Both web servers use one RDS endpoint. Web2 is read only because of a PHP restriction, "
                           "not database replication.", "cap", anchor="start"))

    problems = ba.find_overlaps(ba.ITEMS)
    if problems:
        raise ba.OverlapError("Overlap check failed (rule 12):\n  " + "\n  ".join(problems))

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ba.WIDTH} {ba.HEIGHT}" width="{ba.WIDTH}" '
            f'height="{ba.HEIGHT}" font-family="Helvetica, Arial, sans-serif">{ba.HEAD}'
            f'<rect width="{ba.WIDTH}" height="{ba.HEIGHT}" fill="#fff"/>'
            '<text x="48" y="58" class="h1">HA Web Server on AWS</text>'
            '<text x="48" y="84" class="h2">Cloud Computing course project, built on the AWS Free Tier. '
            'Source of truth: ha-webserver README.md (v2.0.0)</text>'
            + "".join(p) + "</svg>")


def selftest():
    build()
    print("selftest ok: the HA web server diagram has no overlaps")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "img" / "ha-webserver.svg",
                    help="output file (default: docs/img/ha-webserver.svg)")
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
