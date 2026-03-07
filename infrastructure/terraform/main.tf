# RigaCap AWS Infrastructure - Terraform
#
# This creates:
# - S3 bucket for frontend (static website)
# - CloudFront distribution (CDN) with SSL
# - ACM Certificate for rigacap.com
# - Lambda function (backend API)
# - API Gateway (REST API) with custom domain
# - RDS PostgreSQL (database)
# - EventBridge (scheduled scans)
# - Route53 DNS (optional)

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.0"
}

provider "aws" {
  region = var.aws_region
}

# ACM certificates for CloudFront MUST be in us-east-1
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# ============================================================================
# Variables
# ============================================================================

variable "aws_region" {
  default = "us-east-1"
}

variable "project_name" {
  default = "rigacap"
}

variable "environment" {
  default = "prod"
}

variable "domain_name" {
  description = "Primary domain name"
  default     = "rigacap.com"
}

variable "use_route53" {
  description = "Whether to create Route53 hosted zone (set false if using external DNS)"
  default     = true
}

variable "db_password" {
  description = "RDS database password"
  sensitive   = true
}

variable "jwt_secret_key" {
  description = "Secret key for JWT tokens"
  sensitive   = true
}

variable "stripe_secret_key" {
  description = "Stripe secret key"
  sensitive   = true
  default     = ""
}

variable "stripe_webhook_secret" {
  description = "Stripe webhook signing secret"
  sensitive   = true
  default     = ""
}

variable "stripe_price_id" {
  description = "Stripe price ID for monthly subscription"
  default     = ""
}

variable "stripe_price_id_annual" {
  description = "Stripe price ID for annual subscription"
  default     = ""
}

variable "turnstile_secret_key" {
  description = "Cloudflare Turnstile secret key"
  sensitive   = true
  default     = ""
}

variable "smtp_user" {
  description = "Gmail address for SMTP (e.g., your-email@gmail.com)"
  default     = ""
}

variable "smtp_pass" {
  description = "Gmail App Password for SMTP (16 characters, no spaces)"
  sensitive   = true
  default     = ""
}

variable "admin_emails" {
  description = "Comma-separated list of admin email addresses for internal notifications"
  default     = "erik@rigacap.com"
}

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude AI content generation"
  sensitive   = true
  default     = ""
}

variable "apple_client_id" {
  description = "Apple Sign In client/service ID"
  default     = ""
}

variable "twitter_api_key" {
  description = "Twitter API key (consumer key)"
  sensitive   = true
  default     = ""
}

variable "twitter_api_secret" {
  description = "Twitter API secret (consumer secret)"
  sensitive   = true
  default     = ""
}

variable "twitter_access_token" {
  description = "Twitter OAuth access token"
  sensitive   = true
  default     = ""
}

variable "twitter_access_token_secret" {
  description = "Twitter OAuth access token secret"
  sensitive   = true
  default     = ""
}

variable "instagram_access_token" {
  description = "Instagram Graph API access token"
  sensitive   = true
  default     = ""
}

variable "instagram_business_account_id" {
  description = "Instagram Business Account ID"
  default     = ""
}

variable "threads_access_token" {
  description = "Threads API long-lived access token (auto-refreshed weekly)"
  sensitive   = true
  default     = ""
}

variable "threads_user_id" {
  description = "Threads User ID"
  default     = ""
}

variable "alpaca_api_key" {
  description = "Alpaca Markets API key"
  sensitive   = true
  default     = ""
}

variable "alpaca_secret_key" {
  description = "Alpaca Markets secret key"
  sensitive   = true
  default     = ""
}

variable "lambda_image_tag" {
  description = "Docker image tag for Lambda container"
  default     = "latest"
}

data "aws_caller_identity" "current" {}

locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ============================================================================
# ACM Certificate (FREE SSL from AWS)
# ============================================================================

