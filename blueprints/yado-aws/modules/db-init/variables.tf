variable "name" {
  type = string
}

variable "cluster_arn" {
  type = string
}

variable "execution_role_arn" {
  type = string
}

variable "task_role_arn" {
  type = string
}

variable "db_address" {
  type = string
}

variable "db_port" {
  type    = number
  default = 5432
}

variable "master_secret_arn" {
  description = "RDS-managed secret with the master username and password"
  type        = string
}

variable "databases" {
  description = "Role and database to create per service, with the secret holding the role password"
  type = map(object({
    role       = string
    dbname     = string
    secret_arn = string
  }))
}

variable "subnet_ids" {
  type = list(string)
}

variable "security_group_ids" {
  description = "Must include the db-clients group"
  type        = list(string)
}

variable "log_retention_days" {
  type    = number
  default = 365
}
