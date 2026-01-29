# Freshservice Integration Module

This module provides a modular, scalable integration with the Freshservice API.

## Structure

```
freshservice/
├── __init__.py          # Module exports
├── client.py            # Base API client (auth, config, headers)
├── users.py             # User lookup operations
├── tickets.py           # Ticket management operations
├── assets.py            # Asset management operations
├── changes.py           # Change management operations
├── solutions.py         # Knowledge base / Solutions operations
└── tools.py             # Unified interface that aggregates all operations
```

## Usage

### Direct Import
```python
from src.integrations.freshservice import FreshserviceTools

tools = FreshserviceTools()
user = tools.get_user_by_email("user@example.com")
```

### Individual Module Import
```python
from src.integrations.freshservice.users import UserOperations

users = UserOperations()
user = users.get_user_by_email("user@example.com")
```

### Solutions / Knowledge Base
```python
# Search knowledge base
articles = tools.search_solution_articles("VPN setup", limit=5)

# Get popular articles
popular = tools.get_popular_articles(limit=10)

# Get full article content
article = tools.get_solution_article(article_id=123)

# Browse by structure
categories = tools.list_solution_categories()
folders = tools.list_solution_folders(category_id=1)
articles = tools.list_solution_articles(folder_id=5)
```

## Benefits of This Structure

1. **Modularity**: Each operation type is in its own file
2. **Maintainability**: Easy to locate and update specific functionality
3. **Testability**: Can test each module independently
4. **Scalability**: Easy to add new operations without bloating single files
5. **Separation of Concerns**: Client config separate from business logic
6. **Intelligence Access**: Solutions module provides knowledge base insights for smarter automation

## Line Count Comparison

- **Before**: 586 lines in single class in mcp_tools.py
- **After**: 
  - mcp_tools.py: 146 lines (reduced by 75%)
  - freshservice/: 1,170+ lines (spread across 8 focused files)
  - Average per file: ~146 lines (highly maintainable)

## Available Tools

### Users
- `get_user_by_email(email)` - Find user by email address
- `get_user_by_name(first_name, last_name)` - Search users by name

### Tickets
- `list_tickets(requester_id, agent_id)` - List tickets by requester or agent
- `get_ticket_by_id(ticket_id)` - Get specific ticket details
- `create_ticket(...)` - Create a new ticket

### Assets
- `list_assets(user_id)` - List assets assigned to a user
- `get_asset_by_id(asset_id)` - Get specific asset details

### Changes
- `list_recent_changes()` - List recent open changes/maintenance

### Solutions (Knowledge Base)
- `search_solution_articles(query, limit)` - **Search knowledge base by keyword**
- `get_solution_article(article_id)` - **Get full article content**
- `list_solution_articles(folder_id, category_id, limit)` - **Browse articles**
- `get_popular_articles(limit)` - **Get most viewed articles**
- `list_solution_categories()` - **List KB categories**
- `list_solution_folders(category_id)` - **List KB folders**

## Adding New Operations

To add new Freshservice operations:

1. Create a new file (e.g., `incidents.py`)
2. Import and extend `FreshserviceClient`
3. Add methods with `@retry_on_failure` decorator
4. Import in `tools.py` and add delegation methods
5. Update `execute_tool()` dispatcher
