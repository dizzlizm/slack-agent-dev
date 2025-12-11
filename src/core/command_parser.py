"""
Command routing and parsing for Slack bot commands.
"""
import logging
import re
from typing import Optional, Tuple, Callable, Dict
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


# Command validation helpers

def require_args(parsed_command: ParsedCommand, min_args: int) -> None:
    """
    Ensure command has minimum number of arguments.
    
    Args:
        parsed_command: The parsed command
        min_args: Minimum number of required arguments
        
    Raises:
        InvalidCommandError: If not enough arguments
    """
    if len(parsed_command.args) < min_args:
        raise InvalidCommandError(
            f"Command '{parsed_command.command}' requires at least {min_args} arguments"
        )


def validate_password_strength(password: str) -> None:
    """
    Validate password meets minimum requirements.
    
    Args:
        password: The password to validate
        
    Raises:
        InvalidCommandError: If password is too weak
    """
    if len(password) < 8:
        raise InvalidCommandError(
            "Password must be at least 8 characters long"
        )
    
    # Add more validation as needed
    # if not any(c.isupper() for c in password):
    #     raise InvalidCommandError("Password must contain at least one uppercase letter")


def parse_meraki_update_command(text: str) -> Tuple[str, str]:
    """
    Parse a Meraki SSID update command.
    
    Args:
        text: The command text
        
    Returns:
        Tuple of (ssid_name, new_password)
        
    Raises:
        InvalidCommandError: If command format is invalid
    """
    pattern = re.compile(
        r'update\s+ssid\s+"([^"]+)"\s+password\s+"([^"]+)"',
        re.IGNORECASE
    )
    
    match = pattern.search(text)
    
    if not match:
        raise InvalidCommandError(
            'Invalid command format',
            'meraki update ssid "SSID Name" password "New Password"'
        )
    
    ssid_name = match.group(1)
    password = match.group(2)
    
    validate_password_strength(password)
    
    return ssid_name, password


def parse_intune_command(parsed_command: ParsedCommand) -> Tuple[str, str]:
    """
    Parse an Intune command.
    
    Args:
        parsed_command: The parsed command
        
    Returns:
        Tuple of (subcommand, serial_number)
        
    Raises:
        InvalidCommandError: If command format is invalid
    """
    require_args(parsed_command, 2)
    
    subcommand = parsed_command.args[0].lower()
    
    if subcommand != "reboot":
        raise InvalidCommandError(
            f"Unknown intune subcommand: {subcommand}",
            'intune reboot "SerialNumber"'
        )
    
    # Serial number might be quoted
    serial_number = parsed_command.args[1].strip('"')
    
    if not serial_number:
        raise InvalidCommandError(
            "Serial number cannot be empty",
            'intune reboot "SerialNumber"'
        )
    
    return subcommand, serial_number


def parse_admin_command(parsed_command: ParsedCommand) -> Tuple[str, str]:
    """
    Parse an admin command.
    
    Args:
        parsed_command: The parsed command
        
    Returns:
        Tuple of (subcommand, user_id)
        
    Raises:
        InvalidCommandError: If command format is invalid
    """
    require_args(parsed_command, 2)
    
    subcommand = parsed_command.args[0].lower()
    
    if subcommand not in ["add", "remove"]:
        raise InvalidCommandError(
            f"Unknown admin subcommand: {subcommand}",
            'admin add @user OR admin remove @user'
        )
    
    # Extract user mention
    parser = CommandParser()
    mentions = parser.extract_mentions(parsed_command.raw_text)
    
    if not mentions:
        raise InvalidCommandError(
            "Please mention a valid Slack user",
            'admin add @user'
        )
    
    target_user_id = mentions[0]
    
    return subcommand, target_user_id


def parse_fresh_ticket_command(text: str) -> str:
    """
    Parse a Freshservice ticket creation command.
    
    Args:
        text: The command text
        
    Returns:
        The raw ticket description text
        
    Raises:
        InvalidCommandError: If command format is invalid
    """
    pattern = re.compile(
        r'new\s+ticket\s+(.+)',
        re.IGNORECASE | re.DOTALL
    )
    
    match = pattern.search(text)
    
    if not match:
        raise InvalidCommandError(
            'Invalid command format',
            'fresh new ticket "Your problem description"'
        )
    
    raw_text = match.group(1).strip().strip('"')
    
    if not raw_text:
        raise InvalidCommandError(
            "Ticket description cannot be empty",
            'fresh new ticket "Your problem description"'
        )
    
    return raw_text
