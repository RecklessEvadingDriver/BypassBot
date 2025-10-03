# gdflix.py (updated)
import requests
from bs4 import BeautifulSoup
import json
import re

class GDFlixBypass:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.urls_json = "https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json"

    def get_latest_url(self):
        try:
            res = self.session.get(self.urls_json, timeout=10)
            data = res.json()
            gdflix_url = data.get("gdflix")
            if gdflix_url:
                return gdflix_url
        except Exception:
            pass
        
        # Fallback to extracting from common patterns
        return "https://gdflix.dev"

    def bypass(self, url):
        # Extract domain for referer
        domain_match = re.search(r'(https?://[^/]+)', url)
        if domain_match:
            self.session.headers.update({'Referer': domain_match.group(0) + '/'})
        
        latest_url = self.get_latest_url()
        
        # Replace domain in URL
        url_domain = re.search(r'(https?://[^/]+)', url).group(1)
        new_url = url.replace(url_domain, latest_url)

        res = self.session.get(new_url)
        soup = BeautifulSoup(res.text, "html.parser")

        # Metadata
        file_name = ""
        file_size = ""
        try:
            name_element = soup.find('li', string=re.compile('Name'))
            if name_element:
                file_name = name_element.text.split("Name : ")[1].strip()
        except: pass
        
        try:
            size_element = soup.find('li', string=re.compile('Size'))
            if size_element:
                file_size = size_element.text.split("Size : ")[1].strip()
        except: pass

        results = []

        # Server links
        for anchor in soup.select("div.text-center a"):
            text = anchor.get_text(strip=True)
            href = anchor.get("href")

            if not href:
                continue

            # Make relative URLs absolute
            if href.startswith('/'):
                href = latest_url + href

            if "DIRECT DL" in text:
                results.append({"type": "Direct", "file": file_name, "size": file_size, "url": href})

            elif "CLOUD DOWNLOAD" in text:
                results.append({"type": "Cloud R2", "file": file_name, "size": file_size, "url": href})

            elif "PixelDrain" in text:
                results.append({"type": "Pixeldrain", "file": file_name, "size": file_size, "url": href})

            elif "Index Links" in text:
                try:
                    idx_page = self.session.get(href).text
                    idx_soup = BeautifulSoup(idx_page, "html.parser")
                    for btn in idx_soup.select("a.btn.btn-outline-info"):
                        btn_href = btn.get("href")
                        if btn_href.startswith('/'):
                            btn_href = latest_url + btn_href
                        sub_page = self.session.get(btn_href).text
                        sub_soup = BeautifulSoup(sub_page, "html.parser")
                        for src in sub_soup.select("div.mb-4 > a"):
                            results.append({"type": "Index", "file": file_name, "size": file_size, "url": src.get("href")})
                except Exception as e:
                    print("Index Links error:", e)

            elif "Instant DL" in text:
                try:
                    r2 = self.session.get(href, allow_redirects=False)
                    location = r2.headers.get("location", "")
                    if "url=" in location:
                        link = location.split("url=")[-1]
                        results.append({"type": "Instant DL", "file": file_name, "size": file_size, "url": link})
                except Exception as e:
                    print("Instant DL error:", e)

            elif "GoFile" in text:
                results.append({"type": "GoFile", "file": file_name, "size": file_size, "url": href})

            elif "DRIVEBOT" in text:
                results.append({"type": "DriveBot", "file": file_name, "size": file_size, "url": href})

        return {"file_name": file_name, "file_size": file_size, "links": results}
