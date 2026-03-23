"""
update_stocks.py — Aktualisiert Aktienkurse in der Excel-Tabelle.

Holt aktuelle Kurse, Kurse vor 6 Monaten und vor 12 Monaten
von Yahoo Finance und trägt sie per COM-Automation in das Excel-Sheet ein,
sodass alle Formeln erhalten bleiben.
"""
import argparse
import io
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# ── Dynamic Imports & Checks ──────────────────────────────────────────────
try:
    import requests
    import pdfplumber # Only used for old debugging, now unused
    import win32com.client
    from win32com.client import constants as c
    # Attempt to import xlrd/pandas dynamically to check availability for reading XLS
    try:
        import xlrd
        XL_AVAILABLE = True
    except ImportError:
        XL_AVAILABLE = False
except ImportError as e:
    print(f"FATAL ERROR: Missing necessary library: {e}. Please run 'py -m pip install requests pywin32 xlrd' and try again.")
    sys.exit(1)
except Exception as e:
    print(f"FATAL ERROR during initial import: {e}")
    sys.exit(1)

# ── Configuration ──────────────────────────────────────────────────────

XLS_PATH = r"C:\Users\kurt_\Betrieb\Finanzen\Aktienuntersuchung 11.1.2026.xls"
SHEET_NAME = "Tabelle4"

# Column indices in Tabelle4 (0-based)
COL_TITEL = 0      # A
COL_KURS = 3       # D  — aktueller Kurs
COL_KURS_6M = 5    # F  — Kurs vor 6 Monaten
COL_KURS_12M = 6   # G  — Kurs vor 12 Monaten
COL_STK = 14        # O  — derzeitiger Besitz Stk.
COL_STAND = 21      # V  — Stand (date serial)
DATA_START_ROW = 6  # First data row (0-based in xlrd, 1-based in Excel = row 7)
DATA_END_ROW = 82   # Last data row (exclusive; rows after this are notes/analysis)

# Mapping: Ticker (from Excel) → Yahoo Ticker (.VI for Vienna)
YAHOO_TICKERS = {
    # Prime Market (Vienna)
    "AGR": "AGR.VI", "AIR": "AIR.VI", "AMAG": "AMAG.VI", "Andr": "ANDR.VI",
    "ATS": "ATS.VI", "BG": "BG.VI", "BROA": "BROA.VI", "CAI": "CAI.VI",
    "CPI": "CPI.VI", "DOC": "DOC.VI", "EBS": "EBS.VI", "EVN": "EVN.VI",
    "FACC": "FACC.VI", "FLU": "FLU.VI", "FME": "FME.VI", "KTCG": "KTCG.VI",
    "LNZ": "LNZ.VI", "MARI": "MARI.VI", "Mayr Melnhof": "MMK.VI",
    "OMV": "OMV.VI", "PAL": "PAL.VI", "POS": "POS.VI", "POST": "POST.VI",
    "PYT": "PYT.VI", "RBI": "RBI.VI", "RHIM": "RHIM.VI", "RHM": "RHM.VI",
    "ROS": "ROS.VI", "SBO": "SBO.VI", "SEM": "SEM.VI", "STR": "STR.VI",
    "TKA": "TKA.VI", "UBS": "UBS.VI", "UCG": "UCG.VI", "UQA": "UQA.VI",
    "VER": "VER.VI", "VIG": "VIG.VI", "VLA": "VLA.VI", "VOE": "VOE.VI",
    "WIE": "WIE.VI", "WOL": "WOL.VI", "WXF": "WXF.VI", "ZAG": "ZAG.VI",

    # Global Market (US/International stocks traded in Vienna)
    "AAPL": "AAPL.VI", "AMD": "AMD.VI", "AMZN": "AMZN.VI",
    "BNTX": "BNTX.VI", "DIS": "DIS.VI", "GE": "GE.VI",
    "GILD": "GILD.VI", "GOOA": "GOOA.VI", "IBM": "IBM.VI",
    "KO": "KO.VI", "META": "META.VI", "NFLX": "NFLX.VI",
    "MAST": "MAST.VI", "NVIDIA": "NVDA.VI", "ORCL": "ORCL.VI",
    "PLTR": "PLTR.VI", "PLUG": "PLUG.VI",
    "QCOM": "QCOM.VI", "SAP": "SAP.VI", "TSLA": "TSLA.VI",
}

