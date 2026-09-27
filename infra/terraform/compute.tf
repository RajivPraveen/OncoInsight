# ---------------------------------------------------------------- container registry
resource "aws_ecr_repository" "app" {
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.data.arn
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.name}"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "this" {
  name = local.name
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ---------------------------------------------------------------- IAM
data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    actions = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.anthropic.arn, aws_secretsmanager_secret.reader.arn,
    aws_db_instance.warehouse.master_user_secret[0].secret_arn]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.data.arn]
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

data "aws_iam_policy_document" "task" {
  statement {
    sid       = "RawLayerReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*"]
  }
  statement {
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [aws_kms_key.data.arn]
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "raw-layer"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}

# ---------------------------------------------------------------- task definitions
locals {
  image = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  common_env = [
    { name = "ONCO_ENV", value = var.environment },
    { name = "ONCO_STORAGE_BACKEND", value = "s3" },
    { name = "ONCO_S3_BUCKET", value = aws_s3_bucket.raw.bucket },
    { name = "AWS_REGION", value = var.region },
    { name = "WAREHOUSE_HOST", value = aws_db_instance.warehouse.address },
    { name = "WAREHOUSE_PORT", value = "5432" },
    { name = "WAREHOUSE_DB", value = "oncoinsight" },
    { name = "WAREHOUSE_USER", value = "oncoinsight" },
  ]
  common_secrets = [
    { name = "WAREHOUSE_PASSWORD", valueFrom = "${aws_db_instance.warehouse.master_user_secret[0].secret_arn}:password::" },
    { name = "WAREHOUSE_READER_PASSWORD", valueFrom = aws_secretsmanager_secret.reader.arn },
    { name = "ANTHROPIC_API_KEY", valueFrom = aws_secretsmanager_secret.anthropic.arn },
  ]
  services = {
    pipeline  = { command = ["python", "-m", "oncoinsight.pipeline", "all", "--mode", "incremental"], port = null, cpu = 1024, memory = 4096 }
    api       = { command = ["uvicorn", "oncoinsight.api.main:app", "--host", "0.0.0.0", "--port", "8000"], port = 8000, cpu = 512, memory = 1024 }
    dashboard = { command = ["streamlit", "run", "app/Home.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true"], port = 8501, cpu = 512, memory = 2048 }
  }
}

resource "aws_ecs_task_definition" "this" {
  for_each                 = local.services
  family                   = "${local.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }
  container_definitions = jsonencode([{
    name         = each.key
    image        = local.image
    command      = each.value.command
    essential    = true
    environment  = local.common_env
    secrets      = local.common_secrets
    portMappings = each.value.port == null ? [] : [{ containerPort = each.value.port, protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = each.key
      }
    }
  }])
}

resource "aws_ecs_service" "web" {
  for_each        = { for k, v in local.services : k => v if v.port != null }
  name            = each.key
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this[each.key].arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}

# ---------------------------------------------------------------- scheduled pipeline (EventBridge Scheduler -> ECS RunTask)
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${local.name}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["ecs:RunTask"]
    resources = [aws_ecs_task_definition.this["pipeline"].arn]
  }
  statement {
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.execution.arn, aws_iam_role.task.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "run-pipeline"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "pipeline" {
  name                         = "${local.name}-daily-pipeline"
  schedule_expression          = var.pipeline_schedule
  schedule_expression_timezone = "UTC"
  flexible_time_window {
    mode = "OFF"
  }
  target {
    arn      = aws_ecs_cluster.this.arn
    role_arn = aws_iam_role.scheduler.arn
    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.this["pipeline"].arn
      launch_type         = "FARGATE"
      network_configuration {
        subnets          = var.private_subnet_ids
        security_groups  = [aws_security_group.app.id]
        assign_public_ip = false
      }
    }
    retry_policy {
      maximum_retry_attempts = 2
    }
  }
}
