variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Private subnets in at least two availability zones"
  type        = list(string)
}

variable "client_security_group_id" {
  description = "Security group whose members may connect on 5432"
  type        = string
}

variable "engine_version" {
  type    = string
  default = "16"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "max_allocated_storage" {
  description = "Storage autoscaling ceiling in GiB"
  type        = number
  default     = 50
}

variable "multi_az" {
  description = "Standby replica in a second AZ. Off in the prototype to save cost; see docs/cost.md"
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  type    = number
  default = 7
}

variable "deletion_protection" {
  type    = bool
  default = false
}
