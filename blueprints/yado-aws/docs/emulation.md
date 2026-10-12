# Emulation: what was and was not verified

The project is a prototype that is not deployed to a real AWS account. This
page states exactly how far verification went, so nobody reads more into it
than is there.

## Verified

- `terraform validate` passes.
- `terraform plan -var use_emulator=true` completes with 93 resources to add.
  This proves the modules wire together, every reference resolves and every
  argument is accepted by the AWS provider schema.
- `tflint` and `checkov` are clean (see `docs/security-scan.md`).

## Not verified

- **No `terraform apply` has been run, against an emulator or anywhere else.**
  The emulator needs Docker, which was not installed on the development
  machine.
- Whether the free edition of a given emulator supports every service used
  here (ECS, RDS and load balancers have historically been limited or paid in
  some emulators) was not checked, and changes between versions. Check the
  vendor's current service list and licence before relying on it.
- Even where an emulator accepts the API calls, it stores resource definitions
  rather than running Fargate tasks, a Postgres engine or a load balancer. An
  apply against it would prove the Terraform is accepted, not that the system
  works.

## To rehearse an apply later

```bash
docker compose -f emulation/docker-compose.yml up -d
cd envs/prototype
terraform apply -var use_emulator=true
```

Expect some resources to fail on services the emulator does not implement.
Record which ones, and treat that list as emulator coverage, not as defects in
the design.

## What the applications themselves run on

The real workloads (launcher, SSO, PostgreSQL) run on the homelab. Compose
files there are the closest thing to a working reference for what each ECS task
definition describes.
