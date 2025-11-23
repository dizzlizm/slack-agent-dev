"""
Data models for the Slack bot application.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime
import json


@dataclass
class ConversationMessage:
    """Represents a single message in a conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ConversationHistory:
    """Manages conversation history for a user."""
    user_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation."""
        self.messages.append(ConversationMessage(role=role, content=content))
        self.last_updated = datetime.utcnow()
    
    def get_last_n_messages(self, n: int) -> List[ConversationMessage]:
        """Get the last N messages."""
        return self.messages[-n:] if n > 0 else self.messages
    
    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []
        self.last_updated = datetime.utcnow()
    
    def to_json(self) -> str:
        """Convert to JSON string for storage."""
        return json.dumps([msg.to_dict() for msg in self.messages])
    
    @classmethod
    def from_json(cls, user_id: str, json_str: str) -> 'ConversationHistory':
        """Create from JSON string."""
        try:
            messages_data = json.loads(json_str)
            messages = [ConversationMessage(**msg) for msg in messages_data]
            return cls(user_id=user_id, messages=messages)
        except (json.JSONDecodeError, TypeError):
            return cls(user_id=user_id, messages=[])
    
    def to_gemini_format(self) -> List[Dict]:
        """Convert to Gemini API format."""
        return [
            {
                "role": "model" if msg.role == "assistant" else msg.role,
                "parts": [{"text": msg.content}]
            }
            for msg in self.messages
        ]


@dataclass
class TriageSession:
    """Represents an active troubleshooting triage session."""
    channel_id: str
    thread_ts: str
    original_user_id: str
    status: str  # "active", "resolved", "escalated"
    suggested_title: str
    description: str
    history: List[ConversationMessage] = field(default_factory=list)
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the triage history."""
        self.history.append(ConversationMessage(role=role, content=content))
        self.last_updated = datetime.utcnow()
    
    def is_active(self) -> bool:
        """Check if the session is still active."""
        return self.status == "active"
    
    def is_stale(self, timeout_hours: int) -> bool:
        """Check if the session has timed out."""
        if not self.last_updated:
            return False
        delta = datetime.utcnow() - self.last_updated
        return delta.total_seconds() / 3600 > timeout_hours
    
    def to_storage_entity(self) -> dict:
        """Convert to Azure Table Storage entity format."""
        return {
            "PartitionKey": self.channel_id,
            "RowKey": self.thread_ts,
            "OriginalUserID": self.original_user_id,
            "Status": self.status,
            "SuggestedTitle": self.suggested_title,
            "UpdatedDescription": self.description,
            "History": json.dumps([msg.to_dict() for msg in self.history]),
            "CreatedAt": self.created_at.isoformat() if self.created_at else None,
            "LastUpdated": self.last_updated.isoformat() if self.last_updated else None
        }
    
    @classmethod
    def from_storage_entity(cls, entity: dict) -> 'TriageSession':
        """Create from Azure Table Storage entity."""
        try:
            history_data = json.loads(entity.get("History", "[]"))
            history = [ConversationMessage(**msg) for msg in history_data]
        except (json.JSONDecodeError, TypeError):
            history = []
        
        created_at = None
        if created_str := entity.get("CreatedAt"):
            try:
                created_at = datetime.fromisoformat(created_str)
            except (ValueError, TypeError):
                pass
        
        last_updated = None
        if updated_str := entity.get("LastUpdated"):
            try:
                last_updated = datetime.fromisoformat(updated_str)
            except (ValueError, TypeError):
                pass
        
        return cls(
            channel_id=entity.get("PartitionKey", ""),
            thread_ts=entity.get("RowKey", ""),
            original_user_id=entity.get("OriginalUserID", ""),
            status=entity.get("Status", "active"),
            suggested_title=entity.get("SuggestedTitle", ""),
            description=entity.get("UpdatedDescription", ""),
            history=history,
            created_at=created_at,
            last_updated=last_updated
        )
    
    def to_gemini_format(self) -> List[Dict]:
        """Convert history to Gemini API format."""
        return [
            {
                "role": "model" if msg.role == "assistant" else msg.role,
                "parts": [{"text": msg.content}]
            }
            for msg in self.history
        ]


@dataclass
class TriageDecision:
    """Represents the initial triage decision from the LLM."""
    requires_ticket: bool
    suggested_title: Optional[str] = None
    initial_description: Optional[str] = None
    first_question: Optional[str] = None


@dataclass
class TroubleshootStep:
    """Represents a troubleshooting step decision from the LLM."""
    next_question: Optional[str] = None
    updated_description: Optional[str] = None
    suggestions_exhausted: bool = False
    is_resolved: bool = False


@dataclass
class TicketInfo:
    """Represents parsed ticket information."""
    title: str
    description: str
