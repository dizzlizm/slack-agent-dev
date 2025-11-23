# Deployment Guide for Slack Bot with MCP Integration

## Overview

This Slack bot is now fully integrated with MCP (Model Context Protocol) tools for Freshservice. The MCP server is **embedded** in the same Azure Function App (not a separate deployment), which provides:

- ✅ **Better Performance**: Direct function calls instead of HTTP requests
- ✅ **Simpler Deployment**: Single function app to deploy
- ✅ **Easier Maintenance**: All code in one place
- ✅ **Lower Costs**: No separate function app needed

## Architecture

The function app now has **4 HTTP endpoints**:

1. **`POST /slack/events`** - Handles Slack event callbacks (messages, mentions, DMs)
2. **`POST /slack/interactive`** - Handles Slack interactive components (button clicks)
3. **`GET /health`** - Health check endpoint
4. **`POST /mcp/tools`** - MCP Tool Server for Freshservice operations *(NEW)*

## What Changed

### New Files
- **`mcp_tools.py`** - Core Freshservice tool implementations (get_user_by_email, list_tickets, list_assets, list_recent_changes)

### Modified Files
- **`function_app.py`** - Added MCP server endpoint `/mcp/tools`
- **`mcp_integration.py`** - Optimized to use direct function calls instead of HTTP
- **`config.py`** - Added `FRESHSERVICE_DOMAIN` and `FRESHSERVICE_API_KEY` config variables
- **`requirements.txt`** - Added `fastmcp>=0.2.0` and `pydantic>=2.0.0`

### Configuration Template
- **`local.settings.json`** - Template for local development (already gitignored)

## Required Environment Variables

### Core (Required for Slack Bot)
```bash
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_BOT_USER_ID=U01234567890
MONITORED_SLACK_CHANNEL_IDS=C01234567890,C09876543210
AzureWebJobsStorage=DefaultEndpointsProtocol=https;AccountName=...
```

### Freshservice MCP Tools (Required for AI features)
```bash
FRESHSERVICE_DOMAIN=yourcompany.freshservice.com
FRESHSERVICE_API_KEY=your-freshservice-api-key
GEMINI_API_KEY=your-gemini-api-key
```

### Optional Integrations
```bash
MERAKI_API_KEY=your-meraki-api-key
MERAKI_ORG_ID=your-meraki-org-id
INTUNE_REBOOT_WEBHOOK_URL=https://your-intune-webhook
```

## Local Development

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Local Settings
Edit `local.settings.json` with your actual values:
```json
{
  "Values": {
    "SLACK_BOT_TOKEN": "xoxb-...",
    "SLACK_BOT_USER_ID": "U...",
    "FRESHSERVICE_DOMAIN": "yourcompany.freshservice.com",
    "FRESHSERVICE_API_KEY": "your-key",
    "GEMINI_API_KEY": "your-gemini-key"
  }
}
```

### 3. Run Locally
```bash
func start
```

You should see **4 HTTP functions** discovered:
```
Functions:

  HealthCheck: [GET] http://localhost:7071/api/health

  McpToolServer: [POST] http://localhost:7071/api/mcp/tools

  SlackEventsHandler: [POST] http://localhost:7071/api/slack/events

  SlackInteractiveHandler: [POST] http://localhost:7071/api/slack/interactive
```

### 4. Test MCP Endpoint Locally
```bash
curl -X POST http://localhost:7071/api/mcp/tools \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "get_user_by_email",
    "params": {"email": "user@example.com"},
    "id": "test-1"
  }'
```

## Azure Deployment

### Option 1: Deploy via Azure Functions Core Tools
```bash
func azure functionapp publish <your-function-app-name>
```

### Option 2: Deploy via Azure CLI
```bash
az functionapp deployment source config-zip \
  -g <resource-group> \
  -n <function-app-name> \
  --src <zip-file-path>
```

### Option 3: Deploy via VS Code
1. Install Azure Functions extension
2. Right-click on the function app folder
3. Select "Deploy to Function App..."

