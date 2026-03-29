"""
CDO (Chief Data Officer) Data Scraper for data.gov.in
Extracts all CDO profile information from pages 1-13 and saves to CSV
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup
import csv
import time
import re
from datetime import datetime


class CDOScraper:
    def __init__(self):
        self.base_url = "https://www.data.gov.in/cdo"
        self.all_cdo_data = []
        self.processed_names = set()
        self.setup_driver()
        
    def setup_driver(self):
        """Setup Chrome WebDriver with options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            print("✓ Chrome WebDriver initialized successfully")
        except Exception as e:
            print(f"✗ Error initializing WebDriver: {e}")
            raise
    
    def clean_email(self, email_text):
        """Convert obfuscated email format to standard email"""
        if not email_text:
            return ""
        email = email_text.strip()
        email = email.replace(' [dot] ', '.')
        email = email.replace('[dot]', '.')
        email = email.replace(' [at] ', '@')
        email = email.replace('[at]', '@')
        email = email.replace(' ', '')
        return email
    
    def scroll_to_pagination(self):
        """Scroll down to make pagination visible"""
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            try:
                pagination_area = self.driver.find_element(By.XPATH, "//a[contains(text(), '1') or contains(text(), '2') or contains(text(), '›')]/..")
                self.driver.execute_script("arguments[0].scrollIntoView(true);", pagination_area)
                time.sleep(0.5)
            except:
                pass
        except Exception as e:
            print(f"   ⚠ Scroll error: {e}")
    
    def extract_cdo_from_cards(self):
        """Extract CDO data from currently visible cards"""
        cdo_list = []
        page_source = self.driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find all h4 elements that are CDO names
        all_h4 = soup.find_all('h4')
        
        for h4 in all_h4:
            name = h4.get_text(strip=True)
            
            # Skip headers and invalid names
            if not name or len(name) < 5:
                continue
            if any(skip in name.lower() for skip in ['star cdo', 'month', 'ministry', 'department', 'useful', 'chief data officer', 'links']):
                continue
            
            # Skip if already processed
            if name in self.processed_names:
                continue
            
            # Find the parent card container
            parent = h4.find_parent('div')
            card_container = None
            
            # Go up to find a larger container with all the info
            for _ in range(8):
                if parent:
                    card_text = parent.get_text(separator='\n', strip=True)
                    if 'Ministry' in card_text and ('[at]' in card_text or '@' in card_text):
                        card_container = parent
                        break
                    parent = parent.find_parent('div')
            
            if not card_container:
                continue
            
            cdo_info = {
                'name': name,
                'designation': '',
                'nomination_date': '',
                'ministry_department': '',
                'email': '',
                'address': '',
                'document_url': '',
                'document_size': ''
            }
            
            card_text = card_container.get_text(separator='\n', strip=True)
            lines = [l.strip() for l in card_text.split('\n') if l.strip()]
            
            # Find the index of the name
            name_idx = -1
            for i, line in enumerate(lines):
                if name == line:
                    name_idx = i
                    break
            
            if name_idx >= 0:
                # Designation is usually the next line after name
                for j in range(name_idx + 1, min(name_idx + 5, len(lines))):
                    line = lines[j]
                    date_match = re.search(r'\d{2}-\d{2}-\d{4}', line)
                    if date_match:
                        cdo_info['nomination_date'] = date_match.group()
                        break
                    if len(line) < 4 or 'cdo' in line.lower():
                        continue
                    if not cdo_info['designation']:
                        if any(d in line.lower() for d in ['secretary', 'director', 'adviser', 'advisor', 'ddg', 'officer', 'commissioner', 'general', 'manager']):
                            cdo_info['designation'] = line
                        elif not re.search(r'\d{2}-\d{2}-\d{4}', line) and 'ministry' not in line.lower() and 'download' not in line.lower():
                            cdo_info['designation'] = line
            
            # Find date if not found
            if not cdo_info['nomination_date']:
                for line in lines:
                    date_match = re.search(r'\d{2}-\d{2}-\d{4}', line)
                    if date_match:
                        cdo_info['nomination_date'] = date_match.group()
                        break
            
            # Find ministry/department
            for i, line in enumerate(lines):
                if 'ministry / state / department' in line.lower() or 'ministry/state/department' in line.lower():
                    for j in range(i + 1, min(i + 3, len(lines))):
                        if lines[j] and 'email' not in lines[j].lower() and 'address' not in lines[j].lower() and len(lines[j]) > 5:
                            cdo_info['ministry_department'] = lines[j]
                            break
                    break
            
            # Find email
            for line in lines:
                if '[at]' in line.lower():
                    cdo_info['email'] = self.clean_email(line)
                    break
            
            # Find address
            for i, line in enumerate(lines):
                if line.lower().startswith('address') or line.lower() == 'address :' or line.lower() == 'address:':
                    for j in range(i + 1, min(i + 3, len(lines))):
                        if lines[j] and '[at]' not in lines[j].lower() and 'past cdo' not in lines[j].lower() and len(lines[j]) > 5:
                            cdo_info['address'] = lines[j]
                            break
                    break
            
            # Find PDF document
            pdf_links = card_container.find_all('a', href=re.compile(r'\.pdf', re.I))
            for pdf_link in pdf_links:
                href = pdf_link.get('href', '')
                if href:
                    cdo_info['document_url'] = href
                    link_text = pdf_link.get_text(strip=True)
                    size_match = re.search(r'(\d+\s*KB|\d+\s*MB)', link_text)
                    if size_match:
                        cdo_info['document_size'] = size_match.group()
                    break
            
            # Add to list if we have enough info
            if cdo_info['name'] and (cdo_info['email'] or cdo_info['ministry_department']):
                self.processed_names.add(name)
                cdo_list.append(cdo_info)
        
        return cdo_list
    
    def click_pagination_number(self, page_num):
        """Click on a specific page number in pagination"""
        try:
            time.sleep(1)
            selectors = [
                f"//a[text()='{page_num}']",
                f"//a[contains(text(), '{page_num}')]",
                f"//span[text()='{page_num}']",
                f"//button[text()='{page_num}']",
                f"//li/a[text()='{page_num}']",
            ]
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                            time.sleep(0.5)
                            try:
                                elem.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", elem)
                            time.sleep(3)
                            return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"   ⚠ Click error: {e}")
            return False
    
    def click_next_button(self):
        """Click the next (›) button"""
        try:
            selectors = [
                "//a[contains(text(), '›')]",
                "//a[contains(@aria-label, 'Next')]",
                "//a[contains(@class, 'next')]",
                "//button[contains(text(), '›')]",
                "//span[contains(text(), '›')]/..",
            ]
            
            for selector in selectors:
                try:
                    elem = self.driver.find_element(By.XPATH, selector)
                    if elem.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                        time.sleep(0.5)
                        try:
                            elem.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(3)
                        return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"   ⚠ Next button error: {e}")
            return False
    
    def scrape_all_pages(self, max_pages=13):
        """Scrape all CDO data from multiple pages"""
        print(f"\n🚀 Starting to scrape CDO data from {max_pages} pages...")
        print("=" * 60)
        
        # Navigate to the base URL
        self.driver.get(self.base_url)
        time.sleep(5)
        
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "h4"))
            )
        except:
            print("⚠ Timeout waiting for page to load")
        
        for page_num in range(1, max_pages + 1):
            print(f"\n📄 Processing page {page_num}...")
            
            time.sleep(2)
            
            cdo_list = self.extract_cdo_from_cards()
            
            for cdo in cdo_list:
                self.all_cdo_data.append(cdo)
            
            print(f"   ✓ Found {len(cdo_list)} new CDO records (Total: {len(self.all_cdo_data)})")
            
            if page_num < max_pages:
                self.scroll_to_pagination()
                next_page = page_num + 1
                success = self.click_pagination_number(next_page)
                
                if not success:
                    success = self.click_next_button()
                
                if not success:
                    print(f"   Using URL parameter for page {next_page}...")
                    self.driver.get(f"{self.base_url}?page={next_page}")
                    time.sleep(4)
        
        print("\n" + "=" * 60)
        print(f"✅ Scraping complete! Total unique CDO records: {len(self.all_cdo_data)}")
        return self.all_cdo_data
    
    def save_to_csv(self, filename="cdo_data_gov_india.csv"):
        """Save extracted CDO data to CSV file"""
        if not self.all_cdo_data:
            print("⚠ No data to save!")
            return None
        
        fieldnames = [
            'Sr_No',
            'Name',
            'Designation',
            'Nomination_Date',
            'Ministry_Department',
            'Email',
            'Address',
            'Document_URL',
            'Document_Size'
        ]
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for idx, cdo in enumerate(self.all_cdo_data, 1):
                    writer.writerow({
                        'Sr_No': idx,
                        'Name': cdo.get('name', ''),
                        'Designation': cdo.get('designation', ''),
                        'Nomination_Date': cdo.get('nomination_date', ''),
                        'Ministry_Department': cdo.get('ministry_department', ''),
                        'Email': cdo.get('email', ''),
                        'Address': cdo.get('address', ''),
                        'Document_URL': cdo.get('document_url', ''),
                        'Document_Size': cdo.get('document_size', '')
                    })
            
            print(f"\n💾 Data saved to: {filename}")
            print(f"   Total records: {len(self.all_cdo_data)}")
            return filename
            
        except Exception as e:
            print(f"✗ Error saving CSV: {e}")
            return None
    
    def close(self):
        """Close the WebDriver"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            print("\n🔒 WebDriver closed")


def main():
    print("=" * 60)
    print("   CDO Data Scraper for data.gov.in")
    print("   Chief Data Officers Information Extractor")
    print("   Pages: 1 to 13 (Central CDOs)")
    print("=" * 60)
    
    scraper = CDOScraper()
    
    try:
        # Scrape pages 1 to 13
        scraper.scrape_all_pages(max_pages=13)
        
        # Save to CSV
        csv_file = scraper.save_to_csv("cdo_data_gov_india.csv")
        
        if csv_file:
            print(f"\n✅ Scraping completed successfully!")
            print(f"   CSV file: {csv_file}")
            
            # Print sample data
            print("\n📊 Sample data (first 5 records):")
            print("-" * 60)
            for i, cdo in enumerate(scraper.all_cdo_data[:5], 1):
                print(f"\n{i}. {cdo.get('name', 'N/A')}")
                print(f"   Designation: {cdo.get('designation', 'N/A')}")
                ministry = cdo.get('ministry_department', 'N/A')
                print(f"   Ministry: {ministry[:50]}..." if len(ministry) > 50 else f"   Ministry: {ministry}")
                print(f"   Email: {cdo.get('email', 'N/A')}")
        
    except KeyboardInterrupt:
        print("\n\n⚠ Scraping interrupted by user")
    except Exception as e:
        print(f"\n✗ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
