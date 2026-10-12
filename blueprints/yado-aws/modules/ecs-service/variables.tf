variable "name" {
  description = "Service name, e.g. yado-sso"
  type        = string
}

variable "cluster_arn" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "listener_arn" {
  type = string
}

variable "host_header" {
  description = "Hostname routed to this service, e.g. sso.yado-demo.example.com"
  type        = string
  default     = ""
}

variable "listener_priority" {
  type    = number
  default = 100
}

variable "register_with_alb" {
  description = "False for background workers (e.g. a queue worker) that serve no HTTP traffic"
  type        = bool
  default     = true
}

variable "container_name" {
  description = "Container that receives ALB traffic"
  type        = string
  default     = ""
}

variable "container_port" {
  type    = number
  default = 80
}

variable "health_check_path" {
  type    = string
  default = "/health"
}

variable "health_check_grace_period" {
  description = "Seconds before ALB health failures can stop a starting task"
  type        = number
  default     = 60
}

variable "containers" {
  description = "ECS container definitions (camelCase keys, as in the task definition JSON). The module adds logging."
  type        = any
}

variable "volumes" {
  description = "Names of ephemeral volumes shared by the containers"
  type        = list(string)
  default     = []
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "cpu_architecture" {
  type    = string
  default = "X86_64"

  validation {
    condition     = contains(["X86_64", "ARM64"], var.cpu_architecture)
    error_message = "cpu_architecture must be X86_64 or ARM64."
  }
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "execution_role_arn" {
  type = string
}

variable "task_role_arn" {
  type = string
}

variable "extra_security_group_ids" {
  description = "Additional groups to attach, e.g. the db-clients group"
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  type    = number
  default = 365
}
