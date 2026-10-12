variable "name" {
  type = string
}

variable "secret_arns" {
  description = "Secrets the execution role may read"
  type        = list(string)
}

variable "task_roles" {
  description = "Task roles to create. storage_prefix is the S3 prefix the service may use; empty means no S3 access"
  type = map(object({
    storage_prefix = string
  }))
}

variable "storage_bucket_arn" {
  type = string
}
