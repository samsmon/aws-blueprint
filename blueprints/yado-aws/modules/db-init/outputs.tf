output "task_definition_arn" {
  value = aws_ecs_task_definition.this.arn
}

output "run_command" {
  description = "AWS CLI command that runs the init task once"
  value = join(" ", [
    "aws ecs run-task",
    "--cluster ${var.cluster_arn}",
    "--launch-type FARGATE",
    "--task-definition ${aws_ecs_task_definition.this.family}",
    "--network-configuration 'awsvpcConfiguration={subnets=[${join(",", var.subnet_ids)}],securityGroups=[${join(",", var.security_group_ids)}],assignPublicIp=ENABLED}'",
  ])
}
