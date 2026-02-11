import csv
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import selenium_stealth

# Config
CSV_FILE = 'epstein_no_images_pdf_urls.csv'

# Load existing URLs for deduplication/resume
all_urls = set()
if os.path.exists(CSV_FILE):
    try:
        with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for row in reader:
                if row and row[0].strip():
                    all_urls.add(row[0].strip())
        print(f"Loaded {len(all_urls)} existing URLs – duplicates will be skipped")
    except Exception as e:
        print(f"CSV load error: {e}")

# Browser setup – visible (required for manual steps)
options = Options()
# options.add_argument("--headless=new")  # Do NOT enable – need visible for manual
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

selenium_stealth.stealth(driver,
    languages=["en-US", "en"],
    vendor="Google Inc.",
    platform="MacIntel",
    webgl_vendor="Intel Inc.",
    renderer="Intel Iris OpenGL Engine",
    fix_hairline=True,
)

# Open the search page
driver.get("https://www.justice.gov/epstein/search")
print("Browser opened to search page.")

# MANUAL PAUSE
print("\n=== MANUAL STEP ===")
print("1. Solve any anti-bot, age gate, captcha, or Queue-IT challenge.")
print("2. Enter 'no images produced' in the search box and submit.")
print("3. Wait for results to load (PDF links visible).")
print("4. When ready, come back here and press Enter to start scraping.")
input("Press Enter to begin scraping...")

# Confirm results are loaded
try:
    WebDriverWait(driver, 30).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a[href$=".pdf"]'))
    )
    print("PDF results detected – starting scrape")
except:
    print("No PDF links found – check browser manually")
    driver.save_screenshot("manual_error.png")
    driver.quit()
    raise SystemExit

# Save function (atomic, fast)
def save_progress():
    temp_file = CSV_FILE + '.tmp'
    with open(temp_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["URL"])
        for url in all_urls:
            writer.writerow([url])
    os.replace(temp_file, CSV_FILE)
    print(f"   → Saved progress: {len(all_urls)} URLs")

# Current page detection
def get_current_page():
    try:
        current = driver.find_element(By.CSS_SELECTOR, 'a[aria-current="page"]')
        aria = current.get_attribute("aria-label")
        return int(aria.split()[-1])
    except:
        return 1

page_counter = get_current_page()
while True:
    before = len(all_urls)
    pdf_links = driver.find_elements(By.CSS_SELECTOR, 'a[href$=".pdf"]')
    new_added = 0
    for link in pdf_links:
        url = link.get_attribute('href')
        if url and url not in all_urls:
            all_urls.add(url)
            new_added += 1
    
    print(f"Page {page_counter}: {len(pdf_links)} links → {new_added} new → Total: {len(all_urls)}")
    save_progress()
    
    # Click Next (multiple selectors)
    next_clicked = False
    next_selectors = [
        '//a[@rel="next"]',
        '//a[contains(@aria-label, "Next")]',
        '//a[text()="Next" or text()=">"]',
        '//button[contains(text(), "Next")]'
    ]
    for sel in next_selectors:
        try:
            next_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, sel)))
            driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            driver.execute_script("arguments[0].click();", next_btn)
            next_clicked = True
            break
        except:
            continue
    
    if not next_clicked:
        print("No Next button – end of results reached")
        break
    
    print("Clicked Next")
    
    # Wait for page number change (ensures real navigation)
    old_page = page_counter
    try:
        WebDriverWait(driver, 15).until(
            lambda d: get_current_page() > old_page
        )
        page_counter = get_current_page()
        print(f"Advanced to page {page_counter}")
    except:
        print("Page didn't advance – possible block. Screenshot saved.")
        driver.save_screenshot(f"stuck_{old_page}.png")
        break
    
    time.sleep(2)  # Minimal buffer – increase to 3 if timeouts

# Final sorted save
print("Finalizing sorted CSV...")
sorted_urls = sorted(all_urls)
with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["URL"])
    for url in sorted_urls:
        writer.writerow([url])

print(f"DONE! {len(all_urls)} unique URLs saved (~{len(all_urls)//10} pages)")
driver.quit()