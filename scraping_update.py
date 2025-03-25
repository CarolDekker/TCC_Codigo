from scraping import (
    setup_driver,
    close_popup,
)
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

df = pd.read_excel('tcc_excel.xlsx')
links = df["link"]
driver = setup_driver()

# Create lists to store the data
references_list = []
categories_list = []

for link in links:
    driver.get(link)
    try:
        references = driver.find_element(By.CSS_SELECTOR, ".tha__references").text
    except NoSuchElementException:
        references = " "
    try:
        category = driver.find_element(By.CSS_SELECTOR, ".tha__bcLink.tha__bcLink--category").text
    except NoSuchElementException:
        category = " "
    
    references_list.append(references)
    categories_list.append(category)
    print(f"Processed: {link}")

# Add the scraped data back to the DataFrame
df["references"] = references_list
df["category"] = categories_list

# Save the updated DataFrame
df.to_excel('tcc_excel_updated.xlsx', index=False)

driver.quit()