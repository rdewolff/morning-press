# Morning Press

**Morning Press** is a Python-based tool that fetches daily news, weather, and motivational quotes, then generates a multi-column “old-school newspaper” PDF and sends it to your printer.

## Features
- Fetch top stories from Hacker News (via the Hacker News API).
- Pull RSS feeds from Swiss RTS and *Le Temps* (for Swiss news).
- Retrieve weather data (e.g., using OpenWeatherMap).
- Insert a motivational quote (from a public quotes API).
- Format the output into a PDF, styled in multi-column, old-school newspaper fashion.
- Print to your local printer (e.g., via `lpr`).

## Requirements
- Python 3.8+
- [Poetry](https://python-poetry.org/)
- Printer setup compatible with `lpr` or a suitable alternative

## Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/morning_press.git
   cd morning_press