# aws-blueprint

Central collection of AWS implementation blueprints.

Planning only. Nothing here is deployed, and cost figures are estimates, never real bills. Expensive services like RDS and ALB are the reason this stays on paper.

Agents: read [AGENTS.md](AGENTS.md) first.

## Blueprints

| Slug | Status | Tags | Summary |
|------|--------|------|---------|
| [yado-aws](blueprints/yado-aws/) | drafted | ecs, fargate, rds, terraform | Yado homelab services (launcher, SSO, shared PostgreSQL) on ECS Fargate behind an ALB |

Status: `idea`, `drafted`, `reviewed`.

## Add a blueprint

```bash
cp -r _template blueprints/<slug>
```

Fill `README.md` front matter, start at status `idea`, then add a row above.

## Layout

```
blueprints/<slug>/   one folder per blueprint
_template/           starting point for a new blueprint
.github/workflows/   CI, matrix over blueprints with Terraform
AGENTS.md            rules and conventions for AI agents
```
