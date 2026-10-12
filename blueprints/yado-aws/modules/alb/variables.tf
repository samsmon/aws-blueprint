variable "name" {
  type = string
}

variable "domain_name" {
  description = "Apex domain, e.g. yado-demo.example.com. A wildcard certificate is issued for it"
  type        = string
}

variable "hostnames" {
  description = "Fully qualified hostnames that get an alias record to the ALB"
  type        = list(string)
}

variable "subnet_ids" {
  description = "Public subnets in at least two availability zones"
  type        = list(string)
}

variable "security_group_id" {
  type = string
}

variable "deletion_protection" {
  type    = bool
  default = false
}
