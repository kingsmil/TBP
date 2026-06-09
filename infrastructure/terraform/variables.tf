variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-west-2"
}

variable "project" {
  description = "Project name — used as a prefix on all resource names"
  type        = string
  default     = "hdb-match"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "backend_image" {
  description = "Full ECR image URI for the FastAPI backend (e.g. 123456789.dkr.ecr.ap-southeast-1.amazonaws.com/hdb-match-backend:latest)"
  type        = string
}

variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.medium"
}

variable "db_password" {
  description = "Master password for the RDS PostgreSQL instance"
  type        = string
  sensitive   = true
}

variable "backend_cpu" {
  description = "ECS task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "backend_memory" {
  description = "ECS task memory in MiB"
  type        = number
  default     = 1024
}

variable "onemap_token" {
  description = "OneMap API token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ai_gateway_api_key" {
  description = "Vercel AI Gateway API key"
  type        = string
  sensitive   = true
  default     = ""
}
