# Production Environment Infrastructure
# Deploys all resources for the production environment

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration - uncomment and configure for your S3 bucket
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "systems-bot/prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "systems-bot"
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "lambda_s3_bucket" {
  description = "S3 bucket containing Lambda deployment packages"
  type        = string
}

variable "lambda_s3_key" {
  description = "S3 key for the Lambda deployment package"
  type        = string
  default     = "systems-bot/prod/lambda.zip"
}

locals {
  environment = "prod"
  common_tags = {
    Project     = "systems-bot"
    Environment = local.environment
  }
}

# Secrets Manager
module "secrets" {
  source = "../../modules/secrets"

  environment = local.environment
  tags        = local.common_tags
}

# DynamoDB Tables
module "dynamodb" {
  source = "../../modules/dynamodb"

  environment = local.environment
  tags        = local.common_tags
}

# Lambda Functions - Production has more memory and longer retention
module "lambda_slack_events" {
  source = "../../modules/lambda"

  environment   = local.environment
  function_name = "slack-events"
  handler       = "src.handlers.slack_events.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = var.lambda_s3_key
  timeout       = 30
  memory_size   = 512  # More memory for production

  dynamodb_table_arns = module.dynamodb.all_table_arns
  secrets_arn         = module.secrets.secret_arn

  tags = local.common_tags
}

module "lambda_slack_interactive" {
  source = "../../modules/lambda"

  environment   = local.environment
  function_name = "slack-interactive"
  handler       = "src.handlers.slack_interactive.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = var.lambda_s3_key
  timeout       = 30
  memory_size   = 512

  dynamodb_table_arns = module.dynamodb.all_table_arns
  secrets_arn         = module.secrets.secret_arn

  tags = local.common_tags
}

module "lambda_health" {
  source = "../../modules/lambda"

  environment   = local.environment
  function_name = "health"
  handler       = "src.handlers.health.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = var.lambda_s3_key
  timeout       = 10
  memory_size   = 128

  secrets_arn = module.secrets.secret_arn

  tags = local.common_tags
}

# API Gateway
module "api_gateway" {
  source = "../../modules/api-gateway"

  environment = local.environment

  lambda_slack_events_arn            = module.lambda_slack_events.function_arn
  lambda_slack_events_invoke_arn     = module.lambda_slack_events.invoke_arn
  lambda_slack_interactive_arn       = module.lambda_slack_interactive.function_arn
  lambda_slack_interactive_invoke_arn = module.lambda_slack_interactive.invoke_arn
  lambda_health_arn                  = module.lambda_health.function_arn
  lambda_health_invoke_arn           = module.lambda_health.invoke_arn

  tags = local.common_tags
}

# Outputs
output "api_endpoint" {
  description = "Base URL for the API"
  value       = module.api_gateway.api_endpoint
}

output "slack_events_url" {
  description = "URL for Slack events webhook"
  value       = module.api_gateway.slack_events_url
}

output "slack_interactive_url" {
  description = "URL for Slack interactive webhook"
  value       = module.api_gateway.slack_interactive_url
}

output "health_url" {
  description = "URL for health check"
  value       = module.api_gateway.health_url
}

output "secret_name" {
  description = "Name of the Secrets Manager secret"
  value       = module.secrets.secret_name
}

output "dynamodb_tables" {
  description = "DynamoDB table names"
  value = {
    authorized_users     = module.dynamodb.authorized_users_table_name
    conversation_history = module.dynamodb.conversation_history_table_name
    triage_sessions      = module.dynamodb.triage_sessions_table_name
  }
}
