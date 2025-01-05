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
LE_TEMPS_RSS = "https://www.letemps.ch/articles.rss"

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
def summarize_text_with_openai(text, max_tokens=150, temperature=0.7):
    """
    Summarize a given text using OpenAI GPT-4 API.
    Returns an engaging newspaper-style summary.
    """
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    if not OPENAI_API_KEY or not text.strip():
        return text

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "system",
                "content": "You are an experienced newspaper editor. Create engaging, well-written summaries in a journalistic style."
            },
            {
                "role": "user",
                "content": f"Summarize this news article in an engaging way, like a professional newspaper. Don't include any URLs or references:\n\n{text}"
            }],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        print(f"[WARN] Could not summarize with OpenAI: {e}")
        return text

# ------------------------------------------------------
# DATA FETCHING FUNCTIONS
# ------------------------------------------------------
def fetch_hackernews_top_stories(limit=5):
    """
    Fetch top stories from Hacker News, including content and top comments.
    Returns a list of dictionaries with story details and analysis.
    """
    result = []
    try:
        r = requests.get(HN_TOP_STORIES_URL, timeout=10)
        r.raise_for_status()
        top_ids = r.json()
        
        for story_id in top_ids[:limit]:
            # Fetch story details
            story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            s = requests.get(story_url, timeout=10)
            s.raise_for_status()
            story_data = s.json()
            
            title = story_data.get("title", "No Title")
            url = story_data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            
            # Fetch and analyze content if there's a URL
            content_summary = ""
            if url and not url.startswith("https://news.ycombinator.com"):
                try:
                    article_response = requests.get(url, timeout=10)
                    if article_response.status_code == 200:
                        content_summary = summarize_text_with_openai(article_response.text[:4000])
                except Exception as e:
                    print(f"[WARN] Could not fetch article content: {e}")
            
            # Fetch top comments
            comments_analysis = ""
            if story_data.get("kids"):
                comments = []
                for comment_id in story_data["kids"][:3]:  # Get top 3 comments
                    try:
                        comment_url = f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json"
                        c = requests.get(comment_url, timeout=10)
                        c.raise_for_status()
                        comment_data = c.json()
                        if comment_data.get("text"):
                            comments.append(comment_data["text"])
                    except Exception as e:
                        print(f"[WARN] Could not fetch comment: {e}")
                
                if comments:
                    comments_text = "\n".join(comments)
                    comments_analysis = summarize_text_with_openai(
                        f"Analyze these top comments from the discussion:\n\n{comments_text}"
                    )
            
            result.append({
                "title": title,
                "url": url,
                "content_summary": content_summary,
                "comments_analysis": comments_analysis
            })
            
    except Exception as e:
        print(f"[ERROR] Hacker News fetch error: {e}")
    return result

def fetch_rss_headlines(feed_url, limit=5):
    """
    Fetch headlines and content from an RSS feed, returning a list of dicts with 'title', 'description'.
    """
    items = []
    try:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit]:
            title = entry.title
            # Get the full description/content
            content = entry.description if hasattr(entry, 'description') else ''
            
            # If we have OpenAI enabled, summarize the content
            if USE_OPENAI_SUMMARY and content:
                content = summarize_text_with_openai(content)
            
            items.append({
                "title": title,
                "content": content
            })
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
    """Main function to generate the morning press."""
    # Create press directory if it doesn't exist
    os.makedirs("press", exist_ok=True)

    # Generate unique filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"press/{PDF_PREFIX}_{timestamp}.pdf"

    # Prepare content
    content = []
    
    # Add weather
    weather_info = fetch_weather(WEATHER_URL)
    content.append(weather_info)
    content.append("")  # Add spacing
    
    # Fetch and process Hacker News stories
    print("Fetching Hacker News stories...")
    hn_news = fetch_hackernews_top_stories(MAX_ITEMS)
    
    if hn_news:
        content.append("HACKER NEWS - TOP STORIES")
        content.append("-" * 40)
        for idx, item in enumerate(hn_news, 1):
            content.append(f"{idx}. {item['title']}")
            if item.get('content_summary'):
                content.append("")
                content.append("Article Summary:")
                content.append(item['content_summary'])
            if item.get('comments_analysis'):
                content.append("")
                content.append("Discussion Analysis:")
                content.append(item['comments_analysis'])
            content.append("")  # Add spacing between articles
    
    # Fetch and process Le Temps news
    print("Fetching Le Temps news...")
    le_temps_news = fetch_rss_headlines(LE_TEMPS_RSS, MAX_ITEMS)
    
    if le_temps_news:
        content.append("LE TEMPS - TOP STORIES")
        content.append("-" * 40)
        for idx, item in enumerate(le_temps_news, 1):
            content.append(f"{idx}. {item['title']}")
            if item.get('content'):
                content.append("")
                content.append(item['content'])
            content.append("")  # Add spacing between articles
    
    # Generate PDF
    build_newspaper_pdf(pdf_filename, content)
    
    # Print if printer name is configured
    if PRINTER_NAME:
        print_pdf(pdf_filename, PRINTER_NAME)
    
    print(f"Morning Press generated: {pdf_filename}")

# ------------------------------------------------------
if __name__ == "__main__":
    main()