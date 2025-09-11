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

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{
    /* English-first stack with Chinese fallbacks */
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    font-size: 16px;
    margin: 0;
    padding: 20px;  /* top, right, bottom, left */
    background-color: #f5f5f5;
}}
.article-content[lang^="en"] {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
}}
.article-content[lang^="zh"] {{
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}}

.article-content p {{
    margin-top: 0;
    padding-top: 0;
}}

.article-source {{
    color: #888;
    font-size: 0.75em;
    margin: 2px 0 4px 0;
    line-height: 1.2;
    opacity: 0.7;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.articles-container {{
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 24px;
    overflow: auto;
    -ms-overflow-style: none;  /* IE and Edge */
    scrollbar-width: none;  /* Firefox */
    padding: 0;
    max-width: 100%;
    max-height: 100%;
}}

.articles-container::after {{
    content: "";
    flex: 1;
}}


/* Hide scrollbar for Chrome, Safari and Opera */
.articles-container::-webkit-scrollbar {{
    display: none;
}}

.article {{
    flex: 0 0 auto;
    width: 330.5px;  
    height: 450px;
    background: transparent;
    border-radius: 0;
    box-shadow: none;
    padding: 0 0 0 0; /* right gutter; left gutter comes from inline style per column */
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}}
.article-content {{
    text-align: justify;
    text-justify: inter-word;
    hyphens: auto;
    -webkit-hyphens: auto;
    -ms-hyphens: auto;
    -moz-hyphens: auto;
    flex: 1;
    overflow-y: auto;
    -ms-overflow-style: none;  /* IE and Edge */
    scrollbar-width: none;  /* Firefox */
    display: flex;
    flex-direction: column;
    overflow-wrap: break-word;
    word-wrap: break-word;
    -webkit-hyphenate-limit-chars: 6 3 3;  /* min: 6, before: 3, after: 3 */
    -ms-hyphenate-limit-chars: 6 3 3;
    hyphenate-limit-chars: 6 3 3;
    -webkit-hyphenate-limit-lines: 2;
    -ms-hyphenate-limit-lines: 2;
    hyphenate-limit-lines: 2;
    -webkit-hyphenate-limit-zone: 10%;
    hyphenate-limit-zone: 10%;
    text-rendering: optimizeLegibility;
    -webkit-font-feature-settings: "kern" 1;
    font-feature-settings: "kern" 1;
    -webkit-font-kerning: normal;
    font-kerning: normal;
}}


.article-title {{
    font-size: 19.1px;
    line-height: 1.35;
    font-weight: 700;
    color: #222;
    text-align: left;
    background-color: #f5f5f5;
    position: sticky;
    padding: 0 0 0.5rem;
    top: 0;
    z-index: 10;
    box-sizing: border-box;
    letter-spacing: 0.1px;
}}
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