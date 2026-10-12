# Diagrams

The architecture diagram is a hand-drawn SVG, built by a script from the local
AWS icon pack. Follow the house style below. The owner reviews every draft
before it is committed.

## House style

Why these rules exist: an earlier diagram drew each service twice (once per
subnet) with arrows to only one copy, put a blank box where the second
database subnet would be, scattered the supporting services in a row with no
connections, and let arrows cross titles. The owner called it a mess.

| # | Rule | How to check |
|---|---|---|
| 1 | One icon per resource that `main.tf` creates. No per-AZ copies, no placeholder boxes | Count the icons of each kind in the diagram and the resources in `main.tf` |
| 2 | Multi-AZ goes in the container title ("Public subnets, 2 AZs"). A resource built once says so ("single AZ in the prototype") | Compare with `db_multi_az` and the subnet count |
| 3 | Arrows show the request path only: User, DNS, internet gateway, ALB, service, database | Each arrow maps to one hop in the path. No arrow ends in empty space |
| 4 | Supporting services have no arrows. Group them in dashed boxes with a title that states the relationship | No arrow touches ECR, Secrets Manager, S3, CloudWatch or SNS |
| 5 | No arrow crosses a title, a label or an icon. Use straight lines or right angles | View the render at full size |
| 6 | Every label sits inside its container. A label sits next to its icon | View the render at full size |
| 7 | Left to right, one main line. Icons that sit on a border (the internet gateway) get a white patch behind them | View the render |
| 8 | Every label and detail line traces to `main.tf` or a module. Remove what does not | Grep for it |
| 9 | The header reads "Prototype design. Not deployed." and names `main.tf` as the source | Look at the top of the image |
| 10 | Render and look before showing. The owner reviews drafts first, and nothing is committed until they approve | Show the render, then wait |
| 11 | AWS infrastructure diagrams are always the standard white AWS style: white page, official icons, official group colours. This holds in every repo and on the portfolio site. Never recolour a diagram to a site theme | The page is white and the colours match the AWS icon pack |
| 12 | Nothing overlaps, anywhere. No text, icon, arrow, border or box may cover, touch or run through another, in every image and every layout. Leave visible clear space (about 10 px at full size) between each pair. Draw containers first and arrows and labels last, so a box never paints over an arrow or a label. If a label is wider than its gap, shorten it or put it on two lines | The build fails on any overlap (`build_architecture.py` checks every text, icon, arrow and border). Then open the SVG at full size and walk it, because text widths are estimates. A scaled-down preview does not count |

## Source files

| Path | Purpose |
|---|---|
| `diagrams/build_architecture.py` | Generates the SVG. Edit this to change the diagram |
| `docs/img/architecture.svg` | The generated diagram, committed so the README can show it |
| `diagrams/build_findings.py` | Generates the findings-to-design-answers image. Reuses the helpers and the overlap check of `build_architecture.py` |
| `docs/img/findings.svg` | Its output. The portfolio site shows the same file as `static/projects/yado-aws-2.svg` |
| `diagrams/build_ha_webserver.py` | Generates the architecture diagram of the separate HA Web Server project (source of truth: the `ha-webserver` repo README). It lives here because the icon pack and the overlap check live here |
| `docs/img/ha-webserver.svg` | Its output |

Rebuild after any change, and commit both files together:

```bash
python diagrams/build_architecture.py
```

The diagram is one white SVG, 1600 x 1000 (16:10). The portfolio site shows the
same file, so the two cannot drift apart. After a rebuild, copy it over:

```bash
python diagrams/build_architecture.py --out ../portofolio/static/projects/yado-aws-1.svg
```

Rebuild and re-copy whenever the layout or the Terraform changes.

The build enforces rule 12. If two elements overlap or come too close, it
prints which ones and writes nothing. To test the check itself:

```bash
python diagrams/build_architecture.py --selftest
```

The self-test confirms the check catches an overlapping label, an arrow through
a label and stacked text, and that the real diagram is clean. Run it after
changing the script. Keep the clearances in the script, not in your head.

Never edit the SVG by hand. The script needs only Python 3 and the icon pack in
`assets/aws-icons/`. The pack is not committed: its README says where to
download it, and covers the layout and the licence note. Icons
are embedded unmodified, each with its label.

To check a render, open the SVG in a browser at full size and go through the
table above. Do not judge it from a scaled-down preview.

## Accuracy rule

A diagram must match the Terraform. If the diagram shows something the code
does not build (or hides something it does), fix the diagram. Today it shows
the database as single-AZ, because `db_multi_az` is false in the prototype,
and it leaves out security groups and IAM on purpose; those belong in the
module docs.

## Why not diagram-as-code (`awsdac`)

`awslabs/diagram-as-code` was tried first (v0.24). It takes no Terraform input,
and it places arrows itself, so arrows crossed subnet titles and could not be
steered clear. It also forced a duplicate service per subnet. It fails rules 5
and 6 for anything beyond a small diagram, so it is not used here.

## Other SVG diagrams

The portfolio site shows the same white diagram as this repo (rule 11), even
though its pages are dark. Its rules live in the portfolio repo at
`docs/ai/DIAGRAMS.md` and match this section. Any other AWS diagram follows
the same rules, including the white style.

## What goes in the README

Embed the rendered architecture diagram and state that it describes a design,
not a deployment. The status line at the top of the README must stay.
