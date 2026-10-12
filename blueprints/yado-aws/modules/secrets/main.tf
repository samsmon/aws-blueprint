# Two kinds of secrets:
#
# 1. db credentials: generated here (random_password) and stored as JSON
#    {username, password, dbname}. The value therefore lives in Terraform state,
#    so state must be encrypted and access-controlled (see docs/architecture.md).
#
# 2. app secrets (APP_KEY, OAuth client secrets, Passport keys): only the empty
#    secret is created. Values are set out of band with
#    `aws secretsmanager put-secret-value`, so they never enter state or git.

resource "random_password" "db" {
  for_each = var.databases

  length  = 32
  special = false # keeps the value safe to interpolate into shell and SQL
}

resource "aws_secretsmanager_secret" "db" {
  for_each = var.databases

  name                    = "${var.name}/db/${each.key}"
  description             = "PostgreSQL credentials for the ${each.key} service"
  recovery_window_in_days = var.recovery_window_in_days
}

resource "aws_secretsmanager_secret_version" "db" {
  for_each = var.databases

  secret_id = aws_secretsmanager_secret.db[each.key].id
  secret_string = jsonencode({
    username = each.value.role
    password = random_password.db[each.key].result
    dbname   = each.value.dbname
  })
}

resource "aws_secretsmanager_secret" "app" {
  for_each = var.app_secrets

  name                    = "${var.name}/app/${each.key}"
  description             = "Application secrets for ${each.key} (${join(", ", each.value)}); values set out of band"
  recovery_window_in_days = var.recovery_window_in_days
}
