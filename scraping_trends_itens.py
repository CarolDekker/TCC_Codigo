import csv
import time
import random
import psutil
from queue import Queue
from threading import Thread, Lock
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

chrome_lock = Lock()

def setup_driver():
    """Configure Chrome WebDriver with enhanced stability options"""
    kill_chrome_processes()
    
    chrome_options = Options()
    
    # Essential stability options
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Memory and handle management
    chrome_options.add_argument("--disable-features=RendererCodeIntegrity")
    chrome_options.add_argument("--disable-features=All")
    chrome_options.add_argument("--disable-breakpad")
    chrome_options.add_argument("--disable-crash-reporter")
    chrome_options.add_argument("--disable-background-timer-throttling")
    
    # GPU and rendering options
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-webgl")
    chrome_options.add_argument("--disable-accelerated-2d-canvas")
    
    # Process management (helps with GetHandleVerifier)
    chrome_options.add_argument("--disable-process-internal-limit")
    chrome_options.add_argument("--disable-hang-monitor")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--log-level=3")  # Only fatal errors
    
    # Experimental options for handle management
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    chrome_options.add_experimental_option("detach", False)
    
    service = Service(
        executable_path="chromedriver-win64/chromedriver.exe",
        service_args=["--log-level=WARNING"]  # Reduce verbosity
    )
    
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(45)
        driver.set_script_timeout(30)
        return driver
    except Exception as e:
        print(f"Failed to initialize WebDriver: {str(e)}")
        kill_chrome_processes()
        raise

def kill_chrome_processes():
    """More aggressive process cleanup"""
    with chrome_lock:
        for proc in psutil.process_iter(['name', 'pid', 'cmdline']):
            try:
                # Target both Chrome and Chromedriver processes
                if proc.info['name'].lower() in ('chrome.exe', 'chromedriver.exe'):
                    # Skip if it's our current process
                    if any('--test-type=webdriver' in arg for arg in proc.info.get('cmdline', [])):
                        continue
                    
                    # Kill entire process tree
                    parent = psutil.Process(proc.info['pid'])
                    children = parent.children(recursive=True)
                    for child in children:
                        try:
                            child.kill()
                        except:
                            pass
                    parent.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(1)  # Give OS time to clean up

def load_list_urls():
    """Load URLs from CSV file"""
    urls = []
    try:
        with open("trends_list.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("url"):
                    urls.append(row["url"].strip())
    except FileNotFoundError:
        print("Error: trends_list.csv not found")
    return urls

def scrape_ideas_from_list(driver, list_url):
    """Scrape article data from a single list page with robust error handling"""
    ideas = []
    print(f"Processing: {list_url}")
    
    try:
        # Load page with retry logic
        for attempt in range(3):
            try:
                driver.get(list_url)
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
                break
            except Exception as e:
                if attempt == 2:
                    print(f"Failed to load {list_url}: {str(e)}")
                    return ideas
                time.sleep(random.uniform(2, 4))
        
        # Scroll to load content
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Find all idea elements - wait for at least one to be present
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.tha__relArticle")))
        except:
            print(f"No articles found on {list_url}")
            return ideas
        
        idea_elements = driver.find_elements(By.CSS_SELECTOR, "a.tha__relArticle")
        
        for element in idea_elements:
            idea_data = {
                "title": "",
                "description": "",
                "score": "",
                "references": "",
                "category": "",
                "url": "",
                "source_list": list_url
            }
            
            try:
                idea_data["title"] = element.find_element(
                    By.CSS_SELECTOR, ".thar__title1").text.strip()
            except:
                pass
            
            try:
                idea_data["description"] = element.find_element(
                    By.CSS_SELECTOR, ".tha__articleText").text.strip()
            except:
                # Try alternative selectors if primary fails
                try:
                    idea_data["description"] = element.find_element(
                        By.CSS_SELECTOR, ".article-text, .articleBody, .content").text.strip()
                except:
                    pass
            
            try:
                idea_data["score"] = element.find_element(
                    By.CSS_SELECTOR, ".tha__scoreNum").text.strip()
            except:
                pass
            
            try:
                idea_data["references"] = element.find_element(
                    By.CSS_SELECTOR, ".tha__references").text.strip()
            except:
                pass
            
            try:
                idea_data["category"] = element.find_element(
                    By.CSS_SELECTOR, ".tha__bcLink--category").text.strip()
            except:
                pass
            
            try:
                idea_data["url"] = element.get_attribute("href").strip()
            except:
                pass
            
            # Only add if we got at least some data
            if idea_data["title"] or idea_data["description"]:
                ideas.append(idea_data)
                
    except Exception as e:
        print(f"Error processing {list_url}: {str(e)}")
    
    return ideas

def worker(driver_queue, result_queue):
    """Worker thread function to process URLs"""
    driver = None
    try:
        driver = setup_driver()
        processed = 0
        
        while True:
            list_url = driver_queue.get()
            if list_url is None:  # Sentinel value to stop worker
                driver_queue.task_done()
                break
                
            ideas = scrape_ideas_from_list(driver, list_url)
            result_queue.put(ideas)
            processed += 1
            
            # Refresh driver periodically to prevent memory leaks
            if processed % 5 == 0:
                driver.quit()
                driver = setup_driver()
                
            driver_queue.task_done()
            
    except Exception as e:
        print(f"Worker error: {str(e)}")
    finally:
        if driver:
            driver.quit()

def save_ideas_to_csv(ideas):
    """Save scraped data to CSV file"""
    if not ideas:
        print("No ideas to save")
        return
    
    try:
        with open("trends_ideas.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "title", "description", "score", "references", 
                "category", "url", "source_list"
            ])
            writer.writeheader()
            writer.writerows(ideas)
        print(f"Successfully saved {len(ideas)} ideas to trends_ideas.csv")
    except Exception as e:
        print(f"Failed to save CSV: {str(e)}")

def main():
    """Main execution function"""
    list_urls = load_list_urls()
    if not list_urls:
        print("No URLs to process")
        return
    
    print(f"Found {len(list_urls)} URLs to process")
    
    driver_queue = Queue()
    result_queue = Queue()
    
    # Determine number of workers (capped at 3 for resource management)
    num_workers = min(3, len(list_urls))
    threads = []
    
    print(f"Starting {num_workers} worker threads")
    for _ in range(num_workers):
        t = Thread(target=worker, args=(driver_queue, result_queue))
        t.start()
        threads.append(t)
    
    # Add URLs to queue
    for url in list_urls:
        driver_queue.put(url)
    
    # Wait for queue to empty
    driver_queue.join()
    
    # Signal workers to exit
    for _ in range(num_workers):
        driver_queue.put(None)
    
    # Wait for threads to finish
    for t in threads:
        t.join()
    
    # Collect results
    all_ideas = []
    while not result_queue.empty():
        all_ideas.extend(result_queue.get())
    
    # Save results
    save_ideas_to_csv(all_ideas)
    
    print("Scraping completed")

if __name__ == "__main__":
    start_time = time.time()
    main()
    print(f"Execution time: {time.time() - start_time:.2f} seconds")