### Post-Deployment: Configure Environment Variables

In Azure Portal, go to your Function App → Configuration → Application settings and add:

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_BOT_USER_ID=U...
MONITORED_SLACK_CHANNEL_IDS=C...,C...
FRESHSERVICE_DOMAIN=yourcompany.freshservice.com
FRESHSERVICE_API_KEY=your-api-key
GEMINI_API_KEY=your-gemini-key
```

**Important**: Click "Save" and restart the function app.

## Verifying Deployment

### 1. Check Health Endpoint
```bash
curl https://<your-function-app>.azurewebsites.net/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "integrations": {
    "meraki": false,
    "gemini": true,
    "freshservice": true,
    "intune": false
  },
  "monitored_channels": 2
}
```

### 2. Check Azure Portal
Go to your Function App → Functions

You should see **4 functions**:
- ✅ HealthCheck
- ✅ McpToolServer
- ✅ SlackEventsHandler
- ✅ SlackInteractiveHandler

If you see "No triggers found", check:
1. ❌ Make sure `function_app.py` is in the root directory
2. ❌ Make sure Python runtime version matches (e.g., Python 3.9, 3.10, or 3.11)
3. ❌ Check deployment logs for errors
4. ❌ Verify `host.json` exists

### 3. View Logs
```bash
func azure functionapp logstream <your-function-app-name>
```

Or in Azure Portal: Monitor → Log Stream

## Common Issues

### "No triggers found" in Azure
**Cause**: The function app isn't recognizing `function_app.py`

**Solutions**:
1. Verify `function_app.py` is in the root directory (not in a subdirectory)
2. Check the Python version in Azure matches your local environment
3. Redeploy using `func azure functionapp publish <name> --build remote`
4. Check Application Insights logs for deployment errors

### MCP tools return "Configuration missing"
**Cause**: `FRESHSERVICE_DOMAIN` or `FRESHSERVICE_API_KEY` not set

**Solution**: Add these environment variables in Azure Portal → Configuration

### Gemini integration fails
**Cause**: `GEMINI_API_KEY` not set or invalid

**Solution**:
1. Verify API key is correct
2. Check if Gemini API is enabled in your Google Cloud project
3. Ensure billing is set up for Gemini API

## How It Works

### Direct Tool Calls (Optimized!)

When a user asks a question via Slack:

1. **User Message** → Slack → `/slack/events` endpoint
2. **Bot Routes** → `GeminiMCPOrchestrator.process_query()`
3. **Gemini AI** decides if it needs to call tools
4. **Tool Execution** → **DIRECT function call** to `mcp_tools.py` (no HTTP!)
5. **Gemini AI** processes results and responds
6. **Response** → Back to Slack user

**Performance**: Direct calls are ~10-100x faster than HTTP requests!

### External MCP Access (Optional)

If you want external systems to use the MCP tools, they can call:

```
POST https://<your-app>.azurewebsites.net/api/mcp/tools
```

With JSON-RPC payload:
```json
{
  "jsonrpc": "2.0",
  "method": "list_tickets",
  "params": {"requester_id": 123},
  "id": "external-call-1"
}
```

## Available MCP Tools

1. **`get_user_by_email`**
   - Lookup user/agent by email
   - Returns: user_id, name, type

2. **`list_tickets`**
   - List tickets by requester_id or agent_id
   - Returns: ticket id, subject, status, priority

3. **`list_assets`**
   - List IT assets for a user_id
   - Returns: asset id, name, tag, type

4. **`list_recent_changes`**
   - List recent change requests
   - Returns: change id, subject, status, dates

## Security Notes

- The `/mcp/tools` endpoint uses `AuthLevel.FUNCTION` (requires function key)
- Get the function key from Azure Portal → Function App → App keys
- Store keys securely in Azure Key Vault or environment variables

## Support

For issues or questions:
1. Check Application Insights for errors
2. Review function app logs
3. Verify all environment variables are set correctly
