# DynamoDB Tables Module
# Creates all required DynamoDB tables for the Slack bot

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Authorized Users Table
resource "aws_dynamodb_table" "authorized_users" {
  name         = "${var.environment}-AuthorizedUsers"
  billing_mode = "PAY_PER_REQUEST"  # On-demand pricing
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  tags = merge(var.tags, {
    Name = "${var.environment}-AuthorizedUsers"
  })
}

# Conversation History Table
resource "aws_dynamodb_table" "conversation_history" {
  name         = "${var.environment}-ConversationHistory"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # TTL for automatic cleanup of old conversations
  ttl {
    attribute_name = "TTL"
    enabled        = true
  }

  tags = merge(var.tags, {
    Name = "${var.environment}-ConversationHistory"
  })
}

# Triage Sessions Table
resource "aws_dynamodb_table" "triage_sessions" {
  name         = "${var.environment}-TriageSessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # TTL for automatic cleanup of stale sessions
  ttl {
    attribute_name = "TTL"
    enabled        = true
  }

  # GSI for querying by user
  global_secondary_index {
    name            = "UserIndex"
    hash_key        = "OriginalUserID"
    projection_type = "ALL"
  }

  attribute {
    name = "OriginalUserID"
    type = "S"
  }

  tags = merge(var.tags, {
    Name = "${var.environment}-TriageSessions"
  })
}

# Outputs
output "authorized_users_table_name" {
  value = aws_dynamodb_table.authorized_users.name
}

output "authorized_users_table_arn" {
  value = aws_dynamodb_table.authorized_users.arn
}

output "conversation_history_table_name" {
  value = aws_dynamodb_table.conversation_history.name
}

output "conversation_history_table_arn" {
  value = aws_dynamodb_table.conversation_history.arn
}

output "triage_sessions_table_name" {
  value = aws_dynamodb_table.triage_sessions.name
}

output "triage_sessions_table_arn" {
  value = aws_dynamodb_table.triage_sessions.arn
}

output "all_table_arns" {
  value = [
    aws_dynamodb_table.authorized_users.arn,
    aws_dynamodb_table.conversation_history.arn,
    aws_dynamodb_table.triage_sessions.arn
  ]
}
