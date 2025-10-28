import asyncio
import json
import os
import sys
import feedparser
import ssl
import pytz
from bs4 import BeautifulSoup
from readability import Document
from datetime import datetime, timezone, timedelta
import dateutil.parser

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.convert_to_html import convert_json_to_html

def clean_html_content(html_content):
    """Clean HTML content by removing unwanted classes and elements."""
    if not html_content:
        return html_content
        
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove unwanted classes
    unwanted_classes = [
        'ad', 'advertisement', 'social-links', 'share-tools', 'related-links',
        'newsletter-signup', 'comments-section', 'author-info', 'timestamp',
        'recommended', 'trending', 'most-popular', 'video-container', 'gallery',
        'newsletter', 'newsletter-signup', 'newsletter-form', 'newsletter-cta'
    ]
    
    for class_name in unwanted_classes:
        for element in soup.find_all(class_=class_name):
            element.decompose()
    
    # Remove script and style elements
    for element in soup(['script', 'style', 'noscript', 'iframe', 'object', 'embed']):
        element.decompose()
    
    # Remove empty elements
    for element in soup.find_all(True):
        # Remove empty attributes
        for attr in list(element.attrs.keys()):
            if not element[attr]:
                del element[attr]
        
        # Remove empty elements
        if not element.get_text(strip=True) and not element.find_all(True):
            element.decompose()
    
    # Clean up figure and figcaption
    for figure in soup.find_all('figure'):
        if not figure.find('img') and not figure.find('video'):
            figure.decompose()
    
    return str(soup)

# RSS feeds to fetch articles from
RSS_FEEDS = [
    "https://moxie.foxnews.com/google-publisher/latest.xml"  # Fox News Latest
]

# Create unverified SSL context
ssl._create_default_https_context = ssl._create_unverified_context

