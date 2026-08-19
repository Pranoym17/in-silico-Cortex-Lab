data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_secretsmanager_secret" "runtime" {
  name                    = "${local.name_prefix}/runtime"
  recovery_window_in_days = var.environment == "production" ? 7 : 0
}

locals {
  runtime_secret_values = merge(var.runtime_secrets, {
    DATABASE_URL          = "postgresql+asyncpg://${var.database_username}:${random_password.database.result}@${aws_db_instance.postgres.address}:5432/${var.database_name}"
    REDIS_URL             = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0?ssl_cert_reqs=required"
    AWS_REGION            = var.aws_region
    S3_BUCKET_NAME        = aws_s3_bucket.media.id
    SQS_QUEUE_URL         = aws_sqs_queue.jobs.url
    CELERY_BROKER_URL     = "sqs://"
    CELERY_RESULT_BACKEND = "rediss://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0?ssl_cert_reqs=required"
    CELERY_DEFAULT_QUEUE  = aws_sqs_queue.jobs.name
    CELERY_SQS_REGION     = var.aws_region
    SSE_EVENT_BACKEND     = "redis"
    FRONTEND_ORIGIN       = var.domain_name
    FRONTEND_ORIGINS      = join(",", var.frontend_origins)
    ENVIRONMENT           = var.environment
    DEPLOYMENT_STAGE      = var.environment
    JOB_EXECUTION_MODE    = "celery"
  })
}

resource "aws_secretsmanager_secret_version" "runtime" {
  secret_id     = aws_secretsmanager_secret.runtime.id
  secret_string = jsonencode(local.runtime_secret_values)
}

# ECS retrieves container secrets before the task process starts, using this role.
resource "aws_iam_role_policy" "ecs_execution_runtime_secret" {
  name = "runtime-secret-read"
  role = aws_iam_role.ecs_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = aws_secretsmanager_secret.runtime.arn
    }]
  })
}

data "aws_iam_policy_document" "task" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.runtime.arn]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload", "s3:ListBucket"]
    resources = [aws_s3_bucket.media.arn, "${aws_s3_bucket.media.arn}/*"]
  }
  statement {
    actions   = ["sqs:GetQueueAttributes", "sqs:GetQueueUrl", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:SendMessage"]
    resources = [aws_sqs_queue.jobs.arn, aws_sqs_queue.dead_letter.arn]
  }
}

resource "aws_iam_role" "api_task" {
  name               = "${local.name_prefix}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}
resource "aws_iam_role_policy" "api_task" {
  name   = "runtime-access"
  role   = aws_iam_role.api_task.id
  policy = data.aws_iam_policy_document.task.json
}

resource "aws_iam_role" "worker_task" {
  name               = "${local.name_prefix}-worker-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}
resource "aws_iam_role_policy" "worker_task" {
  name   = "runtime-access"
  role   = aws_iam_role.worker_task.id
  policy = data.aws_iam_policy_document.task.json
}
