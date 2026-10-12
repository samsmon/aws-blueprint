output "address" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "identifier" {
  value = aws_db_instance.this.identifier
}

output "master_user_secret_arn" {
  description = "Secrets Manager secret holding the RDS-managed master credentials"
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}
