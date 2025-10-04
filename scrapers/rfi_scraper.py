import asyncio
import json
import os
import sys
import random
import feedparser
import ssl
import pytz
from bs4 import BeautifulSoup
from readability import Document
from datetime import datetime, timezone, timedelta
import dateutil.parser
from playwright.async_api import async_playwright

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.convert_to_html import convert_json_to_html


def clean_html_content(html_content: str) -> str:
    """Clean HTML content by removing unwanted classes and elements."""
    if not html_content:
        return html_content

    soup = BeautifulSoup(html_content, 'html.parser')

    unwanted_classes = [
        'ad', 'advertisement', 'share-tools', 'related-links', 'newsletter',
        'newsletter-signup', 'comments', 'author-info', 'timestamp', 'tags',
        'social', 'media-wrapper', 'player', 'embed', 'footer', 'header'
    ]
    for class_name in unwanted_classes:
        for element in soup.find_all(class_=class_name):
            element.decompose()

    # Remove scripts, styles, embeds
    for element in soup(['script', 'style', 'noscript', 'iframe', 'object', 'embed']):
        element.decompose()

    # Remove media and unwrap anchors/underline
    for el in soup.find_all(['img', 'video', 'picture', 'figure']):
        el.decompose()
    for el in soup.find_all(['a', 'u']):
        el.unwrap()

    # Remove empty elements / attributes
    for element in soup.find_all(True):
        for attr in list(element.attrs.keys()):
            if not element[attr]:
                del element[attr]
        if not element.get_text(strip=True) and not element.find_all(True):
            element.decompose()

    return str(soup)


# RFI main RSS (FR)
RSS_FEED = "https://www.rfi.fr/fr/rss"

# Create unverified SSL context
ssl._create_default_https_context = ssl._create_unverified_context


def fetch_articles_from_rss():
    """Fetch article metadata from RFI RSS feed."""
    print(f"\nFetching RFI feed: {RSS_FEED}")

    utc = pytz.utc
    now = datetime.now(utc)
    yesterday = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=utc)

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
                    pub_date = utc.localize(pub_date)
                if pub_date < yesterday or pub_date > now:
                    continue
            except Exception as e:
                print(f"Error parsing date for article: {str(e)}")
                continue

            link = entry.get('link', '')
            if not link:
                continue

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
                'source': 'RFI',
                'pub_time': pub_date.isoformat(),
                'description': entry.get('description', ''),
                'image_url': image_url,
                'author': author,
                'content': ''  # Will be filled by fetch_article_content
            }
            print(f"Found article from {article['pub_time']}: {article['title']}")
            articles.append(article)

    except Exception as e:
        print(f"Error fetching RSS feed: {str(e)}")

    return articles


USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
]

async def fetch_article_content(url: str, browser) -> str:
    """Fetch and extract article content using Playwright with incognito contexts and rotation."""
    tries = 2
    for attempt in range(tries):
        try:
            ua = random.choice(USER_AGENTS)
            context = await browser.new_context(
                user_agent=ua,
                locale='fr-FR',
                timezone_id='Europe/Paris',
                java_script_enabled=True,
                bypass_csp=True,
                extra_http_headers={
                    'Referer': 'https://www.rfi.fr/fr/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7'
                }
            )
            page = await context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(500 + random.randint(0, 800))
            html = await page.content()
            await context.close()

            doc = Document(html)
            content = doc.summary()
            soup = BeautifulSoup(content, 'html.parser')
            for el in soup.find_all(['img', 'video', 'iframe', 'picture', 'figure']):
                el.decompose()
            for el in soup.find_all(['a', 'u']):
                el.unwrap()
            cleaned = clean_html_content(str(soup))
            if cleaned and len(cleaned) > 50:
                return cleaned
        except Exception as e:
            print(f"Error fetching article (attempt {attempt+1}) {url}: {str(e)}")
            await asyncio.sleep(0.5)
    return "[Error: Failed to extract content]"


async def fetch_news():
    """Main function to fetch and process news articles for RFI."""
    print("Fetching RFI metadata and content...")
    articles = fetch_articles_from_rss()
    print(f"\nFound {len(articles)} articles in total")

    # Optional proxy support via env QUICKNEWS_HTTP_PROXY
    proxy_server = os.environ.get('QUICKNEWS_HTTP_PROXY')

    # Fetch full article content using Playwright
    print("\nExtracting full article content with browser automation...")
    async with async_playwright() as p:
        launch_kwargs = {"headless": True}
        if proxy_server:
            launch_kwargs["proxy"] = {"server": proxy_server}
        browser = await p.chromium.launch(**launch_kwargs)
        tasks = [fetch_article_content(article['link'], browser) for article in articles]
        contents = await asyncio.gather(*tasks)
        await browser.close()

    # Update articles with fetched content and filter valid ones
    valid_articles = []
    for i, content in enumerate(contents):
        if i < len(articles):
            if content and content.strip() and not content.startswith('[Error:') and len(content) > 50:
                articles[i]['content'] = content
                valid_articles.append(articles[i])
            else:
                print(f"Skipping article with invalid content: {articles[i]['title']}")
    
    print(f"\nSuccessfully extracted {len(valid_articles)} articles with full content")

    feed_object = {
        'title': 'RFI',
        'link': 'https://www.rfi.fr/fr/',
        'description': "Dernières actualités de RFI",
        'items': valid_articles,
    }

    os.makedirs('output', exist_ok=True)
    json_file = 'output/rfi_articles.json'
    html_file = 'output/rfi_articles.html'

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(feed_object, f, ensure_ascii=False, indent=2)
    print(f"\nJSON file saved to: {os.path.abspath(json_file)}")

    convert_json_to_html(json_file, html_file)
    print(f"HTML file saved to: {os.path.abspath(html_file)}")

    return feed_object


if __name__ == '__main__':
    result = asyncio.run(fetch_news())
    print(json.dumps(result, indent=2, ensure_ascii=False))
