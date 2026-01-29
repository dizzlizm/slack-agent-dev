"""
Freshservice ticket-related operations.
"""
import logging
from typing import Dict, List, Any, Optional
import requests

from .client import FreshserviceClient
from src.integrations.base_tools import retry_on_failure


class TicketOperations(FreshserviceClient):
    """Handles ticket operations in Freshservice."""

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def list_tickets(
        self, requester_id: Optional[int] = None, agent_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Lists tickets filtered by requester or agent.

        Args:
            requester_id: Optional requester (user) ID
            agent_id: Optional agent (tech) ID

        Returns:
            List of ticket dictionaries with id, subject, status, priority, created_at

        Raises:
            ValueError: If neither requester_id nor agent_id provided, or configuration missing
        """
        self._ensure_configured()

        if not requester_id and not agent_id:
            raise ValueError("Must provide either requester_id or agent_id.")

        query_params = []
        if requester_id:
            query_params.append(f"requester_id={requester_id}")
        if agent_id:
            query_params.append(f"agent_id={agent_id}")

        url = f"{self.base_url}/tickets?{'&'.join(query_params)}&include=stats"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()

            tickets = response.json().get("tickets", [])

            # Return simplified ticket info (limit to 10 for performance)
            return [
                {
                    "id": t["id"],
                    "subject": t["subject"],
                    "status": t["status"],  # 2: Open, 3: Pending, 4: Resolved, 5: Closed
                    "priority": t["priority"],
                    "created_at": t["created_at"],
                }
                for t in tickets[:10]
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing tickets: {e}")
            raise ValueError(f"Failed to list tickets: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_ticket_by_id(self, ticket_id: int) -> Dict[str, Any]:
        """
        Get a specific ticket by its ID.

        Args:
            ticket_id: The numeric ticket ID

        Returns:
            Dictionary with ticket details

        Raises:
            ValueError: If ticket not found or configuration missing
        """
        self._ensure_configured()

        url = f"{self.base_url}/tickets/{ticket_id}"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )

            if response.status_code == 404:
                raise ValueError(f"Ticket #{ticket_id} not found")

            response.raise_for_status()

            ticket = response.json().get("ticket", {})

            return {
                "id": ticket["id"],
                "subject": ticket["subject"],
                "description": ticket.get("description_text", ""),
                "status": ticket["status"],
                "priority": ticket["priority"],
                "requester_id": ticket.get("requester_id"),
                "agent_id": ticket.get("responder_id"),
                "created_at": ticket["created_at"],
                "updated_at": ticket["updated_at"],
            }
        except requests.RequestException as e:
            logging.error(f"Error getting ticket #{ticket_id}: {e}")
            raise ValueError(f"Failed to get ticket: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def create_ticket(
        self,
        subject: str,
        description: str,
        requester_id: int,
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
            requester_id: ID of the requester
            priority: Priority level (1=Low, 2=Medium, 3=High, 4=Urgent)
            status: Ticket status (2=Open, 3=Pending, 4=Resolved, 5=Closed)
            group_id: Optional group/queue ID to assign to
            category: Optional category name

        Returns:
            Dictionary with ticket_id and ticket_url

        Raises:
            ValueError: If creation fails or configuration missing
        """
        self._ensure_configured()

        # Input validation
        if not subject or not description:
            raise ValueError("subject and description are required")

        if priority not in [1, 2, 3, 4]:
            raise ValueError(
                "priority must be 1 (Low), 2 (Medium), 3 (High), or 4 (Urgent)"
            )

        url = f"{self.base_url}/tickets"

        payload = {
            "subject": subject,
            "description": description,
            "requester_id": requester_id,
            "priority": priority,
            "status": status,
        }

        if group_id:
            payload["group_id"] = group_id

        if category:
            payload["category"] = category

        try:
            response = requests.post(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

            ticket = response.json().get("ticket", {})
            ticket_id = ticket["id"]
            ticket_url = f"https://{self.domain}/a/tickets/{ticket_id}"

            return {
                "ticket_id": ticket_id,
                "ticket_url": ticket_url,
                "subject": ticket["subject"],
                "status": ticket["status"],
                "priority": ticket["priority"],
            }
        except requests.RequestException as e:
            logging.error(f"Error creating ticket: {e}")
            raise ValueError(f"Failed to create ticket: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def update_ticket(
        self,
        ticket_id: int,
        status: Optional[int] = None,
        priority: Optional[int] = None,
        description: Optional[str] = None,
        agent_id: Optional[int] = None,
        group_id: Optional[int] = None,
        custom_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing ticket's properties.
        
        Args:
            ticket_id: The ticket ID to update
            status: New status (2=Open, 3=Pending, 4=Resolved, 5=Closed)
            priority: New priority (1=Low, 2=Medium, 3=High, 4=Urgent)
            description: New description (appends to existing)
            agent_id: Assign to specific agent
            group_id: Assign to specific group
            custom_fields: Dictionary of custom field values
            
        Returns:
            Dictionary with updated ticket information
            
        Raises:
            ValueError: If update fails or invalid parameters
        """
        self._ensure_configured()
        
        if not any([status, priority, description, agent_id, group_id, custom_fields]):
            raise ValueError("At least one field must be provided for update")
        
        # Validate status
        if status is not None and status not in [2, 3, 4, 5]:
            raise ValueError("status must be 2 (Open), 3 (Pending), 4 (Resolved), or 5 (Closed)")
        
        # Validate priority
        if priority is not None and priority not in [1, 2, 3, 4]:
            raise ValueError("priority must be 1 (Low), 2 (Medium), 3 (High), or 4 (Urgent)")
        
        url = f"{self.base_url}/tickets/{ticket_id}"
        
        payload = {}
        if status is not None:
            payload["status"] = status
        if priority is not None:
            payload["priority"] = priority
        if description:
            payload["description"] = description
        if agent_id:
            payload["responder_id"] = agent_id
        if group_id:
            payload["group_id"] = group_id
        if custom_fields:
            payload["custom_fields"] = custom_fields
        
        try:
            response = requests.put(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            
            if response.status_code == 404:
                raise ValueError(f"Ticket #{ticket_id} not found")
            
            response.raise_for_status()
            
            ticket = response.json().get("ticket", {})
            
            return {
                "ticket_id": ticket["id"],
                "subject": ticket["subject"],
                "status": ticket["status"],
                "priority": ticket["priority"],
                "updated_at": ticket["updated_at"]
            }
        except requests.RequestException as e:
            logging.error(f"Error updating ticket #{ticket_id}: {e}")
            raise ValueError(f"Failed to update ticket: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def add_ticket_note(
        self,
        ticket_id: int,
        body: str,
        private: bool = True,
        notify_emails: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Add a note or reply to an existing ticket.
        
        Args:
            ticket_id: The ticket ID to add note to
            body: Note content (can be HTML or plain text)
            private: Whether note is internal only (default True)
            notify_emails: Optional list of emails to notify
            
        Returns:
            Dictionary with note information
            
        Raises:
            ValueError: If note creation fails
        """
        self._ensure_configured()
        
        if not body or not body.strip():
            raise ValueError("Note body cannot be empty")
        
        url = f"{self.base_url}/tickets/{ticket_id}/notes"
        
        payload = {
            "body": body,
            "private": private
        }
        
        if notify_emails:
            payload["notify_emails"] = notify_emails
        
        try:
            response = requests.post(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            
            if response.status_code == 404:
                raise ValueError(f"Ticket #{ticket_id} not found")
            
            response.raise_for_status()
            
            note = response.json().get("conversation", {})
            
            return {
                "note_id": note.get("id"),
                "ticket_id": ticket_id,
                "body": note.get("body_text", body),
                "private": note.get("private", private),
                "created_at": note.get("created_at")
            }
        except requests.RequestException as e:
            logging.error(f"Error adding note to ticket #{ticket_id}: {e}")
            raise ValueError(f"Failed to add note: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_ticket_conversations(
        self,
        ticket_id: int,
        include_private: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all conversations/notes on a ticket.
        
        Args:
            ticket_id: The ticket ID to get conversations for
            include_private: Whether to include internal notes (default True)
            
        Returns:
            List of conversation dictionaries with body, author, timestamp
            
        Raises:
            ValueError: If retrieval fails
        """
        self._ensure_configured()
        
        url = f"{self.base_url}/tickets/{ticket_id}/conversations"
        
        try:
            response = requests.get(
                url,
                auth=self._get_auth(),
                headers=self._get_headers(),
                timeout=10
            )
            
            if response.status_code == 404:
                raise ValueError(f"Ticket #{ticket_id} not found")
            
            response.raise_for_status()
            
            conversations = response.json().get("conversations", [])
            
            # Filter and format conversations
            result = []
            for conv in conversations:
                # Skip private notes if not requested
                if not include_private and conv.get("private", False):
                    continue
                
                result.append({
                    "id": conv.get("id"),
                    "body": conv.get("body_text", ""),
                    "private": conv.get("private", False),
                    "user_id": conv.get("user_id"),
                    "created_at": conv.get("created_at"),
                    "incoming": conv.get("incoming", False)  # True if from requester
                })
            
            return result
        except requests.RequestException as e:
            logging.error(f"Error getting conversations for ticket #{ticket_id}: {e}")
            raise ValueError(f"Failed to get conversations: {str(e)}")

