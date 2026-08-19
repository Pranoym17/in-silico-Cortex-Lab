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

# Only licensed, deliberately public template assets live here. User uploads,
# source stimuli, and result artifacts stay in the private media bucket above.
resource "aws_s3_bucket" "public_assets" {
  bucket = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-public-assets"
}

resource "aws_s3_bucket_public_access_block" "public_assets" {
  bucket                  = aws_s3_bucket.public_assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "public_assets" {
  bucket = aws_s3_bucket.public_assets.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_cloudfront_origin_access_control" "public_assets" {
  name                              = "${local.name_prefix}-public-assets"
  description                       = "CloudFront-only access to public template assets"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "public_assets" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "Cortex Lab ${var.environment} public template assets"

  origin {
    domain_name              = aws_s3_bucket.public_assets.bucket_regional_domain_name
    origin_id                = "public-assets"
    origin_access_control_id = aws_cloudfront_origin_access_control.public_assets.id
  }

  default_cache_behavior {
    target_origin_id       = "public-assets"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6" # Managed-CachingOptimized
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate { cloudfront_default_certificate = true }
}

data "aws_iam_policy_document" "public_assets_cloudfront" {
  statement {
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.public_assets.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.public_assets.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "public_assets_cloudfront" {
  bucket = aws_s3_bucket.public_assets.id
  policy = data.aws_iam_policy_document.public_assets_cloudfront.json
}

resource "aws_db_subnet_group" "postgres" {
  name       = "${local.name_prefix}-postgres"
  subnet_ids = values(aws_subnet.data)[*].id
}

resource "aws_db_instance" "postgres" {
  identifier             = "${local.name_prefix}-postgres"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.database_instance_class
  allocated_storage      = 20
  max_allocated_storage  = 100
  storage_encrypted      = true
  db_name                = var.database_name
  username               = var.database_username
  password               = random_password.database.result
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.data.id]
  publicly_accessible    = false
  # Free Tier accounts permit one day of automated RDS backups. Keep manual
  # release snapshots and the restore drill as the recovery safeguard.
  backup_retention_period    = 1
  deletion_protection        = var.environment == "production"
  skip_final_snapshot        = var.environment != "production"
  final_snapshot_identifier  = var.environment == "production" ? "${local.name_prefix}-final" : null
  multi_az                   = var.environment == "production"
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
  num_cache_clusters         = var.environment == "production" ? 2 : 1
  engine                     = "redis"
  engine_version             = "7.1"
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.data.id]
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  automatic_failover_enabled = var.environment == "production"
  snapshot_retention_limit   = var.environment == "production" ? 7 : 1
}
