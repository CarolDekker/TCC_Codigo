import csv
import logging
import time
import random
import psutil
from queue import Queue
from threading import Thread
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (TimeoutException, 
                                      NoSuchElementException, 
                                      WebDriverException,
                                      StaleElementReferenceException)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("trendhunter_ideas_scraper.log"),
        logging.StreamHandler()
    ]
)

SITE_CONFIG = {
    "popup_close_selector": ".lp__formPopClose",
    "idea_items_selector": "a.tha__relArticle",
    "idea_title_selector": ".thar__title1",
    "idea_description_selector": ".tha__articleText",
    "idea_score_selector": ".tha__scoreNum",
    "idea_references_selector": ".tha__references",
    "idea_category_selector": ".tha__bcLink--category",
    "no_content_selector": ".tha__noResults",
    "base_url": "https://www.trendhunter.com"
}

def kill_chrome_processes():
    """Kill any existing Chrome processes"""
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] in ('chrome.exe', 'chromedriver.exe'):
            try:
                proc.kill()
            except:
                pass

def setup_driver():
    """Initialize a new Chrome WebDriver instance with crash protection"""
    kill_chrome_processes()
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    
    service = Service(executable_path="chromedriver-win64/chromedriver.exe")
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(45)
        return driver
    except WebDriverException as e:
        logging.error(f"Failed to initialize WebDriver: {e}")
        return None

def close_popup(driver):
    try:
        popup = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SITE_CONFIG["popup_close_selector"])))
        popup.click()
        time.sleep(random.uniform(0.5, 1.5))
    except TimeoutException:
        pass

def load_list_urls():
    urls = []
    try:
        with open("trends_list.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("url"):
                    urls.append(row["url"])
        logging.info(f"Loaded {len(urls)} list URLs from CSV")
        return urls
    except Exception as e:
        logging.error(f"Error loading list URLs: {e}")
        return []

def scrape_ideas_from_list(driver, list_url):
    ideas = []
    try:
        logging.info(f"Processing list: {list_url}")
        
        # Navigate with retry
        for attempt in range(3):
            try:
                driver.get(list_url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body")))
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(2)
        
        time.sleep(random.uniform(2, 4))
        close_popup(driver)
        
        # Check for empty list
        try:
            no_content = driver.find_elements(By.CSS_SELECTOR, SITE_CONFIG["no_content_selector"])
            if no_content:
                logging.info(f"No ideas found in list: {list_url}")
                return ideas
        except:
            pass
        
        # Scroll to load content (3 attempts)
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        # Find ideas with retry
        idea_elements = []
        for attempt in range(3):
            try:
                idea_elements = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, SITE_CONFIG["idea_items_selector"])))
                break
            except:
                if attempt == 2:
                    return ideas
                time.sleep(2)
        
        # Process ideas
        for idx in range(len(idea_elements)):
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, SITE_CONFIG["idea_items_selector"])
                if idx >= len(elements):
                    continue
                
                element = elements[idx]
                idea_data = {
                    "title": element.find_element(By.CSS_SELECTOR, SITE_CONFIG["idea_title_selector"]).text.strip(),
                    "description": element.find_element(By.CSS_SELECTOR, SITE_CONFIG["idea_description_selector"]).text.strip(),
                    "score": element.find_element(By.CSS_SELECTOR, SITE_CONFIG["idea_score_selector"]).text.strip(),
                    "references": element.find_element(By.CSS_SELECTOR, SITE_CONFIG["idea_references_selector"]).text.strip(),
                    "category": element.find_element(By.CSS_SELECTOR, SITE_CONFIG["idea_category_selector"]).text.strip(),
                    "url": element.get_attribute("href"),
                    "source_list": list_url
                }
                ideas.append(idea_data)
            except Exception as e:
                logging.warning(f"Error processing idea {idx} from {list_url}: {str(e)[:200]}")
                continue
        
        logging.info(f"Found {len(ideas)} ideas in list: {list_url}")
        return ideas
        
    except Exception as e:
        logging.error(f"Error scraping list {list_url}: {str(e)[:200]}")
        return []

def worker(driver_queue, result_queue):
    """Worker thread with crash recovery"""
    while True:
        driver = setup_driver()
        if not driver:
            time.sleep(5)
            continue
            
        processed = 0
        try:
            while True:
                list_url = driver_queue.get()
                if list_url is None:
                    driver_queue.task_done()
                    driver.quit()
                    return
                
                try:
                    ideas = scrape_ideas_from_list(driver, list_url)
                    result_queue.put((list_url, ideas))
                    processed += 1
                    
                    # Refresh driver periodically
                    if processed % 5 == 0:
                        driver.quit()
                        driver = setup_driver()
                        if not driver:
                            break
                            
                except Exception as e:
                    logging.error(f"Worker error processing {list_url}: {str(e)[:200]}")
                    result_queue.put((list_url, []))
                finally:
                    driver_queue.task_done()
                    
        except Exception as e:
            logging.error(f"Worker fatal error: {str(e)[:200]}")
        finally:
            driver.quit()

def save_ideas_to_csv(ideas):
    if not ideas:
        logging.error("No ideas to save")
        return
    
    fieldnames = ["title", "description", "score", "references", "category", "url", "source_list"]
    try:
        with open("trends_ideas.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ideas)
        logging.info(f"Saved {len(ideas)} ideas to trends_ideas.csv")
    except Exception as e:
        logging.error(f"Error saving CSV: {e}")

def main():
    list_urls = load_list_urls()
    if not list_urls:
        logging.error("No list URLs to process")
        return
    
    driver_queue = Queue()
    result_queue = Queue()
    
    # Conservative number of workers
    num_workers = min(3, len(list_urls))
    threads = []
    for i in range(num_workers):
        t = Thread(target=worker, args=(driver_queue, result_queue))
        t.start()
        threads.append(t)
    
    # Add URLs to queue
    for url in list_urls:
        driver_queue.put(url)
    
    # Wait for completion
    driver_queue.join()
    
    # Stop workers
    for _ in range(num_workers):
        driver_queue.put(None)
    for t in threads:
        t.join()
    
    # Collect results
    all_ideas = []
    stats = {"total": 0, "with_ideas": 0, "total_ideas": 0}
    
    while not result_queue.empty():
        url, ideas = result_queue.get()
        stats["total"] += 1
        if ideas:
            stats["with_ideas"] += 1
            stats["total_ideas"] += len(ideas)
            all_ideas.extend(ideas)
    
    # Print report
    logging.info("\n=== Scraping Report ===")
    logging.info(f"Total lists processed: {stats['total']}")
    logging.info(f"Lists with ideas: {stats['with_ideas']}")
    logging.info(f"Empty lists: {stats['total'] - stats['with_ideas']}")
    logging.info(f"Total ideas collected: {stats['total_ideas']}")
    
    save_ideas_to_csv(all_ideas)

if __name__ == "__main__":
    logging.info("Starting TrendHunter scraper")
    start_time = time.time()
    main()
    logging.info(f"Scraping completed in {time.time()-start_time:.2f} seconds")