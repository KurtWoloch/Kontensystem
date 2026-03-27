"""Test which URL patterns work for Wiener Börse historical data PDFs."""
import requests
import io
import pdfplumber

def test_url(isin, name, segments=None):
    """Try different market segments to find the right URL."""
    if segments is None:
        segments = [
            'aktien-prime-market',
            'aktien-global-market', 
            'aktien-standard-market',
            'aktien-direct-market-plus',
        ]
    
    for seg in segments:
        # We need to figure out the slug format: name-ISIN
        # The Wiener Börse uses: {segment}/{company-slug}-{ISIN}/historische-daten.pdf
        # But the slug varies. Let's try the ISIN directly in the search.
        url = f"https://www.wienerborse.at/{seg}/?c7928%5Bquery%5D={isin}"
        # Actually, the PDF URLs we know work have specific slugs.
        # Let's just try the known working pattern with a search.
        pass
    
    # Better approach: use the API/search endpoint
    search_url = f"https://www.wienerborse.at/issuances/list/?ISIN={isin}&c18498%5BDOWNLOAD%5D=csv"
    # Or try the historical data PDF directly with different name patterns
    
    return None

# Test with known working URLs
test_cases = [
    ("AT0000609607", "porr-ag", "aktien-prime-market"),
    ("ATMARINOMED6", "marinomed-biotech-ag", "aktien-standard-market"),
    ("AT000000STR1", "strabag-se", "aktien-prime-market"),
    ("US30303M1027", "meta-platforms-inc-a", "aktien-global-market"),
]

for isin, slug, segment in test_cases:
    url = f"https://www.wienerborse.at/{segment}/{slug}-{isin}/historische-daten.pdf?date-start=18.03.2026&date-end=21.03.2026"
    print(f"Testing {isin} ({slug})...")
    try:
        r = requests.get(url, timeout=10)
        print(f"  Status: {r.status_code}, Size: {len(r.content)} bytes")
        if r.status_code == 200 and len(r.content) > 500:
            pdf = pdfplumber.open(io.BytesIO(r.content))
            page = pdf.pages[0]
            text = page.extract_text()
            # Find closing price line
            lines = text.split('\n')
            for line in lines:
                if '2026' in line or 'Schluss' in line or 'Datum' in line:
                    print(f"  >> {line[:100]}")
            pdf.close()
    except Exception as e:
        print(f"  Error: {e}")
    print()
