#!/usr/bin/env python3

"""
Morning Press: Gather top news (Hacker News, Swiss RTS, Le Temps), 
fetch weather for Morges, optionally summarize with OpenAI, 
then output an old-school multi-column PDF and print it.
"""

import os
import sys
import subprocess
import datetime
import random

import feedparser
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    BaseDocTemplate,
    PageTemplate,
    Frame,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# ------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------

# Hacker News
HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"

# RSS Feeds (Swiss RTS, Le Temps)
RTS_NEWS_RSS = "https://www.rts.ch/info/rss"
LE_TEMPS_RSS = "https://www.letemps.ch/rss"

# Weather: Open-Meteo API
CITY_NAME = "Morges"  # City name for display purposes
MORGES_LAT = 46.5167  # Morges, Switzerland latitude
MORGES_LON = 6.4833   # Morges, Switzerland longitude
WEATHER_URL = (
    f"https://api.open-meteo.com/v1/forecast?"
    f"latitude={MORGES_LAT}&longitude={MORGES_LON}"
    f"&current=temperature_2m,weather_code"
)

# (Optional) OpenAI Summarization
USE_OPENAI_SUMMARY = True
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Get from environment variable

# Printer Name (for 'lpr')
PRINTER_NAME = ""  # e.g., "EPSON_XXXX" or leave blank for default

# PDF output filename prefix
PDF_PREFIX = "morning_press"

# Max number of items to fetch per source
MAX_ITEMS = 5

