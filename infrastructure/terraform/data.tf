resource "random_password" "database" {
  length  = 32
  special = false
}

resource "aws_ecr_repository" "backend" {
  name                 = local.name_prefix
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_s3_bucket" "media" {
  bucket = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-media"
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    id     = "expire-abandoned-multipart-uploads"
    status = "Enabled"
    filter {
      prefix = ""
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_db_subnet_group" "postgres" {
  name       = "${local.name_prefix}-postgres"
  subnet_ids = values(aws_subnet.data)[*].id
}

resource "aws_db_instance" "postgres" {
  identifier                 = "${local.name_prefix}-postgres"
  engine                     = "postgres"
  engine_version             = "16"
  instance_class             = var.database_instance_class
  allocated_storage          = 20
  max_allocated_storage      = 100
  storage_encrypted          = true
  db_name                    = var.database_name
  username                   = var.database_username
  password                   = random_password.database.result
  db_subnet_group_name       = aws_db_subnet_group.postgres.name
  vpc_security_group_ids     = [aws_security_group.data.id]
  publicly_accessible        = false
  backup_retention_period    = var.environment == "production" ? 14 : 7
  deletion_protection        = var.environment == "production"
  skip_final_snapshot        = var.environment != "production"
  final_snapshot_identifier  = var.environment == "production" ? "${local.name_prefix}-final" : null
  multi_az                   = false
  auto_minor_version_upgrade = true
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name_prefix}-redis"
  subnet_ids = values(aws_subnet.data)[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name_prefix}-redis"
  description                = "Cortex Lab ${var.environment} Redis"
  node_type                  = var.redis_node_type
  num_cache_clusters         = 1
  engine                     = "redis"
  engine_version             = "7.1"
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.data.id]
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  automatic_failover_enabled = false
  snapshot_retention_limit   = var.environment == "production" ? 7 : 1
}
