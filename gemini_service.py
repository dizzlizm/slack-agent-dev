"""
Gemini AI service wrapper for LLM operations.
"""
import logging
import json
import time
from typing import Optional, List, Dict
import google.generativeai as genai

from config import Config
from models import (
    ConversationHistory,
    TriageDecision,
    TroubleshootStep,
    TicketInfo,
    TriageSession
)
from exceptions import ExternalAPIError, IntegrationNotConfiguredError


class GeminiService:
    """Service for interacting with Google's Gemini AI."""
    
    def __init__(self):
        if not Config.is_gemini_enabled():
            raise IntegrationNotConfiguredError("Gemini AI")
        
        genai.configure(api_key=Config.GEMINI_API_KEY)
        logging.info("Gemini service initialized")
    
    def _call_model(
        self,
        model_name: str,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.7,
        json_mode: bool = False,
        history: Optional[List[Dict]] = None
    ) -> str:
        """
        Call a Gemini model with error handling and retry logic.
        
        Args:
            model_name: The model to use
            prompt: The prompt to send
            system_instruction: System instruction for the model
            temperature: Sampling temperature
            json_mode: Whether to request JSON output
            history: Optional conversation history
            
        Returns:
            The model's response text
            
        Raises:
            ExternalAPIError: If the API call fails
        """
        try:
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": 8192
            }
            
            if json_mode:
                generation_config["response_mime_type"] = "application/json"
            
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction,
                generation_config=generation_config
            )
            
            if history:
                chat = model.start_chat(history=history)
                response = chat.send_message(prompt)
            else:
                response = model.generate_content(prompt)
            
            return response.text
            
        except Exception as e:
            logging.error(f"Gemini API error: {e}")
            raise ExternalAPIError("Gemini", details=str(e))
    
    def ask_question(
        self,
        question: str,
        conversation_history: ConversationHistory
    ) -> tuple[str, int]:
        """
        Answer a user's question with conversation context.
        
        Args:
            question: The user's question
            conversation_history: Previous conversation context
            
        Returns:
            Tuple of (answer, response_time_ms)
        """
        start_time = time.time()
        
        system_prompt = (
            "You are a technical mastermind who only gives short, concise answers. "
            "If you don't know the answer, say 'I don't know'."
        )
        
        gemini_history = conversation_history.to_gemini_format()
        
        answer = self._call_model(
            model_name=Config.GEMINI_MODEL_ASK,
            prompt=question,
            system_instruction=system_prompt,
            temperature=0.7,
            history=gemini_history
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        return answer, response_time_ms
    
    def make_triage_decision(self, message_text: str) -> TriageDecision:
        """
        Analyze a support request and decide if it needs triage.
        
        Args:
            message_text: The user's support request
            
        Returns:
            TriageDecision object
        """
        system_prompt = """
You are an IT support triage bot. Your job is to analyze a new support request and start a troubleshooting conversation.
Respond ONLY with a JSON object:
{
  "requires_ticket": boolean,
  "suggested_title": string | null,
  "initial_description": string | null,
  "first_question": string | null
}

- "requires_ticket": true if this is a new, actionable support request.
- "suggested_title": A short, 5-10 word ticket title (e.g., "Laptop fan making noise").
- "initial_description": A 2-3 sentence summary of the user's issue.
- "first_question": The *single most important* first question to ask the user (e.g., "Have you tried rebooting the device?", "Is this happening on Wi-Fi or when docked?").

If 'requires_ticket' is false, all other fields should be null.
"""
        
        response_text = self._call_model(
            model_name=Config.GEMINI_MODEL_TRIAGE,
            prompt=message_text,
            system_instruction=system_prompt,
            temperature=0.2,
            json_mode=True
        )
        
        try:
            data = json.loads(response_text)
            return TriageDecision(
                requires_ticket=data.get("requires_ticket", False),
                suggested_title=data.get("suggested_title"),
                initial_description=data.get("initial_description"),
                first_question=data.get("first_question")
            )
        except (json.JSONDecodeError, KeyError) as e:
            logging.error(f"Failed to parse triage decision: {response_text}")
            raise ExternalAPIError("Gemini", details=f"Invalid JSON response: {e}")
    
    def get_troubleshoot_step(
        self,
        session: TriageSession,
        user_reply: str
    ) -> TroubleshootStep:
        """
        Get the next troubleshooting step based on user's reply.
        
        Args:
            session: The current triage session
            user_reply: The user's latest reply
            
        Returns:
            TroubleshootStep object
        """
        system_prompt = f"""
You are an IT support bot in the middle of a troubleshooting session.
The user's original issue is summarized as: "{session.suggested_title}"
The current ticket description is: "{session.description}"

Continue the conversation based on the history. Respond ONLY with a JSON object:
{{
  "next_question": string | null,
  "updated_description": string | null,
  "suggestions_exhausted": boolean,
  "is_resolved": boolean
}}

- "next_question": The next logical question to ask. If you are escalating or resolving, this should be a concluding statement.
- "updated_description": An updated summary of the issue *only if the user provided significant new info*. If the user just said 'yes' or 'no', send null.
- "suggestions_exhausted": Set to true *only* if you have no more ideas and it's time to create a ticket.
- "is_resolved": Set to true *only* if the user's reply indicates the issue is fixed.
- If the user's last message is simple (like 'yes', 'no', 'ok', 'idk'), focus on providing the "next_question" based on *your* last question.
- Never ask if there is anything else you can help with. Always either ask a specific next question, escalate, or resolve.
"""
        
        # Build history including the new user reply
        gemini_history = session.to_gemini_format()
        gemini_history.append({
            "role": "user",
            "parts": [{"text": user_reply}]
        })
        
        response_text = self._call_model(
            model_name=Config.GEMINI_MODEL_TRIAGE,
            prompt=user_reply,
            system_instruction=system_prompt,
            temperature=0.3,
            json_mode=True,
            history=gemini_history[:-1]  # History without the last user message
        )
        
        try:
            if not response_text or not response_text.strip().startswith('{'):
                raise ValueError(f"Non-JSON response: {response_text}")
            
            data = json.loads(response_text)
            return TroubleshootStep(
                next_question=data.get("next_question"),
                updated_description=data.get("updated_description"),
                suggestions_exhausted=data.get("suggestions_exhausted", False),
                is_resolved=data.get("is_resolved", False)
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.error(f"Failed to parse troubleshoot step: {response_text}")
            # Return a safe fallback instead of crashing
            return TroubleshootStep(
                next_question="I'm sorry, I had a temporary error. Could you please rephrase that or try again?",
                updated_description=None,
                suggestions_exhausted=False,
                is_resolved=False
            )
    
    def parse_ticket_request(self, raw_text: str) -> TicketInfo:
        """
        Parse a natural language ticket creation request.
        
        Args:
            raw_text: The user's ticket request
            
        Returns:
            TicketInfo object with title and description
        """
        system_prompt = (
            "You are an IT support assistant. Your job is to parse a user's request into a JSON object "
            "for a new ticket. The JSON must have two keys: 'title' and 'description'. "
            "The 'title' should be a short, clear summary of the problem (max 10 words). "
            "The 'description' should be the user's *full, original, un-modified text* to ensure all details are captured. "
            "Respond ONLY with the JSON object."
        )
        
        response_text = self._call_model(
            model_name=Config.GEMINI_MODEL_TICKET,
            prompt=raw_text,
            system_instruction=system_prompt,
            temperature=0.1,
            json_mode=True
        )
        
        try:
            data = json.loads(response_text)
            return TicketInfo(
                title=data.get("title", "New Ticket (Title Generated by AI)"),
                description=data.get("description", raw_text)
            )
        except (json.JSONDecodeError, KeyError) as e:
            logging.error(f"Failed to parse ticket info: {response_text}")
            # Return a sensible fallback
            return TicketInfo(
                title="New Support Request",
                description=raw_text
            )
