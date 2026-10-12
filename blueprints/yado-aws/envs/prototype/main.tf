resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  # Pinned rather than discovered, so the subnet layout cannot change when AWS
  # adds an availability zone to the region.
  azs = length(var.azs) > 0 ? var.azs : ["${var.region}a", "${var.region}b"]

  hosts = {
    yado = var.domain_name
    sso  = "sso.${var.domain_name}"
  }

  # One role + database per service on the shared RDS instance.
  # malas joins here in a later phase.
  databases = {
    sso = { role = "sso", dbname = "db_sso" }
  }

  # Keys each service expects in its Secrets Manager secret. The values are
  # set out of band (see docs/migration.md), never in Terraform or git.
  app_secrets = {
    sso  = ["APP_KEY", "PASSPORT_PRIVATE_KEY", "PASSPORT_PUBLIC_KEY"]
    yado = ["SSO_CLIENT_SECRET"]
  }

  # ECS injects a single JSON key from a secret with the "<arn>:<key>::" syntax.
  sso_db_secret   = module.secrets.db_secret_arns["sso"]
  sso_app_secret  = module.secrets.app_secret_arns["sso"]
  yado_app_secret = module.secrets.app_secret_arns["yado"]
}

# ---------------------------------------------------------------------------
# Foundations
# ---------------------------------------------------------------------------

module "network" {
  source = "../../modules/network"

  name = var.name
  azs  = local.azs
}

module "ecr" {
  source = "../../modules/ecr"

  name         = var.name
  repositories = ["yado", "sso-app", "sso-nginx"]
  force_delete = var.ephemeral
}

module "storage" {
  source = "../../modules/storage"

  bucket_name   = "${var.name}-storage-${random_id.suffix.hex}"
  force_destroy = var.ephemeral
}

module "secrets" {
  source = "../../modules/secrets"

  name                    = var.name
  databases               = local.databases
  app_secrets             = local.app_secrets
  recovery_window_in_days = var.secret_recovery_window_days
}

module "rds" {
  source = "../../modules/rds"

  name                     = var.name
  vpc_id                   = module.network.vpc_id
  subnet_ids               = module.network.private_subnet_ids
  client_security_group_id = module.network.db_clients_security_group_id
  instance_class           = var.db_instance_class
  multi_az                 = var.db_multi_az
  deletion_protection      = var.deletion_protection
}

module "iam" {
  source = "../../modules/iam"

  name = var.name
  secret_arns = concat(
    values(module.secrets.db_secret_arns),
    values(module.secrets.app_secret_arns),
    [module.rds.master_user_secret_arn],
  )
  storage_bucket_arn = module.storage.bucket_arn

  task_roles = {
    yado    = { storage_prefix = "" }
    sso     = { storage_prefix = "sso" }
    db-init = { storage_prefix = "" }
  }
}

resource "aws_ecs_cluster" "this" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

module "alb" {
  source = "../../modules/alb"

  name                = var.name
  domain_name         = var.domain_name
  hostnames           = values(local.hosts)
  subnet_ids          = module.network.public_subnet_ids
  security_group_id   = module.network.alb_security_group_id
  deletion_protection = var.deletion_protection
}

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

# yado: Next.js launcher and status page (stateless).
# NEXT_PUBLIC_* values are baked into the image at `next build`, so the CI
# pipeline builds one image per environment (see docs/architecture.md).
module "yado" {
  source = "../../modules/ecs-service"

  name                  = "${var.name}-launcher"
  cluster_arn           = aws_ecs_cluster.this.arn
  vpc_id                = module.network.vpc_id
  subnet_ids            = module.network.public_subnet_ids
  alb_security_group_id = module.network.alb_security_group_id
  listener_arn          = module.alb.https_listener_arn
  host_header           = local.hosts.yado
  listener_priority     = 20
  container_name        = "yado"
  container_port        = 3000
  health_check_path     = "/api/health"
  execution_role_arn    = module.iam.execution_role_arn
  task_role_arn         = module.iam.task_role_arns["yado"]

  containers = [{
    name         = "yado"
    image        = "${module.ecr.repository_urls["yado"]}:${var.yado_image_tag}"
    portMappings = [{ containerPort = 3000, protocol = "tcp" }]

    environment = [
      { name = "SSO_HEALTH_URL", value = "https://${local.hosts.sso}/health" },
      # Empty on purpose: an unset probe is reported as "unknown", not guessed.
      { name = "MALAS_HEALTH_URL", value = "" },
      { name = "LIBS_HEALTH_URL", value = "" },
    ]

    secrets = [
      { name = "SSO_CLIENT_SECRET", valueFrom = "${local.yado_app_secret}:SSO_CLIENT_SECRET::" },
    ]
  }]
}

