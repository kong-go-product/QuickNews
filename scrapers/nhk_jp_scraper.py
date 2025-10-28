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

# Standard library
import json as _json
import random
import asyncio as _asyncio

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

def _extract_from_json_ld(html: str) -> str | None:
    """Try to extract articleBody from JSON-LD structures if present."""
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup.find_all('script', type='application/ld+json'):
            try:
                data = _json.loads(tag.string or '')
            except Exception:
                continue
            # JSON-LD may be an object or a list
            candidates = data if isinstance(data, list) else [data]
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                typ = item.get('@type') or item.get('type')
                if isinstance(typ, list):
                    typ = next((t for t in typ if isinstance(t, str)), None)
                if typ and ('Article' in str(typ) or 'NewsArticle' in str(typ)):
                    body = item.get('articleBody') or item.get('description')
                    if body and isinstance(body, str) and len(body.strip()) > 60:
                        # Wrap plain text paragraphs in <p>
                        paragraphs = [f"<p>{p.strip()}</p>" for p in body.split('\n') if p.strip()]
                        return '\n'.join(paragraphs) if paragraphs else f"<p>{body}</p>"
    except Exception:
        pass
    return None

def _extract_from_selectors(html: str) -> str | None:
    """Try common NHK article selectors as a fallback."""
    soup = BeautifulSoup(html, 'html.parser')
    # Known/likely containers for main body; keep broad but safe
    selector_candidates = [
        '#news_textbody',
        'div#news_textbody',
        'article .content',
        'article .article-body',
        'div.content--detail-body',
        'div.module--content',
        'main .content',
        'main article',
    ]
    for sel in selector_candidates:
        node = soup.select_one(sel)
        if node:
            # Collect paragraphs
            ps = node.find_all(['p', 'li'])
            text_parts = []
            for p in ps:
                t = p.get_text(strip=True)
                if t and ('NHK' not in t and 'All rights reserved' not in t):
                    text_parts.append(f"<p>{t}</p>")
            content = '\n'.join(text_parts)
            if len(BeautifulSoup(content, 'html.parser').get_text().strip()) > 80:
                return content
    # As last resort, use all paragraphs on page (risky but better than boilerplate)
    ps = soup.find_all('p')
    text_parts = [f"<p>{p.get_text(strip=True)}</p>" for p in ps if p.get_text(strip=True)]
    content = '\n'.join(text_parts)
    if len(BeautifulSoup(content, 'html.parser').get_text().strip()) > 120:
        return content
    return None

def _is_trivial_content(html: str) -> bool:
    if not html:
        return True
    txt = BeautifulSoup(html, 'html.parser').get_text(separator=' ').strip()
    if len(txt) < 80:
        return True
    # Detect common NHK copyright-only boilerplate
    if 'Copyright NHK' in txt or '許可なく転載することを禁じます' in txt:
        return True
    return False

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
    """Fetch and extract article content using a robust multi-step strategy."""
    try:
        # Rotate among a few realistic mobile/desktop UAs
        uas = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
        ]
        headers = {
            'User-Agent': random.choice(uas),
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.nhk.or.jp/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }

        timeout = aiohttp.ClientTimeout(total=20)
        # Simple retry logic, try normal and AMP variants
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    html = None
                    for target_url in (url, f"{url}?amp=1"):
                        async with session.get(target_url, headers=headers, ssl=False) as response:
                            if response.status == 403:
                                # Likely blocked; change UA and retry this attempt once
                                headers['User-Agent'] = random.choice(uas)
                                continue
                            if response.status >= 400:
                                continue
                            html = await response.text()
                            if html:
                                break
                    if not html:
                        await _asyncio.sleep(0.5 * (attempt + 1))
                        continue

                # 1) Try Readability first
                doc = Document(html)
                content = doc.summary() or ''
                content = clean_html_content(content)
                if not _is_trivial_content(content):
                    return content

                # 2) JSON-LD articleBody
                ld = _extract_from_json_ld(html)
                if ld and not _is_trivial_content(ld):
                    return clean_html_content(ld)

                # 3) Selector-based extraction
                sel = _extract_from_selectors(html)
                if sel and not _is_trivial_content(sel):
                    return clean_html_content(sel)

            except Exception:
                # Backoff and retry
                await _asyncio.sleep(0.5 * (attempt + 1))

        return None
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