# Certificate for rigacap.com and *.rigacap.com
resource "aws_acm_certificate" "main" {
  provider                  = aws.us_east_1 # Must be us-east-1 for CloudFront
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.prefix}-cert"
  }
}

# Route53 Hosted Zone (optional - skip if using external DNS)
resource "aws_route53_zone" "main" {
  count = var.use_route53 ? 1 : 0
  name  = var.domain_name

  tags = {
    Name = "${local.prefix}-zone"
  }
}

# DNS validation records (only if using Route53)
resource "aws_route53_record" "cert_validation" {
  for_each = var.use_route53 ? {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.main[0].zone_id
}

# Wait for certificate validation
resource "aws_acm_certificate_validation" "main" {
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = var.use_route53 ? [for record in aws_route53_record.cert_validation : record.fqdn] : []

  # If not using Route53, you'll need to manually add DNS records
  # and this will wait until they're validated
}

# ============================================================================
# Route53 DNS Records (only if using Route53)
# ============================================================================

# A record for rigacap.com -> CloudFront
resource "aws_route53_record" "frontend" {
  count   = var.use_route53 ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# A record for www.rigacap.com -> CloudFront
resource "aws_route53_record" "frontend_www" {
  count   = var.use_route53 ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "www.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# A record for api.rigacap.com -> API Gateway
resource "aws_route53_record" "api" {
  count   = var.use_route53 ? 1 : 0
  zone_id = aws_route53_zone.main[0].zone_id
  name    = "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
    zone_id                = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }
}

# ============================================================================
# S3 Bucket - Frontend Static Site
# ============================================================================

resource "aws_s3_bucket" "frontend" {
  bucket = "${local.prefix}-frontend-149218244179"
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

# ============================================================================
# CloudFront Distribution (with SSL)
# ============================================================================

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  # Custom domain names
  aliases = [var.domain_name, "www.${var.domain_name}"]

  origin {
    domain_name = aws_s3_bucket_website_configuration.frontend.website_endpoint
    origin_id   = "S3-${aws_s3_bucket.frontend.id}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-${aws_s3_bucket.frontend.id}"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  # SPA routing - return index.html for 404s
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # SSL Certificate from ACM
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.main.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "${local.prefix}-frontend"
  }

  depends_on = [aws_acm_certificate_validation.main]
}

# ============================================================================
# Lambda Function - Backend API
# ============================================================================

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${local.prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# S3 bucket for Lambda code (kept for backwards compatibility)
resource "aws_s3_bucket" "lambda_code" {
  bucket = "${local.prefix}-lambda-deploy-149218244179"
}

# ============================================================================
# ECR Repository - Container Image for Lambda (10GB limit vs 250MB for zip)
# ============================================================================

resource "aws_ecr_repository" "api" {
  name                 = "${local.prefix}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${local.prefix}-api"
  }
}

# Lifecycle policy to keep only last 5 images
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# S3 bucket for persistent price data (parquet files) — NOT publicly accessible
resource "aws_s3_bucket" "price_data" {
  bucket = "${local.prefix}-price-data-149218244179"

  tags = {
    Name = "${local.prefix}-price-data"
  }
}

resource "aws_s3_bucket_public_access_block" "price_data" {
  bucket = aws_s3_bucket.price_data.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# IAM policy for Lambda to access price data bucket
resource "aws_iam_role_policy" "lambda_s3_price_data" {
  name = "${local.prefix}-lambda-s3-price-data"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.price_data.arn,
          "${aws_s3_bucket.price_data.arn}/*"
        ]
      }
    ]
  })
}

# CloudWatch read access for admin health dashboard
resource "aws_iam_role_policy" "lambda_cloudwatch_read" {
  name = "${local.prefix}-lambda-cw-read"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:DescribeAlarms",
          "cloudwatch:GetMetricStatistics",
          "logs:FilterLogEvents"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda self-configuration — allows token auto-refresh to persist env vars
resource "aws_iam_role_policy" "lambda_self_config" {
  name = "${local.prefix}-lambda-self-config"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:GetFunctionConfiguration",
          "lambda:UpdateFunctionConfiguration"
        ]
        Resource = [
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.prefix}-api",
          "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.prefix}-worker"
        ]
      }
    ]
  })
}

