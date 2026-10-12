# Migration runbook: homelab to AWS

How the running Yado services would move. Written against the real setup, but
not executed, since the stack has not been deployed (see the README status).

## 0. Preconditions

- Terraform applied; ECS services created with desired count 0 until the
  steps below are done.
- A domain you control. Do not reuse the live homelab hostnames until cutover.
- A container build for each image, tagged with a version (tags are immutable).

## 1. Images

| Image | Source | Change needed |
|---|---|---|
| `yado` | `Dockerfile` in the launcher repo | Build with the target environment's `NEXT_PUBLIC_*` values |
| `sso-app` | `docker/php/Dockerfile` in the SSO repo | None expected |
| `sso-nginx` | New small image: `nginx:alpine` + the config | **Change `fastcgi_pass app:9000` to `127.0.0.1:9000`.** Under compose, `app` is a service hostname; in a Fargate task both containers share localhost |

The php-fpm entrypoint re-copies `public-src` into the shared `public` volume
on every start. nginx therefore waits for the app container's health check
(`public/index.php` exists) before starting, so it never serves a partial
directory.

## 2. Secrets

Create the values out of band. They must never be committed or placed in
Terraform variables.

- `APP_KEY`: copy the **existing** value. A new key cannot decrypt data the
  application already encrypted.
- `PASSPORT_PRIVATE_KEY` / `PASSPORT_PUBLIC_KEY`: the SSO config reads both from
  the environment. Reusing the existing key pair keeps issued tokens valid.
- `SSO_CLIENT_SECRET` for the launcher: the existing confidential client's
  secret.

Set them with `aws secretsmanager put-secret-value`, one JSON object per
secret, using the keys listed in the `app_secret_arns` output. Tasks fail to
start if a referenced key is missing, so do this before raising the desired
count.

## 3. Database

1. Run the db-init task (`db_init_run_command` output). It creates the `sso`
   role and `db_sso` database, and it is safe to run again.
2. Take a dump from the running SSO database container on the homelab:
   `pg_dump --format=custom db_sso`.
3. Restore into RDS from a one-off task inside the VPC (the instance is not
   reachable from outside). A presigned S3 URL or a temporary private bucket
   can carry the dump into the task.
4. Check row counts per table against the source.

The homelab's unused `shared-postgres` databases are not migrated; they are
empty.

## 4. SSO configuration under AWS

The app uses read/write database splitting, so `DB_HOST`, `DB_READ_HOST` and
`DB_WRITE_HOST` must all point at the RDS endpoint (the stack sets all three).
Because uploads move to S3, `FILESYSTEM_DISK` is `s3`; confirm the avatar
upload path uses the default disk, and add a per-service root so SSO writes
only under its own `sso/` prefix, which is all its IAM role allows.

## 5. Cutover

1. Raise the desired count, wait for target group health.
2. Verify the OAuth flow end to end on the temporary domain: authorize, token
   exchange with PKCE, `/api/user` with the `profile:read` scope.
3. Lower the DNS TTL beforehand, then repoint the production records.
4. Keep the homelab containers running, untouched, for a rollback window.

## 6. Rollback

Repoint DNS to the homelab. Because the homelab stack was never modified, this
is a DNS change and nothing else. After the window, stop the homelab
containers but keep the volumes until a restore from RDS has been tested.

## 7. Backups and restore test

Backups are the biggest gap on the homelab today. On AWS:

- RDS automated backups (7 days) with a daily window.
- A final snapshot on destroy.
- Restore test, to be done before declaring the migration finished: restore the
  latest snapshot to a new instance, run a read check against `db_sso`, record
  the time it took, delete the test instance.
