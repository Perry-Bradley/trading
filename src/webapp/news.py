import json
import urllib.request
from datetime import datetime, timedelta

def get_high_impact_news():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            
        high_impact = []
        for item in data:
            if item.get("impact") == "High":
                # format: "2026-06-24T08:30:00-04:00"
                date_str = item.get("date")
                try:
                    dt = datetime.fromisoformat(date_str).replace(tzinfo=None)
                    high_impact.append({
                        "currency": item.get("country"), # e.g. "USD"
                        "title": item.get("title"),
                        "time": dt
                    })
                except Exception:
                    pass
        return high_impact
    except Exception as e:
        print("Failed to fetch news:", e)
        return []

def is_news_embargo(pair: str, signal_time: datetime, news_data: list, hours_before=2, hours_after=2) -> tuple[bool, str]:
    """Check if the signal is near a high impact news event for its currencies."""
    if not news_data:
        return False, ""
        
    c1 = pair[:3]
    c2 = pair[3:]
    
    for n in news_data:
        if n["currency"] in (c1, c2):
            diff = signal_time - n["time"]
            diff_hours = diff.total_seconds() / 3600
            
            if -hours_before <= diff_hours <= hours_after:
                return True, n["title"]
                
    return False, ""
