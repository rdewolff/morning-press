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
from bs4 import BeautifulSoup
import html2text
from babel.dates import format_date
import locale

load_dotenv()  # Load environment variables from .env file

# ------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------

# Hacker News
HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"

# RSS Feeds and News Sites
RTS_URL = "https://www.rts.ch/"
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

# Default language for summaries
DEFAULT_LANGUAGE = "french"

# Summary configuration
SUMMARY_MAX_TOKENS = 300  # Increased from 150
SUMMARY_TEMPERATURE = 0.5  # Reduced for more focused summaries

# Set locale for date formatting
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR')
    except:
        print("[WARN] Could not set French locale, falling back to default")

# Fallback quotes in French
FALLBACK_QUOTES = [
    {
        "quote": "La vie est courte, l'art est long.",
        "author": "Hippocrate"
    },
    {
        "quote": "Je pense, donc je suis.",
        "author": "René Descartes"
    },
    {
        "quote": "Un petit pas pour l'homme, un grand pas pour l'humanité.",
        "author": "Neil Armstrong"
    },
    {
        "quote": "La beauté est dans les yeux de celui qui regarde.",
        "author": "Oscar Wilde"
    },
    {
        "quote": "L'imagination est plus importante que le savoir.",
        "author": "Albert Einstein"
    },
    {
        "quote": "Le doute est le commencement de la sagesse.",
        "author": "Aristote"
    },
    {
        "quote": "La liberté des uns s'arrête là où commence celle des autres.",
        "author": "Jean-Paul Sartre"
    },
    {
        "quote": "Le hasard ne favorise que les esprits préparés.",
        "author": "Louis Pasteur"
    }
]

# ------------------------------------------------------
# OPTIONAL: OPENAI SUMMARIZATION
# ------------------------------------------------------
def summarize_text_with_openai(text, max_tokens=SUMMARY_MAX_TOKENS, temperature=SUMMARY_TEMPERATURE, language=DEFAULT_LANGUAGE):
    """
    Summarize a given text using OpenAI GPT-4 API.
    Returns an engaging newspaper-style summary in the specified language.
    """
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    if not OPENAI_API_KEY or not text.strip():
        return text

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{
                "role": "system",
                "content": f"""You are an experienced newspaper editor who writes concise, impactful summaries.
                Write in {language}.
                Focus on the key points and maintain journalistic style.
                Be concise but ensure all important information is included.
                Aim for 2-3 short paragraphs maximum."""
            },
            {
                "role": "user",
                "content": f"Write a concise newspaper summary of this article. Focus on the most newsworthy elements:\n\n{text}"
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
def fetch_hackernews_top_stories(limit=5, language=DEFAULT_LANGUAGE):
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
                        content_summary = summarize_text_with_openai(
                            article_response.text[:8000],  # Increased from 4000
                            language=language
                        )
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
                        f"Analyze these key points from the discussion comments. Be concise but insightful:\n\n{comments_text}",
                        language=language,
                        max_tokens=200  # Specific limit for comments analysis
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

def fetch_rss_headlines(feed_url, limit=5, language=DEFAULT_LANGUAGE):
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
                content = summarize_text_with_openai(content, language=language)
            
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

def fetch_rts_news(limit=5, language=DEFAULT_LANGUAGE):
    """
    Scrape news from RTS website and use AI to select and summarize top stories.
    """
    items = []
    try:
        # Fetch the main page
        response = requests.get(RTS_URL, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Convert HTML to plain text for better processing
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        page_text = h.handle(str(soup))
        
        # Use AI to identify and extract top stories
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # First, let AI identify the most important stories
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": f"You are a news editor for RTS. Analyze the webpage content and identify the {limit} most important news stories. Focus on actual news articles, not TV shows or programs. Return the results in a structured format with title and content clearly separated."
            },
            {
                "role": "user",
                "content": f"Here's the RTS webpage content. Identify the {limit} most important news stories, extracting their titles and content. Format your response as 'TITLE: xxx\nCONTENT: yyy' for each story:\n\n{page_text}"
            }],
            max_tokens=1000,
            temperature=0.3
        )
        
        # Parse AI response and extract stories
        stories_text = response.choices[0].message.content.strip()
        story_blocks = stories_text.split('\n\n')
        
        for block in story_blocks:
            if not block.strip():
                continue
                
            lines = block.split('\n')
            title = ""
            content = ""
            
            for line in lines:
                if line.startswith("TITLE:"):
                    title = line.replace("TITLE:", "").strip()
                elif line.startswith("CONTENT:"):
                    content = line.replace("CONTENT:", "").strip()
            
            if title and content:
                # Summarize the content in the target language
                summary = summarize_text_with_openai(content, language=language)
                items.append({
                    "title": title,
                    "content": summary
                })
                
            if len(items) >= limit:
                break
                
    except Exception as e:
        print(f"[ERROR] RTS fetch error: {e}")
    
    return items

