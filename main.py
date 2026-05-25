import json
import requests
from bs4 import BeautifulSoup

# ============================================
# CONFIG
# ============================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ============================================
# MEDICAL EQUIPMENT KEYWORDS
# ============================================

KEYWORDS = [

    # Imaging
    "ultrasound machine",
    "mammography system",
    "x-ray machine",
    "mobile x-ray",
    "fixed x-ray",
    "portable x-ray",
    "ultraportable x-ray",
    "c-arm",
    "ct scanner",
    "mri machine",
    "bone densitometer",
    "pacs system",
    "picture archiving",
    "healthcare it",

    # Monitoring / Diagnostic
    "ecg machine",
    "eeg machine",
    "cat lab",
    "cardiac catheterization",
    "defibrillator",
    "patient monitor",
    "multiparameter monitor",
    "fetal monitor",
    "capnograph",
    "pulse oximeter",
    "bp apparatus",
    "blood pressure monitor",
    "glucometer",
    "thermometer",
    "infrared thermometer",
    "spirometer",
    "weighing scale",

    # Operating Room
    "operating table",
    "surgical lights",
    "examination lamp",
    "anesthesia machine",
    "gas scavenging system",
    "laryngoscope",
    "endotracheal tube",
    "electrosurgical unit",
    "argon plasma coagulation",
    "surgical microscope",

    # General medical words
    "medical equipment",
    "hospital equipment",
    "medical",
    "hospital",
    "laboratory equipment",
    "diagnostic equipment",
    "healthcare equipment"
]

# ============================================
# HELPER: SAFE HTTP GET
# ============================================

def safe_get(url, params=None, json_accept=False):
    hdrs = {**HEADERS}
    if json_accept:
        hdrs["Accept"] = "application/json"
    try:
        r = requests.get(url, headers=hdrs, params=params, timeout=30)
        return r
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Could not connect to {url}")
    except requests.exceptions.Timeout:
        print(f"ERROR: Request timed out for {url}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}")
    return None

# ============================================
# HELPER: MATCH KEYWORDS
# ============================================

def match_keywords(text):
    text_lower = text.lower()
    return [kw for kw in KEYWORDS if kw.lower() in text_lower]

# ============================================================
# SOURCE 1: 2merkato.com — keyword search via Inertia JSON
# ============================================================

MERKATO_BASE = "https://tender.2merkato.com"

MERKATO_SEARCH_TERMS = [
    "medical equipment",
    "hospital equipment",
    "laboratory equipment",
    "diagnostic equipment",
    "surgical equipment",
    "medical supplies",
]

def scrape_2merkato():
    print("\n" + "=" * 60)
    print("SOURCE 1: 2merkato.com")
    print("=" * 60)

    seen_ids = set()
    results = []

    for term in MERKATO_SEARCH_TERMS:
        r = safe_get(f"{MERKATO_BASE}/tenders", params={"q": term})
        if not r or r.status_code != 200:
            print(f"  Skipping '{term}' (fetch failed)")
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        app_div = soup.find(id="app")
        if not app_div or not app_div.get("data-page"):
            continue

        tenders = json.loads(app_div["data-page"]).get("props", {}).get("tenders", {}).get("data", [])

        new = 0
        for t in tenders:
            tid = t.get("id", "")
            if not tid or tid in seen_ids:
                continue
            seen_ids.add(tid)

            title = t.get("title") or ""
            matched = match_keywords(title)
            if not matched:
                continue

            results.append({
                "source": "2merkato.com",
                "title": title,
                "company": (t.get("company") or {}).get("name_en", ""),
                "status": "Open" if t.get("is_open") else ("Closed" if t.get("is_open") is False else "Login required"),
                "closing_date": t.get("bid_closing_date") or "Login required to view",
                "matched_keywords": matched,
                "link": f"{MERKATO_BASE}/tenders/{tid}",
            })
            new += 1

        print(f"  Searched '{term}' -> {len(tenders)} results, {new} new matches")

    print(f"  Total matched from 2merkato: {len(results)}")
    return results


# ============================================================
# SOURCE 2: epss.gov.et — plain HTML tender cards
# ============================================================

EPSS_BASE = "https://epss.gov.et"