# Lambda invoke — allows API and Worker to invoke the Worker (for self-chaining)
resource "aws_iam_role_policy" "lambda_invoke_worker" {
  name = "${local.prefix}-lambda-invoke-worker"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.worker.arn
      }
    ]
  })
}

# Shared env vars for both API and Worker Lambdas (same image, different roles)
locals {
  lambda_env_vars = {
    DATABASE_URL                  = "postgresql://${aws_db_instance.main.username}:${var.db_password}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
    ENVIRONMENT                   = var.environment
    FRONTEND_URL                  = "https://${var.domain_name}"
    JWT_SECRET_KEY                = var.jwt_secret_key
    STRIPE_SECRET_KEY             = var.stripe_secret_key
    STRIPE_WEBHOOK_SECRET         = var.stripe_webhook_secret
    STRIPE_PRICE_ID               = var.stripe_price_id
    STRIPE_PRICE_ID_ANNUAL        = var.stripe_price_id_annual
    TURNSTILE_SECRET_KEY          = var.turnstile_secret_key
    PRICE_DATA_BUCKET             = aws_s3_bucket.price_data.bucket
    SMTP_HOST                     = "smtp.gmail.com"
    SMTP_PORT                     = "587"
    SMTP_USER                     = var.smtp_user
    SMTP_PASS                     = var.smtp_pass
    FROM_EMAIL                    = "daily@rigacap.com"
    FROM_NAME                     = "RigaCap Signals"
    ADMIN_EMAILS                  = var.admin_emails
    STEP_FUNCTIONS_ARN            = "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${local.prefix}-walk-forward"
    ANTHROPIC_API_KEY             = var.anthropic_api_key
    APPLE_CLIENT_ID               = var.apple_client_id
    TWITTER_API_KEY               = var.twitter_api_key
    TWITTER_API_SECRET            = var.twitter_api_secret
    TWITTER_ACCESS_TOKEN          = var.twitter_access_token
    TWITTER_ACCESS_TOKEN_SECRET   = var.twitter_access_token_secret
    INSTAGRAM_ACCESS_TOKEN        = var.instagram_access_token
    INSTAGRAM_BUSINESS_ACCOUNT_ID = var.instagram_business_account_id
    THREADS_ACCESS_TOKEN          = var.threads_access_token
    THREADS_USER_ID               = var.threads_user_id
    ALPACA_API_KEY                = var.alpaca_api_key
    ALPACA_SECRET_KEY             = var.alpaca_secret_key
    WORKER_FUNCTION_NAME          = "${local.prefix}-worker"
  }
}

# Lambda Function — API (HTTP requests only, no pickle, fast cold starts)
resource "aws_lambda_function" "api" {
  function_name = "${local.prefix}-api"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.lambda_image_tag}"
  timeout       = 30   # API Gateway limit is 29s
  memory_size   = 1024 # No pickle needed — dashboard reads from S3 JSON cache

  environment {
    variables = merge(local.lambda_env_vars, {
      LAMBDA_ROLE = "api"
    })
  }

  tags = {
    Name = "${local.prefix}-api"
  }

  depends_on = [aws_ecr_repository.api]
}

# Lambda Function — Worker (background jobs: scans, WF simulations, emails, social)
resource "aws_lambda_function" "worker" {
  function_name = "${local.prefix}-worker"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.lambda_image_tag}"
  timeout       = 900  # 15 minutes (max for Lambda)
  memory_size   = 3008 # AWS account limit

  ephemeral_storage {
    size = 1024 # MB — needed for streaming pickle export (344 MB compressed)
  }

  environment {
    variables = merge(local.lambda_env_vars, {
      LAMBDA_ROLE = "worker"
    })
  }

  tags = {
    Name = "${local.prefix}-worker"
  }

  depends_on = [aws_ecr_repository.api]
}

