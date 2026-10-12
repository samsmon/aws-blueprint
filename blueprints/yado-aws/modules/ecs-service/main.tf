data "aws_region" "current" {}

locals {
  # Every container logs to this service's log group; callers may override any key.
  container_definitions = [
    for c in var.containers : merge({
      essential = true
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = c.name
        }
      }
    }, c)
  ]
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name}"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# Network: tasks accept traffic from the ALB only
# ---------------------------------------------------------------------------

resource "aws_security_group" "task" {
  name        = "${var.name}-task"
  description = "${var.name} tasks: ingress from the ALB only"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-task" }
}

resource "aws_vpc_security_group_ingress_rule" "from_alb" {
  count = var.register_with_alb ? 1 : 0

  security_group_id            = aws_security_group.task.id
  description                  = "App traffic from the ALB"
  referenced_security_group_id = var.alb_security_group_id
  from_port                    = var.container_port
  to_port                      = var.container_port
  ip_protocol                  = "tcp"
}

# Tasks run in public subnets without NAT, so they need outbound access to pull
# images from ECR and reach AWS APIs.
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.task.id
  description       = "Outbound: ECR, Secrets Manager, CloudWatch, S3, RDS"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# ---------------------------------------------------------------------------
# Load balancer wiring
# ---------------------------------------------------------------------------

resource "aws_lb_target_group" "this" {
  count = var.register_with_alb ? 1 : 0

  name                 = "${var.name}-tg"
  vpc_id               = var.vpc_id
  port                 = var.container_port
  protocol             = "HTTP"
  target_type          = "ip"
  deregistration_delay = 30

  health_check {
    path                = var.health_check_path
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener_rule" "this" {
  count = var.register_with_alb ? 1 : 0

  listener_arn = var.listener_arn
  priority     = var.listener_priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[0].arn
  }

  condition {
    host_header {
      values = [var.host_header]
    }
  }
}

# ---------------------------------------------------------------------------
# Task definition and service
# ---------------------------------------------------------------------------

resource "aws_ecs_task_definition" "this" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  # Ephemeral volumes shared between containers of the same task
  # (the homelab's sso_public volume between php-fpm and nginx).
  dynamic "volume" {
    for_each = toset(var.volumes)

    content {
      name = volume.value
    }
  }

  container_definitions = jsonencode(local.container_definitions)
}

resource "aws_ecs_service" "this" {
  name            = var.name
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Roll back automatically if a new deployment never becomes healthy.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = var.register_with_alb ? var.health_check_grace_period : null
  enable_execute_command             = false

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = concat([aws_security_group.task.id], var.extra_security_group_ids)
    assign_public_ip = true
  }

  dynamic "load_balancer" {
    for_each = var.register_with_alb ? [1] : []

    content {
      target_group_arn = aws_lb_target_group.this[0].arn
      container_name   = var.container_name
      container_port   = var.container_port
    }
  }

  depends_on = [aws_lb_listener_rule.this]
}