def scrape_epss():
    print("\n" + "=" * 60)
    print("SOURCE 2: epss.gov.et (Ethiopian Pharmaceuticals Supply Service)")
    print("=" * 60)

    r = safe_get(f"{EPSS_BASE}/epss/tenders")
    if not r or r.status_code != 200:
        print("  ERROR: Could not fetch EPSS tenders page")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    cards = soup.find_all("div", class_="tender-card")
    print(f"  Found {len(cards)} total tenders on EPSS")

    results = []
    for card in cards:
        title_tag = card.find("h3", class_="tender-title")
        link_tag = title_tag.find("a") if title_tag else None
        title = link_tag.get_text(strip=True) if link_tag else ""
        link = link_tag.get("href", "") if link_tag else ""

        category_tag = card.find("div", class_="tender-category")
        category = category_tag.get_text(strip=True) if category_tag else ""

        date_tag = card.find("div", class_="deadline-date")
        closing_date = date_tag.get_text(strip=True) if date_tag else "N/A"

        status_tag = card.find("span", class_="status-badge")
        status = status_tag.get_text(strip=True) if status_tag else "N/A"

        code_tag = card.find("span", class_="tender-code")
        code = code_tag.get_text(strip=True) if code_tag else ""

        # Match by title OR include all Medical Equipment category tenders
        matched = match_keywords(title + " " + category)
        if "medical equipment" in category.lower():
            if "medical equipment" not in matched:
                matched.insert(0, "medical equipment")

        if not matched:
            continue

        results.append({
            "source": "epss.gov.et",
            "title": title,
            "company": "Ethiopian Pharmaceuticals Supply Service (EPSS)",
            "status": status,
            "closing_date": closing_date,
            "category": category,
            "code": code,
            "matched_keywords": matched,
            "link": link,
        })

    print(f"  Total matched from EPSS: {len(results)}")
    return results


# ============================================================
# SOURCE 3: production.egp.gov.et — stats only (auth required for listings)
# ============================================================

EGP_BASE = "https://production.egp.gov.et"

def scrape_egp_summary():
    print("\n" + "=" * 60)
    print("SOURCE 3: production.egp.gov.et (Electronic Government Procurement)")
    print("=" * 60)

    r = safe_get(f"{EGP_BASE}/po-gw/cms-v2/api/sourcing/get-tender-summary", json_accept=True)
    if r and r.status_code == 200:
        try:
            stats = r.json()
            print(f"  Active tenders on EGP portal: {stats.get('totalActive', 'N/A')}")
            print(f"  Published today: {stats.get('publishedToday', 'N/A')}")
            print(f"  Closing today: {stats.get('closingToday', 'N/A')}")
            print(f"  Note: EGP requires account login to view individual tender listings.")
            print(f"  Register at: {EGP_BASE}/egp/home")
            return stats
        except Exception:
            pass

    print("  Could not fetch EGP summary.")
    return {}


# ============================================================
# MAIN — RUN ALL SCRAPERS & SAVE
# ============================================================

print("\nStarting medical equipment tender scraper...\n")

all_results = []
all_results += scrape_2merkato()
all_results += scrape_epss()
egp_stats = scrape_egp_summary()

# ============================================
# BUILD MARKDOWN
# ============================================

web_markdown = "# Medical Equipment Tenders\n\n"

# EGP stats note
if egp_stats:
    web_markdown += "## EGP Portal Summary\n\n"
    web_markdown += f"- **Active tenders:** {egp_stats.get('totalActive', 'N/A')}\n"
    web_markdown += f"- **Published today:** {egp_stats.get('publishedToday', 'N/A')}\n"
    web_markdown += f"- **Closing today:** {egp_stats.get('closingToday', 'N/A')}\n"
    web_markdown += f"- **Portal:** [production.egp.gov.et]({EGP_BASE}/egp/home) *(login required for full listings)*\n\n"
    web_markdown += "---\n\n"

# Print and write each matched tender
print("\n" + "=" * 60)
print(f"TOTAL MATCHED MEDICAL TENDERS: {len(all_results)}")
print("=" * 60 + "\n")

if not all_results:
    print("No medical equipment tenders found.")
    web_markdown += "No medical equipment tenders found.\n"
else:
    for t in all_results:
        title = t["title"]
        source = t["source"]
        company = t.get("company", "")
        status = t.get("status", "")
        closing_date = t.get("closing_date", "")
        matched = t["matched_keywords"]
        link = t["link"]
        category = t.get("category", "")
        code = t.get("code", "")

        print("=" * 80)
        print(f"\n[{source}]")
        print(f"\nTITLE:\n{title}")
        if company:
            print(f"\nCOMPANY:\n{company}")
        if category:
            print(f"\nCATEGORY:\n{category}")
        if code:
            print(f"\nCODE:\n{code}")
        print(f"\nSTATUS: {status}")
        print(f"\nCLOSING DATE: {closing_date}")
        print(f"\nMATCHED KEYWORDS:\n{', '.join(matched)}")
        print(f"\nLINK:\n{link}")
        print("\n" + "=" * 80 + "\n")

        web_markdown += f"## {title}\n\n"
        web_markdown += f"**Source:** {source}\n\n"
        if company:
            web_markdown += f"**Company:** {company}\n\n"
        if category:
            web_markdown += f"**Category:** {category}\n\n"
        if code:
            web_markdown += f"**Tender Code:** {code}\n\n"
        web_markdown += f"**Status:** {status}\n\n"
        web_markdown += f"**Closing Date:** {closing_date}\n\n"
        web_markdown += f"**Matched Keywords:** {', '.join(matched)}\n\n"
        web_markdown += f"**Link:** [{link}]({link})\n\n"
        web_markdown += "---\n\n"

    print(f"\nScraper working correctly.")

# ============================================
# SAVE MARKDOWN FILE
# ============================================

with open("web.md", "w", encoding="utf-8") as scrap_file:
    scrap_file.write(web_markdown)

print("\nMarkdown file saved as web.md")
