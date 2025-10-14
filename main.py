import subprocess
import os
import sys
from bs4 import BeautifulSoup
import os
from datetime import datetime
import pytz


def run_scrapers(region:str):
    """Run all individual scraper scripts."""
    
    if region == 'us':
        scrapers = [
            'scrapers/foxnews_scraper.py',
            'scrapers/cbs_scraper.py',
            'scrapers/npr_scraper.py'
        ]
    
    elif region == 'jp':
        scrapers = [
            'scrapers/mainichi_scraper.py',
            'scrapers/asahi_scraper.py',
            'scrapers/kyodo_scraper.py'
        ]
    
    elif region == 'fr':
        scrapers = [
            'scrapers/euronews_scraper.py',
            'scrapers/rfi_scraper.py',
            'scrapers/twenty_minutes_scraper.py',
        ]
    
    print("Running scrapers...")
    for scraper in scrapers:
        try:
            print(f"Running {scraper}...")
            # Use the same Python interpreter
            subprocess.run([sys.executable, scraper], check=True, env={
                **os.environ,
                'PYTHONPATH': os.path.dirname(os.path.abspath(__file__))
            })
        except subprocess.CalledProcessError as e:
            print(f"Error running {scraper}: {e}")
            continue

def combine_news_articles(region:str):
    # First, run all scrapers
    run_scrapers(region)
    
    # List of HTML files to combine
    if region == 'us':
        html_files = [
            'output/fox_news_articles.html',
            'output/cbs_news_articles.html',
            'output/npr_news_articles.html'
        ]
    elif region == 'jp':
        html_files = [
            'output/mainichi_news_articles.html',
            'output/asahi_news_articles.html',
            'output/kyodo_news_articles.html',
        ]
    elif region == 'fr':
        html_files = [
            'output/euronews_utf8_articles.html',
            'output/rfi_articles.html',
            'output/20minutes_articles.html',
        ]
    
    with open('static/styles.css', 'r', encoding='utf-8') as f:
        css_style = f.read()

    # Create a new BeautifulSoup object for the combined content
    # Choose timezone based on region for title and on-page timestamp
    if region == 'us':
        tz = pytz.timezone('US/Eastern')
        tz_label = 'ET'
    elif region == 'jp':
        tz = pytz.timezone('Asia/Tokyo')
        tz_label = 'JST'
    elif region == 'fr':
        tz = pytz.timezone('Europe/Paris')
        tz_label = 'CET'
    else:
        # Default to US settings
        tz = pytz.timezone('US/Eastern')
        tz_label = 'ET'
    
    date_str_title = datetime.now(tz).strftime('%Y-%m-%d')
    # Localize timestamp label based on region
    if region == 'us':
        timestamp_prefix = 'Updated'
    elif region == 'jp':
        timestamp_prefix = '更新'
    elif region == 'fr':
        timestamp_prefix = 'Mis à jour'
    else:
        timestamp_prefix = 'Updated'
    
    soup = BeautifulSoup(f'''<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QuickNews - {date_str_title}</title>
        <style>{css_style}</style>
    </head>
    <body>
        <div class="timestamp">{timestamp_prefix}: {datetime.now(tz).strftime('%H:%M ' + tz_label + ', %A, %b %d %Y')}</div>
        <div class="articles-container">
            <!-- Articles will be inserted here -->
        </div>
    </body>
    </html>''', 'html.parser')
    
    # Find the container where articles will be inserted
    container = soup.find('div', class_='articles-container')
    
    # Process each HTML file
    for file_path in html_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
                
            # Parse the current HTML file
            file_soup = BeautifulSoup(file_content, 'html.parser')
            
            # Find all articles in the current file
            articles = file_soup.find_all('div', class_='article')
            
            # Add each article to the combined container
            for article in articles:
                container.append(article)
                
            print(f"Processed: {file_path}")
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Skipping.")
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    # Use common 'newspaper' output directory (no region-specific subfolders)
    output_dir = 'newspaper'
    os.makedirs(output_dir, exist_ok=True)

    # Also update a stable alias without date for easy linking
    alias_file = os.path.join(output_dir, f'QuickNews_{region}.html')
    with open(alias_file, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    
    print(f"\nNews articles saved to: {alias_file}")
    
    # Create/update index.html with a region selection list linking to stable alias files
    index_file = os.path.join(output_dir, 'index.html')
    index_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>QuickNews</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" type="text/css" href="../static/styles.css">
    <style>
        .region-list {{
            max-width: 560px;
            margin: 60px auto;
            padding: 24px;
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        .region-list h1 {{
            margin: 0 0 16px 0;
            font-size: 22px;
        }}
        .region-list p {{
            margin: 0 0 20px 0;
            color: #555;
        }}
        .region-list ul {{
            list-style: none;
            padding: 0;
            margin: 0;
            display: grid;
            gap: 12px;
        }}
        .region-list a {{
            display: block;
            padding: 12px 14px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            text-decoration: none;
            color: #111827;
            background: #f9fafb;
        }}
        .region-list a:hover {{
            background: #f3f4f6;
            border-color: #d1d5db;
        }}
        .note {{
            margin-top: 14px;
            font-size: 12px;
            color: #6b7280;
        }}
    </style>
</head>
<body>
    <div class="region-list">
        <h1>QuickNews</h1>
        <p>Select a region:</p>
        <ul>
            <li><a href="QuickNews_us.html">United States (US)</a></li>
            <li><a href="QuickNews_jp.html">日本 (JP)</a></li>
            <li><a href="QuickNews_fr.html">France (FR)</a></li>
        </ul>
        <div class="note">Each link points to the latest generated page for that region.</div>
    </div>
</body>
</html>"""
    
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print(f"Index file updated: {index_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        combine_news_articles(sys.argv[1])
    else:
        combine_news_articles('us')
