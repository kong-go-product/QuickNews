import asyncio
import json
import os
import sys
import feedparser
import requests
import re
import time
import random
from datetime import datetime, timezone
import dateutil.parser
from bs4 import BeautifulSoup
from readability import Document

# Add parent directory to path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.convert_to_html import convert_json_to_html as base_convert_json_to_html


def convert_json_to_html(json_file, output_file):
    """
    Local wrapper to optionally tweak body before delegating.
    Mirrors euronews_scraper but enforces UTF-8 I/O.
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            feed = json.load(f)

        items = feed.get('items', [])
        for item in items:
            body_html = item.get('content') or ''
            if not body_html:
                continue
            soup = BeautifulSoup(body_html, 'html.parser')
            h1 = soup.find('h1')
            if h1:
                h1.decompose()
            item['content'] = str(soup)

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(feed, f, ensure_ascii=False, indent=2)

        return base_convert_json_to_html(json_file, output_file)
    except Exception as e:
        print(f"Error in Euronews UTF-8 convert_json_to_html wrapper: {e}")
        return base_convert_json_to_html(json_file, output_file)


def clean_html_content(html_content: str) -> str:
    """Clean article HTML using Readability then strip noisy elements."""
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

        # Remove generic ad containers often present on Euronews
        for div in soup.find_all('div', class_=lambda x: x and ('c-ad' in x)):
            div.decompose()

        # Remove contributor and publication date blocks
        for p in soup.find_all('p', class_=lambda x: x and ('c-article-contributors' in x)):
            p.decompose()
        for p in soup.find_all('p', class_=lambda x: x and ('c-article-publication-date' in x)):
            p.decompose()
        for d in soup.find_all('div', class_=lambda x: x and ('o-article-newsy__contributors-publication-date' in x)):
            d.decompose()

        # Remove standalone ad label spans like PUBLICITÉ
        for sp in soup.find_all('span'):
            t = sp.get_text(strip=True)
            if not t:
                continue
            t_simple = t.replace('\xa0', ' ').strip()
            t_fold = t_simple.casefold()
            if t_fold in ('publicité', 'publicite'):
                sp.decompose()

        # Unwrap any stray <body> inserted by Readability
        for b in soup.find_all('body'):
            b.unwrap()

        # Remove empty paragraphs and tag paragraphs for styling
        for p in soup.find_all('p'):
            if not p.get_text().strip():
                p.decompose()
            else:
                p['class'] = p.get('class', []) + ['article-paragraph']

        # Prepend original summary header if available (Euronews: h2.c-article-summary)
        try:
            orig = BeautifulSoup(html_content, 'html.parser')
            sum_h2 = orig.find('h2', class_=lambda x: x and ('c-article-summary' in x))
            if sum_h2:
                frag = BeautifulSoup(str(sum_h2), 'html.parser')
                soup.insert(0, frag)
        except Exception:
            pass

        # Drop any remaining empty nodes
        for el in soup.find_all():
            if not el.get_text().strip() and not el.find_all():
                el.decompose()

        return str(soup)
    except Exception as e:
        print(f"Error cleaning HTML content: {e}")
        return "[Error processing content]"


# UTF-8 only character decoding

def _decode_response_utf8(resp) -> str:
    try:
        # Avoid advertising Brotli to keep decoding simple; requests handles gzip/deflate
        raw = resp.content
        # Force UTF-8 only. Use 'replace' to avoid exceptions but never change charset.
        return raw.decode('utf-8', errors='replace')
    except Exception:
        try:
            return resp.text  # requests may already have decoded as utf-8
        except Exception:
            return ""


def _extract_paragraphs_from_html(html: str) -> str:
    try:
        soup = BeautifulSoup(html, 'html.parser')
        main = (
            soup.find('div', class_=lambda x: x and ('c-article-content' in x or 'js-article-content' in x))
            or soup.find('article')
            or soup.find('main')
            or soup
        )
        ps = main.find_all('p')
        out = []
        for p in ps:
            txt = p.get_text(strip=True)
            if len(txt) >= 40:
                p['class'] = p.get('class', []) + ['article-paragraph']
                out.append(p)
        if out:
            container = soup.new_tag('div')
            for p in out:
                container.append(p)
            return str(container)
        return ""
    except Exception:
        return ""


def _fetch_amp_content(session, headers, url: str) -> str:
    try:
        r0 = session.get(url, headers=headers, timeout=12)
        h0 = _decode_response_utf8(r0)
        s0 = BeautifulSoup(h0, 'html.parser')
        link = s0.find('link', rel=lambda x: x and ('amphtml' in x))
        if not link:
            return ""
        amp = link.get('href')
        if not amp:
            return ""
        r = session.get(amp, headers=headers, timeout=12)
        h = _decode_response_utf8(r)
        s = BeautifulSoup(h, 'html.parser')
        main = s.find('main') or s.find('article') or s
        ps = main.find_all('p')
        out = []
        for p in ps:
            txt = p.get_text(strip=True)
            if len(txt) >= 40:
                p['class'] = p.get('class', []) + ['article-paragraph']
                out.append(p)
        if out:
            container = s.new_tag('div')
            for p in out:
                container.append(p)
            return str(container)
        return ""
    except Exception:
        return ""


# Euronews FR RSS
RSS_FEED = "https://fr.euronews.com/rss?format=mrss&level=theme&name=news"


async def fetch_articles_from_rss():
    """Fetch article metadata from Euronews FR RSS feed (UTF-8 pipeline)."""
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

            # image via media:content or enclosure
            image_url = ''
            media_content = getattr(entry, 'media_content', None)
            if media_content and isinstance(media_content, list) and media_content:
                first = media_content[0]
                if isinstance(first, dict):
                    image_url = first.get('url', '')
                else:
                    image_url = getattr(first, 'url', '')
            else:
                img_match = re.search(r'<img[^>]+src="([^"]+)"', summary_html or '')
                if img_match:
                    image_url = img_match.group(1)

            link = entry.get('link') or ''
            if link.startswith('http://fr.euronews.com'):
                link = link.replace('http://', 'https://', 1)

            # Skip video pages for text extraction
            if '/video/' in link:
                continue

            articles.append({
                'title': entry.get('title', 'No title'),
                'url': link,
                'published': published_iso,
                'source': 'Euronews',
                'summary': summary_text,
                'image': image_url,
                'language': 'fr'
            })
        except Exception as e:
            print(f"Error processing Euronews article: {e}")

    return articles


def fetch_article_content_sync(url: str) -> str:
    """Synchronously fetch and extract article content enforcing UTF-8-only decoding."""
    try:
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
        ]
        headers = {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            # Avoid Brotli to keep character decoding strictly UTF-8 from raw bytes
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://fr.euronews.com/',
            'DNT': '1'
        }

        # Random human-like delay
        time.sleep(random.uniform(1.0, 2.5))

        session = requests.Session()
        session.get('https://fr.euronews.com/', headers=headers, timeout=12)
        resp = session.get(url, headers=headers, timeout=12)
        if resp.status_code == 200:
            html = _decode_response_utf8(resp)
            cleaned = clean_html_content(html)
            from bs4 import BeautifulSoup as _BS
            txt = _BS(cleaned or "", 'html.parser').get_text(" ", strip=True)
            if len(txt) < 160:
                amp_body = _fetch_amp_content(session, headers, url)
                if amp_body:
                    txt2 = _BS(amp_body, 'html.parser').get_text(" ", strip=True)
                    if len(txt2) >= 160:
                        return amp_body
                para_body = _extract_paragraphs_from_html(html)
                if para_body:
                    txt3 = _BS(para_body, 'html.parser').get_text(" ", strip=True)
                    if len(txt3) >= 160:
                        return para_body
            return cleaned
        else:
            print(f"Error fetching Euronews article content: HTTP {resp.status_code} - {url}")
            return ""
    except Exception as e:
        print(f"Error while processing Euronews article {url}: {str(e)}")
        return ""


async def fetch_article_content(url: str) -> str:
    """Fetch and extract article content using a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fetch_article_content_sync, url)


