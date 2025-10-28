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
from readability import Document

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.convert_to_html import convert_json_to_html as base_convert_json_to_html

def convert_json_to_html(json_file, output_file):
    """
    Local wrapper (same pattern as Asahi) to optionally tweak body before delegating.
    Currently passes through, but kept for parity and future adjustments.
    """
    try:
        # Load, optionally adjust, then save back before delegating
        with open(json_file, 'r', encoding='utf-8') as f:
            feed = json.load(f)

        items = feed.get('items', [])
        for item in items:
            body_html = item.get('content') or ''
            if not body_html:
                continue
            soup = BeautifulSoup(body_html, 'html.parser')
            # Remove first <h1> to prevent duplicate titles if present
            h1 = soup.find('h1')
            if h1:
                h1.decompose()
            item['content'] = str(soup)

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(feed, f, ensure_ascii=False, indent=2)

        return base_convert_json_to_html(json_file, output_file)
    except Exception as e:
        print(f"Error in Mainichi convert_json_to_html wrapper: {e}")
        return base_convert_json_to_html(json_file, output_file)


def clean_html_content(html_content: str) -> str:
    """Clean article HTML using Readability then strip noisy elements (mirrors Asahi style)."""
    if not html_content:
        return html_content
    try:
        doc = Document(html_content)
        content_html = doc.summary()

        soup = BeautifulSoup(content_html, 'html.parser')

        # Remove scripts, styles, media, utility blocks
        for el in soup(["script", "style", "iframe", "nav", "footer", "img", "picture", "figure", "video", "audio"]):
            el.decompose()

        for el in soup.find_all(['a', 'u']):
            el.unwrap()

        # Remove obvious share/utility containers
        def _cls(x):
            try:
                return (x and ('share' in x or 'sns' in x or 'related' in x or 'advertisement' in x.lower() or 'utility' in x))
            except Exception:
                return False
        for div in soup.find_all("div", class_=_cls):
            div.decompose()

        # Remove empty paragraphs and tag paragraphs for styling
        for p in soup.find_all('p'):
            if not p.get_text().strip():
                p.decompose()
            else:
                p['class'] = p.get('class', []) + ['article-paragraph']

        # Drop any remaining empty nodes
        for el in soup.find_all():
            if not el.get_text().strip() and not el.find_all():
                el.decompose()

        return str(soup)
    except Exception as e:
        print(f"Error cleaning HTML content: {e}")
        return "[Error processing content]"


RSS_FEED = "https://mainichi.jp/rss/etc/mainichi-flash.rss"

async def fetch_articles_from_rss():
    """Fetch article metadata from Mainichi RSS feed (flash)."""
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context

    feed = feedparser.parse(RSS_FEED)
    articles = []

    entries = feed.entries if hasattr(feed, 'entries') else []

    for entry in entries[:10]:
        try:
            # published/pubDate handling
            published_iso = None
            date_fields = ['published', 'pubDate', 'dc:date', 'dc_date', 'updated']
            for field in date_fields:
                if hasattr(entry, field):
                    try:
                        dt = dateutil.parser.parse(getattr(entry, field))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        published_iso = dt.isoformat()
                        break
                    except Exception:
                        continue
            if not published_iso:
                published_iso = datetime.now(timezone.utc).isoformat()

            # summary/description
            summary_html = entry.get('summary', '')
            summary_text = BeautifulSoup(summary_html, 'html.parser').get_text()

            # image via media:thumbnail in some feeds
            image_url = ''
            media_thumbnail = getattr(entry, 'media_thumbnail', None)
            if media_thumbnail and isinstance(media_thumbnail, list) and media_thumbnail:
                image_url = media_thumbnail[0].get('url', '')
            else:
                # Attempt to capture from summary <img>
                img_match = re.search(r'<img[^>]+src="([^">]+)"', summary_html)
                if img_match:
                    image_url = img_match.group(1)

            articles.append({
                'title': entry.title,
                'url': entry.link,
                'published': published_iso,
                'source': '毎日新聞',
                'summary': summary_text,
                'image': image_url,
                'language': 'ja'
            })
        except Exception as e:
            print(f"Error processing Mainichi article: {e}")

    return articles


