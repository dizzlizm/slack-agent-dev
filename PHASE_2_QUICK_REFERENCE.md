# Phase 2 Quick Reference Guide

## New Tools Available to AI Agent

### Ticket Operations (3 new tools)

#### update_ticket
**Purpose:** Update existing ticket properties  
**Parameters:**
- `ticket_id` (required): The ticket ID
- `status` (optional): 2=Open, 3=Pending, 4=Resolved, 5=Closed
- `priority` (optional): 1=Low, 2=Medium, 3=High, 4=Urgent
- `agent_id` (optional): Assign to specific agent
- `group_id` (optional): Assign to specific group/queue

**Example:**
```python
update_ticket(ticket_id=12345, status=4, priority=3)
```

#### add_ticket_note
**Purpose:** Add comment/note to existing ticket  
**Parameters:**
- `ticket_id` (required): The ticket ID
- `body` (required): Note content
- `private` (optional): True for internal-only notes (default: False)

**Example:**
```python
add_ticket_note(ticket_id=12345, body="Escalated to senior tech", private=True)
```

#### get_ticket_conversations
**Purpose:** View all notes/comments on a ticket  
**Parameters:**
- `ticket_id` (required): The ticket ID

**Example:**
```python
get_ticket_conversations(ticket_id=12345)
```

---

### Asset Operations (2 new tools)

#### get_asset_software
**Purpose:** View software installed on an asset for license compliance  
**Parameters:**
- `asset_id` (required): The asset ID

**Returns:** List of installed software with versions, licenses, vendors

**Example:**
```python
get_asset_software(asset_id=67890)
```

#### get_asset_contracts
**Purpose:** View warranty and support contracts for an asset  
**Parameters:**
- `asset_id` (required): The asset ID

**Returns:** List of contracts with expiry dates, costs, renewal info

**Example:**
```python
get_asset_contracts(asset_id=67890)
```

---

### Service Catalog (5 new tools)

#### list_service_items
**Purpose:** Browse available service catalog items  
**Parameters:**
- `category_id` (optional): Filter by category
- `search_query` (optional): Search term

**Use Case:** User needs standard service (access, provisioning, etc)

**Example:**
```python
list_service_items(search_query="sharepoint access")
```

#### get_service_item
**Purpose:** Get details about a catalog item including custom fields  
**Parameters:**
- `item_id` (required): The service item ID

**Example:**
```python
get_service_item(item_id=123)
```

#### create_service_request
**Purpose:** Submit service request through catalog with approval workflows  
**Parameters:**
- `service_item_id` (required): The catalog item ID
- `requester_email` (required): Requester's email
- `custom_fields` (optional): Dict of custom field values

**Key Feature:** Automatically routes through FreshService approval workflows

**Example:**
```python
create_service_request(
    service_item_id=123,
    requester_email="user@company.com",
    custom_fields={"access_level": "read-only", "justification": "Project X"}
)
```

#### list_service_categories
**Purpose:** Browse catalog organization  
**Parameters:** None

**Example:**
```python
list_service_categories()
```

#### get_service_request_status
**Purpose:** Track approval and fulfillment progress  
**Parameters:**
- `service_request_id` (required): The service request ID

**Returns:** Approval status, fulfillment stage, child tickets

**Example:**
```python
get_service_request_status(service_request_id=456)
```

---

### Problem Management (5 new tools)

#### search_problems
**Purpose:** Check if reported issue matches a known problem  
**Parameters:**
- `query` (required): Search term
- `limit` (optional): Max results (default: 10)

**Use Case:** User reports issue → search for existing problem first

**Example:**
```python
search_problems(query="email server down", limit=5)
```

#### list_problems
**Purpose:** Browse known problems with filters  
**Parameters:**
- `status` (optional): 1=Open, 2=Change Requested, 3=Closed
- `priority` (optional): 1=Low, 2=Medium, 3=High, 4=Urgent
- `impact` (optional): 1=Low, 2=Medium, 3=High
- `limit` (optional): Max results (default: 10)

**Example:**
```python
list_problems(status=1, impact=3)  # Open high-impact problems
```

#### get_problem_by_id
**Purpose:** Get problem details with root cause and workaround  
**Parameters:**
- `problem_id` (required): The problem ID

**Returns:** Root cause analysis, symptoms, workaround steps

**Example:**
```python
get_problem_by_id(problem_id=789)
```

#### link_ticket_to_problem
**Purpose:** Associate ticket with known problem for impact tracking  
**Parameters:**
- `ticket_id` (required): The ticket ID
- `problem_id` (required): The problem ID

**Key Feature:** When problem is resolved, all linked tickets auto-update

**Example:**
```python
link_ticket_to_problem(ticket_id=12345, problem_id=789)
```

#### get_problem_tickets
**Purpose:** View all tickets affected by a problem  
**Parameters:**
- `problem_id` (required): The problem ID

**Use Case:** Understand problem scope/impact

