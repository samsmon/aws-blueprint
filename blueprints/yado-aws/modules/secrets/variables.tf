variable "name" {
  description = "Secret name prefix"
  type        = string
}

variable "databases" {
  description = "One entry per service: the PostgreSQL role and database it owns"
  type = map(object({
    role   = string
    dbname = string
  }))
}

variable "app_secrets" {
  description = "Map of service name to the secret keys it expects (documentation only; values are set out of band)"
  type        = map(list(string))
}

variable "recovery_window_in_days" {
  description = "Days a deleted secret stays recoverable (0 = delete immediately, prototype teardown)"
  type        = number
  default     = 7
}
