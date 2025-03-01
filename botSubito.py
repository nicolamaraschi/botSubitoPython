import requests
from bs4 import BeautifulSoup
import time
import json
import logging
import os
import schedule
import re
from urllib.parse import quote_plus

# Configurazione del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("price_monitor.log"),
        logging.StreamHandler()
    ]
)

# Configurazione
CONFIG_FILE = "config.json"

# Configurazione predefinita
DEFAULT_CONFIG = {
    "searches": [],
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class PriceMonitor:
    def __init__(self):
        self.config = self._load_config()
        
    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            logging.info(f"Creato file di configurazione {CONFIG_FILE} con impostazioni predefinite")
            return DEFAULT_CONFIG
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Errore nel caricamento del file di configurazione: {e}")
            return DEFAULT_CONFIG
    
    def _get_page_content(self, url):
        headers = {
            "User-Agent": self.config["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3",
            "Referer": "https://www.subito.it/",
            "Connection": "keep-alive"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Errore durante il recupero della pagina: {e}")
            return None
    
    def _parse_products(self, html_content, product_name):
        products = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Salva la struttura HTML per ispezione in caso di debug
        with open("subito_debug.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        logging.info("HTML salvato in 'subito_debug.html' per ispezione")
        
        # Selettori aggiornati basati sull'HTML fornito
        # Cerchiamo le SmallCard che sono i container dei prodotti
        selectors = [
            'div.SmallCard-module_picture-group__asLo2',  # Contenitore intero della card
            'div.SmallCard-module_item-key-data__fcbjY',  # Contenitore dei dati principali
            'a.SmallCard-module_link__hOkzY',             # Link dell'annuncio
            'a.ItemCard-module_card__Gy7SX',              # Possibile alternativa
            'div[class*="SmallCard-module"]',             # Qualsiasi div con classe che contiene SmallCard-module
            'div[class*="ItemCard-module"]'               # Qualsiasi div con classe che contiene ItemCard-module
        ]
        
        # Proviamo a trovare tutti i container di annunci
        all_items = []
        for selector in selectors:
            items = soup.select(selector)
            if items:
                logging.info(f"Trovati {len(items)} elementi con selettore: {selector}")
                all_items.extend(items)
                # Continuiamo a cercare con altri selettori per trovare più prodotti possibili
        
        # Rimuovi duplicati preservando l'ordine
        seen = set()
        unique_items = []
        for item in all_items:
            item_str = str(item)
            if item_str not in seen:
                seen.add(item_str)
                unique_items.append(item)
        
        logging.info(f"Trovati {len(unique_items)} elementi unici per analisi")
        
        # Se non abbiamo trovato elementi con i selettori specifici, cerchiamo tutte le card possibili
        if not unique_items:
            logging.warning("Nessun elemento trovato con i selettori noti. Tentativo con metodo alternativo...")
            
            # Cerchiamo tutti i possibili container di card in base al modello fornito
            potential_items = soup.find_all(['div', 'a'], class_=re.compile(r'(SmallCard|ItemCard|Card)'))
            
            for item in potential_items:
                item_str = str(item)
                if item_str not in seen:
                    seen.add(item_str)
                    unique_items.append(item)
            
            logging.info(f"Trovati {len(unique_items)} elementi con metodo alternativo")
        
        # Prepara il termine di ricerca per verificare la pertinenza
        search_terms = product_name.lower().split()
        
        # Analizza ogni elemento trovato
        for item in unique_items:
            try:
                # Controlla se l'elemento o uno dei suoi genitori contiene l'indicatore "Venduto"
                # 1. Cerca span con classe "item-sold-badge" e testo "Venduto"
                sold_badge = item.find('span', class_=re.compile(r'item-sold-badge'))
                if sold_badge and 'Venduto' in sold_badge.get_text():
                    logging.debug("Prodotto ignorato perché contiene badge 'Venduto'")
                    continue
                
                # 2. Cerca l'articolo notice con testo che indica che l'oggetto è stato venduto
                sold_notice = item.find('article', class_=re.compile(r'notice-module_notice'))
                if sold_notice and 'concluso la trattativa' in sold_notice.get_text():
                    logging.debug("Prodotto ignorato perché contiene avviso di vendita conclusa")
                    continue
                
                # 3. Cerca qualsiasi elemento con la classe che contiene "no-item-available"
                no_item_element = item.find(class_=re.compile(r'no-item-available'))
                if no_item_element:
                    logging.debug("Prodotto ignorato perché contiene classe 'no-item-available'")
                    continue
                
                # 4. Cerca nel testo generale del prodotto
                item_text = item.get_text().lower()
                if 'venduto' in item_text and ('concluso' in item_text or 'trattativa' in item_text):
                    logging.debug("Prodotto ignorato perché contiene testo che indica vendita conclusa")
                    continue
                
                # Cerchiamo il titolo usando il selettore esatto
                title_element = item.find('h2', class_=re.compile(r'ItemTitle-module_item-title__'))
                
                # Se non troviamo il titolo con il selettore specifico, proviamo selettori alternativi
                if not title_element:
                    title_element = item.find(['h2', 'h3', 'h4'], class_=re.compile(r'(title|item-title)'))
                
                # Se ancora non troviamo, cerchiamo all'interno dell'elemento o nei suoi genitori
                if not title_element:
                    # Cerca in questo elemento e nei suoi genitori
                    parent = item
                    for _ in range(3):  # Limita la ricerca a 3 livelli di genitori
                        if parent:
                            title_element = parent.find(['h2', 'h3', 'h4'])
                            if title_element:
                                break
                            parent = parent.parent
                
                # Se non troviamo ancora un titolo, passiamo all'elemento successivo
                if not title_element:
                    continue
                
                title = title_element.get_text().strip()
                
                # Verifica se il testo del titolo contiene indicazioni che l'oggetto è venduto
                if 'venduto' in title.lower():
                    logging.debug(f"Prodotto ignorato perché il titolo contiene 'venduto': {title}")
                    continue
                
                # Verifica la pertinenza del prodotto rispetto alla ricerca
                title_lower = title.lower()
                is_relevant = any(term in title_lower for term in search_terms)
                
                if not is_relevant and len(search_terms) > 1:
                    # Se non troviamo corrispondenze esatte, controlliamo se almeno il 50% dei termini è presente
                    matches = sum(1 for term in search_terms if term in title_lower)
                    is_relevant = matches / len(search_terms) >= 0.5
                
                if not is_relevant:
                    logging.debug(f"Prodotto ignorato (non pertinente): {title}")
                    continue
                
                # Estrai il prezzo usando il selettore esatto
                price_element = item.find('p', class_=re.compile(r'index-module_price__N7M2x'))
                
                # Se non troviamo il prezzo con il selettore specifico, proviamo selettori alternativi
                if not price_element:
                    price_element = item.find(['p', 'div', 'span'], class_=re.compile(r'price'))
                
                # Se ancora non troviamo, cerchiamo all'interno dell'elemento e anche nei genitori
                if not price_element:
                    # Cerca in questo elemento
                    parent = item
                    for _ in range(3):  # Limita la ricerca a 3 livelli di genitori
                        if parent:
                            price_element = parent.find(['p', 'div', 'span'], class_=re.compile(r'price'))
                            if price_element:
                                break
                            parent = parent.parent
                
                # Se non troviamo un prezzo, cerca nel testo dell'intero elemento
                if not price_element:
                    all_text = item.get_text()
                    price_matches = re.findall(r'(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*€|\€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)', all_text)
                    
                    # Appiattisci la lista di tuple e rimuovi stringhe vuote
                    price_candidates = [p for group in price_matches for p in group if p]
                    
                    if price_candidates:
                        price_text = price_candidates[0]
                    else:
                        continue  # Nessun prezzo trovato
                else:
                    # Ottieni il testo del prezzo e rimuovi elementi figli (come badge di spedizione)
                    price_text = ''.join([text for text in price_element.contents if isinstance(text, str)]).strip()
                    
                    # Se non abbiamo testo diretto, usa il testo completo
                    if not price_text:
                        price_text = price_element.get_text().strip()
                    
                    # Controlla se l'elemento del prezzo ha un badge "Venduto" come figlio
                    if price_element:
                        badge = price_element.find(class_=re.compile(r'(badge|item-sold)'))
                        if badge and 'venduto' in badge.get_text().lower():
                            logging.debug(f"Prodotto ignorato perché il prezzo contiene badge 'Venduto': {title}")
                            continue
                
                # Estrai il prezzo dal testo
                price_match = re.search(r'(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)', price_text)
                if not price_match:
                    continue
                
                price_text = price_match.group(1)
                
                # Pulizia e conversione del prezzo
                price_text = price_text.replace('.', '').replace(',', '.').strip()
                
                try:
                    price = float(price_text)
                except ValueError:
                    logging.debug(f"Impossibile convertire il prezzo '{price_text}' per: {title}")
                    continue
                
                # Estrai il link
                link = None
                
                # Se l'elemento stesso è un link
                if item.name == 'a' and item.has_attr('href'):
                    link = item['href']
                else:
                    # Cerca un link all'interno dell'elemento o nei suoi genitori
                    link_element = item.find('a', href=True)
                    
                    if not link_element:
                        # Cerca nei genitori
                        parent = item.parent
                        while parent and parent.name != 'html':
                            if parent.name == 'a' and parent.has_attr('href'):
                                link_element = parent
                                break
                            parent = parent.parent
                    
                    if link_element:
                        link = link_element['href']
                
                if not link:
                    continue
                
                # Assicurati che il link sia assoluto
                if link and not link.startswith('http'):
                    link = f"https://www.subito.it{link}"
                
                # Trova l'ID del prodotto
                item_id = None
                id_match = re.search(r'/(\d+)\.html', link)
                if id_match:
                    item_id = id_match.group(1)
                else:
                    item_id = link.split('/')[-1]
                
                # Estrai la location se disponibile
                location_element = item.find(class_=re.compile(r'(PostingTimeAndPlace|town|city|location)'))
                location = None
                
                if location_element:
                    location = location_element.get_text().strip()
                    # Pulisci la location da date o altre informazioni
                    location = re.sub(r'\d+\s+\w+\s+alle\s+\d+:\d+', '', location).strip()
                
                # Estrai l'URL dell'immagine
                img_element = item.find('img')
                img_url = None
                if img_element and img_element.has_attr('src'):
                    img_url = img_element['src']
                
                products.append({
                    'id': item_id,
                    'title': title,
                    'price': price,
                    'link': link,
                    'image': img_url,
                    'location': location
                })
                
                logging.debug(f"Estratto prodotto: {title} - €{price}")
                
            except Exception as e:
                logging.error(f"Errore durante l'analisi di un prodotto: {e}")
                continue
        
        return products
    
    def check_prices(self, search_config):
        product_name = search_config["product_name"]
        search_url = search_config["search_url"]
        min_price = search_config.get("min_price", 0)
        max_price = search_config["max_price"]
        results_limit = search_config.get("results_limit", 50)  # Numero massimo di risultati da mostrare
        
        logging.info(f"Controllo dei prezzi per '{product_name}' (min €{min_price}, max €{max_price})...")
        
        # Controlla se ci sono più pagine da controllare
        pages_to_check = search_config.get("pages_to_check", 1)
        all_products = []
        
        for page in range(1, pages_to_check + 1):
            page_url = search_url
            if page > 1:
                # Aggiungi il parametro della pagina all'URL
                if '?' in page_url:
                    page_url += f"&o={page}"
                else:
                    page_url += f"?o={page}"
            
            logging.info(f"Controllando pagina {page}/{pages_to_check}: {page_url}")
            
            html_content = self._get_page_content(page_url)
            if not html_content:
                logging.error(f"Impossibile ottenere contenuti per '{product_name}' pagina {page}")
                continue
            
            products = self._parse_products(html_content, product_name)
            all_products.extend(products)
            
            # Breve pausa tra le pagine per non sovraccaricare il server
            if page < pages_to_check:
                time.sleep(2)
        
        logging.info(f"Trovati {len(all_products)} prodotti totali su {pages_to_check} pagine")
        
        # Rimuovi duplicati basati sull'ID
        unique_products = {}
        for product in all_products:
            unique_products[product['id']] = product
        
        all_products = list(unique_products.values())
        logging.info(f"Filtrati a {len(all_products)} prodotti unici")
        
        # Filtra prodotti nel range di prezzo desiderato
        valid_products = []
        for product in all_products:
            # Verifica che il prezzo sia nel range specificato
            price = product['price']
            if min_price <= price <= max_price:
                valid_products.append(product)
                logging.debug(f"Prodotto valido: {product['title']} - €{price}")
            else:
                logging.debug(f"Prodotto fuori range di prezzo: {product['title']} - €{price} (range: €{min_price}-€{max_price})")
        
        # Ordina i prodotti per prezzo crescente
        valid_products.sort(key=lambda x: x['price'])
        
        # Limita il numero di risultati
        valid_products = valid_products[:results_limit]
        
        logging.info(f"Trovati {len(all_products)} prodotti per '{product_name}', di cui {len(valid_products)} nel range di prezzo €{min_price}-€{max_price}")
        
        # Stampa i prodotti validi
        if valid_products:
            print(f"\nRisultati per '{product_name}' (range €{min_price}-€{max_price}):")
            print("-" * 80)
            for i, product in enumerate(valid_products):
                location_info = f" - {product['location']}" if product.get('location') else ""
                print(f"{i+1}. {product['title']} - €{product['price']}{location_info}")
                print(f"   🔗 {product['link']}")
                print()
        else:
            print(f"\nNessun prodotto trovato per '{product_name}' nel range di prezzo €{min_price}-€{max_price}")
        
        return valid_products
    
    def run_scheduled_check(self):
        for search_config in self.config["searches"]:
            self.check_prices(search_config)
    
    def setup_scheduler(self):
        for search_config in self.config["searches"]:
            interval_minutes = search_config.get("check_interval_minutes", 30)
            
            # Configura il job di pianificazione
            schedule.every(interval_minutes).minutes.do(
                self.check_prices, search_config=search_config
            )
            
            logging.info(f"Pianificato controllo ogni {interval_minutes} minuti per '{search_config['product_name']}'")
    
    def run(self):
        logging.info("Avvio del monitor dei prezzi di Subito.it")
        
        # Esegui il primo controllo immediatamente
        self.run_scheduled_check()
        
        # Configura la pianificazione
        self.setup_scheduler()
        
        # Loop principale
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Monitor dei prezzi interrotto dall'utente")

# Funzione per creare URL di ricerca ottimizzati per Subito.it
def create_search_url(product_name, category=None, region=None):
    # Codifica il nome del prodotto per l'URL
    encoded_product = quote_plus(product_name)
    
    # URL base
    base_url = "https://www.subito.it/annunci-italia"
    
    # Aggiungi categoria se specificata
    if category:
        base_url = f"https://www.subito.it/{category}/italia"
    
    # Aggiungi regione se specificata
    if region:
        base_url = f"https://www.subito.it/annunci-{region.lower()}"
        if category:
            base_url = f"https://www.subito.it/{category}/{region.lower()}"
    
    # Completa l'URL con i parametri di ricerca
    search_url = f"{base_url}/vendita/usato/?q={encoded_product}"
    
    return search_url

# Funzione principale
def main():
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor prezzi per Subito.it')
    parser.add_argument('--test', action='store_true', help='Esegui in modalità test')
    parser.add_argument('--url', help='URL da testare in modalità test')
    parser.add_argument('--product', help='Nome del prodotto da cercare')
    parser.add_argument('--min', type=float, help='Prezzo minimo')
    parser.add_argument('--max', type=float, help='Prezzo massimo')
    parser.add_argument('--category', help='Categoria (es. elettronica, arredamento)')
    parser.add_argument('--region', help='Regione (es. lombardia, lazio)')
    parser.add_argument('--interval', type=int, default=30, help='Intervallo di controllo in minuti')
    parser.add_argument('--limit', type=int, default=50, help='Numero massimo di risultati da mostrare')
    parser.add_argument('--pages', type=int, default=3, help='Numero di pagine da controllare')

    args = parser.parse_args()
    
    # Modalità test
    if args.test:
        if args.url:
            test_url = args.url
        elif args.product:
            test_url = create_search_url(args.product, args.category, args.region)
        else:
            test_url = "https://www.subito.it/annunci-italia/vendita/usato/?q=televisione"
        
        monitor = PriceMonitor()
        html_content = monitor._get_page_content(test_url)
        
        if html_content:
            product_name = args.product or "test"
            products = monitor._parse_products(html_content, product_name)
            
            print(f"\nRisultati del test per '{test_url}':")
            print(f"Trovati {len(products)} prodotti")
            print("-" * 80)
            
            for i, product in enumerate(products[:20]):  # Mostra i primi 20 risultati
                location_info = f" - {product['location']}" if product.get('location') else ""
                print(f"{i+1}. {product['title']} - €{product['price']}{location_info}")
                print(f"   🔗 {product['link']}")
                print()
        
        return
    
    # Normale funzionamento
    if args.product and args.max:
        monitor = PriceMonitor()
        
        min_price = args.min if args.min is not None else 0
        max_price = args.max
        
        if min_price < 0 or max_price < 0:
            print("Errore: I prezzi non possono essere negativi")
            return
            
        if min_price > max_price:
            print("Errore: Il prezzo minimo non può essere maggiore del prezzo massimo")
            return
        
        # Crea URL di ricerca appropriato
        search_url = create_search_url(args.product, args.category, args.region)
        
        # Configura la ricerca
        new_search = {
            "product_name": args.product,
            "search_url": search_url,
            "min_price": min_price,
            "max_price": max_price,
            "check_interval_minutes": args.interval,
            "results_limit": args.limit,
            "pages_to_check": args.pages
        }
        
        monitor.config["searches"] = [new_search]
        
        # Salva la configurazione
        with open(CONFIG_FILE, 'w') as f:
            json.dump(monitor.config, f, indent=4)
        
        print(f"Avvio monitoraggio per '{args.product}' con prezzo tra €{min_price} e €{max_price}")
        print(f"URL di ricerca: {search_url}")
        print(f"Controllo ogni {args.interval} minuti su {args.pages} pagine")
        
        # Avvia il monitoraggio
        monitor.run()
    else:
        print("Usage: python3 botSubito.py --product NOME_PRODOTTO --min PREZZO_MIN --max PREZZO_MAX [--category CATEGORIA] [--region REGIONE] [--interval MINUTI] [--limit NUM_RISULTATI] [--pages NUM_PAGINE]")
        print("  oppure: python3 botSubito.py --test [--url URL_DA_TESTARE]")

if __name__ == "__main__":
    main()

# Per cercare televisori tra 100€ e 500€ su 5 pagine di risultati
 # python3 botSubito.py --product "televisione" --min 100 --max 500 --pages 5

# Per cercare un iPhone in Lombardia con più risultati
# python3 botSubito.py --product "iphone" --min 200 --max 600 --region lombardia --limit 100 --pages 5

# Per testare rapidamente il parser
# python3 botSubito.py --test --product "macbook"