# Terraform AWS Demo Deployment

This Terraform stack deploys the Ticket Assistant demo with low-cost AWS resources:

- One EC2 instance for the Streamlit container.
- One ECR repository for Docker images.
- Four DynamoDB tables for app data.
- IAM roles for EC2 runtime and GitHub Actions OIDC deployment.
- Security group for Streamlit on port `8501`.

## Steps

1. Copy variables:

```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Edit `terraform.tfvars` and set:

```hcl
allowed_ingress_cidr = "YOUR_PUBLIC_IP/32"
github_owner         = "YOUR_GITHUB_USERNAME_OR_ORG"
github_repo          = "YOUR_REPOSITORY_NAME"
github_branch        = "main"
```

3. Apply infrastructure:

```bash
terraform init
terraform fmt
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

4. From the project root, seed DynamoDB:

```bash
python3 scripts/bootstrap_dynamodb.py --region us-east-1 --prefix ticket-assistant
```

5. Add these Terraform outputs as GitHub repository variables:

```text
AWS_DEPLOY_ROLE_ARN
EC2_INSTANCE_ID
ECR_REPOSITORY_URL
DYNAMODB_TABLE_PREFIX
```

6. Push to `main`. GitHub Actions builds the image, pushes it to ECR, and deploys it to EC2 through SSM.

7. Open:

```bash
terraform output app_url
```

## Clean Up

Destroy resources after the demo:

```bash
terraform destroy
```
