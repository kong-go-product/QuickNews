import asyncio
import json
import os
import feedparser
import ssl
import pytz
import aiohttp
from bs4 import BeautifulSoup
from readability import Document
from datetime import datetime, timezone, timedelta
import dateutil.parser
import sys
import os

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
        'newsletter', 'newsletter-signup', 'newsletter-form', 'newsletter-cta',
        'content__meta', 'content__footer', 'content__related', 'content__tools','content-author'
    ]
    
    for class_name in unwanted_classes:
        for element in soup.find_all(class_=class_name):
            element.decompose()
    
    # Remove script and style elements
    for element in soup(['script', 'style', 'noscript', 'iframe', 'object', 'embed']):
        element.decompose()

    for elemet in soup.find_all(['a', 'u']):
        elemet.unwrap()
    
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

# RSS feed for CBS News
RSS_FEED = "https://www.cbsnews.com/latest/rss/main"

# Create unverified SSL context
ssl._create_default_https_context = ssl._create_unverified_context


async def fetch_article_content(url):
    """Fetch and extract article content using Readability."""
    try:
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    html = await response.text()
                    # Extract main content using Readability
                    doc = Document(html)
                    content = doc.summary()

                    # Clean the HTML content
                    content = clean_html_content(content)
                    
                    return content
                else:
                    print(f"Failed to fetch {url}: {response.status}")
                    return f"[Failed to load content: HTTP {response.status}]"
    except Exception as e:
        print(f"Error fetching article {url}: {str(e)}")
        return f"[Error: {str(e)}]"

def fetch_articles_from_rss():
    """Fetch article metadata from CBS News RSS feed."""
    print(f"\nFetching CBS News feed: {RSS_FEED}")
    
    # Get current time in Eastern Time
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=eastern)
    
    articles = []
    
    try:
        feed = feedparser.parse(RSS_FEED)
        print(f"Feed status: {feed.get('status')}")
        print(f"Number of entries: {len(feed.entries)}")
        
        for entry in feed.entries:
            # Skip if no publication date
            if not hasattr(entry, 'published_parsed'):
                continue
                
            # Parse publication date
            try:
                pub_date_str = entry.get('published', '')
                if not pub_date_str and hasattr(entry, 'published_parsed'):
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                else:
                    pub_date = dateutil.parser.parse(pub_date_str)
                
                # Ensure timezone info
                if pub_date.tzinfo is None:
                    pub_date = eastern.localize(pub_date)
                
                # Only include articles from yesterday until now
                if pub_date < yesterday or pub_date > now:
                    continue
                    
            except Exception as e:
                print(f"Error parsing date for article: {str(e)}")
                continue
                
            # Skip video content and non-news articles
            if any(link.get('type', '').startswith('video') for link in entry.get('links', [])) or 'www.cbsnews.com/news/' not in entry.link:
                continue
                
            print(f"Found article from {pub_date}: {entry.get('title', 'No title')}")
            
            # Get article URL
            article_url = entry.link
            
            # Get image URL if available
            image_url = ''
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if hasattr(media, 'url') and media.url:
                        image_url = media.url
                        break
            elif hasattr(entry, 'enclosures') and entry.enclosures:
                for enc in entry.enclosures:
                    if hasattr(enc, 'href') and enc.href:
                        image_url = enc.href
                        break
            
            # Add to articles list
            articles.append({
                'title': entry.get('title', 'No title'),
                'link': article_url,
                'source': 'CBS News',
                'pub_time': pub_date.isoformat(),
                'description': entry.get('description', ''),
                'image_url': image_url,
                'content': ''  # Will be filled later
            })
            
    except Exception as e:
        print(f"Error fetching RSS feed: {str(e)}")
    
    return articles

async def fetch_news():
    """Main function to fetch and process news articles."""
    print("Fetching CBS News metadata (no content extraction)...")
    
    # Fetch article metadata
    articles = fetch_articles_from_rss()
    print(f"\nFound {len(articles)} articles in total")
    
    # Fetch article content for each article
    print("\nExtracting article content...")
    tasks = [fetch_article_content(article['link']) for article in articles]
    contents = await asyncio.gather(*tasks)
    
    # Update articles with their content
    for i, content in enumerate(contents):
        if i < len(articles):
            articles[i]['content'] = content
    
    # Create feed object
    feed_object = {
        "title": "CBS News",
        "link": "https://www.cbsnews.com/",
        "description": "Latest news from CBS News",
        "items": articles
    }
    
    # Save articles to a JSON file
    os.makedirs('output', exist_ok=True)
    json_file = 'output/cbs_news_articles.json'
    html_file = 'output/cbs_news_articles.html'
    
    # Save the articles to a JSON file
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(feed_object, f, ensure_ascii=False, indent=2)
    
    print(f"\nJSON file saved to: {os.path.abspath(json_file)}")
    
    # Convert the JSON to HTML
    convert_json_to_html(json_file, html_file)
    print(f"HTML file saved to: {os.path.abspath(html_file)}")
    
    return feed_object

if __name__ == "__main__":
    import aiohttp
    result = asyncio.run(fetch_news())
    try:
        items = (result or {}).get('items') or (result or {}).get('articles') or []
        print(f"CBS: fetched {len(items)} items.")
    except Exception:
        print("CBS: finished (no summary available).")