# ============================================================================
# API Gateway
# ============================================================================

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = [
      "https://${var.domain_name}",
      "https://www.${var.domain_name}",
      "http://localhost:3000",
      "http://localhost:5173",
      "http://localhost:5176"
    ]
    allow_methods     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers     = ["*"]
    allow_credentials = true
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id             = aws_apigatewayv2_api.main.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.api.invoke_arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# Custom domain for API (api.rigacap.com)
resource "aws_apigatewayv2_domain_name" "api" {
  domain_name = "api.${var.domain_name}"

  domain_name_configuration {
    certificate_arn = aws_acm_certificate_validation.main.certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2"
  }

  depends_on = [aws_acm_certificate_validation.main]
}

# Map custom domain to API Gateway stage
resource "aws_apigatewayv2_api_mapping" "api" {
  api_id      = aws_apigatewayv2_api.main.id
  domain_name = aws_apigatewayv2_domain_name.api.id
  stage       = aws_apigatewayv2_stage.default.id
}

# ============================================================================
# RDS PostgreSQL
# ============================================================================

# Security group for RDS - allows Lambda access
resource "aws_security_group" "rds" {
  name        = "${local.prefix}-rds-sg-v2"
  description = "Security group for RDS PostgreSQL"

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # TODO: Restrict to Lambda in production
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.prefix}-rds-sg"
  }
}

resource "aws_db_instance" "main" {
  identifier             = "${local.prefix}-db-v2"
  engine                 = "postgres"
  engine_version         = "15"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_type           = "gp2"
  db_name                = "rigacap"
  username               = "rigacap"
  password               = var.db_password
  publicly_accessible    = true
  skip_final_snapshot    = true
  deletion_protection    = true # Prevent accidental deletion
  vpc_security_group_ids = [aws_security_group.rds.id]

  tags = {
    Name = "${local.prefix}-db"
  }
}

# ============================================================================
# EventBridge - Scheduled Scanner
# ============================================================================

resource "aws_cloudwatch_event_rule" "scanner" {
  name                = "${local.prefix}-scanner"
  description         = "Run market scan at 4:20 PM ET on weekdays (20 min after close for Alpaca bar settlement)"
  schedule_expression = "cron(20 21 ? * MON-FRI *)" # 4:20 PM ET = 9:20 PM UTC
}

resource "aws_cloudwatch_event_target" "scanner" {
  rule      = aws_cloudwatch_event_rule.scanner.name
  target_id = "lambda-worker"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ daily_scan = true })
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scanner.arn
}

# ============================================================================
# EventBridge - Lambda Warmer (keeps Lambda warm to avoid cold starts)
# ============================================================================

resource "aws_cloudwatch_event_rule" "warmer" {
  name                = "${local.prefix}-warmer"
  description         = "Keep Lambda warm by pinging it every 5 minutes"
  schedule_expression = "rate(5 minutes)"
}

resource "aws_cloudwatch_event_target" "warmer" {
  rule      = aws_cloudwatch_event_rule.warmer.name
  target_id = "lambda-warmer"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ warmer = true })
}

resource "aws_lambda_permission" "warmer" {
  statement_id  = "AllowWarmerEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.warmer.arn
}

# ============================================================================
# EventBridge - Daily Email Digest (6 PM ET = 23:00 UTC, Mon-Fri)
# ============================================================================

resource "aws_cloudwatch_event_rule" "daily_emails" {
  name                = "${local.prefix}-daily-emails"
  description         = "Send daily email digest at 6 PM ET weekdays"
  schedule_expression = "cron(0 23 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "daily_emails" {
  rule      = aws_cloudwatch_event_rule.daily_emails.name
  target_id = "lambda-daily-emails"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ daily_emails = true })
}

