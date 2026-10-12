# Cost

Status: **structure only. No price has been calculated yet.** The figures are
meant to come from Infracost (`infracost breakdown --path envs/prototype`),
which prices the Terraform code without deploying anything. Numbers written
here by hand would be guesses, so this page leaves them out until the tool has
produced them.

## What bills, and how

| Component | Billing nature | Prototype choice |
|---|---|---|
| ALB | Hourly while it exists, plus usage | One shared ALB for all services (host rules) instead of one per service |
| Fargate tasks | Per vCPU-second and GB-second while running | Smallest sizes: 0.25 vCPU for the launcher, 0.5 vCPU for SSO |
| RDS instance | Hourly while it exists, plus storage | One instance, `db.t4g.micro`, single-AZ, 20 GiB gp3 |
| NAT gateway | Hourly plus per-GB processing | **Not used.** The largest avoidable fixed cost |
| Route 53 | Per hosted zone, plus queries | One zone |
| Secrets Manager | Per secret per month, plus API calls | Four today: three created here plus the RDS-managed master secret |
| CloudWatch | Logs ingested and stored, alarms, dashboard | 365-day retention, a handful of alarms |
| ECR, S3 | Storage and requests | Small |
| Data transfer | Per GB out | Low at this scale |

## Levers

- Single-AZ to Multi-AZ roughly doubles the database line item; the switch is
  `db_multi_az`.
- A NAT gateway would be a fixed monthly cost larger than the compute; VPC
  endpoints are the cheaper middle path if tasks move to private subnets.
- Fargate Spot suits the queue worker (when `malas` is added) but not the
  web-facing services.
- Teardown: `terraform destroy` removes every hourly line item. The final RDS
  snapshot remains and bills for storage until deleted.

## Comparison with the homelab

To fill in once the estimate exists:

| Item | Homelab | AWS estimate |
|---|---|---|
| Hardware (amortised) | | |
| Electricity | | |
| Internet | | |
| Backup storage | none today | included in RDS |
| Operator time for patching | | reduced for the managed parts |

The honest conclusion is usually not "AWS is cheaper". It is: what each option
costs, what each one does and does not give you (backups, alerting, rollback),
and at what scale the answer changes. Write that conclusion here, with the
numbers.

## Reproduce

```bash
infracost auth login
infracost breakdown --path envs/prototype
```
