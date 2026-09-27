variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "vpc_id" {
  description = "Existing VPC to deploy into"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnets (>= 2 AZs) for RDS and ECS tasks"
  type        = list(string)
}

variable "allowed_cidr_blocks" {
  description = "CIDRs allowed to reach the API/dashboard (e.g. corporate VPN)"
  type        = list(string)
  default     = []
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "pipeline_schedule" {
  description = "EventBridge Scheduler expression for the daily incremental pipeline"
  type        = string
  default     = "cron(0 6 * * ? *)"
}
