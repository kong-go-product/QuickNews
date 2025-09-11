<div align="center">
  <img src="assets/images/QuickNews.png" alt="QuickNews Logo" width="300"/>
</div>

# QuickNews - News Aggregator

A lightweight Python-based news aggregator that collects articles from various news sources and presents them in a clean, readable HTML format. Perfect for staying updated with the latest news from multiple sources in one place.

## Features

- **Multi-source Aggregation**: Collects news from NPR, Fox News, and CBS
- **Clean Output**: Converts articles to well-formatted HTML
- **Structured Data**: Preserves article metadata and structure
- **Easy to Extend**: Modular design makes it simple to add new sources
- **Lightweight**: Minimal dependencies and efficient processing

## Table of Contents

- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Requirements](#-requirements)
- [Contributing](#-contributing)
- [License](#-license)

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/kong-go-product/QuickNews.git
   cd QuickNews
   ```

2. **Set up a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Collecting News

Collect news from individual sources:

```bash
# NPR News
python npr_scraper.py

# Fox News
python foxnews_scraper.py

# CBS News
python cbs_scraper.py
```

### Output

- **JSON Output**: `output/<source>_articles.json`
- **HTML Output**: `output/<source>_news_articles.html`

## Project Structure

```
QuickNews/
├── assets/                    # Static assets (images, etc.)
├── output/                    # Generated output files
├── scrapers/                  # News source scrapers
│   ├── cbs_scraper.py
│   ├── foxnews_scraper.py
│   └── npr_scraper.py
├── utils/                     # Utility scripts
│   └── convert_to_html.py
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Contributing

This is a personal project, and while I'm not actively seeking contributions, I welcome forks and adaptations under the MIT License. If you create something interesting with this code, I'd love to hear about it!

Please note that I may not be able to respond to all issues or pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
