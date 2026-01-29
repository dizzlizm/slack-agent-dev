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
from .service_catalog import ServiceCatalogOperations
from .problems import ProblemOperations


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
        self._service_catalog = ServiceCatalogOperations()
        self._problems = ProblemOperations()

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

    def update_ticket(
        self,
        ticket_id: int,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        agent_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing ticket.

        Args:
            ticket_id: The ticket ID to update
            status: New status (2=Open, 3=Pending, 4=Resolved, 5=Closed)
            priority: New priority (1=Low, 2=Medium, 3=High, 4=Urgent)
            agent_id: Assign to agent ID
            group_id: Assign to group ID

        Returns:
            Dictionary with updated ticket details
        """
        return self._tickets.update_ticket(
            ticket_id=ticket_id,
            status=status,
            priority=priority,
            agent_id=agent_id,
            group_id=group_id
        )

    def add_ticket_note(
        self,
        ticket_id: int,
        body: str,
        private: bool = False
    ) -> Dict[str, Any]:
        """
        Add a note/comment to an existing ticket.

        Args:
            ticket_id: The ticket ID
            body: Note content
            private: Whether note is private (internal only)

        Returns:
            Dictionary confirming note creation
        """
        return self._tickets.add_ticket_note(
            ticket_id=ticket_id,
            body=body,
            private=private
        )

    def get_ticket_conversations(
        self,
        ticket_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all conversations/notes for a ticket.

        Args:
            ticket_id: The ticket ID

        Returns:
            List of conversation dictionaries
        """
        return self._tickets.get_ticket_conversations(ticket_id)

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

    def get_asset_software(
        self,
        asset_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get software installed on an asset.

        Args:
            asset_id: The asset ID

        Returns:
            List of installed software dictionaries
        """
        return self._assets.get_asset_software(asset_id)

    def get_asset_contracts(
        self,
        asset_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get contracts associated with an asset.

        Args:
            asset_id: The asset ID

        Returns:
            List of contract dictionaries with warranty/support details
        """
        return self._assets.get_asset_contracts(asset_id)

    # --- CHANGE OPERATIONS ---

    def list_recent_changes(self) -> List[Dict[str, Any]]:
        """
        Lists recent open changes (useful for checking outages/maintenance).

        Returns:
            List of change dictionaries
        """
        return self._changes.list_recent_changes()

    # --- SERVICE CATALOG OPERATIONS ---

    def list_service_items(
        self,
        category_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List available service catalog items.

        Args:
            category_id: Optional category ID to filter

        Returns:
            List of service item dictionaries
        """
        return self._service_catalog.list_service_items(
            category_id=category_id
        )

    def search_service_items(
        self,
        search_term: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search service catalog items by keyword.

        Args:
            search_term: The keywords to search for
            limit: Maximum number of items to return

        Returns:
            List of matching service item dictionaries
        """
        return self._service_catalog.search_service_items(
            search_term=search_term,
            limit=limit
        )

    def get_service_item(
        self,
        item_id: int
    ) -> Dict[str, Any]:
        """
        Get detailed information about a service catalog item.

        Args:
            item_id: The service item ID

        Returns:
            Dictionary with service item details and custom fields
        """
        return self._service_catalog.get_service_item(item_id)

    def create_service_request(
        self,
        service_item_id: int,
        requester_email: str,
        custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a service request from catalog item.

        Args:
            service_item_id: The service item ID
            requester_email: Email of requester
            custom_fields: Item-specific custom fields

        Returns:
            Dictionary with service request details
        """
        # Look up requester ID
        try:
            requester_info = self.get_user_by_email(requester_email)
            requester_id = requester_info["id"]
        except ValueError:
            raise ValueError(f"Could not find user with email {requester_email}")
        
        return self._service_catalog.create_service_request(
            service_item_id=service_item_id,
            requester_id=requester_id,
            custom_fields=custom_fields
        )

    def list_service_categories(self) -> List[Dict[str, Any]]:
        """
        List all service catalog categories.

        Returns:
            List of category dictionaries
        """
        return self._service_catalog.list_service_categories()

    def get_service_request_status(
        self,
        service_request_id: int
    ) -> Dict[str, Any]:
        """
        Get status of a service request including approval and fulfillment.

        Args:
            service_request_id: The service request ID

        Returns:
            Dictionary with request status and tracking details
        """
        return self._service_catalog.get_service_request_status(service_request_id)

    # --- PROBLEM MANAGEMENT OPERATIONS ---

    def list_problems(
        self,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        impact: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List problems in Freshservice.

        Args:
            status: Filter by status (1=Open, 2=Change Requested, 3=Closed)
            priority: Filter by priority (1=Low, 2=Medium, 3=High, 4=Urgent)
            impact: Filter by impact (1=Low, 2=Medium, 3=High)
            limit: Maximum number of results

        Returns:
            List of problem dictionaries
        """
        return self._problems.list_problems(
            status=status,
            priority=priority,
            impact=impact,
            limit=limit
        )

    def get_problem_by_id(
        self,
        problem_id: int
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific problem.

        Args:
            problem_id: The problem ID

        Returns:
            Dictionary with complete problem details
        """
        return self._problems.get_problem_by_id(problem_id)

    def link_ticket_to_problem(
        self,
        ticket_id: int,
        problem_id: int
    ) -> Dict[str, Any]:
        """
        Associate a ticket with a known problem.

        Args:
            ticket_id: The ticket ID to link
            problem_id: The problem ID to link to

        Returns:
            Dictionary confirming the link
        """
        return self._problems.link_ticket_to_problem(
            ticket_id=ticket_id,
            problem_id=problem_id
        )

    def get_problem_tickets(
        self,
        problem_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all tickets associated with a problem.

        Args:
            problem_id: The problem ID

        Returns:
            List of associated ticket dictionaries
        """
        return self._problems.get_problem_tickets(problem_id)

    def search_problems(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search problems by keyword.

        Args:
            query: Search term
            limit: Maximum number of results

        Returns:
            List of matching problem dictionaries
        """
        return self._problems.search_problems(
            query=query,
            limit=limit
        )

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
            # User operations
            "get_user_by_email": self.get_user_by_email,
            "get_user_by_name": self.get_user_by_name,
            # Ticket operations
            "list_tickets": self.list_tickets,
            "get_ticket_by_id": self.get_ticket_by_id,
            "create_ticket": self.create_ticket,
            "update_ticket": self.update_ticket,
            "add_ticket_note": self.add_ticket_note,
            "get_ticket_conversations": self.get_ticket_conversations,
            # Asset operations
            "list_assets": self.list_assets,
            "get_asset_by_id": self.get_asset_by_id,
            "get_asset_software": self.get_asset_software,
            "get_asset_contracts": self.get_asset_contracts,
            # Change operations
            "list_recent_changes": self.list_recent_changes,
            # Service Catalog operations
            "list_service_items": self.list_service_items,
            "search_service_items": self.search_service_items,
            "get_service_item": self.get_service_item,
            "create_service_request": self.create_service_request,
            "list_service_categories": self.list_service_categories,
            "get_service_request_status": self.get_service_request_status,
            # Problem Management operations
            "list_problems": self.list_problems,
            "get_problem_by_id": self.get_problem_by_id,
            "link_ticket_to_problem": self.link_ticket_to_problem,
            "get_problem_tickets": self.get_problem_tickets,
            "search_problems": self.search_problems,
            # Solution operations
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