# Fetch article links from RSS feeds and include publication time
def fetch_articles_from_rss():
    articles = []
    # Get the timezone from the RSS feed (Fox News uses Eastern Time)
    eastern = pytz.timezone('US/Eastern')
    
    # Get current time in Eastern Time
    now = datetime.now(eastern)
    
    # Get yesterday at 00:00:00 in Eastern Time
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=eastern)
    
    for feed_url in RSS_FEEDS:
        print(f"\nFetching feed: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            print(f"Feed status: {feed.get('status')}")
            print(f"Feed version: {feed.get('version', 'N/A')}")
            
            if not feed.entries:
                print("No entries found in the feed")
                continue
                
            print(f"Number of entries: {len(feed.entries)}")
            
            if hasattr(feed, 'bozo') and feed.bozo:
                print(f"Feed parsing warning: {feed.bozo_exception}")
                
            for entry in feed.entries:
                # Skip if no publication date
                if not hasattr(entry, 'published_parsed'):
                    continue
                    
                # Skip if not an article (e.g., videos, galleries, etc.)
                if not any(tag.get('term') == 'article' and 'content-type' in tag.get('scheme', '') 
                         for tag in getattr(entry, 'tags', [])):
                    continue
                    
                # Parse publication date with timezone info
                try:
                    # Try to get the published date string
                    pub_date_str = entry.get('published', '')
                    if not pub_date_str and hasattr(entry, 'published_parsed'):
                        # Fallback to parsed date if published string not available
                        pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    else:
                        # Parse the date string with timezone info
                        pub_date = dateutil.parser.parse(pub_date_str)
                        
                    # Ensure the date has timezone info (Fox News is in Eastern Time)
                    if pub_date.tzinfo is None:
                        pub_date = eastern.localize(pub_date)
                    
                    # Only include articles from yesterday until now (in Eastern Time)
                    if pub_date < yesterday or pub_date > now:
                        continue
                        
                except Exception as e:
                    print(f"Error parsing date for article: {str(e)}")
                    continue
                    
                print(f"Found article from {pub_date}: {entry.get('title', 'No title')}")
                
                # Store the formatted publication date with timezone info as ISO format string
                pub_date_str = pub_date.isoformat()
                
                
                # Get the content from the entry
                content = ''
                if hasattr(entry, 'content') and entry.content:
                    # Get the first content item's value if it exists
                    content = entry.content[0].value if hasattr(entry.content[0], 'value') else str(entry.content[0])
                
                # Process the content with Readability
                processed = process_article_content(content)
                
                article_data = {
                    "title": entry.title,
                    "link": entry.link,
                    "source": feed.feed.title,
                    "pub_time": pub_date,
                    "description": entry.get('description', ''),
                    "content": processed['content'],  # Cleaned HTML content
                }
                articles.append(article_data)
        except Exception as e:
            print(f"Error fetching feed {feed_url}: {str(e)}")
            continue
            
    return articles

def process_article_content(html_content):
    """
    Process article content using Readability and Beautifulsoup while preserving HTML structure.
    
    Args:
        html_content (str): Raw HTML content of the article
        
    Returns:
        dict: Dictionary containing cleaned HTML
    """
    if not html_content:
        return {'content': ''}
        
    try:
        # First get the cleaned HTML content
        doc = Document(html_content)
        content = doc.summary()
        
        # Parse with BeautifulSoup for cleaning
        soup = BeautifulSoup(content, 'html.parser')
                
        # Remove all <strong> elements and their content
        for strong in soup.select('strong'):
            strong.extract()

        for tag in soup.find_all(["a", "u"]):
            tag.unwrap()
        
        # Remove empty elements and clean up
        clean_html = clean_html_content(str(soup))
        
        return {
            'content': clean_html,  # Preserve HTML structure
        }
    except Exception as e:
        print(f"Error processing article content: {str(e)}")
        return {'content': ''}


# Extract full article content from each link

# Main function to fetch news
async def fetch_news():
    # Get article data from RSS feeds
    print(f"\nFetching articles from {len(RSS_FEEDS)} RSS feeds")
    rss_articles = fetch_articles_from_rss()
    print(f"Found {len(rss_articles)} articles in total")
    
    # Filter out articles with empty content
    valid_articles = []
    for article in rss_articles:
        print(f"\nProcessing: {article['title']}")
        # Only keep articles with non-empty content
        content = article.get('content', '').strip()
        if (content and 
            content != '[Failed to load content]' and 
            not content.startswith('[Error:') and
            content.lower() not in ['<html><body></body></html>', '<html></html>'] and
            len(content) > 20):  # Minimum content length to avoid very short contents
            valid_articles.append(article)
        else:
            print(f"Skipping article due to empty or invalid content: {article.get('title', 'Untitled')}")
    
    print(f"\nFound {len(valid_articles)} articles with valid content out of {len(rss_articles)}")

    # Prepare the final feed object with only valid articles
    feed_object = {
        "title": "Latest News",
        "link": ", ".join(RSS_FEEDS),
        "description": f"Latest news from {len(RSS_FEEDS)} sources",
        "items": valid_articles
    }
    
    # Save articles to a JSON file
    os.makedirs('output', exist_ok=True)
    json_file = 'output/fox_news_articles.json'
    
    # Generate HTML from the feed
    html_file = 'output/fox_news_articles.html'
    
    # Convert all datetime objects in the feed_object to ISO format strings
    def convert_datetime_to_str(obj):
        if isinstance(obj, dict):
            return {k: convert_datetime_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_datetime_to_str(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj
    
    # Convert all datetime objects in the feed_object
    serializable_feed = convert_datetime_to_str(feed_object)
    
    # Save the articles to a JSON file
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(serializable_feed, f, ensure_ascii=False, indent=2)
    
    print(f"\nJSON file saved to: {os.path.abspath(json_file)}")
    
    # Convert the JSON to HTML
    convert_json_to_html(json_file, html_file)
    print(f"HTML file saved to: {os.path.abspath(html_file)}")

    # Return the serializable version of the feed
    return serializable_feed

# Run script
if __name__ == "__main__":
    result = asyncio.run(fetch_news())
    try:
        items = (result or {}).get('items') or (result or {}).get('articles') or []
        print(f"Fox News: fetched {len(items)} items.")
    except Exception:
        print("Fox News: finished (no summary available).")
