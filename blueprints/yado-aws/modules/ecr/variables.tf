variable "name" {
  description = "Repository namespace, e.g. yado -> yado/<repo>"
  type        = string
}

variable "repositories" {
  description = "Repository names to create"
  type        = set(string)
}

variable "keep_images" {
  description = "How many images the lifecycle policy retains per repository"
  type        = number
  default     = 10
}

variable "force_delete" {
  description = "Allow terraform destroy to delete repositories that still contain images"
  type        = bool
  default     = false
}
