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
    
    # 1. 主要店舗の抽出 (section.store_detail)
    major_sections = soup.find_all("section", class_="store_detail")
    for sec in major_sections:
        name = ""
        all_as = sec.find_all("a", href=re.compile(r"info/author/"))
        for a in all_as:
            t = a.text.strip()
            if t and t != "詳細を見る":
                name = t
                break
        
        if not name:
            continue
            
        img_tag = sec.find("img")
        img_url = img_tag["src"] if img_tag else ""
        if img_url and img_url.startswith("/"):
            img_url = "https://www.ikarisuper.com" + img_url
            
        address = ""
        phone = ""
        parking = "なし"
        hours = ""
        
        dl = sec.find("dl")
        if dl:
            dts = [dt.text.strip() for dt in dl.find_all("dt")]
            dds = [dd.text.strip() for dd in dl.find_all("dd")]
            details = dict(zip(dts, dds))
            address = details.get("所在地", "")
            phone = details.get("電話番号", "")
            parking = details.get("駐車場", "なし")
            hours = details.get("営業時間", "")
            
        if name not in stores_info or (stores_info[name]["image_url"] == "" and img_url != ""):
            stores_info[name] = {
                "image_url": img_url,
                "address": address,
                "phone": phone,
                "parking": parking,
                "hours": hours
            }

    # 2. 一般店舗の抽出 (article タグ)
    # id="contents" や class="pc_none" は除く
    articles = soup.find_all("article")
    for art in articles:
        classes = art.get("class", [])
        art_id = art.get("id", "")
        
        if "pc_none" in classes or art_id == "contents":
            continue
            
        name = ""
        all_as = art.find_all("a", href=re.compile(r"info/author/"))
        for a in all_as:
            t = a.text.strip()
            if t and t != "詳細を見る":
                name = t
                break
                
        if not name:
            continue
            
        img_tag = art.find("img")
        img_url = img_tag["src"] if img_tag else ""
        if img_url and img_url.startswith("/"):
            img_url = "https://www.ikarisuper.com" + img_url
            
        address = ""
        phone = ""
        parking = "なし"
        hours = ""
        
        dl = art.find("dl")
        if dl:
            dts = [dt.text.strip() for dt in dl.find_all("dt")]
            dds = [dd.text.strip() for dd in dl.find_all("dd")]
            details = dict(zip(dts, dds))
            address = details.get("所在地", "")
            phone = details.get("電話番号", "")
            parking = details.get("駐車場", "なし")
            hours = details.get("営業時間", "")
        else:
            addr_tag = art.find("p", class_="mgn_t5")
            if addr_tag:
                address = addr_tag.text.strip()
                
            p_tags = art.find_all("p")
            for p in p_tags:
                text = p.text.strip()
                if text.startswith("TEL"):
                    phone = text.replace("TEL", "").replace(":", "").replace("：", "").strip()
                elif "営業時間" in text:
                    val = text.replace("営業時間", "").strip()
                    if val.startswith(":") or val.startswith("："):
                        val = val[1:].strip()
                    hours = val
                elif "駐車場" in text:
                    parking = text.replace("駐車場", "").replace(":", "").replace("：", "").strip()
                    
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

def clean_store_name(name):
    """
    店舗名を正規化して比較しやすくする。
    例: 'いかり神戸三宮店' -> '神戸三宮'
        '芦屋店' -> '芦屋'
    """
    n = name.strip()
    n = n.replace("いかり", "").replace("スーパー", "").replace("（本店）", "").replace("(本店)", "")
    if n.endswith("店") and n not in ["ラ・グルメゾン", "ライクスホール"]:
        n = n[:-1]
    return n.strip()

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
        norm_web = clean_store_name(web_name)
        
        # config.md 用のキーを短い名前に統一 (e.g. "いかり芦屋店" -> "芦屋店")
        store_key = web_name
        if web_name.startswith("いかり"):
            store_key = web_name.replace("いかり", "", 1).replace("スーパー", "", 1).replace("（本店）", "").strip()
            
        if store_key == "詳細を見る" or not store_key:
            continue
            
        # 特定の愛蓮などの系列レストランは除外
        if "愛蓮" in store_key:
            continue
            
        # デフォルトの特徴値
        features = f"いかりスーパー{store_key}。公式住所: {web_info['address']}"
        
        # 既存の手動設定から特徴（features）を引き継ぐ
        for ex_name, ex_info in existing.items():
            norm_ex = clean_store_name(ex_name)
            if norm_web == norm_ex:
                if ex_info.get("features"):
                    features = ex_info["features"]
                break
            
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
