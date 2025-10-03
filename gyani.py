# gyani.py (updated)
import requests
from bs4 import BeautifulSoup
import re

class GyaniBypass:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def gyani_bypasser(self, url):
        # Extract domain for referer
        domain_match = re.search(r'(https?://[^/]+)', url)
        if domain_match:
            self.session.headers.update({'Referer': domain_match.group(0) + '/'})
        
        # Step 1: Fetch page
        r = self.session.get(url)
        if r.status_code != 200:
            return f"❌ Failed to fetch page: {r.status_code}"

        soup = BeautifulSoup(r.text, "html.parser")

        # Step 2: Look for hidden anchors that might be revealed
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith('http') and not any(domain in href for domain in ['gyanigurus', 'gyani']):
                links.append(href)

        # Step 3: Extract JavaScript logic for show_content_v()
        js_funcs = re.findall(r'function\s+show_content_v\s*\(\)\s*{([^}]+)}', r.text, re.S)
        if js_funcs:
            js_body = js_funcs[0]
            # Look for assignment like `href="..."` inside
            possible_urls = re.findall(r'(https?://[^\s"\'<>]+)', js_body)
            links.extend(possible_urls)

        # Step 4: Check for common download patterns
        common_patterns = [
            r'window\.location\s*=\s*["\']([^"\']+)["\']',
            r'window\.open\s*\(\s*["\']([^"\']+)["\']',
            r'location\.href\s*=\s*["\']([^"\']+)["\']',
            r'downloadUrl\s*=\s*["\']([^"\']+)["\']',
            r'fileUrl\s*=\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in common_patterns:
            matches = re.findall(pattern, r.text)
            links.extend(matches)

        links = list(set(links))  # dedupe
        return links if links else "❌ Could not find final link."
