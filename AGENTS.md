# AGENTS.md

Guidance for AI agents working in this repo.

## Purpose

Central collection of AWS implementation blueprints by samsmon. Each blueprint is a design for running some workload on AWS: architecture, Terraform, cost estimate, and trade-offs.

This repo is planning only. Nothing here is deployed. There is no AWS account behind it and no real billing. Cost figures are estimates from AWS Pricing Calculator or Infracost, never actual spend. Expensive services (RDS, ALB, NAT) are the reason it stays blueprint-only.

## Hard rules

- Never run `terraform apply`, `terraform destroy` against a real account, or any AWS CLI command that creates resources.
- Never add credentials, keys, account IDs, or `*.tfvars` files. Only `*.tfvars.example`.
- Never present a cost estimate as a real bill. Label it as an estimate and state the assumptions.
- Do not claim a blueprint was tested on live AWS unless it was.

## Layout

```
blueprints/<slug>/   one folder per blueprint, kebab-case slug
_template/           copy this to start a new blueprint
docs/                repo-level conventions (if any)
.github/workflows/   one CI file, matrix over blueprints
```

A blueprint folder:

```
README.md            goal, scope, services, status (front matter)
docs/architecture.md diagram, components, networking, security, observability
docs/cost.md         estimate, assumptions, cost drivers, optimization levers
docs/decisions.md    trade-offs, short ADRs
modules/, envs/      Terraform, optional
```

`blueprints/yado-aws` is the reference example. It is complete and has full Terraform, a local emulator, diagrams, and CI checks. It predates `_template`, so its docs have extra files.

## Adding a blueprint

1. Copy `_template/` to `blueprints/<slug>/`.
2. Fill `README.md` front matter: title, slug, status, tags, dates.
3. Start at status `idea`. A blueprint can be docs only.
4. Add Terraform under `envs/` and `modules/` only when the design is concrete. CI treats any blueprint with an `envs/` folder as Terraform.
5. Add a row to the index in the root `README.md`.

Status values: `idea`, `drafted`, `reviewed`.

## Conventions

- Default region for estimates: `ap-southeast-3` (Jakarta). State it if different.
- Diagrams: Mermaid in markdown, or generated SVG (see `blueprints/yado-aws/diagrams/`).
- Write down trade-offs and prototype shortcuts (no NAT, single-AZ, local state) in `docs/decisions.md`. Say what production would change.
- Keep each blueprint self-contained. Do not import modules across blueprints. Copy instead.
- Terraform: `fmt`, `validate`, `tflint`, and Checkov must pass. Checkov skips go in the blueprint's `.checkov.yaml` with a reason per entry.

## CI

`.github/workflows/ci.yml` runs per changed blueprint that has `envs/`: format, init without backend, validate, tflint, Checkov. Infracost runs on pull requests when repo variable `INFRACOST_ENABLED` is `true` and secret `INFRACOST_API_KEY` is set. A change to anything under `.github/` runs all blueprints.

## Style

- Concise and direct. Code, config, and tables over prose.
- Plain punctuation. No emojis, no em dashes.