resource "aws_lambda_permission" "daily_emails" {
  statement_id  = "AllowDailyEmailsEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_emails.arn
}

# ============================================================================
# EventBridge - Double Signal Alerts (5 PM ET = 22:00 UTC, Mon-Fri)
# ============================================================================

resource "aws_cloudwatch_event_rule" "double_signals" {
  name                = "${local.prefix}-double-signals"
  description         = "Check for double signal alerts at 5 PM ET weekdays"
  schedule_expression = "cron(0 22 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "double_signals" {
  rule      = aws_cloudwatch_event_rule.double_signals.name
  target_id = "lambda-double-signals"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ double_signal_alerts = true })
}

resource "aws_lambda_permission" "double_signals" {
  statement_id  = "AllowDoubleSignalsEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.double_signals.arn
}

# ============================================================================
# EventBridge - Ticker Health Check (7 AM ET = 12:00 UTC, Mon-Fri)
# ============================================================================

resource "aws_cloudwatch_event_rule" "ticker_health" {
  name                = "${local.prefix}-ticker-health"
  description         = "Run ticker health check at 7 AM ET weekdays"
  schedule_expression = "cron(0 12 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "ticker_health" {
  rule      = aws_cloudwatch_event_rule.ticker_health.name
  target_id = "lambda-ticker-health"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ ticker_health_check = true })
}

resource "aws_lambda_permission" "ticker_health" {
  statement_id  = "AllowTickerHealthEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ticker_health.arn
}

# ============================================================================
# EventBridge - Nightly Walk-Forward + Social Posts (8 PM ET = 01:00 UTC next day, Tue-Sat)
# ============================================================================

resource "aws_cloudwatch_event_rule" "nightly_wf" {
  name                = "${local.prefix}-nightly-wf"
  description         = "Run nightly walk-forward and generate social posts"
  schedule_expression = "cron(0 1 ? * TUE-SAT *)"
}

resource "aws_cloudwatch_event_target" "nightly_wf" {
  rule      = aws_cloudwatch_event_rule.nightly_wf.name
  target_id = "lambda-nightly-wf"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ nightly_wf_job = {} })
}

resource "aws_lambda_permission" "nightly_wf" {
  statement_id  = "AllowNightlyWfEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.nightly_wf.arn
}

# ============================================================================
# EventBridge - Intraday Position Monitor (every 5 min, 9 AM-3 PM ET = 14-20 UTC, Mon-Fri)
# ============================================================================

resource "aws_cloudwatch_event_rule" "intraday_monitor" {
  name                = "${local.prefix}-intraday-monitor"
  description         = "Monitor positions intraday during market hours"
  schedule_expression = "cron(0/5 14-20 ? * MON-FRI *)"
}

resource "aws_cloudwatch_event_target" "intraday_monitor" {
  rule      = aws_cloudwatch_event_rule.intraday_monitor.name
  target_id = "lambda-intraday-monitor"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ intraday_monitor = true })
}

resource "aws_lambda_permission" "intraday_monitor" {
  statement_id  = "AllowIntradayMonitorEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.intraday_monitor.arn
}

# ============================================================================
# EventBridge - Publish Scheduled Posts (every 15 min, all days)
# ============================================================================

resource "aws_cloudwatch_event_rule" "publish_posts" {
  name                = "${local.prefix}-publish-posts"
  description         = "Publish scheduled social media posts every 15 minutes"
  schedule_expression = "cron(0/15 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "publish_posts" {
  rule      = aws_cloudwatch_event_rule.publish_posts.name
  target_id = "lambda-publish-posts"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ publish_scheduled_posts = true })
}

resource "aws_lambda_permission" "publish_posts" {
  statement_id  = "AllowPublishPostsEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.publish_posts.arn
}

