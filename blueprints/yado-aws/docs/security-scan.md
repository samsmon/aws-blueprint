# Static checks and accepted findings

These run in CI (`.github/workflows/ci.yml`) and can be run locally.

| Check | Command | Result |
|---|---|---|
| Format | `terraform fmt -check -recursive` | clean |
| Validate | `terraform validate` in `envs/prototype` | valid |
| Lint | `tflint --recursive` | no issues |
| Security scan | `checkov` (config in `.checkov.yaml`) | 236 passed, 0 failed |
| Plan | `terraform plan -var use_emulator=true` | 93 resources to add, no errors |

The plan run uses the emulator settings (fake credentials, no account lookup),
so it needs no AWS account and creates nothing.

## How the scan was handled

The first Checkov run reported 41 failed checks across 25 distinct policies. Two
were fixed in code:

- Log retention raised to 365 days (`CKV_AWS_338`).
- Availability zones pinned instead of discovered, so the subnet layout cannot
  shift when a region adds a zone (`CKV_AWS_394`).

The rest are listed in `.checkov.yaml`, each with a reason. They fall into
three groups.

**Cost that is not worth it for a prototype, and is worth it in production:**
WAF, RDS Multi-AZ, enhanced monitoring and Performance Insights, customer
managed KMS keys for ECR, logs, secrets and S3, S3 replication and access
logging, ALB access logs, Route 53 DNSSEC and query logging.

**Controlled by a variable, off so the stack can be destroyed cleanly:** ALB
and RDS deletion protection (`deletion_protection`).

**Intentional design choices:**

- Port 80 is open to the world only to redirect to HTTPS.
- ALB to task traffic is plain HTTP inside the VPC; TLS ends at the ALB.
- Tasks have public IPs because there is no NAT gateway, and accept traffic
  only from the ALB security group.
- RDS uses password authentication with per-service roles and forced SSL,
  because the Laravel apps do not use IAM database authentication.
- Database credentials are generated but not auto-rotated in the prototype.
- The SNS topic is not encrypted with the AWS-managed key because that key
  blocks CloudWatch alarm delivery; a customer-managed key with an explicit
  key policy is the production fix.
- `CKV2_AWS_5` reports the ALB and db-clients security groups as unattached.
  They are attached in other modules through outputs, which the scanner does
  not follow.

## Before a real deployment

Revisit every entry in `.checkov.yaml`. A skip list is a record of risk that
someone accepted, not a clean bill of health.