async def fetch_news_async():
    """Main async function to fetch Euronews FR news (UTF-8-only)."""
    try:
        print("Starting to fetch Euronews FR news (UTF-8-only)...")
        articles = await fetch_articles_from_rss()
        print(f"Found {len(articles)} articles. Fetching content...")

        for i, article in enumerate(articles):
            try:
                print(f"Fetching article {i+1}/{len(articles)}: {article['title']}")
                content = await fetch_article_content(article['url'])

                from bs4 import BeautifulSoup as _BS
                text_len = len(_BS(content or "", 'html.parser').get_text().strip())
                if not content or text_len < 60:
                    summary_text = (article.get('summary') or '').strip()
                    if summary_text:
                        content = f"<p>{summary_text}</p>"
                    else:
                        content = (
                            f"<p>Contenu complet indisponible.</p>"
                            f"<p><a href=\"{article['url']}\" target=\"_blank\" rel=\"noopener\">Lire l'article</a></p>"
                        )

                article['content'] = content

                # Gentle delay
                if i < len(articles) - 1:
                    await asyncio.sleep(random.uniform(1.5, 3.0))

            except Exception as e:
                print(f"Error processing article {article['url']}: {str(e)}")
                article['content'] = f"<p>{article.get('summary', 'No content available.')}</p>"

        return {
            'source': 'Euronews',
            'link': 'https://fr.euronews.com/',
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


def save_to_html(data, filename_prefix='euronews_utf8'):
    """Save the scraped data to an HTML file (UTF-8-only pipeline)."""
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
                'source': 'Euronews',
                'url': article.get('url', ''),
                'published': article.get('published', ''),
                'language': 'fr'
            })

        feed_data = {
            'title': 'Euronews (FR)',
            'link': 'https://fr.euronews.com/',
            'description': 'Dernières actualités de Euronews',
            'language': 'fr',
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
        print(f"Euronews FR (UTF-8-only): fetched {count} articles.")
    except Exception:
        print("Euronews FR (UTF-8-only): finished (no summary available).")
    if 'error' not in result:
        save_to_html(result, 'euronews_utf8')
