variable "region" {
  description = "AWS region. Jakarta by default; check Fargate and RDS availability before a real deployment"
  type        = string
  default     = "ap-southeast-3"
}

variable "azs" {
  description = "Two availability zones to use. Empty means <region>a and <region>b"
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.azs) == 0 || length(var.azs) >= 2
    error_message = "Provide at least two availability zones, or leave empty."
  }
}

variable "name" {
  description = "Name prefix for every resource"
  type        = string
  default     = "yado"
}

variable "domain_name" {
  description = "Apex domain served by the ALB. Use a domain you control; the live yado.my.id stays on the homelab"
  type        = string
  default     = "yado-demo.example.com"
}

variable "use_emulator" {
  description = "Point the AWS provider at a local emulator instead of a real account"
  type        = bool
  default     = false
}

variable "emulator_endpoint" {
  type    = string
  default = "http://localhost:4566"
}

variable "alarm_email" {
  description = "Email for CloudWatch alarm notifications. Empty skips the subscription"
  type        = string
  default     = ""
}

variable "yado_image_tag" {
  description = "Tag of the yado launcher image in ECR. Tags are immutable, so use versions, not latest"
  type        = string
  default     = "0.1.0"
}

variable "sso_app_image_tag" {
  type    = string
  default = "0.1.0"
}

variable "sso_nginx_image_tag" {
  type    = string
  default = "0.1.0"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_multi_az" {
  type    = bool
  default = false
}

variable "deletion_protection" {
  description = "Protect the ALB and RDS from deletion. Off in the prototype so terraform destroy works"
  type        = bool
  default     = false
}

variable "secret_recovery_window_days" {
  description = "0 deletes secrets immediately on destroy (prototype); use 7 or more for real"
  type        = number
  default     = 0
}

variable "ephemeral" {
  description = "Prototype teardown mode: lets destroy remove non-empty ECR repositories and the storage bucket"
  type        = bool
  default     = true
}
