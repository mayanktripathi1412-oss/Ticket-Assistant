output "app_url" {
  description = "Streamlit demo URL."
  value       = "http://${aws_instance.app.public_ip}:8501"
}

output "ec2_instance_id" {
  description = "EC2 instance ID used by GitHub Actions SSM deployment."
  value       = aws_instance.app.id
}

output "ecr_repository_url" {
  description = "ECR repository URL used by GitHub Actions."
  value       = aws_ecr_repository.app.repository_url
}

output "github_deploy_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC."
  value       = aws_iam_role.github_deploy.arn
}

output "dynamodb_table_prefix" {
  description = "Prefix used by the app to find DynamoDB tables."
  value       = var.project_name
}

output "github_actions_variables" {
  description = "Values to add as GitHub repository variables."
  value = {
    AWS_DEPLOY_ROLE_ARN   = aws_iam_role.github_deploy.arn
    EC2_INSTANCE_ID       = aws_instance.app.id
    ECR_REPOSITORY_URL    = aws_ecr_repository.app.repository_url
    DYNAMODB_TABLE_PREFIX = var.project_name
  }
}