def fetch_random_quote(language=DEFAULT_LANGUAGE):
    """
    Fetch and translate a random quote from a famous person.
    Falls back to a predefined list if the API fails.
    """
    try:
        # First try the Quotable API
        response = requests.get("https://api.quotable.io/random", timeout=5)  # Reduced timeout
        response.raise_for_status()
        quote_data = response.json()
        
        # If not in target language, translate it
        if language.lower() != "english":
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{
                    "role": "system",
                    "content": f"You are a professional translator. Translate this quote to {language}, maintaining its poetic and impactful nature."
                },
                {
                    "role": "user",
                    "content": f'Translate this quote and author name: "{quote_data["content"]}" - {quote_data["author"]}'
                }],
                temperature=0.7
            )
            translated = response.choices[0].message.content.strip()
            
            # Split the translation back into quote and author
            if " - " in translated:
                quote, author = translated.rsplit(" - ", 1)
            else:
                quote = translated
                author = quote_data["author"]
            
            return {
                "quote": quote.strip('"'),
                "author": author
            }
            
    except Exception as e:
        print(f"[INFO] Using fallback quote system: {str(e)}")
        # Use fallback quotes if API fails
        return random.choice(FALLBACK_QUOTES)

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
        topMargin=1.5 * cm,  # Increased top margin for header
        bottomMargin=1 * cm,
    )

    gutter = 0.5 * cm
    column_width = (page_width - 2 * doc.leftMargin - 2 * gutter) / 3  # Adjusted for 3 columns

    # Define three columns (Frames)
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

    frame3 = Frame(
        doc.leftMargin + 2 * (column_width + gutter),
        doc.bottomMargin,
        column_width,
        page_height - doc.topMargin - doc.bottomMargin,
        leftPadding=0,
        bottomPadding=0,
        rightPadding=0,
        topPadding=0,
        showBoundary=0
    )

    page_template = PageTemplate(id="ThreeColumns", frames=[frame1, frame2, frame3])
    doc.addPageTemplates([page_template])

    styles = getSampleStyleSheet()

    # Main newspaper title style
    masthead_style = ParagraphStyle(
        "Masthead",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=32,
        leading=36,
        alignment=1,  # Center
        textColor=colors.black,
        spaceAfter=6
    )

    # Date and weather style (subtitle)
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=12,
        leading=14,
        alignment=1,  # Center
        textColor=colors.black,
        spaceBefore=0,
        spaceAfter=20
    )

    # Section headers (e.g., "HACKER NEWS - TOP STORIES")
    section_header_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading1"],
        fontName="Times-Bold",
        fontSize=16,
        leading=20,
        alignment=0,  # Left
        textColor=colors.black,
        spaceBefore=15,
        spaceAfter=10
    )

    # Article titles
    article_title_style = ParagraphStyle(
        "ArticleTitle",
        parent=styles["Heading2"],
        fontName="Times-Bold",
        fontSize=12,
        leading=14,
        alignment=0,  # Left
        textColor=colors.black,
        spaceBefore=10,
        spaceAfter=6
    )

    # Regular article text
    article_style = ParagraphStyle(
        "Article",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=9,  # Slightly smaller font for narrower columns
        leading=11,
        alignment=4,  # Justify
        firstLineIndent=15,  # Slightly smaller indent for narrower columns
        spaceBefore=0,
        spaceAfter=8
    )

    # Quote section style
    quote_section_style = ParagraphStyle(
        "QuoteSection",
        parent=styles["Normal"],
        fontName="Times-Bold",
        fontSize=14,
        leading=16,
        alignment=1,  # Center
        textColor=colors.black,
        spaceBefore=30,
        spaceAfter=10
    )

    # Quote text style
    quote_style = ParagraphStyle(
        "Quote",
        parent=styles["Normal"],
        fontName="Times-Italic",
        fontSize=14,  # Slightly smaller for three columns
        leading=18,
        alignment=1,  # Center
        textColor=colors.black,
        leftIndent=30,  # Adjusted indents for narrower columns
        rightIndent=30,
        spaceBefore=0,
        spaceAfter=10
    )

    # Quote attribution style
    attribution_style = ParagraphStyle(
        "Attribution",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=12,
        leading=14,
        alignment=1,  # Center
        textColor=colors.black,
        spaceBefore=0,
        spaceAfter=20
    )

    # Build flowables
    flowables = []

    # Add masthead (main title)
    try:
        # Try using babel for proper French formatting
        date_str = format_date(datetime.datetime.now(), format="EEEE d MMMM yyyy", locale='fr')
    except:
        # Fallback to basic formatting
        date_str = datetime.datetime.now().strftime("%A %d %B %Y")
    flowables.append(Paragraph("Morning Press", masthead_style))
    flowables.append(Paragraph(date_str, subtitle_style))

    # Process content with appropriate styles
    current_section = None
    
    for text in story_content:
        if not text.strip():
            continue
            
        # Section headers (all caps with dashes)
        if text.isupper() and "-" in text:
            if text == "CITATION DU JOUR":
                flowables.append(Paragraph(text, quote_section_style))
            else:
                flowables.append(Paragraph(text, section_header_style))
            current_section = text
        # Quote content
        elif current_section == "CITATION DU JOUR":
            if text.startswith("❝"):
                flowables.append(Paragraph(text, quote_style))
            elif text.startswith("—"):
                flowables.append(Paragraph(text, attribution_style))
        # Article titles (numbered items)
        elif text.strip().startswith(("1.", "2.", "3.", "4.", "5.")):
            title_text = text.split(". ", 1)[1] if ". " in text else text
            flowables.append(Paragraph(title_text, article_title_style))
        # Regular content
        else:
            flowables.append(Paragraph(text, article_style))

    # Build the PDF
    doc.build(flowables)

