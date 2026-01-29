"""
Freshservice Solutions (Knowledge Base) operations.
Provides access to solution articles, categories, and folders.
"""
import logging
from typing import Dict, List, Any, Optional
import requests

from .client import FreshserviceClient
from src.integrations.base_tools import retry_on_failure


class SolutionOperations(FreshserviceClient):
    """Handles solution article and knowledge base operations in Freshservice."""

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
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
            limit: Maximum number of articles to return (default 20)

        Returns:
            List of article dictionaries with id, title, description, status, etc.

        Raises:
            ValueError: If configuration missing
        """
        self._ensure_configured()

        # Build URL based on filters
        if folder_id:
            url = f"{self.base_url}/solutions/folders/{folder_id}/articles"
        elif category_id:
            url = f"{self.base_url}/solutions/categories/{category_id}/articles"
        else:
            url = f"{self.base_url}/solutions/articles"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()

            articles = response.json().get("articles", [])

            return [
                {
                    "id": a["id"],
                    "title": a["title"],
                    "description": a.get("description"),
                    "description_text": a.get("description_text"),
                    "status": a["status"],  # 1: Draft, 2: Published
                    "thumbs_up": a.get("thumbs_up", 0),
                    "thumbs_down": a.get("thumbs_down", 0),
                    "hits": a.get("hits", 0),
                    "folder_id": a.get("folder_id"),
                    "category_id": a.get("category_id"),
                    "tags": a.get("tags", []),
                    "keywords": a.get("keywords", []),
                    "created_at": a.get("created_at"),
                    "updated_at": a.get("updated_at"),
                }
                for a in articles[:limit]
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing solution articles: {e}")
            return []

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_solution_article(self, article_id: int) -> Dict[str, Any]:
        """
        Get a specific solution article by ID with full content.

        Args:
            article_id: The numeric article ID

        Returns:
            Dictionary with complete article details including full description

        Raises:
            ValueError: If article not found or configuration missing
        """
        self._ensure_configured()

        url = f"{self.base_url}/solutions/articles/{article_id}"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )

            if response.status_code == 404:
                raise ValueError(f"Solution article #{article_id} not found")

            response.raise_for_status()

            article = response.json().get("article", {})

            return {
                "id": article["id"],
                "title": article["title"],
                "description": article.get("description"),
                "description_text": article.get("description_text"),
                "status": article["status"],
                "approval_status": article.get("approval_status"),
                "folder_id": article.get("folder_id"),
                "category_id": article.get("category_id"),
                "tags": article.get("tags", []),
                "keywords": article.get("keywords", []),
                "thumbs_up": article.get("thumbs_up", 0),
                "thumbs_down": article.get("thumbs_down", 0),
                "hits": article.get("hits", 0),
                "author_id": article.get("author_id"),
                "created_at": article.get("created_at"),
                "updated_at": article.get("updated_at"),
                "url": f"https://{self.domain}/support/solutions/articles/{article_id}",
            }
        except requests.RequestException as e:
            logging.error(f"Error getting solution article #{article_id}: {e}")
            raise ValueError(f"Failed to get solution article: {str(e)}")

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def search_solution_articles(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for solution articles by keyword or phrase.

        Args:
            query: Search query string
            limit: Maximum number of results to return (default 10)

        Returns:
            List of matching article dictionaries

        Raises:
            ValueError: If query is empty or configuration missing
        """
        self._ensure_configured()

        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        # Freshservice uses search parameter in the articles endpoint
        url = f"{self.base_url}/solutions/articles?query={requests.utils.quote(query)}"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()

            articles = response.json().get("articles", [])

            return [
                {
                    "id": a["id"],
                    "title": a["title"],
                    "description_text": a.get("description_text", "")[:500],  # Truncate
                    "status": a["status"],
                    "thumbs_up": a.get("thumbs_up", 0),
                    "thumbs_down": a.get("thumbs_down", 0),
                    "hits": a.get("hits", 0),
                    "folder_id": a.get("folder_id"),
                    "category_id": a.get("category_id"),
                    "relevance_score": a.get("relevance", 0),
                    "url": f"https://{self.domain}/support/solutions/articles/{a['id']}",
                }
                for a in articles[:limit]
            ]
        except requests.RequestException as e:
            logging.error(f"Error searching solution articles: {e}")
            return []

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def list_solution_categories(self) -> List[Dict[str, Any]]:
        """
        List all solution categories (top-level organization).

        Returns:
            List of category dictionaries with id, name, description

        Raises:
            ValueError: If configuration missing
        """
        self._ensure_configured()

        url = f"{self.base_url}/solutions/categories"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()

            categories = response.json().get("categories", [])

            return [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "description": c.get("description"),
                    "position": c.get("position"),
                    "visible_in_portals": c.get("visible_in_portals", []),
                    "created_at": c.get("created_at"),
                    "updated_at": c.get("updated_at"),
                }
                for c in categories
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing solution categories: {e}")
            return []

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def list_solution_folders(self, category_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List solution folders (sub-organization within categories).

        Args:
            category_id: Optional category ID to filter folders

        Returns:
            List of folder dictionaries with id, name, description

        Raises:
            ValueError: If configuration missing
        """
        self._ensure_configured()

        if category_id:
            url = f"{self.base_url}/solutions/categories/{category_id}/folders"
        else:
            url = f"{self.base_url}/solutions/folders"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()

            folders = response.json().get("folders", [])

            return [
                {
                    "id": f["id"],
                    "name": f["name"],
                    "description": f.get("description"),
                    "category_id": f.get("category_id"),
                    "position": f.get("position"),
                    "visibility": f.get("visibility"),
                    "articles_count": f.get("articles_count", 0),
                    "created_at": f.get("created_at"),
                    "updated_at": f.get("updated_at"),
                }
                for f in folders
            ]
        except requests.RequestException as e:
            logging.error(f"Error listing solution folders: {e}")
            return []

    @retry_on_failure(max_retries=3, backoff_factor=0.5)
    def get_popular_articles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the most popular solution articles by hits/views.

        Args:
            limit: Maximum number of articles to return (default 10)

        Returns:
            List of popular article dictionaries sorted by hits

        Raises:
            ValueError: If configuration missing
        """
        self._ensure_configured()

        url = f"{self.base_url}/solutions/articles"

        try:
            response = requests.get(
                url, auth=self._get_auth(), headers=self._get_headers(), timeout=10
            )
            response.raise_for_status()

            articles = response.json().get("articles", [])

            # Filter published articles and sort by hits
            published = [a for a in articles if a.get("status") == 2]
            sorted_articles = sorted(
                published, key=lambda x: x.get("hits", 0), reverse=True
            )

            return [
                {
                    "id": a["id"],
                    "title": a["title"],
                    "description_text": a.get("description_text", "")[:300],
                    "hits": a.get("hits", 0),
                    "thumbs_up": a.get("thumbs_up", 0),
                    "thumbs_down": a.get("thumbs_down", 0),
                    "folder_id": a.get("folder_id"),
                    "tags": a.get("tags", []),
                    "url": f"https://{self.domain}/support/solutions/articles/{a['id']}",
                }
                for a in sorted_articles[:limit]
            ]
        except requests.RequestException as e:
            logging.error(f"Error getting popular articles: {e}")
            return []
