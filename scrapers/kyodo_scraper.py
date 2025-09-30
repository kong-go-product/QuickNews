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
import aiohttp

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.convert_to_html import convert_json_to_html

def save_to_html(data, filename_prefix='kyodo_news'):
    """Save the scraped data to an HTML file."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs('output', exist_ok=True)
        
        # Generate filename without timestamp
        json_filename = f'output/{filename_prefix}_articles.json'
        html_filename = f'output/{filename_prefix}_articles.html'
        
        # Prepare data in the format expected by convert_json_to_html
        articles_data = []
        for article in data.get('articles', []):
            articles_data.append({
                'title': article.get('title', ''),
                'content': article.get('content', ''),
                'source': '共同通信',
                'url': article.get('url', ''),
                'published': article.get('published', '')
            })
        
        # Create the feed data structure
        feed_data = {
            'title': 'Kyodo News',
            'link': 'https://www.kyodo.co.jp/',
            'description': 'Latest news from Kyodo News',
            'language': 'ja',
            'items': articles_data
        }
        
        # Save JSON file
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(feed_data, f, indent=2, ensure_ascii=False)
        
        # Convert to HTML
        convert_json_to_html(json_filename, html_filename)
        
        print(f"Data saved to {html_filename}")
        return html_filename
    except Exception as e:
        print(f"Error saving to file: {e}")
        return None

def clean_html_content(html_content):
    """Clean HTML content by removing unwanted elements."""
    if not html_content:
        return html_content
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script, style, navigation, and media elements
    for element in soup(["script", "style", "iframe", "nav", "footer", "img", "picture", "figure", "video", "audio"]):
        element.decompose()
    
    # Remove share and social media elements
    for div in soup.find_all("div", class_=lambda x: x and ('share' in x or 'sns' in x or 'related' in x or 'advertisement' in x.lower())):
        div.decompose()
    
    # Unwrap anchor/underline and common formatting wrappers (keep text only)
    for tag in soup.find_all(["a", "u", "strong", "b", "em", "i", "span", "font"]):
        tag.unwrap()

    # Strip all attributes from remaining tags for cleaner HTML
    for el in soup.find_all(True):
        el.attrs = {}

    # Remove empty elements (no text and no child tags)
    removed = True
    while removed:
        removed = False
        for el in list(soup.find_all(True)):
            if not el.get_text(strip=True) and not el.find(True):
                el.decompose()
                removed = True
    
    return str(soup)

# RSS feed for Kyodo News (共同通信)
RSS_FEED = "https://www.kyodo.co.jp/feed/"

async def fetch_articles_from_rss():
    """Fetch article metadata from Kyodo News RSS feed."""
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    
    feed = feedparser.parse(RSS_FEED)
    articles = []
    
    for entry in feed.entries[:10]:  # Get latest 10 articles
        try:
            published = dateutil.parser.parse(entry.published)
            
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            
            # Extract image if available
            image_url = ''
            if 'media_content' in entry and len(entry.media_content) > 0:
                image_url = entry.media_content[0]['url']
            
            articles.append({
                'title': entry.title,
                'url': entry.link,
                'published': published.isoformat(),
                'source': '共同通信',
                'summary': entry.get('summary', ''),
                'image': image_url
            })
        except Exception as e:
            print(f"Error processing Kyodo article: {e}")
    
    return articles

async def fetch_article_content(url):
    """Fetch and extract article content using Readability."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                html = await response.text()
                doc = Document(html)
                content = doc.summary()
                cleaned_content = clean_html_content(content)
                return cleaned_content
    except Exception as e:
        print(f"Error fetching Kyodo article content: {e}")
        return None

async def fetch_news_async():
    """Main async function to fetch Kyodo news."""
    try:
        articles = await fetch_articles_from_rss()
        tasks = [fetch_article_content(article['url']) for article in articles]
        contents = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, content in enumerate(contents):
            if isinstance(content, str):
                articles[i]['content'] = content
            else:
                articles[i]['content'] = ""
        
        return {
            'source': '共同通信',
            'link': 'https://www.kyodo.co.jp/',
            'articles': articles
        }
    except Exception as e:
        print(f"Error in Kyodo news fetch: {e}")
        return {'error': str(e)}

def fetch_news():
    """Synchronous wrapper for the async function."""
    return asyncio.run(fetch_news_async())

def save_to_file(data, filename_prefix='kyodo_news'):
    """Save the scraped data to a JSON file."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs('output', exist_ok=True)
        
        # Generate filenames without timestamp
        json_filename = f'output/{filename_prefix}_articles.json'
        html_filename = f'output/{filename_prefix}_articles.html'

        # Map 'articles' to the feed schema expected by convert_json_to_html ('items')
        articles_data = []
        for article in data.get('articles', []):
            articles_data.append({
                'title': article.get('title', ''),
                'content': article.get('content', ''),
                'source': article.get('source', '共同通信'),
                'url': article.get('url', ''),
                'published': article.get('published', ''),
                'language': article.get('language', 'ja')
            })

        feed_data = {
            'title': 'Kyodo News',
            'link': 'https://www.kyodo.co.jp/',
            'description': 'Latest news from Kyodo News',
            'language': 'ja',
            'items': articles_data
        }

        # Save JSON then convert to HTML
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(feed_data, f, indent=2, ensure_ascii=False)
        convert_json_to_html(json_filename, html_filename)
        print(f"Data saved to {html_filename}")
        return html_filename
    except Exception as e:
        print(f"Error saving to file: {e}")
        return None

if __name__ == "__main__":
    # Run the scraper
    result = asyncio.run(fetch_news_async())
    
    # Print to console
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Save to HTML file
    if 'error' not in result:
        save_to_html(result, 'kyodo_news')
