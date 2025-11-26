"""
Optimized MCP Integration for Gemini + All IT Tools.

This module provides an orchestrator that connects Google Gemini AI with all IT tools:
- Freshservice (tickets, users, assets, changes)
- Meraki (WiFi management)
- Intune (device management)

It uses DIRECT function calls for maximum performance instead of HTTP requests.
"""
import logging
from typing import Optional
from google import genai
from google.genai import types

from config import Config
from mcp_tools import get_unified_tools


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
        self.model_name = 'gemini-2.0-flash'
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

        # === INTUNE TOOLS ===

        reboot_device = types.FunctionDeclaration(
            name="reboot_device",
            description=(
                "Send a remote reboot command to a device via Intune. "
                "Use this when a device needs to be restarted remotely for troubleshooting."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "serial_number": types.Schema(
                        type=types.Type.STRING,
                        description="The device serial number to reboot."
                    )
                },
                required=["serial_number"]
            )
        )

        return types.Tool(function_declarations=[
            # Freshservice (8 tools)
            get_user_email, get_user_name, list_tickets, list_assets, list_changes,
            get_ticket_by_id, get_asset_by_id, create_ticket,
            # Intune (1 tool)
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
            "- Freshservice: IT tickets, user info, assets, change requests\n"
            "- Intune: Device management (remote reboot, device status)\n\n"

            "## IMPORTANT: When to Use Tools vs Answer Directly\n\n"

            "**Answer DIRECTLY without tools for:**\n"
            "- General knowledge questions (What is VPN? How does DHCP work? What is MFA?)\n"
            "- How-to questions (How do I reset my password? How do I connect to VPN?)\n"
            "- Troubleshooting advice (Try restarting your computer, clear your cache, etc.)\n"
            "- Definitions and explanations\n"
            "- ANY question that starts with 'what is', 'how do I', 'why does', etc.\n\n"

            "**Use tools ONLY for:**\n"
            "- Looking up specific tickets, assets, or users in Freshservice\n"
            "- Creating tickets when user is reporting an actual problem or issue\n"
            "- Checking if there are planned outages (list_recent_changes)\n"
            "- Rebooting devices via Intune\n"
            "- Getting data from IT systems (not from your knowledge base)\n\n"

            "**DO NOT create tickets for:**\n"
            "- Simple questions about technology concepts\n"
            "- Requests for information or explanations\n"
            "- General troubleshooting advice\n"
            "ONLY create tickets when user says things like: 'my laptop is broken', 'I need help with X not working', 'create a ticket for...'\n\n"

            "## How to Handle User Queries\n"
            "When a user asks a question, intelligently choose which tool(s) to use and chain them together:\n\n"

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
            f"Use this when they ask about 'my tickets' or 'my assets'.\n\n"

            "**Response style:**\n"
            "- Be concise, friendly, and helpful\n"
            "- When showing multiple items, format them as a bulleted list\n"
            "- Include relevant details (ticket IDs, asset names, etc.)\n"
            "- If you can't find what they're asking for, explain what you checked and suggest alternatives"
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
            # Call the tool directly using our UnifiedTools instance
            # It will automatically route to the correct backend (Freshservice/Meraki/Intune)
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
