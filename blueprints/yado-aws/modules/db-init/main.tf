# One-off task that creates the per-service roles and databases on the shared
# RDS instance. It is idempotent: safe to run again after adding a service or
# rotating a password. Terraform defines the task; a human (or the pipeline)
# runs it with the command in the `run_command` output.
#
# Why a task and not the Terraform postgresql provider: RDS sits in private
# subnets, so Terraform on a laptop or in CI cannot reach it directly.

data "aws_region" "current" {}

locals {
  env_name = { for k, v in var.databases : k => "PW_${upper(replace(k, "-", "_"))}" }

  per_database_sql = [
    for k, v in var.databases : <<-EOT
      psql -v ON_ERROR_STOP=1 -v pw="$${${local.env_name[k]}}" -d postgres <<'SQL'
      SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', '${v.role}', :'pw') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${v.role}') \gexec
      SELECT format('ALTER ROLE %I PASSWORD %L', '${v.role}', :'pw') \gexec
      SELECT format('GRANT %I TO %I', '${v.role}', current_user) \gexec
      SELECT 'CREATE DATABASE ${v.dbname} OWNER ${v.role}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${v.dbname}') \gexec
      REVOKE ALL ON DATABASE ${v.dbname} FROM PUBLIC;
      SQL
    EOT
  ]

  script = join("\n", concat(["set -eu"], local.per_database_sql))
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name}-db-init"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_task_definition" "this" {
  family                   = "${var.name}-db-init"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([{
    name      = "db-init"
    image     = "postgres:16-alpine"
    essential = true
    command   = ["sh", "-c", local.script]

    environment = [
      { name = "PGHOST", value = var.db_address },
      { name = "PGPORT", value = tostring(var.db_port) },
      { name = "PGSSLMODE", value = "require" },
    ]

    secrets = concat(
      [
        { name = "PGUSER", valueFrom = "${var.master_secret_arn}:username::" },
        { name = "PGPASSWORD", valueFrom = "${var.master_secret_arn}:password::" },
      ],
      [for k, v in var.databases : { name = local.env_name[k], valueFrom = "${v.secret_arn}:password::" }]
    )

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.this.name
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "db-init"
      }
    }
  }])
}
