"""
MCP (Model Context Protocol) Integration for Gemini + IT Tools.

This module implements the GeminiMCPOrchestrator which connects Google Gemini AI
with IT service management tools using the Model Context Protocol pattern.

Architecture Overview:
    The orchestrator acts as a bridge between conversational AI (Gemini) and
    IT tools (FreshService, Intune, etc.). It follows this pattern:
    
    User Query → Gemini (with tool schemas) → Tool Selection → Tool Execution
         ↑                                                           ↓
         └──────────────────── Final Response ←───────────────────┘

Key Components:
    - GeminiMCPOrchestrator: Main orchestrator class
    - FunctionDeclaration: Tool schema definitions for Gemini
    - UnifiedTools: Backend tool implementations
    
Supported Integrations:
    - FreshService (29 tools): Tickets, Assets, Service Catalog, Problems, Solutions
    - Intune (1 tool): Device reboot
    
Tool Categories:
    1. User Operations: get_user_by_email, get_user_by_name
    2. Ticket Management: create_ticket, update_ticket, add_ticket_note, list_tickets
    3. Asset Management: list_assets, get_asset_software, get_asset_contracts
    4. Service Catalog: list_service_items, create_service_request
    5. Problem Management: search_problems, link_ticket_to_problem
    6. Knowledge Base: search_solution_articles, get_solution_article
    7. Device Management: reboot_device (Intune)

Usage Example:
    ```python
    orchestrator = GeminiMCPOrchestrator()
    response = orchestrator.process_query(
        user_query="What are my open tickets?",
        user_email="user@company.com"
    )
    ```

Performance Characteristics:
    - Direct function calls (no HTTP overhead)
    - Streaming not supported (returns full response)
    - Average latency: 2-5 seconds for simple queries
    - Tool execution adds 0.5-2s per tool call

Design Philosophy:
    - Gemini decides which tools to call based on natural language understanding
    - Tools are stateless and idempotent where possible
    - System instructions guide Gemini toward knowledge base first, ticket creation last
    - Sensitive actions (reboot) require explicit user confirmation

See Also:
    - src/integrations/mcp_tools.py: Tool implementations
    - src/integrations/freshservice/tools.py: FreshService operations
"""
import logging
from typing import Optional
from google import genai
from google.genai import types

from src.config import Config
from src.integrations.mcp_tools import get_unified_tools


