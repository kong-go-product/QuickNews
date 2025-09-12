"""JSON to HTML converter for the NewsReader."""

import json
import os
import sys

def convert_json_to_html(json_file, output_file):
    """
    Convert a JSON feed (with structure { title, link, description, items: [...] })
    into the same HTML layout used by convert_to_html.
    Prefers each item's 'content_text' for readability; falls back to 'summary',
    then 'description', then plain empty if none.
    """

    with open(json_file, 'r', encoding='utf-8') as f:
        feed = json.load(f)

    items = feed.get('items', [])

    # Build article HTML blocks using ONLY RSS 'content' (HTML), but include title
    articles_html = ''
    
    # Determine if content is primarily English
    is_english = any(lang in (feed.get('language') or '').lower() for lang in ['en', 'en-us', 'en-gb'])
    
    for item in items:
        title = item.get('title', '')
        body_html = item.get('content') or ''
        # No soft separator between columns
        article_style = ""

        # Determine language for better hyphenation (fallback to feed-level lang)
        feed_lang = feed.get('language') or feed.get('lang') or ('en' if is_english else '')
        item_lang = item.get('language') or item.get('lang') or feed_lang or 'en'
        lang_attr = f' lang="{item_lang}"'

        # Title block with combined styles from .article-content .title
        title_block = f'<div class="article-title">{title}</div>' if title else ''

        # Get source information (more compact display)
        source = item.get('source', feed.get('title', 'Unknown Source'))
        source_html = f'<div class="article-source">{source}</div>' if source else ''

        # Compose article column with title + source + raw RSS HTML content
        articles_html += f"""
        <div class=\"article\" style=\"{article_style}\">
            <div class=\"article-content\"{lang_attr}>
                {title_block}
                {source_html}
                {body_html}
            </div>
        </div>
        """

    # Read the CSS from the external file
    css_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'styles.css')
    try:
        with open(css_file, 'r', encoding='utf-8') as f:
            css_content = f.read()
    except FileNotFoundError:
        print(f"Warning: CSS file not found at {css_file}. Using default styles.")
        css_content = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
            font-size: 16px;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    {css_content}
    </style>
</head>
<body>
    <div class="articles-container">
        {articles_html}
    </div>
</body>
</html>
"""

    # Write the HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML file created from JSON: {output_file}")
    return output_file

def main():
    """Main function to handle command line arguments and execute conversion."""
    
    # Default file paths
    default_input = 'output/fox_news_articles.json'
    default_output = 'output/fox_news_articles.html'
    
    if len(sys.argv) == 1:
        # No arguments provided, use defaults
        if not os.path.exists(default_input):
            print(f"Error: Input file '{default_input}' not found")
            sys.exit(1)
        convert_json_to_html(default_input, default_output)
    elif len(sys.argv) == 3:
        # Use provided input and output files
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        convert_json_to_html(input_file, output_file)
    else:
        print("Usage: python convert_to_html.py [input_json_file] [output_html_file]")
        print(f"       python convert_to_html.py  # Uses defaults: {default_input} -> {default_output}")
        sys.exit(1)

if __name__ == "__main__":
    main()