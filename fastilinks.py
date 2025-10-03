# fastilinks.py (updated)
import requests
from bs4 import BeautifulSoup
import re

class FastLinksBypass:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def bypass(self, url):
        # Extract domain for base_url
        domain_match = re.search(r'(https?://[^/]+)', url)
        base_url = domain_match.group(1) if domain_match else "https://fastilinks.online"
        
        # Step 1: GET request to grab session cookies
        res = self.session.get(url)
        if "PHPSESSID" not in self.session.cookies:
            raise Exception("No PHPSESSID cookie found.")
        
        # Grab PHPSESSID
        ssid = self.session.cookies.get("PHPSESSID")

        # Step 2: Look for CSRF token dynamically
        soup = BeautifulSoup(res.text, "html.parser")
        csrf_input = soup.find('input', {'name': re.compile(r'_csrf_token_')})
        
        if not csrf_input:
            # Try to find CSRF token in other common locations
            csrf_pattern = r'_csrf_token_[a-f0-9]+'
            csrf_match = re.search(csrf_pattern, res.text)
            if csrf_match:
                csrf_name = csrf_match.group(0)
                # Use a default token or try to extract it
                form_data = {csrf_name: "default_token_placeholder"}
            else:
                form_data = {}
        else:
            csrf_name = csrf_input['name']
            csrf_value = csrf_input.get('value', 'default_token_placeholder')
            form_data = {csrf_name: csrf_value}

        res_post = self.session.post(url, data=form_data, cookies={"PHPSESSID": ssid})
        soup = BeautifulSoup(res_post.text, "html.parser")

        # Step 3: Extract links from various possible locations
        links = []
        
        # From div.well > a
        for a in soup.select("div.well > a"):
            href = a.get("href")
            if href and href.startswith('http'):
                links.append(href)
        
        # From any download buttons
        for a in soup.select(".btn-download, .download-btn, .btn-success, a[href*='download']"):
            href = a.get("href")
            if href and href.startswith('http'):
                links.append(href)
        
        # From JavaScript links
        script_patterns = [
            r'window\.location\s*=\s*["\']([^"\']+)["\']',
            r'window\.open\s*\(\s*["\']([^"\']+)["\']',
            r'location\.href\s*=\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in script_patterns:
            matches = re.findall(pattern, res_post.text)
            links.extend(matches)

        # Make relative URLs absolute
        final_links = []
        for link in links:
            if link.startswith('/'):
                link = base_url + link
            final_links.append(link)

        return list(set(final_links))  # Remove duplicates
