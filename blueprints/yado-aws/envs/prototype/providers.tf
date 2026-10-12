locals {
  tags = {
    Project     = "yado"
    Environment = "prototype"
    ManagedBy   = "terraform"
  }
}

# With use_emulator = true the provider talks to a local AWS emulator instead
# of a real account: fake credentials, no account lookup, and every service
# endpoint pointed at the emulator. With the default (false) this is a normal
# AWS provider and uses your standard credential chain.
provider "aws" {
  region = var.region

  default_tags {
    tags = local.tags
  }

  access_key                  = var.use_emulator ? "test" : null
  secret_key                  = var.use_emulator ? "test" : null
  skip_credentials_validation = var.use_emulator
  skip_metadata_api_check     = var.use_emulator
  skip_requesting_account_id  = var.use_emulator
  s3_use_path_style           = var.use_emulator

  dynamic "endpoints" {
    for_each = var.use_emulator ? [1] : []

    content {
      acm            = var.emulator_endpoint
      cloudwatch     = var.emulator_endpoint
      cloudwatchlogs = var.emulator_endpoint
      ec2            = var.emulator_endpoint
      ecr            = var.emulator_endpoint
      ecs            = var.emulator_endpoint
      elbv2          = var.emulator_endpoint
      iam            = var.emulator_endpoint
      rds            = var.emulator_endpoint
      route53        = var.emulator_endpoint
      s3             = var.emulator_endpoint
      secretsmanager = var.emulator_endpoint
      sns            = var.emulator_endpoint
      sts            = var.emulator_endpoint
    }
  }
}
