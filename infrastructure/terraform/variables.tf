variable "environment" {
  type        = string
  description = "Deployment environment. Use staging or production."

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "aws_region" {
  type        = string
  description = "All Cortex Lab runtime resources live in this AWS region."
  default     = "us-east-2"
}

variable "domain_name" {
  type        = string
  description = "The frontend domain for this environment."
}

variable "api_domain_name" {
  type        = string
  description = "The API domain for this environment."
}

variable "frontend_origins" {
  type        = list(string)
  description = "Exact browser origins allowed to call the API."
}

variable "database_name" {
  type    = string
  default = "cortexlab"
}

variable "database_username" {
  type    = string
  default = "cortexlab"
}

variable "database_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "api_image" {
  type        = string
  description = "Immutable ECR image URI for FastAPI."
}

variable "worker_image" {
  type        = string
  description = "Immutable ECR image URI for Celery worker."
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "worker_desired_count" {
  type    = number
  default = 0
}

variable "worker_max_count" {
  type    = number
  default = 1
}

variable "api_task_cpu" {
  type        = number
  default     = 256
  description = "Fargate CPU units for the always-on API."
}

variable "api_task_memory" {
  type        = number
  default     = 512
  description = "Fargate MiB for the always-on API."
}

variable "worker_task_cpu" {
  type        = number
  default     = 512
  description = "Fargate CPU units for the queue-driven worker."
}

variable "worker_task_memory" {
  type        = number
  default     = 1024
  description = "Fargate MiB for the queue-driven worker."
}

variable "alarm_email" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional email address that receives CloudWatch alarm notifications."
}

variable "runtime_secrets" {
  type        = map(string)
  sensitive   = true
  description = "Non-AWS backend secrets, such as Supabase JWT and Modal credentials."
}
