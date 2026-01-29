"""
Unified Freshservice tools interface.
Aggregates all Freshservice operations into a single tools class.
"""
from typing import Dict, List, Any, Optional

from .users import UserOperations
from .tickets import TicketOperations
from .assets import AssetOperations
from .changes import ChangeOperations
from .solutions import SolutionOperations


class FreshserviceTools:
    """
    Unified Freshservice tool implementations.
    These can be called directly (for internal use) or via JSON-RPC (for external MCP).
    """

    def __init__(self):
        """Initialize all Freshservice operation modules."""
        self._users = UserOperations()
        self._tickets = TicketOperations()
        self._assets = AssetOperations()
        self._changes = ChangeOperations()
        self._solutions = SolutionOperations()

    # --- USER OPERATIONS ---

    def get_user_by_email(self, email: str) -> Dict[str, Any]:
        """
        Finds a requester or agent by email to get their ID.

        Args:
            email: The email address to search for

        Returns:
            Dictionary with user information including id, first_name, last_name, type, email
        """
        return self._users.get_user_by_email(email)

    def get_user_by_name(
        self, first_name: Optional[str] = None, last_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for users by first and/or last name.

        Args:
            first_name: Optional first name to search for
            last_name: Optional last name to search for

        Returns:
            List of matching user dictionaries
        """
        return self._users.get_user_by_name(first_name, last_name)

    # --- TICKET OPERATIONS ---

    def list_tickets(
        self, requester_id: Optional[int] = None, agent_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Lists tickets filtered by requester or agent.

        Args:
            requester_id: Optional requester (user) ID
            agent_id: Optional agent (tech) ID

        Returns:
            List of ticket dictionaries
        """
        return self._tickets.list_tickets(requester_id, agent_id)

    def get_ticket_by_id(self, ticket_id: int) -> Dict[str, Any]:
        """
        Get a specific ticket by its ID.

        Args:
            ticket_id: The numeric ticket ID

        Returns:
            Dictionary with ticket details
        """
        return self._tickets.get_ticket_by_id(ticket_id)

    def create_ticket(
        self,
        subject: str,
        description: str,
        requester_email: str,
        priority: int = 1,
        status: int = 2,
        group_id: Optional[int] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new ticket in Freshservice.

        Args:
            subject: Ticket subject/title
            description: Ticket description
            requester_email: Email of the requester
            priority: Priority level (1=Low, 2=Medium, 3=High, 4=Urgent)
            status: Ticket status (2=Open, 3=Pending, 4=Resolved, 5=Closed)
            group_id: Optional group/queue ID to assign to
            category: Optional category name

        Returns:
            Dictionary with ticket_id and ticket_url
        """
        # Input validation
        if not subject or not description or not requester_email:
            raise ValueError("subject, description, and requester_email are required")

        # Look up requester ID
        try:
            requester_info = self.get_user_by_email(requester_email)
            requester_id = requester_info["id"]
        except ValueError:
            raise ValueError(f"Could not find user with email {requester_email}")

        return self._tickets.create_ticket(
            subject=subject,
            description=description,
            requester_id=requester_id,
            priority=priority,
            status=status,
            group_id=group_id,
            category=category,
        )

    # --- ASSET OPERATIONS ---

    def list_assets(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Lists assets assigned to a specific user.

        Args:
            user_id: The numeric ID of the user

        Returns:
            List of comprehensive asset dictionaries
        """
        return self._assets.list_assets(user_id)

    def get_asset_by_id(self, asset_id: int) -> Dict[str, Any]:
        """
        Get a specific asset by its ID.

        Args:
            asset_id: The numeric asset ID

        Returns:
            Dictionary with comprehensive asset details
        """
        return self._assets.get_asset_by_id(asset_id)

    # --- CHANGE OPERATIONS ---

    def list_recent_changes(self) -> List[Dict[str, Any]]:
        """
        Lists recent open changes (useful for checking outages/maintenance).

        Returns:
            List of change dictionaries
        """
        return self._changes.list_recent_changes()

    # --- SOLUTION OPERATIONS ---

    def list_solution_articles(
        self,
        folder_id: Optional[int] = None,
        category_id: Optional[int] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List solution articles from the knowledge base.

        Args:
            folder_id: Optional folder ID to filter articles
            category_id: Optional category ID to filter articles
            limit: Maximum number of articles to return

        Returns:
            List of article dictionaries
        """
        return self._solutions.list_solution_articles(folder_id, category_id, limit)

    def get_solution_article(self, article_id: int) -> Dict[str, Any]:
        """
        Get a specific solution article by ID with full content.

        Args:
            article_id: The numeric article ID

        Returns:
            Dictionary with complete article details
        """
        return self._solutions.get_solution_article(article_id)

    def search_solution_articles(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for solution articles by keyword or phrase.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of matching article dictionaries
        """
        return self._solutions.search_solution_articles(query, limit)

    def list_solution_categories(self) -> List[Dict[str, Any]]:
        """
        List all solution categories (top-level organization).

        Returns:
            List of category dictionaries
        """
        return self._solutions.list_solution_categories()

    def list_solution_folders(
        self, category_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List solution folders (sub-organization within categories).

        Args:
            category_id: Optional category ID to filter folders

        Returns:
            List of folder dictionaries
        """
        return self._solutions.list_solution_folders(category_id)

    def get_popular_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most popular solution articles by hits/views.

        Args:
            limit: Maximum number of articles to return

        Returns:
            List of popular article dictionaries
        """
        return self._solutions.get_popular_articles(limit)

    # --- TOOL DISPATCH ---

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        Execute a tool by name with given parameters.
        This is used for JSON-RPC dispatch and internal calls.

        Args:
            tool_name: The name of the tool to execute
            params: Dictionary of parameters

        Returns:
            The tool result

        Raises:
            ValueError: If tool not found or execution fails
        """
        tool_map = {
            "get_user_by_email": self.get_user_by_email,
            "get_user_by_name": self.get_user_by_name,
            "list_tickets": self.list_tickets,
            "list_assets": self.list_assets,
            "list_recent_changes": self.list_recent_changes,
            "get_ticket_by_id": self.get_ticket_by_id,
            "get_asset_by_id": self.get_asset_by_id,
            "create_ticket": self.create_ticket,
            "list_solution_articles": self.list_solution_articles,
            "get_solution_article": self.get_solution_article,
            "search_solution_articles": self.search_solution_articles,
            "list_solution_categories": self.list_solution_categories,
            "list_solution_folders": self.list_solution_folders,
            "get_popular_articles": self.get_popular_articles,
        }

        if tool_name not in tool_map:
            raise ValueError(
                f"Tool '{tool_name}' not found. Available tools: {list(tool_map.keys())}"
            )

        tool_func = tool_map[tool_name]

        try:
            # Call the tool with unpacked parameters
            result = tool_func(**params)
            return result
        except TypeError as e:
            raise ValueError(f"Invalid parameters for tool '{tool_name}': {str(e)}")