# ------------------------------------------------------
# OPTIONAL: OPENAI SUMMARIZATION
# ------------------------------------------------------
def summarize_text_with_openai(text, max_tokens=100, temperature=0.7):
    """
    Summarize a given text using OpenAI GPT-3/4 API.
    If you don't want to use the OpenAI API, you can disable it with USE_OPENAI_SUMMARY=False.
    """
    import openai

    openai.api_key = OPENAI_API_KEY
    if not OPENAI_API_KEY or not text.strip():
        return text  # Fallback: return original text if no API key or text is blank

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or "gpt-4" if you have access
            messages=[{"role": "user", "content": f"Summarize the following text:\n\n{text}"}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        summary = response["choices"][0]["message"]["content"].strip()
        return summary
    except Exception as e:
        print(f"[WARN] Could not summarize with OpenAI: {e}")
        return text  # fallback to original text

# ------------------------------------------------------
# DATA FETCHING FUNCTIONS
# ------------------------------------------------------
def fetch_hackernews_top_stories(limit=5):
    """
    Fetch top stories from Hacker News, returning a list of dictionaries 
    with keys: 'title', 'url'
    """
    result = []
    try:
        r = requests.get(HN_TOP_STORIES_URL, timeout=10)
        r.raise_for_status()
        top_ids = r.json()
        for story_id in top_ids[:limit]:
            story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            s = requests.get(story_url, timeout=10)
            s.raise_for_status()
            data = s.json()
            title = data.get("title", "No Title")
            url = data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            result.append({"title": title, "url": url})
    except Exception as e:
        print(f"[ERROR] Hacker News fetch error: {e}")
    return result

def fetch_rss_headlines(feed_url, limit=5):
    """
    Fetch headlines from an RSS feed, returning a list of dicts with 'title', 'url'.
    """
    items = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            title = entry.title
            link = entry.link
            items.append({"title": title, "url": link})
    except Exception as e:
        print(f"[ERROR] RSS fetch error for {feed_url}: {e}")
    return items

def fetch_weather(city_url):
    """
    Fetch weather data from Open-Meteo API, returning a string description.
    """
    try:
        resp = requests.get(city_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if "current" in data:
            temp = data["current"]["temperature_2m"]
            weather_code = data["current"]["weather_code"]
            
            # WMO Weather interpretation codes (https://open-meteo.com/en/docs)
            weather_descriptions = {
                0: "Clear sky",
                1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Foggy", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
                77: "Snow grains",
                80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                85: "Slight snow showers", 86: "Heavy snow showers",
                95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"
            }
            
            desc = weather_descriptions.get(weather_code, "Unknown conditions")
            return f"Weather in {CITY_NAME}: {temp}°C, {desc}"
        else:
            return "Weather data not found."
    except Exception as e:
        return f"[ERROR] Weather fetch: {e}"

# ------------------------------------------------------
# PDF GENERATION
# ------------------------------------------------------
def build_newspaper_pdf(pdf_filename, story_content):
    """
    Generate a multi-column PDF (A4) with an old-school newspaper style.
    :param pdf_filename: The name/path of the output PDF file.
    :param story_content: List of paragraphs (strings) to place into the PDF.
    """
    page_width, page_height = A4

    doc = BaseDocTemplate(
        pdf_filename,
        pagesize=A4,
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm,
    )

    gutter = 0.5 * cm
    column_width = (page_width - 2 * doc.leftMargin - gutter) / 2

    # Define two columns (Frames)
    frame1 = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        column_width,
        page_height - doc.topMargin - doc.bottomMargin,
        leftPadding=0,
        bottomPadding=0,
        rightPadding=0,
        topPadding=0,
        showBoundary=0
    )

    frame2 = Frame(
        doc.leftMargin + column_width + gutter,
        doc.bottomMargin,
        column_width,
        page_height - doc.topMargin - doc.bottomMargin,
        leftPadding=0,
        bottomPadding=0,
        rightPadding=0,
        topPadding=0,
        showBoundary=0
    )

    page_template = PageTemplate(id="TwoColumns", frames=[frame1, frame2])
    doc.addPageTemplates([page_template])

    styles = getSampleStyleSheet()

    old_newspaper_style = ParagraphStyle(
        "OldNewspaper",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=10,
        leading=13,
        alignment=4,  # Justify
    )

    headline_style = ParagraphStyle(
        "Headline",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=18,
        leading=22,
        alignment=1,  # Center
        textColor=colors.black
    )

    # Build flowables
    flowables = []

    # Add big headline
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    flowables.append(Paragraph(f"Morning Press - {date_str}", headline_style))
    flowables.append(Spacer(1, 0.2 * inch))

    # Add story content
    for paragraph_text in story_content:
        # Each paragraph_text is a string
        p = Paragraph(paragraph_text, old_newspaper_style)
        flowables.append(p)
        flowables.append(Spacer(1, 0.2 * cm))

    # Build the PDF
    doc.build(flowables)

def print_pdf(pdf_filename, printer_name=""):
    """
    Print the PDF file using the 'lpr' command (common on Linux/macOS).
    :param pdf_filename: path to the PDF
    :param printer_name: optional printer name
    """
    if not os.path.exists(pdf_filename):
        print(f"[ERROR] PDF file not found: {pdf_filename}")
        return

    print_cmd = ["lpr", pdf_filename]
    if printer_name:
        print_cmd = ["lpr", "-P", printer_name, pdf_filename]

    try:
        subprocess.run(print_cmd, check=True)
        print(f"Sent {pdf_filename} to printer '{printer_name or 'default'}'.")
    except Exception as e:
        print(f"[ERROR] Printing file: {e}")

# ------------------------------------------------------
# MAIN
# ------------------------------------------------------
def main():
    # Create press directory if it doesn't exist
    press_dir = "press"
    os.makedirs(press_dir, exist_ok=True)

    now = datetime.datetime.now()
    pdf_filename = os.path.join(press_dir, f"{PDF_PREFIX}_{now.strftime('%Y%m%d_%H%M%S')}.pdf")

    # Step 1: Gather data

    # Hacker News
    hn_data = fetch_hackernews_top_stories(MAX_ITEMS)
    # Summarize each headline with OpenAI (optional)
    hn_content = []
    for item in hn_data:
        text = f"{item['title']} (Link: {item['url']})"
        if USE_OPENAI_SUMMARY:
            text = summarize_text_with_openai(text, max_tokens=60)
        hn_content.append(text)

    # RTS headlines
    rts_data = fetch_rss_headlines(RTS_NEWS_RSS, MAX_ITEMS)
    rts_content = []
    for item in rts_data:
        text = f"{item['title']} (Link: {item['url']})"
        if USE_OPENAI_SUMMARY:
            text = summarize_text_with_openai(text, max_tokens=60)
        rts_content.append(text)

    # Le Temps headlines
    lt_data = fetch_rss_headlines(LE_TEMPS_RSS, MAX_ITEMS)
    lt_content = []
    for item in lt_data:
        text = f"{item['title']} (Link: {item['url']})"
        if USE_OPENAI_SUMMARY:
            text = summarize_text_with_openai(text, max_tokens=60)
        lt_content.append(text)

    # Weather for Morges
    weather_info = fetch_weather(WEATHER_URL)

    # Step 2: Build a final list of paragraphs
    paragraphs = []

    # Weather
    paragraphs.append(weather_info)
    paragraphs.append("")

    # Hacker News
    paragraphs.append("Hacker News (Top Stories):")
    for c in hn_content:
        paragraphs.append(f" - {c}")
    paragraphs.append("")

    # RTS
    paragraphs.append("RTS Headlines:")
    for c in rts_content:
        paragraphs.append(f" - {c}")
    paragraphs.append("")

    # Le Temps
    paragraphs.append("Le Temps Headlines:")
    for c in lt_content:
        paragraphs.append(f" - {c}")
    paragraphs.append("")

    # Optionally add a random motivational quote
    # For demonstration, we'll just embed a static quote or call a simple quotes API
    # e.g. type.fit or your own approach
    try:
        resp = requests.get("https://type.fit/api/quotes", timeout=10)
        quotes_list = resp.json()
        if quotes_list and isinstance(quotes_list, list):
            rand_quote = random.choice(quotes_list)
            quote_txt = rand_quote.get("text", "Stay motivated!")
            quote_auth = rand_quote.get("author", "Unknown")
            paragraphs.append("Today's Motivational Quote:")
            paragraphs.append(f"\"{quote_txt}\" - {quote_auth}")
    except:
        paragraphs.append("Stay motivated!")

    # Step 3: Create the PDF
    build_newspaper_pdf(pdf_filename, paragraphs)

    # Step 4: Print the PDF
    print_pdf(pdf_filename, PRINTER_NAME)

    print(f"Done. PDF saved as: {pdf_filename}")

# ------------------------------------------------------
if __name__ == "__main__":
    main()