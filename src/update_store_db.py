import os
import json
import requests
from bs4 import BeautifulSoup
import re

def scrape_ikari_stores():
    url = "https://www.ikarisuper.com/info/store/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch store page: {response.status_code}")
        return {}
        
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    stores_info = {}
    
    # info/author/ へのリンクを持つ <a> タグを起点として各店舗ブロックを特定
    author_links = soup.find_all("a", href=re.compile(r"info/author/"))
    
    for a in author_links:
        name = a.text.strip()
        if not name:
            continue
            
        # 親のブロック要素 (article または section.store_detail) を探す
        parent = a.find_parent("article")
        if not parent:
            parent = a.find_parent("section", class_="store_detail")
        if not parent:
            parent = a.find_parent("div", class_="info")
            if parent:
                parent = parent.parent
                
        if not parent:
            continue
            
        # 画像URLの取得
        img_tag = parent.find("img")
        img_url = img_tag["src"] if img_tag else ""
        if img_url and img_url.startswith("/"):
            img_url = "https://www.ikarisuper.com" + img_url
            
        # 詳細情報の抽出
        address = ""
        phone = ""
        hours = ""
        parking = "なし"
        
        dl = parent.find("dl")
        if dl:
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            details = {}
            for dt, dd in zip(dts, dds):
                key = dt.text.strip()
                val = dd.text.strip()
                details[key] = val
            address = details.get("所在地", "")
            phone = details.get("電話番号", "")
            parking = details.get("駐車場", "なし")
            hours = details.get("営業時間", "")
        else:
            addr_tag = parent.find("p", class_="mgn_t5")
            if addr_tag:
                address = addr_tag.text.strip()
                
            p_tags = parent.find_all("p")
            for p in p_tags:
                text = p.text.strip()
                if "TEL" in text or "電話" in text:
                    phone = text.split(":")[-1].strip()
                elif "営業時間" in text:
                    hours = text.split("：")[-1].strip()
                    
        if name not in stores_info or (stores_info[name]["image_url"] == "" and img_url != ""):
            stores_info[name] = {
                "image_url": img_url,
                "address": address,
                "phone": phone,
                "parking": parking,
                "hours": hours
            }
            
    return stores_info

def parse_current_config(config_path):
    if not os.path.exists(config_path):
        return {}
    
    # 既存の config.md を読み込んで特徴などを退避
    existing_data = {}
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    table_started = False
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            if "店舗名" in line and "住所" in line:
                table_started = True
                continue
            if table_started:
                if re.match(r"^\|[\s:|#-]+\|$", line):
                    continue
                cols = [c.strip() for c in line.split("|")][1:-1]
                if len(cols) >= 7:
                    name = cols[0]
                    existing_data[name] = {
                        "features": cols[5]
                    }
    return existing_data

def update_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    config_path = os.path.join(project_root, "config.md")
    
    # 1. 既存の config.md をパースして特徴などを退避
    existing = parse_current_config(config_path)
    
    # 2. 公式サイトから最新データを取得
    scraped = scrape_ikari_stores()
    print(f"Scraped {len(scraped)} stores from website.")
    
    # 3. マージ処理
    final_stores = {}
    for web_name, web_info in scraped.items():
        # 表記揺れの正規化
        norm_web = web_name.replace("いかり", "").replace("スーパー", "").replace("（本店）", "").strip()
        
        # デフォルトの特徴値
        features = f"いかりスーパー{web_name}。公式住所: {web_info['address']}"
        
        # 既存の手動設定から特徴（features）を引き継ぐ
        for ex_name, ex_info in existing.items():
            norm_ex = ex_name.replace("いかり", "").replace("スーパー", "").replace("（本店）", "").strip()
            if norm_web == norm_ex or norm_ex in norm_web or norm_web in norm_ex:
                if ex_info.get("features"):
                    features = ex_info["features"]
                break
        
        # config.md 用のキーを短い名前に統一 (e.g. "いかり芦屋店" -> "芦屋店")
        store_key = web_name
        if web_name.startswith("いかり"):
            store_key = web_name.replace("いかり", "", 1).replace("スーパー", "", 1).replace("（本店）", "").strip()
            
        # 特定の愛蓮などの系列レストランは除外
        if "愛蓮" in store_key:
            continue
            
        final_stores[store_key] = {
            "address": web_info["address"],
            "phone": web_info["phone"],
            "parking": web_info["parking"],
            "hours": web_info["hours"],
            "features": features,
            "image_url": web_info["image_url"]
        }
        
    # 4. config.md の書き出し
    markdown_lines = [
        "# 店舗情報設定",
        "",
        "このファイルで、マップに表示されるいかりスーパー各店舗の情報（住所、営業時間、駐車場、特徴、画像など）を手動で変更・更新できます。",
        "",
        "### 設定テーブル",
        "※「店舗名」は変更しないでください（マッチングに使用します）。",
        "※ 各店舗ごとの情報（住所、電話番号、駐車場、営業時間、特徴、画像URL）を書き換えて保存した後、フォルダ内の `run_update.bat` を実行するとマップに反映されます。",
        "",
        "| 店舗名 | 住所 | 電話番号 | 駐車場 | 営業時間 | 特徴 | 画像URL |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    # 店舗名順にソートして書き出す
    for name, info in sorted(final_stores.items()):
        addr = info["address"].replace("|", "\\|")
        phone = info["phone"].replace("|", "\\|")
        parking = info["parking"].replace("|", "\\|")
        hours = info["hours"].replace("|", "\\|")
        features = info["features"].replace("|", "\\|")
        image_url = info["image_url"].replace("|", "\\|")
        
        markdown_lines.append(f"| {name} | {addr} | {phone} | {parking} | {hours} | {features} | {image_url} |")
        
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_lines) + "\n")
        
    print(f"Successfully updated config.md with website information. (Existing features retained)")

if __name__ == "__main__":
    update_config()
