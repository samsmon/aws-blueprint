# diagram

Renders an AWS architecture diagram (white AWS style, official icons) from a small YAML spec.
Agents: edit the spec, run `render`, read the one-line result. Do not read `render.py`.

```bash
python tools/diagram/render.py render blueprints/<slug>/diagrams/architecture.yml   # writes docs/img/architecture.svg
python tools/diagram/render.py icons lambda s3 textract                             # find icon keys
python tools/diagram/render.py selftest
```

`render` prints `OK <file> (N nodes, ...)` or `ERROR ...` with the overlapping pairs. Output goes to
`<blueprint>/docs/img/<name>.svg` when the spec sits in a `diagrams/` folder, else next to the spec.
Commit the spec and the SVG together. Never edit the SVG by hand.

## Icon pack

AWS's package is not in the repo (see `blueprints/yado-aws/assets/aws-icons/README.md`). Lookup order:
env `AWS_ICON_PACK`, then `pack = "<folder>"` in `tools/diagram/config.toml` (git-ignored), then
`~/Downloads/**/Icon-package_*`. The folder holds `Architecture-Service-Icons_*`, `Resource-Icons_*`,
`Architecture-Group-Icons_*`.

## Spec

```yaml
title: RAG on AWS
source: blueprints/rag-aws/README.md      # shown in the header; the design is the source of truth
canvas: [1600, 1000]                       # optional, default
cell: [200, 150]                           # px per grid step, default
origin: [100, 150]                         # px of grid (0,0), default
nodes:
  fn: {icon: lambda, label: [Lambda, ingest-api], at: [3, 1]}   # at = [col, row], floats allowed
edges:
  - [apigw, fn]                  # elbows go horizontal first; add "vh" for vertical first
  - {from: a, to: b, via: [[2, 3]]}   # explicit waypoints (grid coords); every segment axis-aligned
groups:
  vpc: {title: VPC, style: vpc, members: [fn, db]}   # members: node ids or group ids; box is computed
```

Node keys: `icon` (alias, service name, `res:<resource>`, or `user`), `label` (string, or list: bold line then
sub lines), `at`, `label_pos` (below, above, right, left), `size` (default 56), `border: true` (icon sits on a
group border; gets a white patch), `support: true` (supporting service, see rule 4).
Group keys: `title`, `style` (cloud, region, vpc, public, private, dashed), `members`, `pad` (28),
`grow: [left, top, right, bottom]` px to align sibling groups.
Aliases: s3, sqs, sns, apigw, kms, secrets, acm, route53, ecr, iam, alb, igw, vpce, bucket, queue, function.

## House style (from yado-aws, `docs/diagrams.md`)

| # | Rule | Enforced |
|---|---|---|
| 1 | One icon per resource the design creates. No per-AZ copies, no placeholder boxes | author |
| 2 | Multi-AZ goes in the group title ("Private subnets, 2 AZs"); a resource built once says so in its label | author |
| 3 | Arrows show the data path only, hop by hop, no arrow into empty space | author |
| 4 | Supporting services (ECR, Secrets Manager, KMS, CloudWatch, SNS) have no arrows; group them in a `dashed` group titled by the relationship | tool (`support: true`) |
| 5, 6 | No arrow crosses a title, label or icon; every label sits inside its container, next to its icon | tool (overlap check) |
| 7 | Left to right, one main line. Icons on a border get a white patch | `border: true` |
| 8 | Every label traces to the design doc. Remove what does not | author |
| 9 | Header reads "Prototype design. Not deployed." and names the source | tool (`source:`) |
| 10 | Render, look at it at full size, show the owner, wait for approval before committing | author |
| 11 | Always the white AWS style, official icons and group colours. Never recolour | tool |
| 12 | Nothing overlaps: text, icon, arrow, border keep clear space; the render fails otherwise | tool |

Text widths are estimates, so after `OK` still open the SVG in a browser at full size and walk it.
A RAG-style design has two data paths (ingest and query): draw both as arrows, never arrows to support services.
