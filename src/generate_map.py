# generate_map.py
import os
import json
import winreg
import re

def get_desktop_path():
    try:
        # Windows レジストリから実際のデスクトップのパスを取得 (OneDrive 同期に対応)
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        desktop_val, _ = winreg.QueryValueEx(key, "Desktop")
        return os.path.expandvars(desktop_val)
    except Exception:
        # フォールバック処理
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        onedrive_desktop = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')
        if not os.path.exists(desktop) and os.path.exists(onedrive_desktop):
            return onedrive_desktop
        return desktop

def parse_config_md(config_path):
    if not os.path.exists(config_path):
        return {}
        
    stores_override = {}
    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    table_started = False
    for line in lines:
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            if "店舗名" in line and "住所" in line:
                table_started = True
                continue
            if table_started:
                # 区切り行 (e.g. |:---|:---|) をスキップ
                if re.match(r"^\|[\s:|#-]+\|$", line):
                    continue
                # データ行の解析
                cols = [c.strip() for c in line.split("|")][1:-1]
                if len(cols) >= 7:
                    name = cols[0]
                    if not name:
                        continue
                    stores_override[name] = {
                        "address": cols[1],
                        "phone": cols[2],
                        "parking": cols[3],
                        "hours": cols[4],
                        "features": cols[5],
                        "image_url": cols[6]
                    }
    return stores_override

def main():
    # 実行スクリプトのディレクトリを基準にする
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    template_path = os.path.join(project_root, "map_only_template.html")
    db_base_path = os.path.join(project_root, "stores_db_base.json")
    config_path = os.path.join(project_root, "config.md")
    
    # 動的に取得したデスクトップに出力
    desktop = get_desktop_path()
    output_path = os.path.join(desktop, "ikari_map.html")

    if not os.path.exists(template_path):
        print(f"Error: {template_path} not found.")
        return
    if not os.path.exists(db_base_path):
        print(f"Error: {db_base_path} not found.")
        return

    # 1. 座標マスタ (stores_db_base.json) の読み込み
    with open(db_base_path, "r", encoding="utf-8") as f:
        db_base_data = json.load(f)
        
    ikari_stores = db_base_data.get("ikari_stores", {})

    # 2. 店舗設定 (config.md) から手動/更新詳細設定をパースして取得
    overrides = parse_config_md(config_path)
    
    # 3. 座標マスタと詳細テキスト情報を結合 (中間のJSONへの書き戻しはせず、メモリ上で完結)
    combined_ikari_stores = {}
    for db_name, db_info in ikari_stores.items():
        coords = db_info.get("coords")
        
        # デフォルト値
        address = ""
        phone = ""
        parking = "なし"
        hours = ""
        features = ""
        image_url = ""
        
        # config.md から一致する店名を検索
        norm_db = db_name.replace("いかり", "").replace("スーパー", "").strip()
        matched_info = None
        for cfg_name, cfg_info in overrides.items():
            norm_cfg = cfg_name.replace("いかり", "").replace("スーパー", "").strip()
            if norm_db == norm_cfg:
                matched_info = cfg_info
                break
                
        if matched_info:
            address = matched_info["address"]
            phone = matched_info["phone"]
            parking = matched_info["parking"]
            hours = matched_info["hours"]
            features = matched_info["features"]
            image_url = matched_info["image_url"]
            
        combined_ikari_stores[db_name] = {
            "coords": coords,
            "address": address,
            "phone": phone,
            "parking": parking,
            "hours": hours,
            "features": features,
            "image_url": image_url
        }

    # 4. プレースホルダ置換用の JSON データ構造を組み立て
    combined_data = {
        "ikari_stores": combined_ikari_stores,
        "competitors": {} # 競合店舗のプロットは非表示 (不要)
    }
    
    combined_data_str = json.dumps(combined_data, ensure_ascii=False, indent=2)

    # 5. テンプレートの読み込み
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 6. プレースホルダを置換
    dynamic_html = html_content.replace("/*STORE_DATA_PLACEHOLDER*/", combined_data_str.strip())
    dynamic_html = dynamic_html.replace("/*REPORT_DATA_PLACEHOLDER*/", "{}")

    # 7. デスクトップに直接書き出し
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dynamic_html)

    print(f"Successfully generated independent map page: {output_path}")

if __name__ == "__main__":
    main()
