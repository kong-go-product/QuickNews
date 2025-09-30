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
from utils.convert_to_html import convert_json_to_html, convert_data_to_html

def save_to_html(data, filename_prefix='nhk_news'):
    """Save the scraped data to an HTML file."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs('output', exist_ok=True)
        
        # Generate simple filename without timestamp
        html_filename = f'output/{filename_prefix}.html'
        
        # Prepare data in the format expected by convert_json_to_html
        articles_data = []
        for article in data.get('articles', []):
            articles_data.append({
                'title': article.get('title', ''),
                'content': article.get('content', ''),
                'source': 'NHKニュース',
                'url': article.get('url', ''),
                'published': article.get('published', '')
            })
        
        # Create the feed data structure
        feed_data = {
            'title': 'NHK News',
            'link': 'https://www.nhk.or.jp/news/',
            'description': 'Latest news from NHK (Japan Broadcasting Corporation)',
            'language': 'ja',
            'items': articles_data
        }
        
        # Convert data to HTML directly
        convert_data_to_html(feed_data, html_filename)
        
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
    
    # Remove script and style elements
    for script in soup(["script", "style", "iframe", "nav", "footer"]):
        script.decompose()
    
    # Remove share and social media elements
    for div in soup.find_all("div", class_=lambda x: x and ('share' in x or 'sns' in x or 'related' in x or 'advertisement' in x.lower())):
        div.decompose()
    
    return str(soup)

# RSS feed for NHK (Japanese)
RSS_FEED = "https://www.nhk.or.jp/rss/news/cat0.xml"

async def fetch_articles_from_rss():
    """Fetch article metadata from NHK RSS feed."""
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    
    feed = feedparser.parse(RSS_FEED)
    articles = []
    
    for entry in feed.entries[:10]:  # Get latest 10 articles
        try:
            published = dateutil.parser.parse(entry.published)
            
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            
            articles.append({
                'title': entry.title,
                'url': entry.link,
                'published': published.isoformat(),
                'source': 'NHKニュース',
                'summary': entry.get('summary', ''),
                'image': entry.get('media_thumbnail', [{}])[0].get('url', '') if hasattr(entry, 'media_thumbnail') else '',
                'language': 'ja'
            })
        except Exception as e:
            print(f"Error processing NHK article: {e}")
    
    return articles

async def fetch_article_content(url):
    """Fetch and extract article content using Readability."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.nhk.or.jp/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                html = await response.text()
                doc = Document(html)
                content = doc.summary()
                cleaned_content = clean_html_content(content)
                return cleaned_content
    except Exception as e:
        print(f"Error fetching NHK article content: {e}")
        return None

async def fetch_news_async():
    """Main async function to fetch NHK news."""
    try:
        print(f"Starting to fetch NHK news...")
        articles = await fetch_articles_from_rss()
        print(f"Found {len(articles)} articles. Fetching content...")
        
        # Process articles in batches with delay to avoid rate limiting
        tasks = []
        for i, article in enumerate(articles):
            if i > 0 and i % 3 == 0:  # Add delay every 3 requests
                await asyncio.sleep(1)
            tasks.append(fetch_article_content(article['url']))
        contents = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, content in enumerate(contents):
            if isinstance(content, str):
                articles[i]['content'] = content
            else:
                articles[i]['content'] = ""
        
        return {
            'source': 'NHKニュース',
            'link': 'https://www.nhk.or.jp/news/',
            'articles': articles
        }
    except Exception as e:
        print(f"Error in NHK news fetch: {e}")
        return {'error': str(e)}

def fetch_news():
    """Synchronous wrapper for the async function."""
    return asyncio.run(fetch_news_async())

def save_to_file(data, filename_prefix='nhk_jp_news'):
    """Save the scraped data to a JSON file."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs('output', exist_ok=True)
        
        # Generate filename without timestamp
        json_filename = f'output/{filename_prefix}_articles.json'
        html_filename = f'output/{filename_prefix}_articles.html'
        
        # Map incoming data (which uses 'articles') to the feed schema expected by convert_json_to_html ('items')
        articles_data = []
        for article in data.get('articles', []):
            articles_data.append({
                'title': article.get('title', ''),
                'content': article.get('content', ''),
                'source': article.get('source', 'NHKニュース'),
                'url': article.get('url', ''),
                'published': article.get('published', ''),
                'language': article.get('language', 'ja')
            })
        
        feed_data = {
            'title': 'NHK News',
            'link': 'https://www.nhk.or.jp/news/',
            'description': 'Latest news from NHK (Japan Broadcasting Corporation)',
            'language': 'ja',
            'items': articles_data
        }
        
        # Save JSON in expected schema then convert to HTML
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(feed_data, f, ensure_ascii=False, indent=2)
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
        save_to_file(result, 'nhk_jp_news')
