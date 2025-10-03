# photolinx.py (updated)
import requests
from bs4 import BeautifulSoup
import json
import re

class PhotoLinxBypass:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def bypass(self, url):
        # Extract domain for base_url
        domain_match = re.search(r'(https?://[^/]+)', url)
        base_url = domain_match.group(1) if domain_match else "https://photolinx.space"
        
        # Step 1: GET the page
        res = self.session.get(url)
        if "PHPSESSID" not in self.session.cookies:
            raise Exception("No PHPSESSID cookie found.")
        
        ssid = self.session.cookies.get("PHPSESSID")

        # Step 2: Parse HTML to get filename, token, uid
        soup = BeautifulSoup(res.text, "html.parser")
        file_name = soup.select_one("h1").text if soup.select_one("h1") else ""

        generate_btn = soup.select_one("#generate_url")
        if not generate_btn:
            # Try alternative selectors
            generate_btn = soup.select_one(".generate-url, .btn-generate, [data-token]")
            if not generate_btn:
                raise Exception("Couldn't find generate button.")
        
        access_token = generate_btn.get("data-token")
        uid = generate_btn.get("data-uid")

        if not access_token or not uid:
            # Try to extract from JavaScript
            token_pattern = r"data-token\s*=\s*['\"]([^'\"]+)['\"]"
            uid_pattern = r"data-uid\s*=\s*['\"]([^'\"]+)['\"]"
            
            token_match = re.search(token_pattern, res.text)
            uid_match = re.search(uid_pattern, res.text)
            
            access_token = token_match.group(1) if token_match else access_token
            uid = uid_match.group(1) if uid_match else uid

        if not access_token or not uid:
            raise Exception("Missing token/uid.")

        # Step 3: Prepare JSON body
        body = {
            "type": "DOWNLOAD_GENERATE",
            "payload": {
                "access_token": access_token,
                "uid": uid
            }
        }

        headers = {
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest",
            "cookie": f"PHPSESSID={ssid}",
            "Referer": url,
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Type": "application/json; charset=utf-8"
        }

        # Step 4: POST to /action
        action_url = f"{base_url}/action"
        res2 = self.session.post(action_url, data=json.dumps(body), headers=headers)

        if res2.status_code != 200:
            raise Exception(f"POST failed with status {res2.status_code}")

        data = res2.json()
        dw_url = data.get("download_url")

        # Make relative URL absolute if needed
        if dw_url and dw_url.startswith('/'):
            dw_url = base_url + dw_url

        return {
            "file_name": file_name,
            "download_url": dw_url
        }
