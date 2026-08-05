# -*- coding: utf-8 -*-
"""
Avigilon Spec Sheet Downloader

A utility that retrieves product datasheets for Avigilon cameras
and Cloud Connectors directly from the Avigilon website.

This module has no dependency on Streamlit, so it can be run directly
from the terminal:

    python scraper.py "H6A"

or imported by app.py for the Streamlit UI.
"""

import os
import sys
from functools import lru_cache

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
BASE_URL = "https://www.avigilon.com"

CAMERA_CATEGORIES = {
    "Dome": "/security-cameras/dome",
    "Bullet & Box": "/security-cameras/bullet",
    "Pan, Tilt & Zoom (PTZ)": "/security-cameras/ptz",
    "360° & Panoramic": "/security-cameras/panoramic-360",
    "Specialty": "/security-cameras/specialty",
}

CLOUD_CONNECTOR_CATEGORIES = {
    "Cloud Connector Workstations": "/cloud-connectors/workstation",
    "Cloud Connector Rack-Mounted Servers": "/cloud-connectors/rack-mounted",
}


@lru_cache(maxsize=32)
def get_products_in_category(category_path):
    """
    Retrieve all products available in the selected category.

    Returns a list of dicts: [{"name": ..., "url": ...}, ...]
    """
    url = BASE_URL + category_path
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    products = []
    seen_hrefs = set()

    # Find every "Learn More" link on the page.
    for link in soup.find_all('a', href=True):
        if link.get_text(" ", strip=True) != "Learn More":
            continue

        href = link['href']
        if href in seen_hrefs:
            continue

        name_tag = link.find_previous(['h2', 'h3', 'h4'])
        name = name_tag.get_text(" ", strip=True) if name_tag else href.rstrip('/').split('/')[-1]

        full_url = href if href.startswith('http') else BASE_URL + href
        products.append({"name": name, "url": full_url})
        seen_hrefs.add(href)

    return products


@lru_cache(maxsize=64)
def get_spec_sheets(page_url):
    """
    Retrieve datasheet and fact sheet links from a product page.

    Returns:
        direct_pdfs: dict of {label: url} for downloadable PDF files.
        portal_links: dict of {label: url} for documentation portal links.
    """
    response = requests.get(page_url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    doc_links = {}

    # Look for documentation links on the page. We don't try to guess
    # PDF vs. portal from the URL here (query strings like ?save_local=true
    # make that unreliable) — the caller checks the real Content-Type
    # when the link is actually requested.
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text(strip=True)
        normalized = text.lower().replace(' ', '')

        if 'datasheet' not in normalized and 'factsheet' not in normalized:
            continue

        full_url = href if href.startswith('http') else BASE_URL + href
        doc_links[text] = full_url

    return doc_links


def resolve_document(url):
    """
    Fetch a documentation link and determine whether it's a directly
    downloadable file (PDF) or an HTML portal page, based on the real
    Content-Type returned by the server (not just the URL's extension).

    Returns a dict:
        {"kind": "pdf", "content": <bytes>, "filename": <str>}
        or
        {"kind": "portal", "url": <str>}
    On network failure, raises requests.RequestException.
    """
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()

    if "application/pdf" in content_type or url.lower().split("?")[0].endswith(".pdf"):
        filename = url.split("?")[0].split("/")[-1]
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        return {"kind": "pdf", "content": response.content, "filename": filename}

    return {"kind": "portal", "url": url}


def download_file(url, output_dir="spec_sheets"):
    """
    Download a PDF file and save it locally. Returns the saved file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = url.split('/')[-1]
    filepath = os.path.join(output_dir, filename)

    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    with open(filepath, 'wb') as f:
        f.write(response.content)

    return filepath


@lru_cache(maxsize=1)
def get_all_camera_products():
    """
    Fetch every camera product across all categories, deduplicated by URL.
    Cached so it only hits the network once per process.
    """
    all_products = []
    seen_urls = set()

    for category_path in CAMERA_CATEGORIES.values():
        try:
            products = get_products_in_category(category_path)
        except Exception:
            continue

        for product in products:
            if product["url"] in seen_urls:
                continue
            seen_urls.add(product["url"])
            all_products.append(product)

    return all_products


def search_products(search_text):
    """
    Search all camera products by name and return matches.
    Kept for backwards compatibility / CLI use.
    """
    if not search_text:
        return []

    search_text = search_text.lower()
    return [p for p in get_all_camera_products() if search_text in p["name"].lower()]


if __name__ == "__main__":
    # Simple CLI test: python scraper.py "H6A"
    query = sys.argv[1] if len(sys.argv) > 1 else input("Search for a product: ")
    results = search_products(query)

    if not results:
        print(f"No products found matching '{query}'.")
    else:
        for product in results:
            print(f"- {product['name']}: {product['url']}")