def print_pdf(pdf_filename, printer_name=""):
    """Print the PDF file using the 'lpr' command."""
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
    hn_news = fetch_hackernews_top_stories(MAX_ITEMS, DEFAULT_LANGUAGE)
    
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
    
    # Fetch and process RTS news
    print("Fetching RTS news...")
    rts_news = fetch_rts_news(MAX_ITEMS, DEFAULT_LANGUAGE)
    
    if rts_news:
        content.append("RTS - TOP STORIES")
        content.append("-" * 40)
        for idx, item in enumerate(rts_news, 1):
            content.append(f"{idx}. {item['title']}")
            if item.get('content'):
                content.append("")
                content.append(item['content'])
            content.append("")  # Add spacing between articles
    
    # Fetch and process Le Temps news
    print("Fetching Le Temps news...")
    le_temps_news = fetch_rss_headlines(LE_TEMPS_RSS, MAX_ITEMS, DEFAULT_LANGUAGE)
    
    if le_temps_news:
        content.append("LE TEMPS - TOP STORIES")
        content.append("-" * 40)
        for idx, item in enumerate(le_temps_news, 1):
            content.append(f"{idx}. {item['title']}")
            if item.get('content'):
                content.append("")
                content.append(item['content'])
            content.append("")  # Add spacing between articles
    
    # Add quote of the day
    print("Fetching quote of the day...")
    quote_data = fetch_random_quote(DEFAULT_LANGUAGE)
    if quote_data:
        content.append("CITATION DU JOUR")
        content.append("-" * 40)
        content.append(f"❝{quote_data['quote']}❞")
        content.append(f"— {quote_data['author']}")
    
    # Generate PDF
    build_newspaper_pdf(pdf_filename, content)
    
    # Print if printer name is configured
    if PRINTER_NAME:
        print_pdf(pdf_filename, PRINTER_NAME)
    
    print(f"Morning Press generated: {pdf_filename}")

# ------------------------------------------------------
if __name__ == "__main__":
    main()