# ============================================================================
# EventBridge - Post Notifications (every hour, all days)
# ============================================================================

resource "aws_cloudwatch_event_rule" "post_notifications" {
  name                = "${local.prefix}-post-notifications"
  description         = "Send T-24h and T-1h post notifications every hour"
  schedule_expression = "cron(0 * * * ? *)"
}

resource "aws_cloudwatch_event_target" "post_notifications" {
  rule      = aws_cloudwatch_event_rule.post_notifications.name
  target_id = "lambda-post-notifications"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ post_notifications = true })
}

resource "aws_lambda_permission" "post_notifications" {
  statement_id  = "AllowPostNotificationsEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.post_notifications.arn
}

# ============================================================================
# EventBridge - Strategy Auto-Analysis (Fri 6:30 PM ET = 23:30 UTC)
# ============================================================================

resource "aws_cloudwatch_event_rule" "strategy_analysis" {
  name                = "${local.prefix}-strategy-analysis"
  description         = "Run weekly strategy auto-analysis Friday 6:30 PM ET"
  schedule_expression = "cron(30 23 ? * FRI *)"
}

resource "aws_cloudwatch_event_target" "strategy_analysis" {
  rule      = aws_cloudwatch_event_rule.strategy_analysis.name
  target_id = "lambda-strategy-analysis"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ strategy_auto_analysis = true })
}

resource "aws_lambda_permission" "strategy_analysis" {
  statement_id  = "AllowStrategyAnalysisEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.strategy_analysis.arn
}

# ============================================================================
# EventBridge - Onboarding Drip Emails (10 AM ET = 15:00 UTC, daily)
# ============================================================================

resource "aws_cloudwatch_event_rule" "onboarding_drip" {
  name                = "${local.prefix}-onboarding-drip"
  description         = "Send onboarding drip emails at 10 AM ET daily"
  schedule_expression = "cron(0 15 * * ? *)"
}

resource "aws_cloudwatch_event_target" "onboarding_drip" {
  rule      = aws_cloudwatch_event_rule.onboarding_drip.name
  target_id = "lambda-onboarding-drip"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ onboarding_drip = true })
}

resource "aws_lambda_permission" "onboarding_drip" {
  statement_id  = "AllowOnboardingDripEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.onboarding_drip.arn
}

# Weekly pickle rebuild — Saturday 8 PM ET (Sunday 01:00 UTC)
# Catches new symbols added to universe, rebuilds missing symbol cache
resource "aws_cloudwatch_event_rule" "pickle_rebuild" {
  name                = "${local.prefix}-pickle-rebuild"
  description         = "Weekly pickle rebuild for missing universe symbols"
  schedule_expression = "cron(0 1 ? * SUN *)"
}

resource "aws_cloudwatch_event_target" "pickle_rebuild" {
  rule      = aws_cloudwatch_event_rule.pickle_rebuild.name
  target_id = "lambda-pickle-rebuild"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ pickle_rebuild = true })
}

resource "aws_lambda_permission" "pickle_rebuild" {
  statement_id  = "AllowPickleRebuildEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pickle_rebuild.arn
}

# ============================================================================
# EventBridge - Daily Pipeline Health Report (7:30 AM ET = 12:30 UTC, daily)
# Runs lightweight checks (S3 HEAD, CloudWatch, DB counts) — no pickle loading.
# Emails admins only when warnings/errors are detected.
# ============================================================================

resource "aws_cloudwatch_event_rule" "pipeline_health" {
  name                = "${local.prefix}-pipeline-health"
  description         = "Daily pipeline health report at 7:30 AM ET"
  schedule_expression = "cron(30 12 * * ? *)"
}

resource "aws_cloudwatch_event_target" "pipeline_health" {
  rule      = aws_cloudwatch_event_rule.pipeline_health.name
  target_id = "lambda-pipeline-health"
  arn       = aws_lambda_function.worker.arn
  input     = jsonencode({ pipeline_health_report = { always_send = false } })
}

