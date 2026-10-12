output "db_secret_arns" {
  value = { for k, s in aws_secretsmanager_secret.db : k => s.arn }
}

output "app_secret_arns" {
  value = { for k, s in aws_secretsmanager_secret.app : k => s.arn }
}

