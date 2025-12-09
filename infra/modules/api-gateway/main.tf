# API Gateway Module
# Creates REST API for Slack bot endpoints

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "lambda_slack_events_arn" {
  description = "ARN of the Slack events Lambda function"
  type        = string
}

variable "lambda_slack_events_invoke_arn" {
  description = "Invoke ARN of the Slack events Lambda function"
  type        = string
}

variable "lambda_slack_interactive_arn" {
  description = "ARN of the Slack interactive Lambda function"
  type        = string
}

variable "lambda_slack_interactive_invoke_arn" {
  description = "Invoke ARN of the Slack interactive Lambda function"
  type        = string
}

variable "lambda_health_arn" {
  description = "ARN of the health check Lambda function"
  type        = string
}

variable "lambda_health_invoke_arn" {
  description = "Invoke ARN of the health check Lambda function"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# REST API
resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.environment}-systems-bot-api"
  description = "Systems Bot API - ${var.environment}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = var.tags
}

# /slack resource
resource "aws_api_gateway_resource" "slack" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "slack"
}

# /slack/events
resource "aws_api_gateway_resource" "slack_events" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.slack.id
  path_part   = "events"
}

resource "aws_api_gateway_method" "slack_events_post" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.slack_events.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "slack_events" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.slack_events.id
  http_method             = aws_api_gateway_method.slack_events_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_slack_events_invoke_arn
}

# /slack/interactive
resource "aws_api_gateway_resource" "slack_interactive" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.slack.id
  path_part   = "interactive"
}

resource "aws_api_gateway_method" "slack_interactive_post" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.slack_interactive.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "slack_interactive" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.slack_interactive.id
  http_method             = aws_api_gateway_method.slack_interactive_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_slack_interactive_invoke_arn
}

# /health
resource "aws_api_gateway_resource" "health" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "health"
}

resource "aws_api_gateway_method" "health_get" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.health.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "health" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.health.id
  http_method             = aws_api_gateway_method.health_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_health_invoke_arn
}

# Lambda permissions for API Gateway
resource "aws_lambda_permission" "slack_events" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_slack_events_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "slack_interactive" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_slack_interactive_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "health" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_health_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

# Deployment
resource "aws_api_gateway_deployment" "deployment" {
  depends_on = [
    aws_api_gateway_integration.slack_events,
    aws_api_gateway_integration.slack_interactive,
    aws_api_gateway_integration.health
  ]

  rest_api_id = aws_api_gateway_rest_api.api.id

  lifecycle {
    create_before_destroy = true
  }
}

# Stage
resource "aws_api_gateway_stage" "stage" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = var.environment

  tags = var.tags
}

# Outputs
output "api_id" {
  value = aws_api_gateway_rest_api.api.id
}

output "api_endpoint" {
  value = aws_api_gateway_stage.stage.invoke_url
}

output "slack_events_url" {
  value = "${aws_api_gateway_stage.stage.invoke_url}/slack/events"
}

output "slack_interactive_url" {
  value = "${aws_api_gateway_stage.stage.invoke_url}/slack/interactive"
}

output "health_url" {
  value = "${aws_api_gateway_stage.stage.invoke_url}/health"
}