class GeminiMCPOrchestrator:
    """
    Orchestrates conversations between users, Gemini AI, and ALL IT tools.

    This implementation uses DIRECT tool calls (no HTTP overhead) for optimal performance.
    Gemini intelligently routes queries to the appropriate backend service.
    """

    def __init__(self):
        """Initialize the orchestrator with Gemini API and all IT tools."""
        self.api_key = Config.GEMINI_API_KEY

        if not self.api_key:
            logging.error("Missing GEMINI_API_KEY configuration.")
            raise ValueError("Gemini configuration missing.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = 'gemini-2.5-flash'
        self.tools = self._define_all_tools()

        # Get direct access to ALL tools (Freshservice, Meraki, Intune)
        self.unified_tools = get_unified_tools()

    def _define_all_tools(self) -> types.Tool:
        """
        Define ALL tool schemas for Gemini (Freshservice, Meraki, Intune).

        These schemas tell Gemini what tools are available and how to use them.
        Gemini will intelligently choose which tool to call based on the user's query.
        """

        # === FRESHSERVICE TOOLS ===

        get_user_email = types.FunctionDeclaration(
            name="get_user_by_email",
            description=(
                "Lookup a Freshservice user (requester or agent) by email to get their numeric ID. "
                "Use this when you have an email address."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "email": types.Schema(
                        type=types.Type.STRING,
                        description="The email address to search for."
                    )
                },
                required=["email"]
            )
        )

        get_user_name = types.FunctionDeclaration(
            name="get_user_by_name",
            description=(
                "Search for Freshservice users by first and/or last name. "
                "Use this when you have a person's name but not their email. "
                "Returns a list of matching users."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "first_name": types.Schema(
                        type=types.Type.STRING,
                        description="The first name to search for (optional if last_name provided)."
                    ),
                    "last_name": types.Schema(
                        type=types.Type.STRING,
                        description="The last name to search for (optional if first_name provided)."
                    )
                }
            )
        )

        list_tickets = types.FunctionDeclaration(
            name="list_tickets",
            description="List support tickets associated with a specific user or agent ID.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "requester_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Optional. The numeric ID of the requester (user)."
                    ),
                    "agent_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Optional. The numeric ID of the agent (tech)."
                    )
                }
            )
        )

        list_assets = types.FunctionDeclaration(
            name="list_assets",
            description="List IT assets (hardware/software) assigned to a specific user ID.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "user_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The numeric ID of the user to check assets for."
                    )
                },
                required=["user_id"]
            )
        )

        list_changes = types.FunctionDeclaration(
            name="list_recent_changes",
            description=(
                "List recent Change Requests to check for planned maintenance or outages. "
                "Use this when users report widespread issues or connectivity problems."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={}  # No parameters required
            )
        )

        get_ticket_by_id = types.FunctionDeclaration(
            name="get_ticket_by_id",
            description="Get details about a specific ticket by its ID number.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticket_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The numeric ticket ID."
                    )
                },
                required=["ticket_id"]
            )
        )

        get_asset_by_id = types.FunctionDeclaration(
            name="get_asset_by_id",
            description="Get details about a specific IT asset by its ID number.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "asset_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The numeric asset ID."
                    )
                },
                required=["asset_id"]
            )
        )

        create_ticket = types.FunctionDeclaration(
            name="create_ticket",
            description=(
                "Create a new support ticket in Freshservice. "
                "Use this to log issues, requests, or incidents for users."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "subject": types.Schema(
                        type=types.Type.STRING,
                        description="The ticket subject/title (concise summary)."
                    ),
                    "description": types.Schema(
                        type=types.Type.STRING,
                        description="Detailed description of the issue or request."
                    ),
                    "requester_email": types.Schema(
                        type=types.Type.STRING,
                        description="Email address of the person requesting support."
                    ),
                    "priority": types.Schema(
                        type=types.Type.INTEGER,
                        description="Priority level: 1=Low, 2=Medium, 3=High, 4=Urgent. Default is 1."
                    ),
                    "status": types.Schema(
                        type=types.Type.INTEGER,
                        description="Ticket status: 2=Open, 3=Pending, 4=Resolved, 5=Closed. Default is 2."
                    ),
                    "group_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Optional group/queue ID to assign the ticket to."
                    ),
                    "category": types.Schema(
                        type=types.Type.STRING,
                        description="Optional category name for the ticket."
                    )
                },
                required=["subject", "description", "requester_email"]
            )
        )

        # === SOLUTIONS (KNOWLEDGE BASE) TOOLS ===

        search_solution_articles = types.FunctionDeclaration(
            name="search_solution_articles",
            description=(
                "Search the Freshservice knowledge base for solution articles by keyword or phrase. "
                "Use this to find how-to guides, troubleshooting steps, and answers to common questions. "
                "ALWAYS USE THIS FIRST before creating a ticket for common issues like password resets, VPN setup, etc."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="The search query/keywords to find relevant articles."
                    ),
                    "limit": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum number of results to return (default 10)."
                    )
                },
                required=["query"]
            )
        )
        # === NEW PHASE 2 TOOLS ===

        update_ticket = types.FunctionDeclaration(
            name="update_ticket",
            description=(
                "Update an existing ticket's status, priority, or assignment. "
                "Use this to change ticket properties after creation."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticket_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The ticket ID to update."
                    ),
                    "status": types.Schema(
                        type=types.Type.INTEGER,
                        description="New status (2=Open, 3=Pending, 4=Resolved, 5=Closed)."
                    ),
                    "priority": types.Schema(
                        type=types.Type.INTEGER,
                        description="New priority (1=Low, 2=Medium, 3=High, 4=Urgent)."
                    ),
                    "agent_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Assign to agent ID."
                    ),
                    "group_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Assign to group/queue ID."
                    )
                },
                required=["ticket_id"]
            )
        )

        add_ticket_note = types.FunctionDeclaration(
            name="add_ticket_note",
            description=(
                "Add a note or comment to an existing ticket. "
                "Use this to update ticket progress or communicate with the requester."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticket_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The ticket ID."
                    ),
                    "body": types.Schema(
                        type=types.Type.STRING,
                        description="The note content."
                    ),
                    "private": types.Schema(
                        type=types.Type.BOOLEAN,
                        description="Whether note is private (internal only). Default false."
                    )
                },
                required=["ticket_id", "body"]
            )
        )

        get_ticket_conversations = types.FunctionDeclaration(
            name="get_ticket_conversations",
            description=(
                "Get all conversations and notes for a ticket to see communication history."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticket_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The ticket ID."
                    )
                },
                required=["ticket_id"]
            )
        )

        get_asset_software = types.FunctionDeclaration(
            name="get_asset_software",
            description=(
                "Get software installed on an asset for license compliance and inventory. "
                "Uses FreshService's built-in asset-software relationship tracking."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "asset_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The asset ID."
                    )
                },
                required=["asset_id"]
            )
        )

        get_asset_contracts = types.FunctionDeclaration(
            name="get_asset_contracts",
            description=(
                "Get contracts (warranty, support) associated with an asset. "
                "Uses FreshService's built-in asset-contract relationship tracking."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "asset_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The asset ID."
                    )
                },
                required=["asset_id"]
            )
        )

        list_service_items = types.FunctionDeclaration(
            name="list_service_items",
            description=(
                "List available service catalog items (pre-configured service requests with workflows). "
                "Use this when users want to request standard services like access, provisioning, etc."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "category_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Optional category ID to filter items."
                    ),
                    "search_query": types.Schema(
                        type=types.Type.STRING,
                        description="Optional search term."
                    )
                }
            )
        )

        get_service_item = types.FunctionDeclaration(
            name="get_service_item",
            description=(
                "Get detailed information about a service catalog item including required custom fields."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "item_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The service item ID."
                    )
                },
                required=["item_id"]
            )
        )

        create_service_request = types.FunctionDeclaration(
            name="create_service_request",
            description=(
                "Create a service request from catalog item. "
                "This leverages FreshService's built-in workflows with approvals, automation, and fulfillment tracking."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "service_item_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The service item ID."
                    ),
                    "requester_email": types.Schema(
                        type=types.Type.STRING,
                        description="Email of requester."
                    ),
                    "custom_fields": types.Schema(
                        type=types.Type.OBJECT,
                        description="Item-specific custom fields as key-value pairs."
                    )
                },
                required=["service_item_id", "requester_email"]
            )
        )

        list_service_categories = types.FunctionDeclaration(
            name="list_service_categories",
            description="List all service catalog categories to explore available services.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={}
            )
        )

        get_service_request_status = types.FunctionDeclaration(
            name="get_service_request_status",
            description=(
                "Get status of a service request including approval and fulfillment progress."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "service_request_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The service request ID."
                    )
                },
                required=["service_request_id"]
            )
        )

        list_problems = types.FunctionDeclaration(
            name="list_problems",
            description=(
                "List known problems (root causes of recurring incidents). "
                "Use this to check if a reported issue is already known."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "status": types.Schema(
                        type=types.Type.INTEGER,
                        description="Filter by status (1=Open, 2=Change Requested, 3=Closed)."
                    ),
                    "priority": types.Schema(
                        type=types.Type.INTEGER,
                        description="Filter by priority (1=Low, 2=Medium, 3=High, 4=Urgent)."
                    ),
                    "impact": types.Schema(
                        type=types.Type.INTEGER,
                        description="Filter by impact (1=Low, 2=Medium, 3=High)."
                    ),
                    "limit": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum number of results (default 10)."
                    )
                }
            )
        )

        get_problem_by_id = types.FunctionDeclaration(
            name="get_problem_by_id",
            description="Get detailed information about a specific problem including root cause analysis.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "problem_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The problem ID."
                    )
                },
                required=["problem_id"]
            )
        )

        link_ticket_to_problem = types.FunctionDeclaration(
            name="link_ticket_to_problem",
            description=(
                "Associate a ticket with a known problem for impact tracking. "
                "When problem is resolved, all linked tickets are automatically updated."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ticket_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The ticket ID."
                    ),
                    "problem_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The problem ID."
                    )
                },
                required=["ticket_id", "problem_id"]
            )
        )

        get_problem_tickets = types.FunctionDeclaration(
            name="get_problem_tickets",
            description="Get all tickets associated with a problem to understand scope/impact.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "problem_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The problem ID."
                    )
                },
                required=["problem_id"]
            )
        )

        search_problems = types.FunctionDeclaration(
            name="search_problems",
            description=(
                "Search problems by keyword to check if a user's issue matches a known problem."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Search term."
                    ),
                    "limit": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum number of results (default 10)."
                    )
                },
                required=["query"]
            )
        )

        # === SOLUTION OPERATIONS ===
        get_solution_article = types.FunctionDeclaration(
            name="get_solution_article",
            description=(
                "Get the full content of a specific solution article by its ID. "
                "Use this after searching to retrieve detailed step-by-step instructions."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "article_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="The numeric article ID to retrieve."
                    )
                },
                required=["article_id"]
            )
        )

        list_solution_articles = types.FunctionDeclaration(
            name="list_solution_articles",
            description=(
                "Browse solution articles by category or folder. "
                "Use this to explore available knowledge base content."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "folder_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Optional folder ID to filter articles."
                    ),
                    "category_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Optional category ID to filter articles."
                    ),
                    "limit": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum number of articles to return (default 20)."
                    )
                }
            )
        )

        get_popular_articles = types.FunctionDeclaration(
            name="get_popular_articles",
            description=(
                "Get the most popular/viewed solution articles from the knowledge base. "
                "Use this to see what issues are trending or commonly referenced."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "limit": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum number of articles to return (default 10)."
                    )
                }
            )
        )

        list_solution_categories = types.FunctionDeclaration(
            name="list_solution_categories",
            description=(
                "List all solution categories in the knowledge base. "
                "Use this to understand how the knowledge base is organized."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={}  # No parameters required
            )
        )

        list_solution_folders = types.FunctionDeclaration(
            name="list_solution_folders",
            description=(
                "List solution folders within categories. "
                "Use this to browse the knowledge base structure."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "category_id": types.Schema(
                        type=types.Type.INTEGER,
                        description="Optional category ID to filter folders."
                    )
                }
            )
        )

        # === INTUNE TOOLS ===

        reboot_device = types.FunctionDeclaration(
            name="reboot_device",
            description=(
                "Send a remote reboot command to a device via Intune. "
                "IMPORTANT: This is a DESTRUCTIVE action that will interrupt the user. "
                "You must set confirmed=true ONLY if the user has explicitly confirmed the reboot. "
                "If confirmed is false or not provided, return a warning and ask for confirmation."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "serial_number": types.Schema(
                        type=types.Type.STRING,
                        description="The device serial number to reboot."
                    ),
                    "confirmed": types.Schema(
                        type=types.Type.BOOLEAN,
                        description="Set to true ONLY if user explicitly confirmed the reboot action. Default is false."
                    )
                },
                required=["serial_number"]
            )
        )

        return types.Tool(function_declarations=[
            # Freshservice User operations
            get_user_email, get_user_name,
            # Freshservice Ticket operations
            list_tickets, get_ticket_by_id, create_ticket,
            update_ticket, add_ticket_note, get_ticket_conversations,
            # Freshservice Asset operations
            list_assets, get_asset_by_id, get_asset_software, get_asset_contracts,
            # Freshservice Change operations
            list_changes,
            # Service Catalog operations
            list_service_items, get_service_item, create_service_request,
            list_service_categories, get_service_request_status,
            # Problem Management operations
            list_problems, get_problem_by_id, link_ticket_to_problem,
            get_problem_tickets, search_problems,
            # Solution/Knowledge Base operations
            search_solution_articles, get_solution_article, list_solution_articles,
            get_popular_articles, list_solution_categories, list_solution_folders,
            # Intune operations
            reboot_device
        ])

    def process_query(self, user_query: str, user_email: Optional[str] = None) -> str:
        """
        Orchestrate the conversation between user, Gemini, and ALL IT tools.

        Args:
            user_query: The user's question or request
            user_email: Optional email of the current user (for context)

        Returns:
            The final response from Gemini after tool execution

        Raises:
            Exception: If Gemini API fails or tools encounter errors
        """
        # Build system instruction for intelligent routing
        system_instr = (
            "You are an intelligent IT Support Assistant with access to multiple systems:\n"
            "- Freshservice: IT tickets, user info, assets, SOFTWARE, CONTRACTS, change requests, KNOWLEDGE BASE, SERVICE CATALOG, PROBLEMS\n"
            "- Intune: Device management (remote reboot, device status)\n\n"

            "## IMPORTANT: When to Use Tools vs Answer Directly\n\n"

            "**ALWAYS Search Knowledge Base FIRST for:**\n"
            "- How-to questions (How do I reset my password? How do I connect to VPN?)\n"
            "- Common issues (Can't login, forgot password, VPN not working, etc.)\n"
            "- Setup instructions (Setting up email, configuring software, etc.)\n"
            "- Troubleshooting steps (Computer won't start, printer issues, etc.)\n"
            "USE search_solution_articles() to find existing articles before answering!\n\n"

            "**Answer DIRECTLY without tools for:**\n"
            "- General knowledge questions IF no relevant KB article exists\n"
            "- Definitions and explanations of basic IT concepts\n"
            "- Quick troubleshooting advice if KB search returns nothing\n\n"

            "**Use tools for:**\n"
            "- Searching KB: search_solution_articles(), get_solution_article()\n"
            "- Looking up specific tickets, assets, or users in Freshservice\n"
            "- Creating tickets when user is reporting an actual problem or issue\n"
            "- Updating tickets: update_ticket(), add_ticket_note(), get_ticket_conversations()\n"
            "- Asset details: get_asset_software() for installed software, get_asset_contracts() for warranty\n"
            "- Service Catalog: list_service_items(), create_service_request() for standard service requests with workflows\n"
            "- Problem Management: search_problems() to check if issue is a known problem, link_ticket_to_problem() for tracking\n"
            "- Checking if there are planned outages (list_recent_changes)\n"
            "- Rebooting devices via Intune (REQUIRES explicit user confirmation - see below)\n"
            "- Getting data from IT systems (not from your knowledge base)\n\n"

            "**NEW CAPABILITIES:**\n"
            "- Service Catalog: For standard requests (access, provisioning, etc), use list_service_items() and create_service_request()\n"
            "  - Service requests have built-in approval workflows, custom fields, and automatic fulfillment tracking\n"
            "  - Example: 'I need access to X' → list_service_items(search='access') → create_service_request()\n"
            "- Problem Management: Check if recurring issues are known problems\n"
            "  - search_problems(query) finds related known problems\n"
            "  - link_ticket_to_problem() associates tickets with root cause for impact tracking\n"
            "  - Example: User reports 'email down' → search_problems('email') → if found, link ticket to problem\n"
            "- Asset Software & Contracts:\n"
            "  - get_asset_software() shows installed software for license compliance\n"
            "  - get_asset_contracts() shows warranty, support entitlements, renewal dates\n\n"

            "**CRITICAL - Device Reboot Safety:**\n"
            "- Rebooting a device is DISRUPTIVE and will interrupt the user's work\n"
            "- NEVER call reboot_device with confirmed=true unless the user has explicitly said 'yes', 'confirm', 'go ahead', or similar\n"
            "- First call reboot_device with confirmed=false to get a warning message\n"
            "- Present the warning to the user and ask them to confirm\n"
            "- Only after explicit confirmation, call reboot_device with confirmed=true\n\n"

            "**DO NOT create tickets for:**\n"
            "- Simple questions about technology concepts\n"
            "- Requests for information or explanations\n"
            "- General troubleshooting advice\n"
            "- Standard service requests that should use Service Catalog (access provisioning, account setup, etc.)\n"
            "ONLY create tickets when user says things like: 'my laptop is broken', 'I need help with X not working', 'create a ticket for...'\n"
            "ALWAYS search the knowledge base FIRST - you may find a self-service article that solves their issue!\n"
            "For standard requests, check Service Catalog items first - they have pre-configured workflows!\n\n"

            "## How to Handle User Queries\n"
            "When a user asks a question, intelligently choose which tool(s) to use and chain them together:\n\n"

            "**Knowledge Base Workflow (PRIORITY #1):**\n"
            "1. User asks 'How do I reset my password?' → search_solution_articles('password reset') → get_solution_article(id) → provide steps + link\n"
            "2. User asks 'VPN not working' → search_solution_articles('VPN troubleshooting') → show top articles\n"
            "3. Check get_popular_articles() to see what issues are trending\n"
            "4. If article found, provide the solution AND the article URL for reference\n"
            "5. Only create ticket if NO relevant KB article exists\n\n"

            "**Service Catalog Workflow (for standard requests):**\n"
            "1. User asks 'I need access to SharePoint' → list_service_items(search='sharepoint access')\n"
            "2. If service item exists → create_service_request(item_id, requester_email, custom_fields)\n"
            "3. Service requests automatically route through approval workflows and fulfillment\n"
            "4. Track progress with get_service_request_status()\n\n"

            "**Problem Management Workflow (for recurring issues):**\n"
            "1. User reports common issue → search_problems(query) to check if known\n"
            "2. If problem found → get_problem_by_id() for root cause and workaround\n"
            "3. Provide workaround info to user\n"
            "4. Create ticket for tracking → link_ticket_to_problem() for automatic updates\n"
            "5. When problem is resolved, all linked tickets auto-update\n\n"

            "**Looking up users:**\n"
            "- If you see email addresses in the query (especially in [Mentioned users: ...] context), use get_user_by_email\n"
            "- If you see names like 'John Smith' or 'Matt Abbott', use get_user_by_name\n"
            "- The [Mentioned users: ...] section contains emails extracted from Slack @mentions - use these!\n\n"

            "**Filtering results:**\n"
            "- API tools return lists of items (tickets, assets, etc.)\n"
            "- YOU CAN AND SHOULD FILTER THESE RESULTS based on user criteria\n"
            "- Example: list_assets returns asset names like 'Lenovo ThinkPad T14' - filter for 'Lenovo' or 'laptop'\n"
            "- Example: list_tickets returns ticket subjects - filter for keywords the user mentioned\n"
            "- Don't say 'I cannot filter' - you absolutely can filter results after getting them!\n\n"

            "**Multi-step workflows:**\n"
            "1. User asks about 'John's laptop' → call get_user_by_name → get user_id → call list_assets → filter for 'laptop'\n"
            "2. User asks 'what tickets does jane@company.com have?' → call get_user_by_email → call list_tickets\n"
            "3. User mentions asset type (Lenovo, Dell, iPhone) → get ALL assets first, then filter by name\n\n"

            f"**Current user context:**\n"
            f"The requesting user's email is: {user_email if user_email else 'unknown'}\n"
            f"If you need to look up this user, use the email in this context with get_user_by_email.\n\n"

            "Response Requirements\n"
            "- Format: Be concise, friendly, and helpful. Use bulleted lists for multiple results (e.g., tickets, assets).\n"
            "- Detail: Include relevant IDs (Ticket ID, Asset Name, Serial Number).\n"
            "- No Tool Talk: Only mention the final result. Do not reveal the tool calls or the internal system names (Freshservice, Intune) in the final response.\n"
            "- Failure: If you can't find what they're asking for, explain what you checked (e.g., 'I checked your open tickets but found none matching \"VPN\"').\n"
            "- Escalation: If you have run out of relevant ideas or tools, offer to create a ticket using create_ticket with the conversation details to escalate to a real person."
        )

        # Initialize conversation history with user's query
        history = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_query)]
            )
        ]

        max_iterations = 10  # Prevent infinite loops
        final_response = "I'm sorry, I couldn't complete that request."

        for i in range(max_iterations):
            logging.info(f"MCP Orchestrator - Iteration {i + 1}/{max_iterations}")

            try:
                # Ask Gemini to respond (may include tool calls)
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=history,
                    config=types.GenerateContentConfig(
                        tools=[self.tools],
                        system_instruction=system_instr
                    )
                )
            except Exception as e:
                logging.error(f"Gemini API Error: {e}", exc_info=True)
                return f"⚠️ I encountered an error connecting to my AI: {str(e)}"

            # Check if Gemini wants to call a tool
            if response.function_calls:
                # Process the first function call
                tool_call = response.function_calls[0]
                tool_name = tool_call.name
                tool_args = dict(tool_call.args)

                logging.info(f"Executing Tool: {tool_name} with args {tool_args}")

                # Execute tool DIRECTLY (no HTTP request!)
                tool_result = self._execute_tool_directly(tool_name, tool_args)

                # Add the model's tool call to history
                history.append(types.Content(
                    role="model",
                    parts=[types.Part(function_call=tool_call)]
                ))

                # Add the tool result to history
                history.append(types.Content(
                    role="tool",
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response={"result": tool_result}
                        )
                    )]
                ))

                # Continue loop to let Gemini process the result
                continue

            else:
                # No tool call means we have the final answer
                if response.text:
                    final_response = response.text
                else:
                    # Sometimes Gemini returns empty text
                    final_response = "I processed your request but don't have additional information to share."

                break

        return final_response

    def _execute_tool_directly(self, tool_name: str, args: dict) -> any:
        """
        Execute ANY IT tool DIRECTLY (no HTTP call).

        This is much faster and more efficient than making HTTP requests to an external MCP server.
        Routes to the appropriate backend: Freshservice, Meraki, or Intune.

        Args:
            tool_name: The name of the tool to execute
            args: Dictionary of arguments for the tool

        Returns:
            The tool result (could be dict, list, etc.)
        """
        try:
            # SECURITY: Intercept reboot_device and require explicit confirmation
            if tool_name == "reboot_device":
                confirmed = args.get("confirmed", False)
                serial_number = args.get("serial_number", "unknown")

                if not confirmed:
                    # Return a warning instead of executing
                    logging.info(f"Reboot request for {serial_number} - awaiting confirmation")
                    return {
                        "status": "confirmation_required",
                        "message": (
                            f"⚠️ **Reboot Confirmation Required**\n\n"
                            f"You are about to reboot device with serial number: **{serial_number}**\n\n"
                            f"This action will:\n"
                            f"• Immediately restart the device\n"
                            f"• Interrupt any work in progress\n"
                            f"• Disconnect the user from all applications\n\n"
                            f"Please reply with **'yes, reboot'** or **'confirm reboot'** to proceed, "
                            f"or **'cancel'** to abort."
                        ),
                        "serial_number": serial_number
                    }

                # User confirmed - remove 'confirmed' arg before passing to actual tool
                exec_args = {"serial_number": serial_number}
                logging.info(f"Reboot CONFIRMED for device {serial_number} - executing")
                result = self.unified_tools.execute_tool(tool_name, exec_args)
                logging.info(f"Tool {tool_name} executed successfully")
                return result

            # All other tools - execute directly
            result = self.unified_tools.execute_tool(tool_name, args)
            logging.info(f"Tool {tool_name} executed successfully")
            return result

        except ValueError as ve:
            # Tool not found, invalid parameters, or configuration missing
            error_msg = f"Tool Error: {str(ve)}"
            logging.warning(f"Tool execution failed (client error): {ve}")
            return error_msg

        except Exception as ex:
            # Unexpected error (network, API failure, etc.)
            error_msg = f"System Error: Could not execute tool. {str(ex)}"
            logging.error(f"Tool execution failed (server error): {ex}", exc_info=True)
            return error_msg
