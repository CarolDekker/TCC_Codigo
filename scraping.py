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
    "producthunt": {
        "url": "https://www.producthunt.com/leaderboard/yearly/2024/all",
        "idea_selector": 'section[data-test^="post-item-"]',  # Seletor para cada item de produto
        "title1_class": 'text-16 font-semibold text-dark-gray',  # Classe para o título do produto
        "title2_class": 'text-16 font-normal text-dark-gray text-secondary',  # Classe para a descrição do produto
        "summary_class": ''  # Não há um resumo separado, a descrição é o que se pode usar
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
        pop_up_close_button = WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, popup_selector))
        )
        pop_up_close_button.click()
    except TimeoutException:
        pass  # Ignora a exceção se o pop-up não for encontrado

def scroll(driver, max_records, idea_selector):
    """Rola para baixo na página até que o número especificado de registros seja atingido ou não haja mais conteúdo."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    total_records = 0

    while total_records < max_records:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)  # Aumente o tempo se necessário para garantir que o conteúdo carregue

        new_height = driver.execute_script("return document.body.scrollHeight")
        total_records = len(driver.find_elements(By.CSS_SELECTOR, idea_selector))

        if new_height == last_height:
            break  # Não há mais conteúdo para carregar

        last_height = new_height
        
    return total_records  # Retorna o total de registros carregados

def extract_ideas(driver, writer, idea_selector, title1_class, title2_class, summary_class):
    """Extrai as ideias da página e salva no arquivo CSV."""
    ideas = driver.find_elements(By.CSS_SELECTOR, idea_selector)
    for idea in ideas:
        try:
            title1 = idea.find_element(By.CLASS_NAME, title1_class).text.strip()
            title2 = idea.find_element(By.CLASS_NAME, title2_class).text.strip()
            summary = ''
            if summary_class:  # Verifica se a classe do resumo está definida
                summary = idea.find_element(By.CLASS_NAME, summary_class).text.strip()
            writer.writerow([title1, title2, summary])
        except NoSuchElementException:
            continue  # Ignora a exceção se um dos elementos não for encontrado

def open_page(driver, config, writer):
    """Abre a página, fecha o pop-up, rola para carregar mais conteúdo e extrai ideias."""
    driver.get(config["url"])
    WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
    if "popup_selector" in config:
        close_popup(driver, config["popup_selector"])
    total_records = scroll(driver, max_records=100000, idea_selector=config["idea_selector"])  # Define o limite de registros
    extract_ideas(driver, writer, config["idea_selector"], config["title1_class"], config["title2_class"], config["summary_class"])
    return total_records  # Retorna o total de registros extraídos

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
        pass  # Ignora a exceção se as configurações para o site não forem encontradas
    except Exception as e:
        # Você pode optar por registrar a exceção em um arquivo de log, se desejar
        pass
    finally:
        driver.quit()  # Garante que o driver seja fechado
        if writer:
            file.close()  # Garante que o arquivo CSV seja fechado

# Chamada da função main após sua definição
if __name__ == "__main__":
    main("producthunt")  # Você pode mudar para "trendhunter" conforme necessário