# Stocks that are NOT on Wiener Börse / known to fail/are funds/bonds — skip these
SKIP_TICKERS = {
    "Amundi Ethik Fonds", "Amundi GF Vorsorge Aktiv", "Amundi Healthcare Stock",
    "Real Invest Austria", "BWO", "RNA", "RNM", "UAU", "EBN", "KOT", "BAP",
    "Gold",
}

# ── Yahoo Finance Price fetching ─────────────────────────────────────────

def fetch_close_price_yahoo(yahoo_ticker: str, ref_date: datetime) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Fetch current, 6M, and 12M prices using Yahoo Finance."""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Calculate target timestamps (in seconds since epoch)
    target_now = datetime.now().timestamp()
    target_6m = (ref_date - timedelta(days=182)).timestamp()
    target_12m = (ref_date - timedelta(days=365)).timestamp()
    
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?range=1y&interval=1d"
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"  WARN Yahoo {yahoo_ticker} HTTP {r.status_code}")
            return None, None, None
            
        data = r.json()
        result = data['chart']['result'][0]
        ts = result['timestamp']
        closes = result['indicators']['quote'][0]['close']
        
        # Find indices closest to target dates
        idx_now = max(i for i, t in enumerate(ts) if t <= target_now)
        idx_6m = min(range(len(ts)), key=lambda i: abs(ts[i] - target_6m))
        idx_12m = min(range(len(ts)), key=lambda i: abs(ts[i] - target_12m))
        
        current = closes[idx_now]
        price_6m = closes[idx_6m]
        price_12m = closes[idx_12m]

        return current, price_6m, price_12m
        
    except Exception as e:
        print(f"    Error fetching {yahoo_ticker}: {e}")
        return None, None, None


# ── Excel COM automation ──────────────────────────────────────────────

def update_excel(updates: Dict[int, Dict], dry_run: bool = False):
    """Write updated prices into Excel using COM automation."""
    if dry_run:
        print("\n[DRY RUN] Would write the following updates:")
        for row, prices in sorted(updates.items()):
            print(f"  Row {row}: Kurs={prices.get('current')}, 6M={prices.get('6m')}, 12M={prices.get('12m')}")
        return
    
    print("\nOpening Excel...")
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    
    try:
        wb = excel.Workbooks.Open(XLS_PATH)
        ws = wb.Sheets(SHEET_NAME)
        
        # Serial date for today's date (Excel's internal format)
        today_serial = int((datetime.now() - datetime(1899, 12, 30)).days)
        
        for row, prices in sorted(updates.items()):
            row_index = row # COM Excel uses 1-based indexing directly
            
            if prices.get("current") is not None:
                ws.Cells(row_index, COL_KURS + 1).Value = prices["current"]
            if prices.get("6m") is not None:
                ws.Cells(row_index, COL_KURS_6M + 1).Value = prices["6m"]
            if prices.get("12m") is not None:
                ws.Cells(row_index, COL_KURS_12M + 1).Value = prices["12m"]
            # Update Stand to today
            ws.Cells(row_index, COL_STAND + 1).Value = today_serial
        
        wb.Save()
        print(f"SUCCESS: Saved {len(updates)} updates to {XLS_PATH}")
        
    except Exception as e:
        print(f"FATAL COM ERROR: Could not write to Excel: {e}")
    finally:
        if 'wb' in locals():
            wb.Close(False)
        excel.Quit()


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Update stock prices in Excel")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only show what would be updated")
    parser.add_argument("--ticker", nargs="*",
                        help="Only update specific tickers")
    parser.add_argument("--all", action="store_true",
                        help="Update ALL stocks in the list (not just held ones)")
    args = parser.parse_args()
    
    # Read current state from XLS to know what to update and check for holdings
    if not XL_AVAILABLE:
        print("FATAL ERROR: xlrd is not available. Cannot read initial file state.")
        return 1
        
    try:
        wb = xlrd.open_workbook(XLS_PATH)
        sh = wb.sheet_by_name(SHEET_NAME)
    except Exception as e:
        print(f"ERROR: Could not open or read Excel file: {e}")
        return 1

    ref_date = datetime.now()
    # Adjust reference date to last trading day (assume last Friday if today is weekend)
    if ref_date.weekday() == 5:  # Saturday
        ref_date -= timedelta(days=1)
    elif ref_date.weekday() == 6:  # Sunday
        ref_date -= timedelta(days=2)
    
    print(f"Reference date for 'Current': {ref_date.strftime('%d.%m.%Y')}")
    print(f"6M reference:   {(ref_date - timedelta(days=182)).strftime('%d.%m.%Y')}")
    print(f"12M reference:  {(ref_date - timedelta(days=365)).strftime('%d.%m.%Y')}")
    print()
    
    updates = {}  # {excel_row_1based: {current, 6m, 12m}}
    errors = []
    
    for r in range(DATA_START_ROW, min(DATA_END_ROW, sh.nrows)):
        ticker = str(sh.cell_value(r, COL_TITEL)).strip()
        if not ticker:
            continue
        
        # Skip control rows, notes, and non-tracked items
        if ticker in SKIP_TICKERS:
            continue
        # Skip rows that are clearly comments/notes, not tickers:
        # - contains spaces and is longer than a reasonable ticker+name
        # - contains certain keywords indicating notes/headers
        if len(ticker) > 20 or any(p in ticker for p in [
            "Kandidaten", "Kauf:", "Verkauf:", "URL", "Stand",
            "http", "Theorie", "Neuzug", "notiert erst", "Ausstieg",
            "Bollinger", "richtiger", "->", "(",
        ]):
            continue
        
        # Check if held (Stk > 0)
        try:
            stk = int(float(sh.cell_value(r, COL_STK)))
        except:
            stk = 0
        
        if stk == 0 and not args.all:
            continue
        
        # Map ticker symbol to Yahoo symbol
        yahoo_ticker = YAHOO_TICKERS.get(ticker)
        if not yahoo_ticker:
            # Manual mapping check for stocks not in initial map (e.g., ZAG, PYT, DOC sometimes)
            # For now, we skip if not in the main map, as manual inspection is required for Tickers missing in the map.
            errors.append(f"Ticker '{ticker}' (row {r+1}): No explicit Yahoo mapping found. Skipping.")
            continue
        
        excel_row = r + 1  # COM Excel is 1-based
        
        held_marker = f"{stk} Stk" if stk > 0 else "nicht gehalten"
        print(f"[{ticker}] (row {excel_row}, {held_marker})")
        current, price_6m, price_12m = fetch_close_price_yahoo(yahoo_ticker, ref_date)
        
        if current is None:
            errors.append(f"Could not fetch data for {ticker} (row {excel_row}) using {yahoo_ticker}")
            print(f"  WARN Could not fetch current price!")
        else:
            p6 = f"{price_6m:.2f}" if price_6m else "?"
            p12 = f"{price_12m:.2f}" if price_12m else "?"
            print(f"  OK Current: {current:.2f}, 6M: {p6}, 12M: {price_12m if price_12m else '?'}")
            updates[excel_row] = {
                "current": current, 
                "6m": price_6m, 
                "12m": price_12m
            }
        
        time.sleep(0.3) # Be gentle with the server
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Results: {len(updates)} stocks updated, {len(errors)} errors")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  WARN {e}")
    
    if updates:
        update_excel(updates, dry_run=args.dry_run)
    
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())