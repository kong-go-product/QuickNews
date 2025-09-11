import asyncio
import json
import os
import feedparser
import ssl
import pytz
from bs4 import BeautifulSoup
from readability import Document
from convert_to_html import convert_json_to_html
from bs4.element import Comment
from datetime import datetime, timezone, timedelta
import dateutil.parser
import aiohttp

def clean_html_content(html_content):
    """
    Clean HTML content by removing unwanted classes and elements.

    Removes unwanted tags, empty paragraphs and divs, and empty attributes
    """
    if not html_content:
        return html_content
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove unwanted classes from the HTML content
    unwanted_classes = [
        # Classes used by NPR to hide captions on images
        'hide-caption',
        'toggle-caption',
        'credit-caption',
        'caption-wrap',
        # Classes used by NPR to wrap audio and video content
        'bucketwrap',
        # Classes used by NPR to hide transcript content
        'icn-story-transcript',
        # Classes used by NPR to display disclaimers
        'disclaimer'
    ]
    
    for class_name in unwanted_classes:
        for element in soup.find_all(class_=class_name):
            element.decompose()
    
    # Remove empty paragraphs and divs
    for element in soup.find_all(['p', 'div']):
        if not element.get_text(strip=True):
            element.decompose()
    
    # Clean up any remaining empty elements
    for element in soup.find_all(True):
        # Remove empty attributes
        for attr in list(element.attrs.keys()):
            if not element[attr]:
                del element[attr]
    
    return str(soup)

# 
# RSS feed for NPR News
RSS_FEED = "https://www.npr.org/rss/rss.php?id=1001"

# Create unverified SSL context
ssl._create_default_https_context = ssl._create_unverified_context

# Fetch article links from RSS feed
def fetch_articles_from_rss():
    articles = []
    # Get the timezone from the RSS feed (NPR uses Eastern Time)
    eastern = pytz.timezone('US/Eastern')
    
    # Get current time in Eastern Time
    now = datetime.now(eastern)
    
    # Get yesterday at 00:00:00 in Eastern Time
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=eastern)
    
    print(f"\nFetching feed: {RSS_FEED}")
    try:
        feed = feedparser.parse(RSS_FEED)
        print(f"Feed status: {feed.get('status')}")
        print(f"Feed version: {feed.get('version', 'N/A')}")
        print(f"Number of entries: {len(feed.entries)}")
        
        if hasattr(feed, 'bozo') and feed.bozo:
            print(f"Feed parsing warning: {feed.bozo_exception}")
            
        for entry in feed.entries:
            # Skip if no publication date
            if not hasattr(entry, 'published_parsed'):
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
                    
                # Ensure the date has timezone info (NPR is in Eastern Time)
                if pub_date.tzinfo is None:
                    pub_date = eastern.localize(pub_date)
                
                # Only include articles from yesterday until now
                if pub_date < yesterday or pub_date > now:
                    continue
                    
            except Exception as e:
                print(f"Error parsing date for article: {str(e)}")
                continue
                
            print(f"Found article from {pub_date}: {entry.get('title', 'No title')}")
            
            # Store the formatted publication date with timezone info as ISO format string
            pub_date_str = pub_date.isoformat()
            
            # Get the article URL
            article_url = entry.link
            
            # Get the title
            title = entry.get('title', 'No title')
            
            # Get the description
            description = entry.get('description', '')
            
            # Get the content from the entry
            content = ''
            if hasattr(entry, 'content'):
                # Try to get content from content field first
                for content_item in entry.content:
                    if hasattr(content_item, 'value'):
                        content = content_item.value
                        break
            
            # If no content in content field, try description
            if not content and hasattr(entry, 'description'):
                content = entry.description
            
            # Store the article data
            article = {
                'title': title,
                'link': article_url,
                'source': 'NPR News',
                'pub_time': pub_date_str,
                'description': description,
                'content': content if content and len(content.strip()) > 50 else ''
            }
            
            # Get the author
            if hasattr(entry, 'author'):
                article['author'] = entry.author
            elif hasattr(entry, 'dc_creator'):
                article['author'] = entry.dc_creator
            
            # Get the image URL if available
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if hasattr(media, 'url') and media.url:
                        article['image_url'] = media.url
                        break
            
            # Add to articles list
            articles.append(article)
            
    except Exception as e:
        print(f"Error fetching RSS feed: {str(e)}")
    
    return articles

# Main async function to fetch article content
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
                    
                    # Remove images and videos
                    soup = BeautifulSoup(content, 'html.parser')
                    for element in soup.find_all(['img', 'video', 'iframe', 'picture', 'figure']):
                        element.decompose()
                    
                    # Unwrap <a> and <u> tags
                    for element in soup.find_all(['a', 'u']):
                        element.unwrap()
                    
                    # Clean the HTML content using the clean_html_content function
                    return clean_html_content(str(soup))
                else:
                    print(f"Failed to fetch {url}: {response.status}")
                    return "[Failed to load content]"
    except Exception as e:
        print(f"Error fetching article {url}: {str(e)}")
        return f"[Error: {str(e)}]"

# Main function to fetch news
async def fetch_news_async():
    articles = fetch_articles_from_rss()
    
    # Process articles to fetch content
    tasks = [fetch_article_content(article['link']) for article in articles]
    
    # Wait for all content to be fetched
    contents = await asyncio.gather(*tasks)
    
    # Update articles with fetched content and filter out empty ones
    valid_articles = []
    for i, content in enumerate(contents):
        if i < len(articles):
            # Only keep articles with non-empty content
            if content and content.strip() and content != '[Failed to load content]' and not content.startswith('[Error:'):
                articles[i]['content'] = content
                valid_articles.append(articles[i])
    
    # Create feed object with only valid articles
    feed_object = {
        "title": "NPR News",
        "link": "https://www.npr.org/",
        "description": "Latest news from NPR",
        "items": valid_articles
    }
    
    # Save articles to a JSON file
    os.makedirs('output', exist_ok=True)
    json_file = 'output/npr_news_articles.json'
    html_file = 'output/npr_news_articles.html'
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(feed_object, f, ensure_ascii=False, indent=2)
    
    print(f"\nJSON file saved to: {os.path.abspath(json_file)}")
    
    # Convert the JSON to HTML
    convert_json_to_html(json_file, html_file)
    print(f"HTML file saved to: {os.path.abspath(html_file)}")
    
    return feed_object

def fetch_news():
    return asyncio.run(fetch_news_async())

# Run script
if __name__ == "__main__":
    result = asyncio.run(fetch_news_async())
    print(json.dumps(result, indent=2, ensure_ascii=False))
