data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# Execution role: used by ECS itself to pull images, write logs and inject
# secrets. It can read only the secrets this stack owns.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "execution" {
  name               = "${var.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    sid       = "ReadStackSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secret_arns
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "read-stack-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

# ---------------------------------------------------------------------------
# Task roles: what the application code itself may do. One per service, and
# empty unless the service needs object storage.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "task" {
  for_each = var.task_roles

  name               = "${var.name}-${each.key}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "task_storage" {
  for_each = { for k, v in var.task_roles : k => v if v.storage_prefix != "" }

  statement {
    sid       = "ListOwnPrefix"
    actions   = ["s3:ListBucket"]
    resources = [var.storage_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${each.value.storage_prefix}/*"]
    }
  }

  statement {
    sid       = "ReadWriteOwnPrefix"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.storage_bucket_arn}/${each.value.storage_prefix}/*"]
  }
}

resource "aws_iam_role_policy" "task_storage" {
  for_each = data.aws_iam_policy_document.task_storage

  name   = "own-storage-prefix"
  role   = aws_iam_role.task[each.key].id
  policy = each.value.json
}
