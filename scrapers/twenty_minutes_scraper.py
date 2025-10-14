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
import random

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.convert_to_html import convert_json_to_html


def clean_html_content(html_content: str) -> str:
    """Clean HTML content by removing unwanted classes and elements."""
    if not html_content:
        return html_content

    soup = BeautifulSoup(html_content, 'html.parser')

    unwanted_classes = [
        'ad', 'advertisement', 'share', 'related', 'newsletter', 'comments',
        'author-info', 'timestamp', 'tags', 'social', 'player', 'embed',
        'footer', 'header', 'subscription', 'paywall'
    ]
    for class_name in unwanted_classes:
        for element in soup.find_all(class_=class_name):
            element.decompose()

    # Remove scripts, styles, embeds and media
    for element in soup(['script', 'style', 'noscript', 'iframe', 'object', 'embed', 'img', 'video', 'picture', 'figure', 'audio']):
        element.decompose()

    # Unwrap anchors/underline and inline wrappers
    for el in soup.find_all(['a', 'u', 'span', 'strong', 'em', 'b', 'i', 'font']):
        el.unwrap()

    # Strip attributes and remove empty elements
    for element in soup.find_all(True):
        element.attrs = {}
    removed = True
    while removed:
        removed = False
        for el in list(soup.find_all(True)):
            if not el.get_text(strip=True) and not el.find(True):
                el.decompose()
                removed = True

    return str(soup)


# 20 Minutes RSS (Monde)
RSS_FEED = "https://www.20minutes.fr/feeds/rss-monde.xml"

# Create unverified SSL context (some feeds have cert issues in CI)
ssl._create_default_https_context = ssl._create_unverified_context


def fetch_articles_from_rss():
    """Fetch article metadata from 20 Minutes RSS feed for the last 24h."""
    print(f"\nFetching 20 Minutes feed: {RSS_FEED}")

    tz = pytz.timezone('Europe/Paris')
    now = datetime.now(tz)
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=tz)

    articles = []

    try:
        feed = feedparser.parse(RSS_FEED)
        print(f"Feed status: {feed.get('status')}")
        print(f"Number of entries: {len(feed.entries)}")

        for entry in feed.entries:
            # Parse publication date
            try:
                pub_date_str = entry.get('published', '') or entry.get('pubDate', '')
                if not pub_date_str and hasattr(entry, 'published_parsed'):
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                else:
                    pub_date = dateutil.parser.parse(pub_date_str)
                if pub_date.tzinfo is None:
                    pub_date = tz.localize(pub_date)
                # Filter to yesterday..now
                if pub_date < yesterday or pub_date > now:
                    continue
            except Exception as e:
                print(f"Error parsing date for article: {str(e)}")
                continue

            link = entry.get('link', '')
            if not link:
                continue

            # Try to extract image
            image_url = ''
            if hasattr(entry, 'media_content') and entry.media_content:
                for media in entry.media_content:
                    if hasattr(media, 'url') and media.url:
                        image_url = media.url
                        break
            elif hasattr(entry, 'links'):
                for l in entry.links:
                    if l.get('rel') == 'enclosure' and 'image' in l.get('type', '') and l.get('href'):
                        image_url = l['href']
                        break

            author = ''
            if hasattr(entry, 'dc_creator'):
                author = entry.dc_creator
            elif hasattr(entry, 'author'):
                author = entry.author

            article = {
                'title': entry.get('title', 'No title'),
                'link': link,
                'source': '20 Minutes',
                'pub_time': pub_date.isoformat(),
                'description': entry.get('description', ''),
                'image_url': image_url,
                'author': author,
                'content': ''
            }
            print(f"Found article from {article['pub_time']}: {article['title']}")
            articles.append(article)

    except Exception as e:
        print(f"Error fetching RSS feed: {str(e)}")

    return articles


async def fetch_article_content(url: str) -> str:
    """Fetch and extract article content using Readability with basic UA rotation."""
    uas = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    ]
    timeout = aiohttp.ClientTimeout(total=25)

    for attempt in range(3):
        headers = {
            'User-Agent': random.choice(uas),
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers, ssl=False) as response:
                    if response.status >= 400:
                        await asyncio.sleep(0.4 * (attempt + 1))
                        continue
                    html = await response.text()
            doc = Document(html)
            content = doc.summary() or ''
            cleaned = clean_html_content(content)
            text_len = len(BeautifulSoup(cleaned, 'html.parser').get_text().strip())
            if text_len >= 60:
                return cleaned
        except Exception as e:
            print(f"Error fetching article (attempt {attempt+1}) {url}: {e}")
            await asyncio.sleep(0.5 * (attempt + 1))
            continue
    return ""


async def fetch_news_async():
    """Main async function to fetch 20 Minutes articles and contents."""
    articles = fetch_articles_from_rss()
    tasks = [fetch_article_content(a['link']) for a in articles]
    contents = await asyncio.gather(*tasks, return_exceptions=True)

    valid_articles = []
    for i, content in enumerate(contents):
        if isinstance(content, str) and content.strip():
            articles[i]['content'] = content
            valid_articles.append(articles[i])

    feed_object = {
        'title': '20 Minutes',
        'link': 'https://www.20minutes.fr/',
        'description': 'Dernières actualités de 20 Minutes',
        'items': valid_articles,
    }

    os.makedirs('output', exist_ok=True)
    json_file = 'output/20minutes_articles.json'
    html_file = 'output/20minutes_articles.html'

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(feed_object, f, ensure_ascii=False, indent=2)
    convert_json_to_html(json_file, html_file)
    print(f"Saved: {os.path.abspath(html_file)}")

    return feed_object


def fetch_news():
    return asyncio.run(fetch_news_async())


if __name__ == '__main__':
    result = asyncio.run(fetch_news_async())
    try:
        items = (result or {}).get('items') or []
        print(f"20 Minutes: fetched {len(items)} items.")
    except Exception:
        print("20 Minutes: finished (no summary available).")
