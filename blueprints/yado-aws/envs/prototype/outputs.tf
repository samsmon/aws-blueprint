output "alb_dns_name" {
  value = module.alb.dns_name
}

output "name_servers" {
  description = "Delegate the domain to these name servers at your registrar"
  value       = module.alb.name_servers
}

output "rds_address" {
  value = module.rds.address
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}

output "app_secret_arns" {
  description = "Fill these with `aws secretsmanager put-secret-value` before the first deploy"
  value       = module.secrets.app_secret_arns
}

output "db_init_run_command" {
  description = "Run once after RDS is available to create the per-service roles and databases"
  value       = module.db_init.run_command
}
