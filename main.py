import subprocess
import os
import sys
from bs4 import BeautifulSoup
import os
from datetime import datetime


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
    soup = BeautifulSoup(f'''<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Combined News</title>
        <style>{css_style}</style>
    </head>
    <body>
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
    
    # Get current date for filename
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    # Save the combined HTML to a file with date in the name
    output_file = f'QuickNews_{date_str}.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    
    print(f"\nCombined news articles have been saved to: {output_file}")

if __name__ == "__main__":
    combine_news_articles()
