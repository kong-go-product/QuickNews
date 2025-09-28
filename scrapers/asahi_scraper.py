import asyncio
import json
import os
import sys
import feedparser
import aiohttp
import ssl
import re
import time
import random
import requests
from datetime import datetime, timezone
import dateutil.parser
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from readability import Document

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.convert_to_html import convert_json_to_html

def clean_html_content(html_content):
    """
    Clean HTML content by removing unwanted elements while preserving structure.
    Similar to NHK scraper's approach but tailored for Asahi's HTML structure.
    """
    if not html_content:
        return html_content
    
    try:
        # First, use readability to extract the main content
        doc = Document(html_content)
        content_html = doc.summary()
        
        # Parse with BeautifulSoup for additional cleaning
        soup = BeautifulSoup(content_html, 'html.parser')
        
        # Remove script, style, and media elements
        for element in soup(["script", "style", "iframe", "nav", "footer", "img", "picture", "figure", "video", "audio"]):
            element.decompose()
        
        for element in soup.find_all(['a', 'u']):
            element.unwrap()    

        # Remove share and social media elements
        for div in soup.find_all("div", class_=lambda x: x and ('share' in x or 
                                                               'sns' in x or 
                                                               'related' in x or 
                                                               'advertisement' in x.lower() or
                                                               'news-utility' in x or
                                                               'articleFooter' in x)):
            div.decompose()
            
        # Remove empty paragraphs and add some basic styling for better readability
        for p in soup.find_all('p'):
            if not p.get_text().strip():
                p.decompose()
            else:
                # Add a class for styling
                p['class'] = p.get('class', []) + ['article-paragraph']
                
        # Clean up any remaining empty elements
        for element in soup.find_all():
            if not element.get_text().strip() and not element.find_all():
                element.decompose()
                
        # Return the cleaned HTML as a string
        return str(soup)
        
    except Exception as e:
        print(f"Error cleaning HTML content: {e}")
        return "[Error processing content]"

RSS_FEED = "https://rss.asahi.com/rss/asahi/newsheadlines.rdf"

async def fetch_articles_from_rss():
    """Fetch article metadata from Asahi Shimbun RSS feed."""
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    
    feed = feedparser.parse(RSS_FEED)
    articles = []
    
    # The Asahi feed uses RDF format, so we need to check both 'entries' and 'items'
    entries = feed.entries if hasattr(feed, 'entries') else []
    
    for entry in entries[:10]:  # Get latest 10 articles
        try:
            # Handle missing or invalid published date
            published = None
            
            # Check for different possible date fields in the entry
            date_fields = ['published', 'pubDate', 'dc:date', 'dc_date']
            for field in date_fields:
                if hasattr(entry, field):
                    try:
                        published = dateutil.parser.parse(getattr(entry, field))
                        if published.tzinfo is None:
                            published = published.replace(tzinfo=timezone.utc)
                        published = published.isoformat()
                        break
                    except (ValueError, AttributeError, TypeError):
                        continue
            
            # If no valid published date, use current time
            if not published:
                published = datetime.now(timezone.utc).isoformat()
            
            # Extract image URL from description if available
            image_url = ''
            if 'summary' in entry:
                img_match = re.search(r'<img[^>]+src="([^">]+)"', entry.summary)
                if img_match:
                    image_url = img_match.group(1)
            
            articles.append({
                'title': entry.title,
                'url': entry.link,
                'published': published,
                'source': '朝日新聞',
                'summary': BeautifulSoup(entry.get('summary', ''), 'html.parser').get_text(),
                'image': image_url
            })
        except Exception as e:
            print(f"Error processing Asahi article: {e}")
    
    return articles

def fetch_article_content_sync(url):
    """Synchronously fetch and extract article content."""
    try:
        # List of common desktop user agents to rotate
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.asahi.com/',
            'DNT': '1'
        }
        
        # Add a random delay to mimic human behavior
        time.sleep(random.uniform(1.0, 3.0))
        
        # Use a session to maintain cookies
        session = requests.Session()
        
        # First, make a request to the main page to get cookies
        session.get('https://www.asahi.com/', headers=headers, timeout=10)
        
        # Then request the article page
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Clean the HTML content
            cleaned_content = clean_html_content(response.text)
            return cleaned_content
        else:
            print(f"Error fetching Asahi article content: HTTP {response.status_code} - {url}")
            return ""
            
    except Exception as e:
        print(f"Error while processing Asahi article {url}: {str(e)}")
        return ""

async def fetch_article_content(url):
    """Fetch and extract article content using a thread pool."""
    loop = asyncio.get_event_loop()
    # Run the synchronous function in a thread pool
    return await loop.run_in_executor(None, fetch_article_content_sync, url)

async def fetch_news_async():
    """Main async function to fetch Asahi Shimbun news."""
    try:
        print(f"Starting to fetch Asahi Shimbun news...")
        articles = await fetch_articles_from_rss()
        print(f"Found {len(articles)} articles. Fetching content...")
        
        # Process articles one by one to be more gentle on the server
        for i, article in enumerate(articles):
            try:
                print(f"Fetching article {i+1}/{len(articles)}: {article['title']}")
                
                # First, try to get the full content
                content = await fetch_article_content(article['url'])
                
                # If no content was fetched, use the summary from the RSS feed
                if not content or len(content.strip()) < 100:  # 100 chars minimum
                    print(f"Using RSS summary for: {article['title']}")
                    content = f"<p>{article.get('summary', 'No content available.')}</p>"
                
                article['content'] = content
                
                # Add a delay between requests
                if i < len(articles) - 1:
                    delay = random.uniform(2.0, 5.0)
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                print(f"Error processing article {article['url']}: {str(e)}")
                # Use the summary as fallback content
                article['content'] = f"<p>{article.get('summary', 'No content available.')}</p>"
        
        return {
            'source': '朝日新聞',
            'link': 'https://www.asahi.com/',
            'articles': articles
        }
    except Exception as e:
        print(f"Error in fetch_news_async: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}

def fetch_news():
    """Synchronous wrapper for the async function."""
    return asyncio.run(fetch_news_async())
def save_to_html(data, filename_prefix='asahi_news'):
    """Save the scraped data to an HTML file."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs('output', exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_filename = f'output/{filename_prefix}_{timestamp}.json'
        html_filename = f'output/{filename_prefix}_{timestamp}.html'
        
        # Prepare data in the format expected by convert_json_to_html
        articles_data = []
        for article in data.get('articles', []):
            articles_data.append({
                'title': article.get('title', ''),
                'content': article.get('content', ''),
                'source': '朝日新聞',
                'url': article.get('url', ''),
                'published': article.get('published', '')
            })
        
        # Create the feed data structure
        feed_data = {
            'title': 'Asahi Shimbun',
            'link': 'https://www.asahi.com/',
            'description': 'Latest news from Asahi Shimbun',
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

if __name__ == "__main__":
    # Run the scraper
    result = asyncio.run(fetch_news_async())
    
    # Print to console
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Save to HTML file
    if 'error' not in result:
        save_to_html(result, 'asahi_news')
