import requests
from bs4 import BeautifulSoup
import json
import time
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("namasha.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.namasha.com/channel"
DELAY = 0.1
MAX_ID_STEP = 1000
FILENAME = "namasha_channels.json"
MAX_THREADS = 100
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def fetch_channel(id_):
    url = f"{BASE_URL}{id_}/"
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 404:
            return None
        soup = BeautifulSoup(res.text, "html.parser")

        name_tag = soup.select_one("meta[property='og:title']")
        name = name_tag['content'].replace("- ویدیوها", "").strip() if name_tag else ""

        if not name:
            return None

        created_tag = soup.select_one("meta[name='DC.Date.Created']")
        created_at = created_tag['content'] if created_tag else ""

        description_tag = soup.select_one("meta[property='og:description']")
        description = description_tag['content'] if description_tag and description_tag.get('content') else ""

        avatar_tag = soup.select_one("meta[property='og:image']")
        avatar = avatar_tag['content'] if avatar_tag and avatar_tag.get('content') else ""

        return {
            "id": id_,
            "url": url,
            "name": name,
            "created_at": created_at,
            "description": description,
            "avatar": avatar,
        }
    except Exception as e:
        logger.warning(f"[{id_}] ❌ Error: {e}")
        return None

def save_results(results):
    with open(FILENAME, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(results)} total channels.")

def load_results():
    if os.path.exists(FILENAME):
        with open(FILENAME, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def update_existing_channels(results):
    updated_results = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_id = {executor.submit(fetch_channel, ch["id"]): ch["id"] for ch in results}
        for future in as_completed(future_to_id):
            ch_id = future_to_id[future]
            data = future.result()
            if data:
                logger.info(f"[{ch_id}] 🔁 Updated: {data['name']}")
                updated_results.append(data)
    return updated_results

def fetch_new_channels(start_id, end_id, existing_ids):
    new_results = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_id = {executor.submit(fetch_channel, i): i for i in range(start_id, end_id) if i not in existing_ids}
        for future in as_completed(future_to_id):
            i = future_to_id[future]
            data = future.result()
            if data:
                logger.info(f"[{i}] ➕ New: {data['name']}")
                new_results.append(data)
            else:
                time.sleep(DELAY)
    return new_results

def main():
    results = load_results()
    logger.info("Updating existing channels...")
    results = update_existing_channels(results)

    if results:
        last_id = max(item["id"] for item in results)
    else:
        last_id = 0

    start_id = last_id + 1
    end_id = start_id + MAX_ID_STEP
    logger.info(f"Fetching new channels from ID {start_id} to {end_id}")

    existing_ids = set(ch["id"] for ch in results)
    new_channels = fetch_new_channels(start_id, end_id, existing_ids)
    results.extend(new_channels)

    save_results(results)
    logger.info("✅ Scan Done.")

if __name__ == "__main__":
    main()
