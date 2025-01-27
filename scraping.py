import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

# Configurações específicas para cada site
site_configs = {
    "trendhunter": {
        "url": "https://www.trendhunter.com/",
        "popup_selector": 'i.lp__formPopClose',
        "idea_selector": '.tha__relArticle.thar.thar--five',
        "title1_class": 'thar__title1',
        "title2_class": 'thar__title2',
        "summary_class": 'thar__summary'
    },
}

def setup_driver():
    """Configura o WebDriver do Chrome."""
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")  # Desativa a GPU
    chrome_options.add_argument("--headless")  # Executa em modo headless
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")  # Desativa o carregamento de imagens
    service = Service("C:/Users/carol/OneDrive/Documentos/chromedriver_win32/chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def close_popup(driver, popup_selector):
    """Fecha o pop-up se estiver presente."""
    try:
        pop_up_close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, popup_selector))
        )
        pop_up_close_button.click()
        print("Pop-up fechado.")
    except TimeoutException:
        print("Pop-up não encontrado ou não está clicável.")

def scroll(driver, max_records):
    """Rola para baixo na página até que o número especificado de registros seja atingido ou não haja mais conteúdo."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    total_records = 0

    while total_records < max_records:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Aumente o tempo se necessário para garantir que o conteúdo carregue

        new_height = driver.execute_script("return document.body.scrollHeight")
        total_records = len(driver.find_elements(By.CSS_SELECTOR, '.tha__relArticle.thar.thar--five'))

        if new_height == last_height:
            print("Não há mais conteúdo para carregar.")
            break

        last_height = new_height
        
    print(f"Rolagem concluída. Total de registros carregados: {total_records}")

def extract_ideas(driver, writer, idea_selector, title1_class, title2_class, summary_class):
    """Extrai as ideias da página e salva no arquivo CSV."""
    ideas = driver.find_elements(By.CSS_SELECTOR, idea_selector)
    for idea in ideas:
        try:
            title1 = idea.find_element(By.CLASS_NAME, title1_class).text.strip()
            title2 = idea.find_element(By.CLASS_NAME, title2_class).text.strip()
            summary = idea.find_element(By.CLASS_NAME, summary_class).text.strip()
            writer.writerow([title1, title2, summary])
        except NoSuchElementException:
            print("Um dos elementos não foi encontrado para esta ideia.")

def open_page(driver, config, writer):
    """Abre a página, fecha o pop-up, rola para carregar mais conteúdo e extrai ideias."""
    driver.get(config["url"])
    WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
    close_popup(driver, config["popup_selector"])
    scroll(driver, max_records=100000)  # Define o limite de registros
    extract_ideas(driver, writer, config["idea_selector"], config["title1_class"], config["title2_class"], config["summary_class"])

def main(site):
    """Função principal para executar o processo de scraping."""
    driver = setup_driver()
    file_path = f'{site}_ideas.csv'
    writer = None
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Title 1', 'Title 2', 'Summary'])
            config = site_configs[site]
            open_page(driver, config, writer)
    except KeyError:
        print(f"Configurações para o site '{site}' não encontradas.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
        if writer:
            print(f"Salvando o arquivo CSV em caso de erro: {file_path}")
    finally:
        driver.quit()

# Chamada da função main após sua definição
if __name__ == "__main__":
    main("trendhunter")  # Você pode mudar para outro site conforme necessário