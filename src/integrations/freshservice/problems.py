"""
Freshservice Problem Management operations.

Problems in FreshService represent root causes of recurring incidents.
This module integrates with the existing problem management system
rather than building custom tracking.
"""
import logging
from typing import Dict, List, Any, Optional
import requests

from .client import FreshserviceClient
from src.integrations.base_tools import retry_on_failure


class ProblemOperations(FreshserviceClient):
    """Handles Problem Management operations in Freshservice."""

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def list_problems(
        self,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        impact: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List problems in Freshservice.
        
        Problems represent known issues affecting multiple tickets.
        Useful for checking if a reported issue is already known.
        
        Args:
            status: Filter by status
                    1=Open, 2=Change Requested, 3=Closed
            priority: Filter by priority
                      1=Low, 2=Medium, 3=High, 4=Urgent
            impact: Filter by impact
                    1=Low, 2=Medium, 3=High
            limit: Maximum number of problems to return (default 10)
            
        Returns:
            List of problem dictionaries with id, subject, status, impact
            
        Raises:
            ValueError: If retrieval fails or configuration missing
        """
        self._ensure_configured()
        
        url = f"{self.base_url}/problems"
        
        params = {}
        if status is not None:
            params["filter"] = f"status:{status}"
        if priority is not None:
            if params.get("filter"):
                params["filter"] += f" AND priority:{priority}"
            else:
                params["filter"] = f"priority:{priority}"
        if impact is not None:
            if params.get("filter"):
                params["filter"] += f" AND impact:{impact}"
            else:
                params["filter"] = f"impact:{impact}"
        
        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            problems = response.json().get("problems", [])
            
            # Return formatted problems (limit results)
            return [
                {
                    "id": p["id"],
                    "subject": p["subject"],
                    "description": p.get("description_text", "")[:200],  # Truncate
                    "status": p["status"],  # 1=Open, 2=Change Requested, 3=Closed
                    "priority": p.get("priority", 1),
                    "impact": p.get("impact", 1),  # 1=Low, 2=Medium, 3=High
                    "known_error": p.get("known_error", False),
                    "agent_id": p.get("agent_id"),
                    "group_id": p.get("group_id"),
                    "created_at": p.get("created_at"),
                    "updated_at": p.get("updated_at")
                }
                for p in problems[:limit]
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing problems: {e}")
            raise ValueError(f"Failed to list problems: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_problem_by_id(
        self,
        problem_id: int
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific problem.
        
        Args:
            problem_id: The problem ID
            
        Returns:
            Dictionary with complete problem details including analysis and workaround
            
        Raises:
            ValueError: If problem not found or retrieval fails
        """
        self._ensure_configured()
        
        url = f"{self.base_url}/problems/{problem_id}"
        
        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 404:
                raise ValueError(f"Problem #{problem_id} not found")
            
            response.raise_for_status()
            
            problem = response.json().get("problem", {})
            
            return {
                "id": problem["id"],
                "subject": problem["subject"],
                "description": problem.get("description_text", ""),
                "status": problem["status"],
                "priority": problem.get("priority", 1),
                "impact": problem.get("impact", 1),
                "known_error": problem.get("known_error", False),
                "due_by": problem.get("due_by"),
                "agent_id": problem.get("agent_id"),
                "group_id": problem.get("group_id"),
                "department_id": problem.get("department_id"),
                "category": problem.get("category"),
                "sub_category": problem.get("sub_category"),
                "item_category": problem.get("item_category"),
                "analysis": problem.get("analysis_text", ""),  # Root cause analysis
                "symptoms": problem.get("symptoms_text", ""),
                "root_cause": problem.get("root_cause_text", ""),
                "created_at": problem.get("created_at"),
                "updated_at": problem.get("updated_at")
            }
        except requests.RequestException as e:
            logging.error(f"Error getting problem #{problem_id}: {e}")
            raise ValueError(f"Failed to get problem: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def link_ticket_to_problem(
        self,
        ticket_id: int,
        problem_id: int
    ) -> Dict[str, Any]:
        """
        Associate a ticket with a known problem.
        
        Links an incident ticket to its root cause problem.
        This helps track problem impact and provides automatic
        updates to all affected tickets when the problem is resolved.
        
        Args:
            ticket_id: The ticket ID to link
            problem_id: The problem ID to link to
            
        Returns:
            Dictionary confirming the link
            
        Raises:
            ValueError: If linking fails or IDs not found
        """
        self._ensure_configured()
        
        url = f"{self.base_url}/tickets/{ticket_id}"
        
        payload = {
            "problem_id": problem_id
        }
        
        try:
            response = requests.put(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            
            if response.status_code == 404:
                raise ValueError(f"Ticket #{ticket_id} or Problem #{problem_id} not found")
            
            response.raise_for_status()
            
            ticket = response.json().get("ticket", {})
            
            return {
                "ticket_id": ticket["id"],
                "problem_id": ticket.get("problem_id"),
                "subject": ticket["subject"],
                "status": ticket["status"],
                "updated_at": ticket["updated_at"]
            }
        except requests.RequestException as e:
            logging.error(f"Error linking ticket #{ticket_id} to problem #{problem_id}: {e}")
            raise ValueError(f"Failed to link ticket to problem: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_problem_tickets(
        self,
        problem_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get all tickets associated with a problem.
        
        Useful for understanding the scope/impact of a problem.
        
        Args:
            problem_id: The problem ID
            
        Returns:
            List of associated ticket dictionaries
            
        Raises:
            ValueError: If retrieval fails
        """
        self._ensure_configured()
        
        # FreshService stores problem_id on tickets, so we query tickets
        url = f"{self.base_url}/tickets"
        params = {"filter": f"problem_id:{problem_id}"}
        
        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            tickets = response.json().get("tickets", [])
            
            return [
                {
                    "id": t["id"],
                    "subject": t["subject"],
                    "status": t["status"],
                    "priority": t.get("priority", 1),
                    "requester_id": t.get("requester_id"),
                    "created_at": t.get("created_at")
                }
                for t in tickets
            ]
        except requests.RequestException as e:
            logging.error(f"Error getting tickets for problem #{problem_id}: {e}")
            raise ValueError(f"Failed to get problem tickets: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def search_problems(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search problems by keyword.
        
        Useful for checking if a user's issue matches a known problem.
        
        Args:
            query: Search term (searches subject and description)
            limit: Maximum number of results (default 10)
            
        Returns:
            List of matching problem dictionaries
            
        Raises:
            ValueError: If search fails
        """
        self._ensure_configured()
        
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")
        
        url = f"{self.base_url}/problems"
        params = {
            "query": f'"{query}"',  # Quoted for phrase search
            "per_page": limit
        }
        
        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            problems = response.json().get("problems", [])
            
            return [
                {
                    "id": p["id"],
                    "subject": p["subject"],
                    "description": p.get("description_text", "")[:200],
                    "status": p["status"],
                    "impact": p.get("impact", 1),
                    "known_error": p.get("known_error", False),
                    "created_at": p.get("created_at")
                }
                for p in problems[:limit]
            ]
        except requests.RequestException as e:
            logging.error(f"Error searching problems for '{query}': {e}")
            raise ValueError(f"Failed to search problems: {str(e)}")
