import csv
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Site configuration
SITE_CONFIG = {
    "trendhunter": {
        "url": "https://www.trendhunter.com/",
        "popup_selector": ".lp__formPopClose",
        "idea_selector": "a.tha__relArticle",
        "title_selector": ".tha__title1",
        "summary_selector": ".tha__articleText",
        "score_selector": ".tha__scoreNum",
        "author_selector": ".tha__referenceAuthor",
    }
}


def setup_driver():
    """Initialize and return a Chrome WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
    chrome_options.add_argument("--ignore-certificate-errors")  # Ignore SSL errors
    chrome_options.add_argument("--log-level=3")  # Disable DevTools logging


    service = Service("chromedriver-win64/chromedriver.exe")  # Update path to your chromedriver

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except WebDriverException as e:
        logging.error(f"Failed to initialize WebDriver: {e}")
        raise


def close_popup(driver, popup_selector):
    """Close a popup if it appears."""
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, popup_selector))
        ).click()
        logging.info("Popup closed.")
    except TimeoutException:
        logging.info("No popup found or popup close button not clickable.")


def scroll(driver, ideas, config):
    """Scroll the page to load more ideas."""
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    logging.info("Scrolled to load more ideas.")

    # Wait for new ideas to load
    time.sleep(30)  # Adjust the sleep time as needed
    new_ideas = driver.find_elements(By.CSS_SELECTOR, config["idea_selector"])

    if len(new_ideas) == len(ideas):
        logging.info("No more ideas loaded.")
        return ideas  # Return the same list if no new ideas are loaded
    return new_ideas  # Return the updated list of ideas


def extract_idea_details(driver, config, link):
    """Extract details from the current idea page."""
    try:
        title = driver.find_element(By.CSS_SELECTOR, config["title_selector"]).text
    except NoSuchElementException:
        title = " "
        logging.warning(f"Title not found for link: {link}")

    try:
        summary = driver.find_element(By.CSS_SELECTOR, config["summary_selector"]).text
    except NoSuchElementException:
        summary = " "
        logging.warning(f"Summary not found for link: {link}")

    try:
        score = driver.find_element(By.CSS_SELECTOR, config["score_selector"]).text
    except NoSuchElementException:
        score = " "
        logging.warning(f"Score not found for link: {link}")

    try:
        author = driver.find_element(By.CSS_SELECTOR, config["author_selector"]).text
    except NoSuchElementException:
        author = " "
        logging.warning(f"Author not found for link: {link}")

    return [title, summary, score, author, link]


def scrape_idea(driver, config, link):
    """Scrape details from a single idea page."""
    try:
        driver.get(link)
        close_popup(driver, config["popup_selector"])
        details = extract_idea_details(driver, config, link)
        return details
    except Exception as e:
        logging.error(f"Error scraping {link}: {e}")
        return None
    finally:
        driver.quit()  # Ensure the browser is closed after scraping
        
def scrape_idea_with_retry(driver, config, link, retries=3):
    for attempt in range(retries):
        try:
            return scrape_idea(driver, config, link)
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed for {link}: {e}")
            time.sleep(5)  # Wait before retrying
    return None

def scrape_site(config, max_records, num_threads=4):
    """Scrape the site for ideas using multiple threads."""
    driver = setup_driver()
    driver.get(config["url"])
    close_popup(driver, config["popup_selector"])

    records_collected = 0
    accessed_links = set()
    scroll_attempts = 0
    max_scroll_attempts = 5  # Maximum number of scroll attempts

    while records_collected < max_records and scroll_attempts < max_scroll_attempts:
        try:
            # Wait for ideas to load
            ideas = WebDriverWait(driver, 120).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, config["idea_selector"]))
            )

            # Collect links to scrape
            links_to_scrape = []
            for idea in ideas:
                link = idea.get_attribute("href")
                if link.startswith("https://www.trendhunter.com/trends/"):
                    if link not in accessed_links:
                        accessed_links.add(link)
                        links_to_scrape.append(link)
                else: 
                    continue

            # Use ThreadPoolExecutor to scrape links concurrently
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = []
                for link in links_to_scrape:
                    futures.append(executor.submit(scrape_idea_with_retry, setup_driver(), config, link))

                for future in as_completed(futures):
                    details = future.result()
                    if details:
                        yield details
                        records_collected += 1
                        logging.info(f"Record {records_collected} collected.")
                        if records_collected >= max_records:
                            break

            # Scroll to load more ideas
            new_ideas = scroll(driver, ideas, config)
            if len(new_ideas) == len(ideas):
                scroll_attempts += 1
                logging.info(f"No new ideas loaded. Attempt {scroll_attempts}/{max_scroll_attempts}.")
            else:
                ideas = new_ideas  # Update the list of ideas
                scroll_attempts = 0  # Reset scroll attempts

        except TimeoutException:
            logging.warning("Timed out waiting for ideas to load.")
            break
        except StaleElementReferenceException:
            logging.warning("Stale element encountered. Re-locating elements...")
            ideas = driver.find_elements(By.CSS_SELECTOR, config["idea_selector"])  # Re-locate ideas
            continue
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            break

    driver.quit()

def main(site, max_records, num_threads=4):
    """Main function to orchestrate the scraping process."""
    config = SITE_CONFIG.get(site)
    if not config:
        logging.error(f"Configuration for site '{site}' not found.")
        return

    file_path = f"{site}_ideas.csv"

    try:
        with open(file_path, mode="w", newline="", encoding="utf-8-sig", errors="ignore") as file:
            writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(["Title", "Summary", "Score", "Author", "Link"])  # Write header

            for record in scrape_site(config, max_records, num_threads):
                writer.writerow(record)

        logging.info(f"Scraping completed. {max_records} records saved to {file_path}.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")


if __name__ == "__main__":
    try:
        main("trendhunter", max_records=10000, num_threads=4)  # Set max_records and num_threads as needed
    except Exception as e:
        logging.error(f"Script failed: {e}")
        exit(1)