# Subito.it Price Monitor

A Python tool to monitor product prices on Subito.it and get notified when items matching your criteria are listed.

![Subito.it Logo](https://assets.subito.it/static/images/logo.png)

## 📖 Overview

This tool helps you monitor Subito.it, Italy's popular marketplace, for items that match your specified criteria. It searches for products within a defined price range and notifies you when matching items are found. Items marked as "VENDUTO" (sold) are automatically filtered out.

### Key Features

- 🔍 Search for products with customizable filters
- 💰 Set minimum and maximum price ranges
- 🚫 Automatically filter out sold items
- 🔄 Schedule regular checks at custom intervals
- 📊 Sort results by price for easy browsing
- 🌍 Filter by region or category
- 📱 Simple command-line interface

## 🚀 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/subito-price-monitor.git
   cd subito-price-monitor
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 📋 Requirements

- Python 3.6+
- Required Python packages (install via pip):
  - requests
  - beautifulsoup4
  - schedule

## 🛠️ Usage

### Basic Usage

Monitor a product with price range:

```bash
python botSubito.py --product "macbook" --min 500 --max 1000
```

### Advanced Options

```bash
python botSubito.py --product "televisione" --min 100 --max 500 --pages 5 --interval 60 --region lombardia --category elettronica
```

### Available Parameters

| Parameter     | Description                              | Default   |
|---------------|------------------------------------------|-----------|
| `--product`   | Name of the product to search for        | Required  |
| `--min`       | Minimum price                            | 0         |
| `--max`       | Maximum price                            | Required  |
| `--category`  | Product category (e.g., elettronica)     | None      |
| `--region`    | Region to search in (e.g., lombardia)    | None      |
| `--interval`  | Check interval in minutes                | 30        |
| `--limit`     | Maximum number of results to show        | 50        |
| `--pages`     | Number of pages to check                 | 3         |

### Test Mode

To test the parser without scheduling:

```bash
python botSubito.py --test --product "iphone"
```

Or test a specific URL:

```bash
python botSubito.py --test --url "https://www.subito.it/annunci-italia/vendita/usato/?q=playstation"
```

## 🧰 How It Works

1. **URL Creation**: The program generates optimized search URLs based on your criteria
2. **Web Scraping**: It fetches and parses the Subito.it search results pages
3. **Content Analysis**: The HTML is processed to extract products, prices, and details
4. **Filtering**: Products are filtered based on:
   - Price range (min/max)
   - Sold status (items marked as "VENDUTO" are excluded)
   - Relevance to search terms
5. **Scheduling**: Regular checks are performed at specified intervals
6. **Notification**: Matching products are displayed in the console

## 📝 Configuration

The program uses a `config.json` file that is created automatically on first run. You can manually edit this file to:

- Add multiple search configurations
- Modify user agent settings
- Change default behaviors

Example config file:

```json
{
    "searches": [
        {
            "product_name": "macbook",
            "search_url": "https://www.subito.it/annunci-italia/vendita/usato/?q=macbook",
            "min_price": 500,
            "max_price": 1200,
            "check_interval_minutes": 60,
            "results_limit": 50,
            "pages_to_check": 3
        }
    ],
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
```

## 🔍 Advanced Filtering for Sold Items

The tool intelligently filters out sold items by checking for:
- Spans with "item-sold-badge" class containing "Venduto" text
- Notice elements about completed transactions
- Elements with "no-item-available" in their class names
- Text indicating an item is sold in the product description or title

## ⚠️ Limitations

- The tool is designed specifically for Subito.it and may break if the website changes its structure
- Rate limiting may occur if checks are scheduled too frequently
- Region and category options must match Subito.it's URL structure

## 🤝 Contributing

Contributions are welcome! Feel free to:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

If you encounter issues or have questions, please open an issue on GitHub.

---

**Note**: This tool is for personal use only. Please be respectful of Subito.it's terms of service and avoid excessive requests.