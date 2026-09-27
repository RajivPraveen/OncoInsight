# `infra/terraform/`: AWS infrastructure as code

[← back to project README](../../README.md)

Production target for the platform. Passes `terraform validate` and `fmt` (checked in CI); **not yet applied** to an
AWS account.

| File | Resources |
|---|---|
| `main.tf` | KMS key (rotation on); **S3 raw bucket**: versioned, SSE-KMS, public access blocked, TLS-only bucket policy, lifecycle tiering to Glacier IR after 90 days; security groups (tasks egress 443/5432, DB ingress from tasks only); **RDS PostgreSQL 16**: private, encrypted, master password managed and rotated by Secrets Manager, backups, Performance Insights, multi-AZ and deletion protection in prod; Secrets Manager entries for the LLM key and reader password |
| `compute.tf` | ECR (immutable tags, scan on push, KMS); CloudWatch logs; ECS cluster with Container Insights; least-privilege IAM (task role limited to the raw bucket); Fargate task definitions (ARM64) for pipeline, API and dashboard with secrets injected; ECS services with circuit-breaker rollback; **EventBridge Scheduler** running the daily pipeline task with retries |
| `variables.tf` / `outputs.tf` / `versions.tf` | Inputs (existing VPC, private subnets, allowed CIDRs, instance class, schedule), outputs (bucket, DB endpoint, secret ARN, ECR URL, cluster), provider pinning, default tags and a commented remote-state backend |
| `terraform.tfvars.example` | Example inputs |

## Usage

```bash
cp terraform.tfvars.example terraform.tfvars
```

```bash
terraform init && terraform plan
```
