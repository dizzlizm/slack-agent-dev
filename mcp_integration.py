import os
import json
import time
import logging
import requests
from google import genai
from google.genai import types
from config import Config # Assuming your Config class handles env vars

class GeminiMCPOrchestrator:
    def __init__(self):
        self.api_key = Config.GEMINI_API_KEY 
        self.mcp_server_url = Config.MCP_TOOL_SERVER_URL
        
        if not self.api_key or not self.mcp_server_url:
            logging.error("Missing GEMINI_API_KEY or MCP_TOOL_SERVER_URL configuration.")
            raise ValueError("Gemini/MCP Configuration missing.")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = 'gemini-2.0-flash'
        self.tools = self._define_freshservice_tools()

    def _define_freshservice_tools(self) -> types.Tool:
        """Defines the Freshservice tool schemas for Gemini."""
        
        # 1. Get User (The crucial first step for most queries)
        get_user = types.FunctionDeclaration(
            name="get_user_by_email",
            description="Lookup a Freshservice user (requester or agent) by email to get their numeric ID. ALWAYS call this first if you only have an email.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "email": types.Schema(type=types.Type.STRING, description="The email address to search for.")
                },
                required=["email"]
            )
        )

        # 2. List Tickets
        list_tickets = types.FunctionDeclaration(
            name="list_tickets",
            description="List support tickets associated with a user or agent ID.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "requester_id": types.Schema(type=types.Type.INTEGER, description="Optional. The numeric ID of the requester (user)."),
                    "agent_id": types.Schema(type=types.Type.INTEGER, description="Optional. The numeric ID of the agent (tech).")
                }
            )
        )

        # 3. List Assets
        list_assets = types.FunctionDeclaration(
            name="list_assets",
            description="List IT assets (hardware/software) assigned to a specific user ID.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "user_id": types.Schema(type=types.Type.INTEGER, description="The numeric ID of the user.")
                },
                required=["user_id"]
            )
        )

        # 4. List Changes
        list_changes = types.FunctionDeclaration(
            name="list_recent_changes",
            description="List recent Change Requests to check for maintenance or outages.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={}, 
            )
        )

        return types.Tool(function_declarations=[get_user, list_tickets, list_assets, list_changes])

    def process_query(self, user_query: str, user_email: str = None) -> str:
        """
        Orchestrates the conversation between User, Gemini, and the Azure MCP Server.
        """
        # System prompt to give the bot context and helpful behaviors
        system_instr = (
            "You are a helpful IT Support Assistant integrated with Freshservice. "
            "Use the available tools to look up information. "
            "If you are looking up tickets or assets for the current user, try to find their ID using their email first. "
            f"The current user's email is: {user_email if user_email else 'unknown'}."
        )

        history = [types.Content(role="user", parts=[types.Part.from_text(text=user_query)])]
        
        max_iterations = 8
        final_response = "I'm sorry, I couldn't complete that request."

        for i in range(max_iterations):
            logging.info(f"MCP Orchestrator Iteration {i+1}")
            
            try:
                # Ask Gemini
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=history,
                    config=types.GenerateContentConfig(
                        tools=[self.tools],
                        system_instruction=system_instr
                    )
                )
            except Exception as e:
                logging.error(f"Gemini API Error: {e}")
                return f"⚠️ I encountered an error talking to my AI brain: {str(e)}"

            # Check for Tool Calls
            if response.function_calls:
                # We only handle the first call in the list for simplicity in this loop
                tool_call = response.function_calls[0]
                tool_name = tool_call.name
                tool_args = dict(tool_call.args)
                
                logging.info(f"Executing Tool: {tool_name} with {tool_args}")
                
                # Execute against Azure MCP Server
                tool_result = self._call_azure_mcp_server(tool_name, tool_args)
                
                # Add interaction to history so Gemini sees the result
                history.append(types.Content(
                    role="model", 
                    parts=[types.Part(function_call=tool_call)]
                ))
                
                history.append(types.Content(
                    role="tool", 
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=tool_name,
                            response={"result": tool_result}
                        )
                    )]
                ))
            else:
                # No tool call means we have the final answer
                if response.text:
                    final_response = response.text
                break
        
        return final_response

    def _call_azure_mcp_server(self, tool_name: str, args: dict) -> any:
        """Sends the JSON-RPC request to the remote Azure Function."""
        payload = {
            "jsonrpc": "2.0",
            "method": tool_name,
            "params": args,
            "id": f"slack-{int(time.time())}"
        }
        
        try:
            resp = requests.post(self.mcp_server_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            if "error" in data:
                return f"Tool Error: {data['error']['message']}"
            return data.get("result")
            
        except Exception as e:
            logging.error(f"Azure MCP Server Call Failed: {e}")
            return f"System Error: Could not reach IT tools server. {str(e)}"