# sso: Laravel + Passport OAuth2 identity provider.
# Two containers in one task share localhost, as php-fpm and nginx do in
# docker-compose today. nginx must therefore proxy to 127.0.0.1:9000, not to
# the compose hostname "app" (see docs/migration.md).
module "sso" {
  source = "../../modules/ecs-service"

  name                  = "${var.name}-sso"
  cluster_arn           = aws_ecs_cluster.this.arn
  vpc_id                = module.network.vpc_id
  subnet_ids            = module.network.public_subnet_ids
  alb_security_group_id = module.network.alb_security_group_id
  listener_arn          = module.alb.https_listener_arn
  host_header           = local.hosts.sso
  listener_priority     = 10
  container_name        = "nginx"
  container_port        = 80
  health_check_path     = "/health"
  cpu                   = 512
  memory                = 1024
  volumes               = ["public"]
  execution_role_arn    = module.iam.execution_role_arn
  task_role_arn         = module.iam.task_role_arns["sso"]

  extra_security_group_ids = [module.network.db_clients_security_group_id]

  containers = [
    {
      name  = "app"
      image = "${module.ecr.repository_urls["sso-app"]}:${var.sso_app_image_tag}"

      mountPoints = [{ sourceVolume = "public", containerPath = "/var/www/html/public", readOnly = false }]

      # The entrypoint re-copies public-src into the shared volume on every
      # start. nginx waits for this check so it never serves a half-copied
      # public/ directory.
      healthCheck = {
        command     = ["CMD-SHELL", "test -f /var/www/html/public/index.php"]
        interval    = 5
        timeout     = 3
        retries     = 10
        startPeriod = 20
      }

      environment = [
        { name = "APP_ENV", value = "production" },
        { name = "APP_DEBUG", value = "false" },
        { name = "APP_URL", value = "https://${local.hosts.sso}" },
        { name = "LOG_CHANNEL", value = "stderr" },
        { name = "SESSION_DRIVER", value = "database" },
        { name = "FILESYSTEM_DISK", value = "s3" },
        { name = "AWS_BUCKET", value = module.storage.bucket_name },
        { name = "AWS_DEFAULT_REGION", value = var.region },
        # The app uses read/write splitting, so all three hosts are set.
        { name = "DB_CONNECTION", value = "pgsql" },
        { name = "DB_HOST", value = module.rds.address },
        { name = "DB_READ_HOST", value = module.rds.address },
        { name = "DB_WRITE_HOST", value = module.rds.address },
        { name = "DB_PORT", value = tostring(module.rds.port) },
        { name = "DB_SSLMODE", value = "require" },
      ]

      secrets = [
        { name = "DB_DATABASE", valueFrom = "${local.sso_db_secret}:dbname::" },
        { name = "DB_USERNAME", valueFrom = "${local.sso_db_secret}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${local.sso_db_secret}:password::" },
        { name = "APP_KEY", valueFrom = "${local.sso_app_secret}:APP_KEY::" },
        { name = "PASSPORT_PRIVATE_KEY", valueFrom = "${local.sso_app_secret}:PASSPORT_PRIVATE_KEY::" },
        { name = "PASSPORT_PUBLIC_KEY", valueFrom = "${local.sso_app_secret}:PASSPORT_PUBLIC_KEY::" },
      ]
    },
    {
      name  = "nginx"
      image = "${module.ecr.repository_urls["sso-nginx"]}:${var.sso_nginx_image_tag}"

      portMappings = [{ containerPort = 80, protocol = "tcp" }]
      mountPoints  = [{ sourceVolume = "public", containerPath = "/var/www/html/public", readOnly = true }]
      dependsOn    = [{ containerName = "app", condition = "HEALTHY" }]
    },
  ]
}

# ---------------------------------------------------------------------------
# Database bootstrap and observability
# ---------------------------------------------------------------------------

module "db_init" {
  source = "../../modules/db-init"

  name               = var.name
  cluster_arn        = aws_ecs_cluster.this.arn
  execution_role_arn = module.iam.execution_role_arn
  task_role_arn      = module.iam.task_role_arns["db-init"]
  db_address         = module.rds.address
  db_port            = module.rds.port
  master_secret_arn  = module.rds.master_user_secret_arn
  subnet_ids         = module.network.public_subnet_ids
  security_group_ids = [module.network.db_clients_security_group_id]

  databases = {
    for k, v in local.databases : k => {
      role       = v.role
      dbname     = v.dbname
      secret_arn = module.secrets.db_secret_arns[k]
    }
  }
}

module "monitoring" {
  source = "../../modules/monitoring"

  name         = var.name
  cluster_name = aws_ecs_cluster.this.name
  alarm_email  = var.alarm_email

  service_names = {
    yado = module.yado.service_name
    sso  = module.sso.service_name
  }

  target_group_arn_suffixes = {
    yado = module.yado.target_group_arn_suffix
    sso  = module.sso.target_group_arn_suffix
  }

  alb_arn_suffix = module.alb.arn_suffix
  db_instance_id = module.rds.identifier
}