def fetch_article_content_sync(url: str) -> str:
    """Synchronously fetch and extract article content (Asahi-style approach)."""
    try:
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
        ]
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://mainichi.jp/',
            'DNT': '1'
        }

        # Random human-like delay
        time.sleep(random.uniform(1.0, 2.5))

        session = requests.Session()
        session.get('https://mainichi.jp/', headers=headers, timeout=12)
        resp = session.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            return clean_html_content(resp.text)
        else:
            print(f"Error fetching Mainichi article content: HTTP {resp.status_code} - {url}")
            return ""
    except Exception as e:
        print(f"Error while processing Mainichi article {url}: {str(e)}")
        return ""


async def fetch_article_content(url: str) -> str:
    """Fetch and extract article content using a thread pool (same as Asahi)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fetch_article_content_sync, url)


async def fetch_news_async():
    """Main async function to fetch Mainichi news (flash RSS)."""
    try:
        print("Starting to fetch Mainichi news...")
        articles = await fetch_articles_from_rss()
        print(f"Found {len(articles)} articles. Fetching content...")

        for i, article in enumerate(articles):
            try:
                print(f"Fetching article {i+1}/{len(articles)}: {article['title']}")
                content = await fetch_article_content(article['url'])

                # If content empty/too short, fallback to summary or link-out
                from bs4 import BeautifulSoup as _BS
                text_len = len(_BS(content or "", 'html.parser').get_text().strip())
                if not content or text_len < 60:
                    summary_text = (article.get('summary') or '').strip()
                    if summary_text:
                        content = f"<p>{summary_text}</p>"
                    else:
                        content = (
                            f"<p>本文を取得できませんでした。</p>"
                            f"<p><a href=\"{article['url']}\" target=\"_blank\" rel=\"noopener\">記事を読む</a></p>"
                        )

                article['content'] = content

                # Gentle delay
                if i < len(articles) - 1:
                    await asyncio.sleep(random.uniform(1.5, 3.0))

            except Exception as e:
                print(f"Error processing article {article['url']}: {str(e)}")
                article['content'] = f"<p>{article.get('summary', 'No content available.')}</p>"

        return {
            'source': '毎日新聞',
            'link': 'https://mainichi.jp/',
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


def save_to_html(data, filename_prefix='mainichi_news'):
    """Save the scraped data to an HTML file (same pipeline shape as Asahi)."""
    try:
        os.makedirs('output', exist_ok=True)
        json_filename = f'output/{filename_prefix}_articles.json'
        html_filename = f'output/{filename_prefix}_articles.html'

        # Prepare data for converter
        articles_data = []
        for article in data.get('articles', []):
            articles_data.append({
                'title': article.get('title', ''),
                'content': article.get('content', ''),
                'source': '毎日新聞',
                'url': article.get('url', ''),
                'published': article.get('published', '')
            })

        feed_data = {
            'title': 'Mainichi Flash',
            'link': 'https://mainichi.jp/',
            'description': 'Latest flash news from Mainichi',
            'language': 'ja',
            'items': articles_data
        }

        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(feed_data, f, indent=2, ensure_ascii=False)

        convert_json_to_html(json_filename, html_filename)
        print(f"Data saved to {html_filename}")
        return html_filename
    except Exception as e:
        print(f"Error saving to file: {e}")
        return None


if __name__ == "__main__":
    result = asyncio.run(fetch_news_async())
    try:
        count = len((result or {}).get('articles', []))
        print(f"Mainichi: fetched {count} articles.")
    except Exception:
        print("Mainichi: finished (no summary available).")
    if 'error' not in result:
        save_to_html(result, 'mainichi_news')
