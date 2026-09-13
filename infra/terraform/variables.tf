variable "project_name" {
  description = "Name used as a prefix for AWS resources."
  type        = string
  default     = "ticket-assistant"
}

variable "environment" {
  description = "Environment label."
  type        = string
  default     = "demo"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "Low-cost EC2 instance type for the Streamlit app."
  type        = string
  default     = "t3.micro"
}

variable "allowed_ingress_cidr" {
  description = "CIDR allowed to access Streamlit on port 8501. Use your public IP /32 for safer demos."
  type        = string
  default     = "0.0.0.0/0"
}

variable "github_owner" {
  description = "GitHub user or organization that owns the repository."
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name."
  type        = string
}

variable "github_branch" {
  description = "GitHub branch allowed to deploy."
  type        = string
  default     = "main"
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub OIDC provider. Set false if the AWS account already has one."
  type        = bool
  default     = true
}

variable "common_tags" {
  description = "Extra tags to add to resources."
  type        = map(string)
  default     = {}
}
