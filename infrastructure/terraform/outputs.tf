output "s3_bucket_name" {
  description = "S3 bucket for HDB data and analytics cache"
  value       = aws_s3_bucket.data.bucket
}

output "ecr_repository_url" {
  description = "ECR repository URL — set this as BACKEND_IMAGE in CI secrets"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS — point your domain CNAME here"
  value       = aws_lb.backend.dns_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (private, only reachable within VPC)"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "ecs_task_role_arn" {
  description = "IAM role ARN attached to ECS tasks — has S3/Bedrock/SageMaker access"
  value       = aws_iam_role.ecs_task.arn
}

output "deploy_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC deploy — set as AWS_DEPLOY_ROLE_ARN secret"
  value       = aws_iam_role.github_deploy.arn
}
