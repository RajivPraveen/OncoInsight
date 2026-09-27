locals {
  name = "oncoinsight-${var.environment}"
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------- encryption
resource "aws_kms_key" "data" {
  description             = "${local.name} raw data and warehouse encryption"
  deletion_window_in_days = 14
  enable_key_rotation     = true
}

resource "aws_kms_alias" "data" {
  name          = "alias/${local.name}-data"
  target_key_id = aws_kms_key.data.key_id
}

# ---------------------------------------------------------------- S3 raw layer (bronze)
resource "aws_s3_bucket" "raw" {
  bucket = "${local.name}-raw-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    id     = "tier-old-extracts"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
    noncurrent_version_expiration {
      noncurrent_days = 180
    }
  }
}

data "aws_iam_policy_document" "raw_tls_only" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "raw" {
  bucket = aws_s3_bucket.raw.id
  policy = data.aws_iam_policy_document.raw_tls_only.json
}

# ---------------------------------------------------------------- networking
resource "aws_security_group" "app" {
  name        = "${local.name}-app"
  description = "OncoInsight ECS tasks"
  vpc_id      = var.vpc_id

  egress {
    description = "HTTPS to public source APIs (GDC, cBioPortal), AWS APIs and Anthropic"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "Postgres inside the VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.this.cidr_block]
  }
  dynamic "ingress" {
    for_each = length(var.allowed_cidr_blocks) > 0 ? [1] : []
    content {
      description = "API and dashboard from allowed networks"
      from_port   = 8000
      to_port     = 8501
      protocol    = "tcp"
      cidr_blocks = var.allowed_cidr_blocks
    }
  }
}

data "aws_vpc" "this" {
  id = var.vpc_id
}

resource "aws_security_group" "db" {
  name        = "${local.name}-db"
  description = "OncoInsight warehouse"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Postgres from app tasks only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

# ---------------------------------------------------------------- warehouse (RDS PostgreSQL)
resource "aws_db_subnet_group" "this" {
  name       = local.name
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "warehouse" {
  identifier                      = "${local.name}-warehouse"
  engine                          = "postgres"
  engine_version                  = "16"
  instance_class                  = var.db_instance_class
  allocated_storage               = 50
  max_allocated_storage           = 200
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.data.arn
  db_name                         = "oncoinsight"
  username                        = "oncoinsight"
  manage_master_user_password     = true # password generated and rotated in Secrets Manager
  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = [aws_security_group.db.id]
  publicly_accessible             = false
  multi_az                        = var.environment == "prod"
  backup_retention_period         = 7
  deletion_protection             = var.environment == "prod"
  skip_final_snapshot             = var.environment != "prod"
  final_snapshot_identifier       = "${local.name}-final"
  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.data.arn
  enabled_cloudwatch_logs_exports = ["postgresql"]
  auto_minor_version_upgrade      = true
}

# ---------------------------------------------------------------- secrets
resource "aws_secretsmanager_secret" "anthropic" {
  name        = "${local.name}/anthropic-api-key"
  description = "Anthropic API key for the AI analytics assistant (value set out-of-band)"
  kms_key_id  = aws_kms_key.data.arn
}

resource "aws_secretsmanager_secret" "reader" {
  name        = "${local.name}/warehouse-reader"
  description = "Password for the read-only onco_reader role (value set out-of-band)"
  kms_key_id  = aws_kms_key.data.arn
}
