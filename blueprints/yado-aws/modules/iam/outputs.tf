output "execution_role_arn" {
  value = aws_iam_role.execution.arn
}

output "task_role_arns" {
  value = { for k, r in aws_iam_role.task : k => r.arn }
}
