import csv
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time

# Configure logging
logging.basicConfig(filename='scraping.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

site_configs = {
    "trendhunter": {
        "url": "https://www.trendhunter.com/",
        "popup_selector": 'i.lp__formPopPopClose',
        "idea_selector": '.tha__relArticle.thar.thar--five',
        "title1_class": 'thar__title1',
        "title2_class": 'thar__title2',
        "summary": 'thar__summary',
    },
}

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service("C:/Users/carol/OneDrive/Documentos/chromedriver_win32/chromedriver.exe")
    return webdriver.Chrome(service=service, options=chrome_options)

def close_popup(driver, popup_selector):
    try:
        pop_up_close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, popup_selector))
        )
        pop_up_close_button.click()
    except (TimeoutException, NoSuchElementException):
        logging.warning("Popup close button not found or timed out.")

def scroll_and_extract(driver, writer, max_records, idea_selector):
    last_height = driver.execute_script("return document.body.scrollHeight")
    total_records = 0

    while total_records < max_records:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        WebDriverWait(driver, 5).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        
        new_height = driver.execute_script("return document.body.scrollHeight")
        total_records = len(driver.find_elements(By.CSS_SELECTOR, idea_selector))
        
        if new_height == last_height:
            break

        last_height = new_height
        time.sleep(1)

        # Extract ideas after scrolling
        extract_ideas(driver, writer, idea_selector)

def extract_ideas(driver, writer, idea_selector):
    ideas = driver.find_elements(By.CSS_SELECTOR, idea_selector)
    for idea in ideas:
        try:
            title1 = idea.find_element(By.CLASS_NAME, site_configs["trendhunter"]["title1_class"]).text
            title2 = idea.find_element(By.CLASS_NAME, site_configs["trendhunter"]["title2_class"]).text if site_configs["trendhunter"]["title2_class"] else " "
            summary = idea.find_element(By.CLASS_NAME, site_configs["trendhunter"]["summary"]).text if site_configs["trendhunter"]["summary"] else " "
                
            idea_link = idea.get_attribute('href')
            driver.get(idea_link)
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')
            score = driver.find_element(By.CSS_SELECTOR, '.tha__scoreNum').text if driver.find_elements(By.CSS_SELECTOR, '.tha__scoreNum') else " "
            author = driver.find_element(By.CSS_SELECTOR, '.tha__referenceAuthor').text if driver.find_elements(By.CSS_SELECTOR, '.tha__referenceAuthor') else " "
            references = [link.get_attribute('href') for link in driver.find_elements(By.CSS_SELECTOR, '.tha__referenceLink')] or [" "]

            writer.writerow([title1, title2, summary, author, references, score])

        except (NoSuchElementException, StaleElementReferenceException) as e:
            logging.error(f"Error extracting idea: {e}")
            continue  # Skip to the next idea if an error occurs

def open_page(driver, config, writer):
    driver.get(config["url"])
    WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')
    close_popup(driver, config["popup_selector"])
    scroll_and_extract(driver, writer, max_records=10000, idea_selector=config["idea_selector"])

def main(site):
    driver = setup_driver()
    file_path = f'{site}_ideas.csv'
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Title 1', 'Title 2', 'Summary', 'Author', 'References', 'Score'])
        config = site_configs[site]
        open_page(driver, config, writer)
    driver.quit()

if __name__ == "__main__":
    main("trendhunter")
