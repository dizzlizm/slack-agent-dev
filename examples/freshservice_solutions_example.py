"""
Example: Using Freshservice Solutions (Knowledge Base) Integration

This demonstrates how to read and gain intelligence from Freshservice Solutions.
"""

from src.integrations.freshservice import FreshserviceTools


def example_solution_intelligence():
    """Examples of gaining intel from Freshservice knowledge base."""
    
    tools = FreshserviceTools()
    
    # 1. Search for articles about a specific topic
    print("🔍 Searching for VPN articles...")
    vpn_articles = tools.search_solution_articles("VPN", limit=5)
    for article in vpn_articles:
        print(f"  - {article['title']} (hits: {article['hits']}, 👍 {article['thumbs_up']})")
        print(f"    URL: {article['url']}")
    
    # 2. Get the most popular articles (what users are reading)
    print("\n📊 Most popular knowledge base articles...")
    popular = tools.get_popular_articles(limit=5)
    for article in popular:
        print(f"  - {article['title']} ({article['hits']} views)")
    
    # 3. Browse knowledge base structure
    print("\n📚 Knowledge base categories...")
    categories = tools.list_solution_categories()
    for cat in categories:
        print(f"  - {cat['name']}: {cat.get('description', 'No description')}")
    
    # 4. Get detailed article content
    if vpn_articles:
        article_id = vpn_articles[0]['id']
        print(f"\n📄 Full content of article #{article_id}...")
        full_article = tools.get_solution_article(article_id)
        print(f"  Title: {full_article['title']}")
        print(f"  Status: {full_article['status']}")
        print(f"  Content preview: {full_article.get('description_text', '')[:200]}...")
    
    # 5. List folders to understand knowledge organization
    print("\n📁 Solution folders...")
    folders = tools.list_solution_folders()
    for folder in folders[:5]:
        print(f"  - {folder['name']} ({folder.get('articles_count', 0)} articles)")


def intelligent_search_example():
    """Use solutions to answer user questions intelligently."""
    
    tools = FreshserviceTools()
    
    # Scenario: User asks "How do I reset my password?"
    user_question = "password reset"
    
    print(f"User asks: 'How do I reset my password?'")
    print(f"Searching knowledge base for '{user_question}'...\n")
    
    results = tools.search_solution_articles(user_question, limit=3)
    
    if results:
        print("📖 Found these helpful articles:")
        for i, article in enumerate(results, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   Relevance score: {article.get('relevance_score', 'N/A')}")
            print(f"   Community rating: 👍 {article['thumbs_up']} / 👎 {article['thumbs_down']}")
            print(f"   Link: {article['url']}")
            
            # Get full content for top result
            if i == 1:
                full = tools.get_solution_article(article['id'])
                print(f"   Preview: {full.get('description_text', '')[:150]}...")
    else:
        print("No articles found. Creating a ticket might be necessary.")


def browse_by_category():
    """Browse solutions organized by category."""
    
    tools = FreshserviceTools()
    
    # Get all categories
    categories = tools.list_solution_categories()
    
    if categories:
        # Pick first category
        category = categories[0]
        print(f"📂 Category: {category['name']}")
        
        # Get folders in this category
        folders = tools.list_solution_folders(category_id=category['id'])
        print(f"   Contains {len(folders)} folders")
        
        # Get articles from first folder if exists
        if folders:
            folder = folders[0]
            articles = tools.list_solution_articles(folder_id=folder['id'], limit=10)
            print(f"\n📁 Folder: {folder['name']}")
            print(f"   Contains {len(articles)} articles:")
            for article in articles:
                print(f"   - {article['title']}")


if __name__ == "__main__":
    print("=" * 60)
    print("Freshservice Solutions Intelligence Example")
    print("=" * 60 + "\n")
    
    # Uncomment to run examples:
    # example_solution_intelligence()
    # intelligent_search_example()
    # browse_by_category()
    
    print("\nℹ️  Uncomment examples in __main__ to run them")
