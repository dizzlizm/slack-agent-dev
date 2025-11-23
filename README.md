# TRR Systems Slack Bot

An intelligent IT support assistant powered by Gemini AI and MCP (Model Context Protocol). This bot provides natural language access to IT services including Freshservice, Meraki, and Intune.

## Features

- **Natural Language Interface** - No syntax to remember, just ask naturally
- **Intelligent Routing** - Gemini AI automatically determines which service to use
- **Unified MCP Architecture** - All IT services accessible through a single interface
- **Automatic Ticket Triage** - Monitors channels and assists users automatically
- **Multi-Service Integration** - Freshservice, Meraki, Intune support

## Quick Start

### Prerequisites

- Python 3.9+
- Azure Functions Core Tools
- Slack workspace with bot token
- Gemini API key
- (Optional) Freshservice, Meraki, Intune credentials

### Installation

1. Clone the repository:
```bash
git clone https://github.com/your-org/trr-systems-slack-bot-dev.git
cd trr-systems-slack-bot-dev
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables (see Configuration section)

4. Run locally:
```bash
func start
```

5. Deploy to Azure:
```bash
func azure functionapp publish <your-function-app-name>
```

## Usage

### For Admins (Authorized Users)

Admins can interact with the bot using natural language. No special syntax required!

**Example commands:**
```
@systems help me with user john.smith@company.com
@systems what tickets does jane doe have?
@systems show assets for john smith
@systems update guest WiFi password to NewSecure2024
@systems reboot device ABC123
@systems are there any planned outages?
```

**Admin management:**
```
@systems admin add @user
@systems admin remove @user
```

**Q&A with context:**
```
@systems ask how do I reset my VPN password?
@systems reset  (clears conversation history)
```

### For Regular Users (Non-Admins)

Regular users get automatic assistance in monitored channels without needing to @mention the bot:

1. Post a support request in a monitored channel
2. Bot automatically starts troubleshooting
3. Guided conversation to gather details
4. Automatic ticket creation when needed

## Architecture

### MCP (Model Context Protocol) Integration

The bot uses a unified MCP architecture that consolidates all IT services:

```
User Query → Gemini AI → MCP Orchestrator → Unified Tools → Service APIs
```

**Available MCP Tools:**

**Freshservice (5 tools):**
- `get_user_by_email(email)` - Lookup users by email
- `get_user_by_name(first_name, last_name)` - Lookup users by name
- `list_tickets(requester_id, agent_id)` - List IT tickets
- `list_assets(user_id)` - List user's IT assets
- `list_recent_changes()` - Check for planned outages

**Meraki (1 tool):**
- `update_ssid_password(ssid_name, new_password)` - Update WiFi passwords

**Intune (1 tool):**
- `reboot_device(serial_number)` - Remote reboot devices

### Key Components

- **function_app.py** - Azure Functions entry point
- **mcp_tools.py** - Unified tool registry for all services
- **mcp_integration.py** - Gemini MCP orchestrator
- **command_handlers.py** - Bot command handlers
- **command_parser.py** - Command routing with default handler
- **slack_client.py** - Slack API wrapper
- **auth_manager.py** - User authorization
- **triage_manager.py** - Automatic ticket triage

## Configuration

### Required Environment Variables

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_BOT_USER_ID=U01234ABCDE

# Gemini AI (required for MCP)
GEMINI_API_KEY=your-gemini-api-key

# Azure Table Storage (for conversation history)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
```

### Optional Service Integrations

```bash
# Freshservice
FRESHSERVICE_DOMAIN=yourcompany.freshservice.com
FRESHSERVICE_API_KEY=your-freshservice-api-key

# Meraki
MERAKI_API_KEY=your-meraki-api-key
MERAKI_ORG_ID=your-org-id

# Intune
INTUNE_REBOOT_WEBHOOK_URL=https://your-webhook-url
```

### Optional Features

```bash
# Automatic Triage (comma-separated channel IDs)
MONITORED_SLACK_CHANNEL_IDS=C01234567,C89012345

# Admin Users (comma-separated Slack user IDs)
ADMIN_SLACK_USER_IDS=U01234567,U89012345
```

## Deployment

### Azure Functions Deployment

1. Create an Azure Function App (Python 3.9+)

2. Configure application settings with environment variables

3. Deploy using Azure Functions Core Tools:
```bash
func azure functionapp publish <your-function-app-name>
```

### Slack App Configuration

1. Create a Slack app at api.slack.com/apps

2. Enable the following bot token scopes:
   - `chat:write`
   - `users:read`
   - `users:read.email`
   - `channels:history`
   - `groups:history`
   - `im:history`
   - `mpim:history`
   - `reactions:write`

3. Configure Event Subscriptions:
   - Request URL: `https://your-function-app.azurewebsites.net/api/slack/events`
   - Subscribe to bot events:
     - `app_mention`
     - `message.channels`
     - `message.groups`
     - `message.im`

4. Configure Interactivity:
   - Request URL: `https://your-function-app.azurewebsites.net/api/slack/interactive`

5. Install the app to your workspace

## Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SLACK_BOT_TOKEN=xoxb-...
export GEMINI_API_KEY=...
# (set other variables as needed)

# Start the function app
func start
```

### Testing MCP Tools

You can test the MCP endpoint directly:

```bash
curl -X POST https://your-function-app.azurewebsites.net/api/mcp/tools \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'
```

## Benefits

| Aspect | Traditional Approach | MCP-Powered Bot |
|--------|---------------------|-----------------|
| **Learning Curve** | Hours (documentation) | Minutes (just ask) |
| **Syntax Requirements** | Complex service-specific commands | Natural language |
| **Error Rate** | High (syntax errors) | Low (flexible queries) |
| **Extensibility** | Hard (new handlers needed) | Easy (add MCP tools) |
| **User Experience** | Frustrating | Delightful |
| **Onboarding** | Training required | Self-explanatory |

## Documentation

- [CONSOLIDATION.md](CONSOLIDATION.md) - MCP architecture consolidation details
- [NATURAL_LANGUAGE.md](NATURAL_LANGUAGE.md) - Natural language transformation guide
- [CLEANUP_ANALYSIS.md](CLEANUP_ANALYSIS.md) - Code cleanup analysis
- [IMPROVEMENTS.md](IMPROVEMENTS.md) - Code review and recommendations
- [DEPLOYMENT.md](DEPLOYMENT.md) - Detailed deployment guide

## Troubleshooting

### Bot doesn't respond to @mentions

- Verify `SLACK_BOT_USER_ID` is set correctly
- Check Event Subscriptions are configured
- Ensure bot has required OAuth scopes

### "Service not configured" errors

- Verify service credentials are set (FRESHSERVICE_API_KEY, etc.)
- Check Azure Function App configuration

### MCP tools not working

- Verify `GEMINI_API_KEY` is set
- Check function app logs for errors
- Ensure Gemini API quota is not exceeded

### Automatic triage not working

- Verify `MONITORED_SLACK_CHANNEL_IDS` is set
- Ensure bot is invited to the channels
- Check that message events are subscribed

## License

Proprietary - TRR Systems

## Support

For issues or questions, contact your IT administrator or open an issue in this repository.
