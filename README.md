# News Scraper and Aggregator

A Python-based news scraper that collects articles from various news sources and converts them into a clean HTML format.

## Features

- Scrapes news from multiple sources (NPR, Fox News, CBS)
- Converts articles to a clean, readable HTML format
- Preserves article structure and formatting
- Lightweight and easy to extend

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd news-scraper
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running Individual Scrapers

```bash
# Run NPR scraper
python npr_scraper.py

# Run Fox News scraper
python foxnews_scraper.py

# Run CBS scraper
python cbs_scraper.py
```

### Viewing Output

- JSON output: `output/<source>_articles.json`
- HTML output: `output/<source>_news_articles.html`

## Project Structure

- `npr_scraper.py`: Scraper for NPR news
- `foxnews_scraper.py`: Scraper for Fox News
- `cbs_scraper.py`: Scraper for CBS News
- `convert_to_html.py`: Utility to convert scraped data to HTML
- `requirements.txt`: Python dependencies

## Contributing

This is a personal project, and while I'm not actively seeking contributions, feel free to fork the repository and adapt it to your needs under the terms of the MIT License. If you've created something interesting with this code, I'd love to hear about it!

Please note that while I appreciate your interest, I may not be able to respond to all issues or pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
