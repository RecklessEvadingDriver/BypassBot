# hubdrive.py (updated)
import requests
import re

class HubDriveBypass:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'
        })

    def extract(self, base_url):
        try:
            # Extract domain for referer
            domain_match = re.search(r'(https?://[^/]+)', base_url)
            if domain_match:
                self.session.headers.update({'Referer': domain_match.group(0) + '/'})
            
            response = self.session.get(base_url)
            response.raise_for_status()
            
            html_content = response.text
            
            url_patterns = [
                r"https:\/\/hubcloud\.\w+\/drive\/[a-zA-Z0-9]+",
                r"https:\/\/[^\/\s]+\.hubcloud\.[^\/\s]+\/[^\s\"'<>]+",
                r"https:\/\/cdn\.fsl-buckets\.xyz\/[^\s\"'<>]+",
                r"https:\/\/pixeldrain\.\w+\/api\/file\/[^\s\"'<>]+",
                r"https:\/\/pixel\.hubcdn\.\w+\/\?id=[^\s\"'<>]+",
                r"https:\/\/[^\/\s]+\.\w+\/[^\s\"'<>]+\.(mkv|mp4|avi|mov)",
            ]
            
            js_patterns = [
                r"var\s+(?:url|link|download|file)\s*=\s*['\"]([^'\"]+)['\"]",
                r"(?:url|link|download|file)\s*[:=]\s*['\"]([^'\"]+)['\"]",
                r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
                r"window\.open\s*\(\s*['\"]([^'\"]+)['\"]",
            ]
            
            download_url = None
            
            # First try direct URL patterns
            for pattern in url_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    for match in matches:
                        if not any(skip in match.lower() for skip in ['javascript:', 'mailto:', '#', 'void(0)']):
                            download_url = match.strip().replace('"', '').replace("'", "")
                            break
                    if download_url:
                        break
            
            # If no direct URLs found, try JavaScript patterns
            if not download_url:
                for pattern in js_patterns:
                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                    if matches:
                        for match in matches:
                            if match.startswith('http') and not any(skip in match.lower() for skip in ['javascript:', 'mailto:', '#']):
                                download_url = match.strip()
                                break
                        if download_url:
                            break
            
            return download_url
                
        except Exception as e:
            print(f"Error: {e}")
            return None
