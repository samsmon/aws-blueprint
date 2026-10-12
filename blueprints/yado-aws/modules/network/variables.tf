variable "name" {
  description = "Name prefix for all network resources"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets across (at least two for RDS)"
  type        = list(string)
}

variable "flow_log_retention_days" {
  description = "Retention of VPC flow logs in CloudWatch"
  type        = number
  default     = 365
}