resource "aws_lambda_permission" "pipeline_health" {
  statement_id  = "AllowPipelineHealthEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pipeline_health.arn
}

resource "aws_cloudwatch_event_rule" "generate_social_posts" {
  name                = "${local.prefix}-generate-social-posts"
  description         = "Generate AI social posts from live portfolio trades at 9 PM ET"
  schedule_expression = "cron(0 2 ? * TUE-SAT *)"
}

resource "aws_cloudwatch_event_target" "generate_social_posts" {
  rule      = aws_cloudwatch_event_rule.generate_social_posts.name
  target_id = "lambda-generate-social-posts"
  arn       = aws_lambda_function.worker.arn
  input = jsonencode({
    generate_social_posts = {
      min_pnl_pct = 5.0
      max_trades  = 5
    }
  })
}

resource "aws_lambda_permission" "generate_social_posts" {
  statement_id  = "AllowGenerateSocialPostsEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.worker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.generate_social_posts.arn
}

# ============================================================================
# Step Functions - Walk-Forward Simulation
# ============================================================================

# IAM Role for Step Functions
resource "aws_iam_role" "step_functions" {
  name = "${local.prefix}-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

# Allow Step Functions to invoke Worker Lambda
resource "aws_iam_role_policy" "step_functions_lambda" {
  name = "${local.prefix}-sfn-lambda"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = aws_lambda_function.worker.arn
      }
    ]
  })
}

# Allow Step Functions to write CloudWatch logs
resource "aws_iam_role_policy" "step_functions_logs" {
  name = "${local.prefix}-sfn-logs"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups",
          "logs:PutLogEvents",
          "logs:CreateLogGroup",
          "logs:CreateLogStream"
        ]
        Resource = "*"
      }
    ]
  })
}

# CloudWatch Log Group for Step Functions
resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/states/${local.prefix}-walk-forward"
  retention_in_days = 30

  tags = {
    Name = "${local.prefix}-sfn-logs"
  }
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "walk_forward" {
  name     = "${local.prefix}-walk-forward"
  role_arn = aws_iam_role.step_functions.arn

  definition = templatefile("${path.module}/step-functions/walk-forward.json", {
    lambda_arn = aws_lambda_function.worker.arn
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ERROR"
  }

  tags = {
    Name = "${local.prefix}-walk-forward"
  }
}

# Allow Lambda to start Step Functions executions
resource "aws_iam_role_policy" "lambda_step_functions" {
  name = "${local.prefix}-lambda-sfn"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution",
          "states:DescribeExecution"
        ]
        Resource = aws_sfn_state_machine.walk_forward.arn
      }
    ]
  })
}

# ============================================================================
# CloudWatch Alarms + SNS Notifications
# ============================================================================

resource "aws_sns_topic" "alarms" {
  name = "${local.prefix}-alarms"

  tags = {
    Name = "${local.prefix}-alarms"
  }
}

resource "aws_sns_topic_subscription" "alarm_email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.admin_emails
}

# Lambda Errors — more than 3 errors in 15 minutes
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.prefix}-lambda-errors"
  alarm_description   = "Lambda error rate exceeded threshold"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 3
  threshold           = 3
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-lambda-errors"
  }
}

# Lambda Throttles — any throttling at all
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.prefix}-lambda-throttles"
  alarm_description   = "Lambda function is being throttled"
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-lambda-throttles"
  }
}

# Lambda Duration — approaching 900s timeout
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${local.prefix}-lambda-duration"
  alarm_description   = "Lambda duration approaching 900s timeout"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 720000 # 720 seconds in milliseconds
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-lambda-duration"
  }
}

# API Gateway 5xx errors
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.prefix}-api-5xx"
  alarm_description   = "API Gateway 5xx error rate exceeded threshold"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiId = aws_apigatewayv2_api.main.id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-api-5xx"
  }
}