**Example:**
```python
get_problem_tickets(problem_id=789)
```

---

## Workflow Examples for AI Agent

### Service Catalog Workflow
```
User: "I need access to SharePoint"
AI Decision Tree:
1. list_service_items(search_query="sharepoint access")
2. If item found:
   - get_service_item(item_id) to see required fields
   - create_service_request(service_item_id, user_email, custom_fields)
   - Response: "Service request submitted! Tracking ID: #456. It will be routed through approval."
3. If not found:
   - create_ticket() as fallback
```

### Problem Management Workflow
```
User: "Email isn't working"
AI Decision Tree:
1. search_problems(query="email")
2. If problem found:
   - get_problem_by_id(problem_id) to get workaround
   - Provide workaround to user
   - create_ticket() for tracking
   - link_ticket_to_problem() for auto-updates
   - Response: "This is a known issue. Here's the workaround: [steps]. I've created ticket #12345 and linked it to the problem. You'll be notified when it's resolved."
3. If not found:
   - create_ticket() and troubleshoot normally
```

### Asset Intelligence Workflow
```
User: "What software is on my laptop?"
AI Decision Tree:
1. get_user_by_email(user_email)
2. list_assets(user_id)
3. For each asset:
   - get_asset_software(asset_id)
   - Response: "Your laptop has: Office 365 (v16.0), Chrome (v121), Zoom (v5.17), etc."
```

### Ticket Update Workflow
```
User: "Can you update ticket #12345 to high priority?"
AI Decision Tree:
1. update_ticket(ticket_id=12345, priority=3)
2. Response: "Updated ticket #12345 to high priority"

User: "Add a note that I tried restarting"
AI Decision Tree:
1. add_ticket_note(ticket_id=12345, body="User confirmed they tried restarting the device")
2. Response: "Added your note to ticket #12345"
```

---

## Tool Integration in mcp_integration.py

All 15 Phase 2 tools have been registered with Gemini via FunctionDeclaration schemas. The AI agent can now:

1. **Discover Tools:** See all 29 available tools in `_define_all_tools()`
2. **Understand Parameters:** Each tool has detailed parameter schemas with descriptions
3. **Chain Tools:** Gemini can chain multiple tools together (e.g., search_problems → create_ticket → link_ticket_to_problem)
4. **Context-Aware:** System instruction guides when to use Service Catalog vs regular tickets

---

## Configuration Requirements

### FreshService Configuration
These tools require certain FreshService features to be enabled:

**Service Catalog:**
- Service Catalog module enabled
- Service items configured with custom fields
- Approval workflows configured per item

**Problem Management:**
- Problem module enabled (usually on by default)
- Problems created and maintained

**Asset Relationships:**
- Asset module enabled
- Software assets tracked
- Contract module enabled (optional)

### Code Configuration
No additional environment variables needed. All tools use existing FreshService credentials:
- `FRESHSERVICE_DOMAIN`
- `FRESHSERVICE_API_KEY`

---

## Error Handling

### Graceful Degradation
Some tools return empty lists instead of failing:
- `get_asset_software()` - Returns [] if relationships not configured
- `get_asset_contracts()` - Returns [] if contracts not used

### Explicit Errors
Some tools raise ValueError for critical failures:
- `get_problem_by_id()` - Raises if problem not found
- `create_service_request()` - Raises if item not found or requester invalid

---

## Performance Notes

### API Calls
- All tools use `@retry_on_failure` decorator (3 retries, exponential backoff)
- Service catalog operations may be slower due to approval workflow lookups
- Asset software queries use relationship API (1 call per asset)

### Rate Limiting
FreshService API limits (typically 5000 requests/hour):
- Phase 2 tools respect existing rate limits
- Retry logic helps with transient failures
- Batch operations recommended where possible

---

## Testing Checklist

### Service Catalog
- [ ] List service items returns configured catalog items
- [ ] Create service request triggers approval workflow
- [ ] Service request status shows approval progress
- [ ] Custom fields are properly passed and validated

### Problem Management
- [ ] Search finds relevant problems
- [ ] Link ticket to problem creates association
- [ ] Problem details include root cause analysis
- [ ] Linked tickets show in get_problem_tickets()

### Asset Enhancements
- [ ] Asset software shows installed applications
- [ ] Asset contracts show warranty information
- [ ] Empty results handled gracefully if not configured

### Ticket Operations
- [ ] Update ticket changes status/priority
- [ ] Add ticket note creates comment
- [ ] Get conversations returns all notes
- [ ] Private notes marked correctly

---

## Summary

**Phase 2 Added:**
- 15 new tools across 4 categories
- 2 new modules (service_catalog, problems)
- Enhanced 2 existing modules (tickets, assets)
- Updated MCP integration with Gemini
- Total tool count: 14 → 29 (+107%)

**Key Philosophy:**
Leverage FreshService's existing ecosystem (workflows, approvals, relationships) rather than building custom logic. This maximizes functionality while minimizing maintenance.
