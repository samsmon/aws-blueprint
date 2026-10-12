variable "bucket_name" {
  description = "Globally unique bucket name"
  type        = string
}

variable "force_destroy" {
  description = "Allow terraform destroy to delete a non-empty bucket (prototype only)"
  type        = bool
  default     = false
}
