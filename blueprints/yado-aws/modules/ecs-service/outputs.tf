output "service_name" {
  value = aws_ecs_service.this.name
}

output "task_security_group_id" {
  value = aws_security_group.task.id
}

output "target_group_arn_suffix" {
  description = "Target group identifier used as a CloudWatch dimension (null for workers)"
  value       = var.register_with_alb ? aws_lb_target_group.this[0].arn_suffix : null
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.this.name
}
