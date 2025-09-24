import subprocess
import os
import sys
from bs4 import BeautifulSoup
import os
from datetime import datetime
import pytz


def run_scrapers():
    """Run all individual scraper scripts."""
    scrapers = [
        'scrapers/foxnews_scraper.py',
        'scrapers/cbs_scraper.py',
        'scrapers/npr_scraper.py'
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

def combine_news_articles():
    # First, run all scrapers
    run_scrapers()
    
    # List of HTML files to combine
    html_files = [
        'output/fox_news_articles.html',
        'output/cbs_news_articles.html',
        'output/npr_news_articles.html'
    ]
    
    with open('static/styles.css', 'r', encoding='utf-8') as f:
        css_style = f.read()

    # Create a new BeautifulSoup object for the combined content
    # Get current date in Eastern Time for the title
    eastern = pytz.timezone('US/Eastern')
    date_str_title = datetime.now(eastern).strftime('%Y-%m-%d')
    
    soup = BeautifulSoup(f'''<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QuickNews - {date_str_title}</title>
        <style>{css_style}</style>
    </head>
    <body>
        <div class="timestamp">Updated: {datetime.now(eastern).strftime('%H:%M ET, %A, %b %d %Y')}</div>
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
    
    # Create output directory if it doesn't exist
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    
    # Get current date in Eastern Time for filename
    eastern = pytz.timezone('US/Eastern')
    date_str = datetime.now(eastern).strftime('%Y-%m-%d')
    
    # Save the combined HTML to a file with date in the name
    output_file = os.path.join(output_dir, f'QuickNews_{date_str}.html')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    
    print(f"\nCombined news articles have been saved to: {output_file}")
    
    # Create/update index.html with automatic redirect to the latest file
    index_file = os.path.join(output_dir, 'index.html')
    index_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>QuickNews</title>
    <meta http-equiv="refresh" content="0; url=QuickNews_{date_str}.html">
    <link rel="stylesheet" type="text/css" href="../static/styles.css">
    <style>
        .redirect-message {{
            text-align: center;
            margin-top: 50px;
            font-size: 1.2em;
        }}
        .redirect-message a {{
            color: #0066cc;
            text-decoration: none;
        }}
        .redirect-message a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="redirect-message">
        <p>Redirecting to the latest news...<br>
        <a href="QuickNews_{date_str}.html">Click here if you are not redirected automatically</a></p>
    </div>
</body>
</html>"""
    
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print(f"Index file updated: {index_file}")

if __name__ == "__main__":
    combine_news_articles()
