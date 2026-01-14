"""
Command routing and parsing for Slack bot commands.
"""
import logging
import re
from typing import Optional, Callable, Dict
from dataclasses import dataclass

from src.config import Config
from src.exceptions import InvalidCommandError


@dataclass
class ParsedCommand:
    """Represents a parsed Slack command."""
    command: str
    args: list[str]
    raw_text: str
    user_id: str
    channel_id: str
    thread_ts: Optional[str] = None

    @property
    def args_text(self) -> str:
        """
        Get the text of all arguments as a single string.
        Extracts everything after the bot mention and command name.
        """
        # Remove bot mention and command from raw text
        parts = self.raw_text.split(maxsplit=2)
        if len(parts) > 2:
            # parts[0] = bot mention, parts[1] = command, parts[2] = rest
            return parts[2]
        return ""


class CommandParser:
    """Parses Slack messages into structured commands."""
    
    def __init__(self):
        self.bot_mention = f"<@{Config.SLACK_BOT_USER_ID}>"
    
    def is_bot_mention(self, text: str) -> bool:
        """Check if message starts with bot mention."""
        return text.strip().startswith(self.bot_mention)
    
    def parse_mention_command(
        self,
        text: str,
        user_id: str,
        channel_id: str,
        thread_ts: Optional[str] = None
    ) -> Optional[ParsedCommand]:
        """
        Parse a command from a bot mention.
        
        Args:
            text: The message text
            user_id: The user who sent the message
            channel_id: The channel ID
            thread_ts: Optional thread timestamp
            
        Returns:
            ParsedCommand if valid, None if just a mention
        """
        if not self.is_bot_mention(text):
            return None
        
        # Remove bot mention and split
        parts = text.split()
        
        if len(parts) < 2:
            # Just a mention, no command
            return None
        
        command = parts[1].lower()
        args = parts[2:] if len(parts) > 2 else []
        
        return ParsedCommand(
            command=command,
            args=args,
            raw_text=text,
            user_id=user_id,
            channel_id=channel_id,
            thread_ts=thread_ts
        )
    
    def extract_quoted_args(self, text: str) -> list[str]:
        """
        Extract arguments enclosed in double quotes.
        
        Args:
            text: The text to parse
            
        Returns:
            List of quoted strings
        """
        # Match anything inside double quotes
        pattern = r'"([^"]*)"'
        matches = re.findall(pattern, text)
        return matches
    
    def extract_mentions(self, text: str) -> list[str]:
        """
        Extract user mentions from text.
        
        Args:
            text: The text to parse
            
        Returns:
            List of user IDs
        """
        pattern = r'<@([A-Z0-9]+)(?:\|[^>]+)?>'
        matches = re.findall(pattern, text)
        return matches


class CommandRouter:
    """Routes commands to appropriate handlers."""

    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.default_handler: Optional[Callable] = None
        self.parser = CommandParser()

    def register(self, command: str, handler: Callable) -> None:
        """
        Register a command handler.

        Args:
            command: The command name
            handler: The handler function
        """
        self.handlers[command] = handler
        logging.debug(f"Registered handler for command: {command}")

    def set_default_handler(self, handler: Callable) -> None:
        """
        Set a default handler for unknown commands.

        Args:
            handler: The default handler function
        """
        self.default_handler = handler
        logging.debug("Registered default handler for unknown commands")

    def route(self, parsed_command: ParsedCommand) -> Callable:
        """
        Get the handler for a command.

        Args:
            parsed_command: The parsed command

        Returns:
            The handler function

        Raises:
            InvalidCommandError: If command is not recognized and no default handler
        """
        handler = self.handlers.get(parsed_command.command)

        if not handler:
            # Use default handler if available
            if self.default_handler:
                return self.default_handler

            available_commands = ", ".join(sorted(self.handlers.keys()))
            raise InvalidCommandError(
                f"Unknown command: {parsed_command.command}",
                f"@{Config.SLACK_BOT_USER_ID} help"
            )

        return handler
    
    def get_available_commands(self) -> list[str]:
        """Get list of all registered commands."""
        return sorted(self.handlers.keys())
