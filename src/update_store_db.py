import os
import json
import requests
from bs4 import BeautifulSoup
import re
import argparse

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
                # 旧列数: 8列（店舗名(0)〜画像URL(7)）
                # 新列数: 10列（店舗名(0), 座標(1), 住所(2), 電話番号(3), 駐車場(4), 営業時間(5), 特徴(6), 店長の一言(7), 画像URL(8), 詳細URL(9)）
                if len(cols) == 8:
                    name = cols[0]
                    existing_data[name] = {
                        "coords": cols[1],
                        "address": cols[2],
                        "phone": cols[3],
                        "parking": cols[4],
                        "hours": cols[5],
                        "features": cols[6],
                        "manager": "",
                        "image_url": cols[7],
                        "detail_url": ""
                    }
                elif len(cols) >= 10:
                    name = cols[0]
                    existing_data[name] = {
                        "coords": cols[1],
                        "address": cols[2],
                        "phone": cols[3],
                        "parking": cols[4],
                        "hours": cols[5],
                        "features": cols[6],
                        "manager": cols[7],
                        "image_url": cols[8],
                        "detail_url": cols[9]
                    }
    return existing_data

def scrape_store_detail(url):
    """
    個別店舗ページから詳細情報をスクレイピングする
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to fetch detail page {url}: {e}")
        return None

    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    detail_info = {
        "address": "",
        "phone": "",
        "parking": "なし",
        "hours": "",
        "features": "",
        "manager": "",
        "image_url": "",
        "detail_url": url
    }
    
    sec = soup.find("section", class_="store_detail")
    if not sec:
        sec = soup.find("div", id="main")
        
    if sec:
        img_tag = sec.find("img")
        if img_tag and img_tag.get("src"):
            img_url = img_tag["src"]
            if img_url.startswith("/"):
                img_url = "https://www.ikarisuper.com" + img_url
            # http:// を https:// に変換して Mixed Content と CSP ブロックを防ぐ
            if img_url.startswith("http://"):
                img_url = img_url.replace("http://", "https://", 1)
            detail_info["image_url"] = img_url
            
        dl = sec.find("dl")
        if dl:
            dts = [dt.text.strip() for dt in dl.find_all("dt")]
            dds = [dd.text.strip() for dd in dl.find_all("dd")]
            details = dict(zip(dts, dds))
            detail_info["address"] = details.get("所在地", "")
            detail_info["phone"] = details.get("電話番号", "")
            detail_info["parking"] = details.get("駐車場", "なし")
            detail_info["hours"] = details.get("営業時間", "")
            
        # 紹介文（特徴）
        p_desc = sec.find("p", class_="mgn_b15")
        if p_desc:
            # 求人リンク等を除くテキスト
            detail_info["features"] = p_desc.text.strip().replace("\n", " ").replace("\r", "")
            
    # 店長からの一言 (二つ目の store_detail にある可能性があるため、soup 全体から探す)
    manager_div = soup.find("div", id="store_manager")
    if manager_div:
        h4_tag = manager_div.find("h4")
        manager_title = h4_tag.text.strip().replace("\n", " ").replace("\r", "").replace("  ", " ") if h4_tag else ""
        
        p_msg = manager_div.find_next_sibling("p")
        if p_msg:
            manager_msg = p_msg.text.strip().replace("\n", " ").replace("\r", "").replace("  ", " ")
            detail_info["manager"] = f"{manager_title} : {manager_msg}"
        else:
            detail_info["manager"] = manager_title
            
    return detail_info

def scrape_ikari_stores(target_store=None):
    url = "https://www.ikarisuper.com/info/store/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to fetch store list page: {e}")
        return {}
        
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    store_links = {}
    
    # 1. 主要店舗の抽出 (section.store_detail)
    major_sections = soup.find_all("section", class_="store_detail")
    for sec in major_sections:
        all_as = sec.find_all("a", href=re.compile(r"info/author/"))
        name = ""
        detail_url = ""
        for a in all_as:
            t = a.text.strip()
            if t and t != "詳細を見る" and "求人" not in t:
                name = t
                detail_url = a["href"]
                if detail_url.startswith("/"):
                    detail_url = "https://www.ikarisuper.com" + detail_url
                break
        if name and detail_url:
            store_links[name] = detail_url

    # 2. 一般店舗の抽出 (article タグ)
    articles = soup.find_all("article")
    for art in articles:
        classes = art.get("class", [])
        art_id = art.get("id", "")
        if "pc_none" in classes or art_id == "contents":
            continue
            
        all_as = art.find_all("a", href=re.compile(r"info/author/"))
        name = ""
        detail_url = ""
        for a in all_as:
            t = a.text.strip()
            if t and t != "詳細を見る" and "求人" not in t:
                name = t
                detail_url = a["href"]
                if detail_url.startswith("/"):
                    detail_url = "https://www.ikarisuper.com" + detail_url
                break
        if name and detail_url:
            store_links[name] = detail_url

    stores_info = {}
    target_norm = clean_store_name(target_store) if target_store else None
    if target_norm:
        print(f"Filtering target store: {target_store} (normalized: {target_norm})")

    for store_name, detail_url in store_links.items():
        store_key = store_name
        if store_name.startswith("いかり"):
            store_key = store_name.replace("いかり", "", 1).replace("スーパー", "", 1).replace("（本店）", "").replace("(本店)", "").strip()
            
        if store_key == "詳細を見る" or not store_key:
            continue
        if "愛蓮" in store_key:
            continue
            
        norm_name = clean_store_name(store_name)
        if target_norm and norm_name != target_norm:
            continue
            
        print(f"Scraping detail for: {store_name} ({detail_url})")
        detail_data = scrape_store_detail(detail_url)
        if detail_data:
            stores_info[store_key] = detail_data
            
    return stores_info

def update_config(target_store=None):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    config_path = os.path.join(project_root, "config.md")
    
    # 1. 既存の config.md をパースして全情報を退避
    existing = parse_current_config(config_path)
    
    # 2. 公式サイトから最新データを取得
    scraped = scrape_ikari_stores(target_store)
    print(f"Scraped details for {len(scraped)} stores.")
    
    # 3. マージ処理
    final_stores = {}
    
    # target_store が指定されている場合は、既存データ全てをベースとして構築する
    if target_store:
        # まず既存のconfigデータをすべて引き継ぐ
        for ex_name, ex_info in existing.items():
            final_stores[ex_name] = {
                "coords": ex_info["coords"],
                "address": ex_info["address"],
                "phone": ex_info["phone"],
                "parking": ex_info["parking"],
                "hours": ex_info["hours"],
                "features": ex_info["features"],
                "manager": ex_info["manager"],
                "image_url": ex_info["image_url"],
                "detail_url": ex_info["detail_url"]
            }
            
        # 次にスクレイピングした対象店舗の情報のみを上書きする
        for web_key, web_info in scraped.items():
            norm_web = clean_store_name(web_key)
            matched_key = None
            for ex_name in existing.keys():
                if clean_store_name(ex_name) == norm_web:
                    matched_key = ex_name
                    break
            
            store_key = matched_key if matched_key else web_key
            
            coords = existing[matched_key]["coords"] if matched_key else ""
            features = web_info["features"] if web_info["features"] else f"いかりスーパー{store_key}。公式住所: {web_info['address']}"
            if matched_key and existing[matched_key].get("features"):
                features = existing[matched_key]["features"]
                
            manager = web_info["manager"]
            if matched_key and existing[matched_key].get("manager"):
                manager = existing[matched_key]["manager"]
                
            final_stores[store_key] = {
                "coords": coords,
                "address": web_info["address"],
                "phone": web_info["phone"],
                "parking": web_info["parking"],
                "hours": web_info["hours"],
                "features": features,
                "manager": manager,
                "image_url": web_info["image_url"],
                "detail_url": web_info["detail_url"]
            }
    else:
        # target_store 指定がない場合は、新しくスクレイピングされたデータで全更新
        for web_key, web_info in scraped.items():
            norm_web = clean_store_name(web_key)
            store_key = web_key
            
            coords = ""
            features = web_info["features"] if web_info["features"] else f"いかりスーパー{store_key}。公式住所: {web_info['address']}"
            manager = web_info["manager"]
            
            for ex_name, ex_info in existing.items():
                if clean_store_name(ex_name) == norm_web:
                    coords = ex_info["coords"]
                    if ex_info.get("features"):
                        features = ex_info["features"]
                    if ex_info.get("manager"):
                        manager = ex_info["manager"]
                    break
                    
            final_stores[store_key] = {
                "coords": coords,
                "address": web_info["address"],
                "phone": web_info["phone"],
                "parking": web_info["parking"],
                "hours": web_info["hours"],
                "features": features,
                "manager": manager,
                "image_url": web_info["image_url"],
                "detail_url": web_info["detail_url"]
            }
            
    # 4. config.md の書き出し
    markdown_lines = [
        "# 店舗情報設定",
        "",
        "このファイルで、マップに表示されるいかりスーパー各店舗の情報（座標、住所、営業時間、駐車場、特徴、画像など）を手動で変更・更新できます。",
        "",
        "### 設定テーブル",
        "※「店舗名」は変更しないでください（マッチングに使用します）。",
        "※ 各店舗ごとの情報（座標、住所、電話番号、駐車場、営業時間、特徴、画像URL）を書き換えて保存した後、フォルダ内の `run_update.bat` を実行するとマップに反映されます。",
        "",
        "| 店舗名 | 座標 | 住所 | 電話番号 | 駐車場 | 営業時間 | 特徴 | 店長の一言 | 画像URL | 詳細URL |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for name, info in sorted(final_stores.items()):
        coords = info["coords"].replace("|", "\\|")
        addr = info["address"].replace("|", "\\|")
        phone = info["phone"].replace("|", "\\|")
        parking = info["parking"].replace("|", "\\|")
        hours = info["hours"].replace("|", "\\|")
        features = info["features"].replace("|", "\\|")
        manager = info["manager"].replace("|", "\\|")
        image_url = info["image_url"].replace("|", "\\|")
        # 出力時に http:// を https:// に変換して書き出す
        if image_url.startswith("http://"):
            image_url = image_url.replace("http://", "https://", 1)
        detail_url = info["detail_url"].replace("|", "\\|")
        
        markdown_lines.append(f"| {name} | {coords} | {addr} | {phone} | {parking} | {hours} | {features} | {manager} | {image_url} | {detail_url} |")
        
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_lines) + "\n")
        
    print(f"Successfully updated config.md with website information. (Existing coords and features retained)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update ikari store database from official website.")
    parser.add_argument("--target", type=str, default=None, help="Target store name to update (e.g., 岡本店). If omitted, all stores are processed.")
    args = parser.parse_args()
    
    update_config(args.target)