# API Gateway 4xx spike — possible abuse or misconfiguration
resource "aws_cloudwatch_metric_alarm" "api_4xx" {
  alarm_name          = "${local.prefix}-api-4xx-spike"
  alarm_description   = "API Gateway 4xx error spike detected"
  namespace           = "AWS/ApiGateway"
  metric_name         = "4xx"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 50
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiId = aws_apigatewayv2_api.main.id
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-api-4xx-spike"
  }
}

# RDS CPU — sustained high CPU
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.prefix}-rds-cpu"
  alarm_description   = "RDS CPU utilization exceeded 80%"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-rds-cpu"
  }
}

# RDS Free Storage — less than 3 GB remaining
resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "${local.prefix}-rds-storage"
  alarm_description   = "RDS free storage space below 3 GB"
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = 3000000000 # 3 GB in bytes
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-rds-storage"
  }
}

# RDS Connections — too many open connections
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "${local.prefix}-rds-connections"
  alarm_description   = "RDS database connections exceeded 40"
  namespace           = "AWS/RDS"
  metric_name         = "DatabaseConnections"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 40
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.identifier
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-rds-connections"
  }
}

# Worker Lambda Errors — any errors in 5 minutes (currently NO alarm on Worker)
resource "aws_cloudwatch_metric_alarm" "worker_errors" {
  alarm_name          = "${local.prefix}-worker-errors"
  alarm_description   = "Worker Lambda errors exceeded threshold"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.worker.function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-worker-errors"
  }
}

# Worker Lambda Duration — approaching 900s timeout (alert at 810s = 90%)
resource "aws_cloudwatch_metric_alarm" "worker_duration" {
  alarm_name          = "${local.prefix}-worker-duration"
  alarm_description   = "Worker Lambda duration approaching 900s timeout"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 810000 # 810 seconds in milliseconds (90% of 900s)
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.worker.function_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-worker-duration"
  }
}

# ============================================================================
# Outputs
# ============================================================================

output "frontend_url" {
  value       = "https://${var.domain_name}"
  description = "Frontend URL (custom domain)"
}

output "frontend_cloudfront_url" {
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
  description = "Frontend CloudFront URL (for testing)"
}

output "api_url" {
  value       = "https://api.${var.domain_name}"
  description = "API URL (custom domain)"
}

output "api_gateway_url" {
  value       = aws_apigatewayv2_api.main.api_endpoint
  description = "API Gateway URL (for testing)"
}

output "s3_bucket" {
  value       = aws_s3_bucket.frontend.bucket
  description = "S3 bucket for frontend"
}

output "rds_endpoint" {
  value       = aws_db_instance.main.endpoint
  description = "RDS endpoint"
}

output "nameservers" {
  value       = var.use_route53 ? aws_route53_zone.main[0].name_servers : []
  description = "Route53 nameservers (point your domain registrar to these)"
}

output "cloudfront_domain" {
  value       = aws_cloudfront_distribution.frontend.domain_name
  description = "CloudFront domain (for CNAME if not using Route53)"
}

output "api_gateway_domain" {
  value       = aws_apigatewayv2_domain_name.api.domain_name_configuration[0].target_domain_name
  description = "API Gateway domain (for CNAME if not using Route53)"
}

output "price_data_bucket" {
  value       = aws_s3_bucket.price_data.bucket
  description = "S3 bucket for persistent price data"
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.api.repository_url
  description = "ECR repository URL for Lambda container image"
}

output "step_functions_arn" {
  value       = aws_sfn_state_machine.walk_forward.arn
  description = "Step Functions state machine ARN for walk-forward simulations"
}

# ============================================================================
# DNS Setup Instructions
# ============================================================================
# After deployment, update your domain's nameservers to the values in 'nameservers' output.
# Or if using external DNS, create CNAME records pointing to cloudfront_domain and api_gateway_domain.
