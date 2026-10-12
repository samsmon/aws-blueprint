variable "name" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "service_names" {
  description = "Map of short name to ECS service name, one running-task alarm each"
  type        = map(string)
}

variable "target_group_arn_suffixes" {
  description = "Map of short name to ALB target group arn_suffix"
  type        = map(string)
}

variable "alb_arn_suffix" {
  type = string
}

variable "db_instance_id" {
  type = string
}

variable "db_connection_threshold" {
  description = "t4g.micro allows roughly 80 connections, so alert well before the limit"
  type        = number
  default     = 60
}

variable "alarm_email" {
  description = "Email subscribed to the alarm topic. Empty skips the subscription"
  type        = string
  default     = ""
}
