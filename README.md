# Morning Press 📰

A Python application that generates a beautiful daily newspaper in PDF format, combining news from multiple sources:
- Hacker News
- RTS (Radio Télévision Suisse)
- Le Temps
- Weather information
- Quote of the day

The content is automatically summarized and translated to French using AI, and formatted in an elegant three-column newspaper layout.

## Features

- 🌐 Multi-source news aggregation
- 🤖 AI-powered content summarization
- 🇫🇷 French translation of content
- 📊 Three-column newspaper layout
- 🖨️ Optional direct printing support
- 🌡️ Local weather information
- 💭 Daily inspirational quote
- 📝 Hacker News discussion analysis

## Prerequisites

- Python 3.11 or higher
- Poetry (Python package manager)
- OpenAI API key

## Installation

1. Install Poetry if you haven't already:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Clone the repository:
```bash
git clone https://github.com/yourusername/morning-press.git
cd morning-press
```

3. Install dependencies using Poetry:
```bash
poetry install
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=your_openai_api_key_here
```

3. (Optional) Configure printer name in `daily_newspaper.py` if you want automatic printing:
```python
PRINTER_NAME = "YOUR_PRINTER_NAME"  # Leave empty for default printer
```

## Usage

Run the script with optional parameters:
```bash
poetry run python daily_newspaper.py [options]
```

Available options:
- `--use-cache`: Use cached content if available
- `--print`: Automatically print the generated PDF
- `--articles N`: Number of articles to fetch per source (default: 5)
- `--pages N`: Number of pages to generate (default: 2)

Examples:
```bash
# Generate with default settings (2 pages, 5 articles per source)
poetry run python daily_newspaper.py

# Generate a 3-page newspaper with 7 articles per source
poetry run python daily_newspaper.py --pages 3 --articles 7

# Use cached content and print automatically
poetry run python daily_newspaper.py --use-cache --print
```

The application will:
1. Fetch news from all sources (or use cache if specified)
2. Summarize and translate content
3. Generate a PDF in the `press` directory
4. Optionally print the newspaper if `--print` is used or printer is configured

## PDF Output

The generated PDF will be saved in the `press` directory with a timestamp:
```
press/morning_press_YYYYMMDD_HHMMSS.pdf
```

## Customization

You can modify the following settings in `daily_newspaper.py`:

- `MAX_ITEMS`: Number of articles to fetch from each source (default: 5)
- `DEFAULT_LANGUAGE`: Language for summaries and translations (default: "french")
- `CITY_NAME`, `MORGES_LAT`, `MORGES_LON`: Location for weather information
- `SUMMARY_MAX_TOKENS`: Length of article summaries
- `SUMMARY_TEMPERATURE`: AI creativity level for summaries

## Dependencies

The project uses several key libraries:
- `openai`: For AI-powered summarization and translation
- `reportlab`: For PDF generation
- `feedparser`: For RSS feed parsing
- `beautifulsoup4`: For web scraping
- `requests`: For API calls
- `babel`: For date localization

## Troubleshooting

### Common Issues

1. **OpenAI API Error**:
   - Verify your API key is correct
   - Check your OpenAI account has sufficient credits

2. **PDF Generation Error**:
   - Ensure the `press` directory exists and is writable
   - Check available disk space

3. **Printing Error**:
   - Verify printer name if configured
   - Check printer is online and accessible

### Locale Issues

If you see locale warnings, install the required locale:

```bash
# On Ubuntu/Debian
sudo locale-gen fr_FR.UTF-8
sudo update-locale

# On macOS
brew install gettext
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.