# Secrets Manager Module
# Creates secret for storing sensitive configuration

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

# Secret for bot configuration
resource "aws_secretsmanager_secret" "bot_secrets" {
  name        = "systems-bot/${var.environment}"
  description = "Secrets for Systems Bot - ${var.environment}"

  tags = var.tags
}

# Note: The secret VALUE is not managed by Terraform for security
# It should be set manually or via CI/CD after initial creation

# Outputs
output "secret_arn" {
  value = aws_secretsmanager_secret.bot_secrets.arn
}

output "secret_name" {
  value = aws_secretsmanager_secret.bot_secrets.name
}
