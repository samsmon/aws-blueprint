output "https_listener_arn" {
  value = aws_lb_listener.https.arn
}

output "dns_name" {
  value = aws_lb.this.dns_name
}

output "arn_suffix" {
  description = "ALB identifier used as a CloudWatch dimension"
  value       = aws_lb.this.arn_suffix
}

output "name_servers" {
  description = "Delegate the domain to these name servers at your registrar"
  value       = aws_route53_zone.this.name_servers
}
