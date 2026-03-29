from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import time
import requests
from pathlib import Path
import re

class KonguWebScraper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.visited_urls = set()
        
        # Create directories
        self.dirs = {
            'text': 'scraped_data/text',
            'images': 'scraped_data/images',
            'videos': 'scraped_data/videos'
        }
        for dir_path in self.dirs.values():
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        self.image_count = 0
        self.video_count = 0
        self.page_count = 0
        
        # Setup Selenium WebDriver
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome WebDriver with options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')  # Run in background (new headless mode)
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # Selenium 4+ has built-in driver management
            # It will automatically download the correct ChromeDriver version
            self.driver = webdriver.Chrome(options=chrome_options)
            print("✓ Chrome WebDriver initialized successfully")
        except Exception as e:
            print(f"✗ Error initializing WebDriver: {e}")
            print("\n📦 Troubleshooting:")
            print("1. Make sure Chrome/Chromium is installed:")
            print("   sudo apt-get install chromium-browser")
            print("2. Update Selenium:")
            print("   pip install -U selenium")
            print("3. If issues persist, try:")
            print("   pip install -U selenium webdriver-manager requests beautifulsoup4")
            raise
    
    def normalize_url(self, url):
        """Normalize URL to handle malformed URLs"""
        if not url:
            return None
        
        # Skip javascript, mailto, tel links
        if url.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            return None
        
        # Handle malformed localhost URLs
        if 'localhost' in url:
            return None
        
        try:
            # Join with base URL
            full_url = urljoin(self.base_url, url)
            parsed = urlparse(full_url)
            
            # Skip invalid schemes
            if parsed.scheme not in ['http', 'https']:
                return None
            
            # Remove fragment
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            
            return clean_url
        except Exception as e:
            return None
    
    def is_valid_url(self, url):
        """Check if URL belongs to the same domain"""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.domain
        except:
            return False
    
    def download_file(self, url, folder):
        """Download a file (image/video) from URL"""
        try:
            response = requests.get(url, timeout=15, stream=True)
            response.raise_for_status()
            
            filename = os.path.basename(urlparse(url).path)
            if not filename:
                ext = '.jpg'
                content_type = response.headers.get('content-type', '')
                if 'png' in content_type:
                    ext = '.png'
                elif 'gif' in content_type:
                    ext = '.gif'
                elif 'mp4' in content_type:
                    ext = '.mp4'
                filename = f"file_{abs(hash(url))}{ext}"
            
            # Sanitize filename
            filename = re.sub(r'[^\w\s\.-]', '_', filename)
            filepath = os.path.join(folder, filename)
            
            # Avoid overwriting
            counter = 1
            base, ext = os.path.splitext(filepath)
            while os.path.exists(filepath):
                filepath = f"{base}_{counter}{ext}"
                counter += 1
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"    ✓ Downloaded: {filename}")
            return filepath
        except Exception as e:
            print(f"    ✗ Error downloading {url}: {e}")
            return None
    
    def scrape_page(self, url, depth=0, max_depth=2):
        """Scrape a single page using Selenium"""
        if depth > max_depth or url in self.visited_urls:
            return
        
        # Normalize URL
        url = self.normalize_url(url)
        if not url or not self.is_valid_url(url):
            return
        
        if url in self.visited_urls:
            return
        
        self.visited_urls.add(url)
        self.page_count += 1
        
        print(f"\n{'  ' * depth}[{self.page_count}] Scraping: {url} (Depth: {depth})")
        
        try:
            # Load page with Selenium
            self.driver.get(url)
            
            # Wait for page to load (adjust time as needed)
            time.sleep(3)
            
            # Wait for body to be present
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Scroll to load lazy images
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Get page source after JavaScript execution
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract content
            self.extract_text(soup, url)
            self.extract_images(soup, url)
            self.extract_videos(soup, url)
            
            # Find and follow links
            if depth < max_depth:
                links = soup.find_all('a', href=True)
                valid_links = []
                
                for link in links:
                    next_url = self.normalize_url(link['href'])
                    if next_url and self.is_valid_url(next_url) and next_url not in self.visited_urls:
                        valid_links.append(next_url)
                
                print(f"  Found {len(links)} links, {len(valid_links)} valid internal links")
                
                for next_url in valid_links:
                    time.sleep(0.5)  # Be polite
                    self.scrape_page(next_url, depth + 1, max_depth)
        
        except Exception as e:
            print(f"  ✗ Error scraping {url}: {e}")
    
    def extract_text(self, soup, url):
        """Extract and save text content"""
        try:
            # Remove unwanted elements
            for element in soup(['script', 'style', 'meta', 'link']):
                element.decompose()
            
            # Get text
            text = soup.get_text(separator='\n', strip=True)
            
            # Save to file
            path_part = urlparse(url).path.replace('/', '_').replace('https://chatgpt.com/\\', '_') or 'index'
            filename = f"page_{self.page_count}_{path_part}.txt"
            filename = re.sub(r'[^\w\s\.-]', '_', filename)[:200]  # Limit length
            filepath = os.path.join(self.dirs['text'], filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"URL: {url}\n")
                f.write(f"Scraped: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                f.write(text)
            
            print(f"  ✓ Saved text: {filename} ({len(text)} chars)")
        except Exception as e:
            print(f"  ✗ Error saving text: {e}")
    
    def extract_images(self, soup, url):
        """Extract and download images"""
        img_tags = soup.find_all('img')
        images_found = 0
        
        for img in img_tags:
            img_url = img.get('src') or img.get('data-src') or img.get('data-original')
            if img_url:
                img_url = self.normalize_url(img_url)
                if img_url and img_url.startswith('http'):
                    if self.download_file(img_url, self.dirs['images']):
                        self.image_count += 1
                        images_found += 1
        
        if images_found > 0:
            print(f"  ✓ Found {images_found} images on this page")
    
    def extract_videos(self, soup, url):
        """Extract and save video information"""
        videos_found = 0
        
        # Find video tags
        video_tags = soup.find_all('video')
        for video in video_tags:
            sources = video.find_all('source')
            for source in sources:
                video_url = source.get('src')
                if video_url:
                    video_url = self.normalize_url(video_url)
                    if video_url and video_url.startswith('http'):
                        if self.download_file(video_url, self.dirs['videos']):
                            self.video_count += 1
                            videos_found += 1
            
            video_url = video.get('src')
            if video_url:
                video_url = self.normalize_url(video_url)
                if video_url and video_url.startswith('http'):
                    if self.download_file(video_url, self.dirs['videos']):
                        self.video_count += 1
                        videos_found += 1
        
        # Find embedded videos
        iframes = soup.find_all('iframe')
        video_links_file = os.path.join(self.dirs['videos'], 'video_links.txt')
        
        for iframe in iframes:
            src = iframe.get('src', '')
            if src and ('youtube' in src or 'vimeo' in src or 'video' in src.lower()):
                with open(video_links_file, 'a', encoding='utf-8') as f:
                    f.write(f"{src}\n")
                print(f"  ✓ Found embedded video: {src}")
                self.video_count += 1
                videos_found += 1
        
        if videos_found > 0:
            print(f"  ✓ Found {videos_found} videos on this page")
    
    def start_scraping(self, max_depth=2):
        """Start the scraping process"""
        print("=" * 80)
        print("WEB SCRAPER")
        print("=" * 80)
        print(f"Target: {self.base_url}")
        print(f"Max depth: {max_depth}")
        print(f"Output directory: scraped_data/")
        print("=" * 80)
        
        start_time = time.time()
        
        try:
            self.scrape_page(self.base_url, max_depth=max_depth)
        finally:
            self.driver.quit()
            print("\n✓ Browser closed")
        
        end_time = time.time()
        
        print("\n" + "=" * 80)
        print("SCRAPING COMPLETED!")
        print("=" * 80)
        print(f"Total pages scraped: {self.page_count}")
        print(f"Total images downloaded: {self.image_count}")
        print(f"Total videos found: {self.video_count}")
        print(f"Time taken: {end_time - start_time:.2f} seconds")
        print(f"Data saved in: scraped_data/")
        print("=" * 80)


if __name__ == "__main__":
    # Initialize scraper
    scraper = KonguWebScraper("https://www.data.gov.in/cdo?page=1")
    
    # Start scraping
    # max_depth=2 recommended (more = longer time)
    scraper.start_scraping(max_depth=2)
