import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

async def crawl_social_trends():
    # Daftar URL Tren Global
    targets = {
        "tiktok": "https://ads.tiktok.com/business/creativecenter/trends/popular/hashtags/pc/en",
        "youtube": "https://www.youtube.com/feed/trending",
        "reddit": "https://www.reddit.com/r/all/top/?t=day",
        "x_twitter": "https://twitter.com/i/trends",
        "facebook": "https://www.facebook.com/trending"
    }

    # Strategi Ekstraksi Universal (Mengambil teks judul/konten & link)
    schema = {
        "name": "Global Trend Extractor",
        "baseSelector": "h3, h2, .title, [class*='item'], article", 
        "fields": [
            {"name": "topic", "selector": "text", "type": "text"},
            {"name": "link", "selector": "a", "type": "attribute", "attribute": "href"}
        ]
    }
    
    strategy = JsonCssExtractionStrategy(schema)

    async with AsyncWebCrawler(verbose=True) as crawler:
        results = {}

        for platform, url in targets.items():
            print(f"--- Scraping {platform} Global Trends ---")
            
            # Eksekusi Crawl
            result = await crawler.arun(
                url=url,
                extraction_strategy=strategy,
                wait_for=2.0,           # Tunggu konten loading
                browser_cfg={"stealth": True}, # Hindari blokir
                bypass_cache=True
            )

            if result.success:
                # Simpan hasil dalam format JSON yang bersih
                results[platform] = json.loads(result.extracted_content)
            else:
                results[platform] = f"Gagal mengambil data: {result.error_message}"

        # Simpan semua hasil ke file JSON agar bisa dibaca Multi-Agent
        with open('global_trends.json', 'w') as f:
            json.dump(results, f, indent=4)
        
        print("\n✅ Selesai! Data disimpan di 'global_trends.json'")

if __name__ == "__main__":
    asyncio.run(crawl_social_trends())