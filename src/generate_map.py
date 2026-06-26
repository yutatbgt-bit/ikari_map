# generate_map.py
import os
import json
import re
import subprocess

def get_desktop_path():
    # 1. Windows環境の場合
    if os.name == 'nt':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
            desktop_val, _ = winreg.QueryValueEx(key, "Desktop")
            return os.path.expandvars(desktop_val)
        except Exception:
            pass

    # 2. WSL (Linux) 環境から Windows 側のデスクトップパスを検出
    is_wsl = False
    if os.path.exists('/proc/version'):
        try:
            with open('/proc/version', 'r') as f:
                if 'microsoft' in f.read().lower():
                    is_wsl = True
        except Exception:
            pass

    if is_wsl:
        try:
            # cmd.exe から Windows の USERPROFILE 環境変数を動的に取得
            win_profile = subprocess.check_output(
                ["cmd.exe", "/c", "echo %USERPROFILE%"],
                stderr=subprocess.DEVNULL
            ).decode("shift-jis").strip()
            # wslpath を使用して WSL 用のパスに変換
            wsl_profile = subprocess.check_output(
                ["wslpath", win_profile],
                stderr=subprocess.DEVNULL
            ).decode("utf-8").strip()
            
            paths_to_try = [
                os.path.join(wsl_profile, "OneDrive", "Desktop"),
                os.path.join(wsl_profile, "Desktop")
            ]
            for p in paths_to_try:
                if os.path.exists(p):
                    return p
        except Exception:
            pass

    # 3. 一般的なフォールバック
    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    onedrive_desktop = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')
    if not os.path.exists(desktop) and os.path.exists(onedrive_desktop):
        return onedrive_desktop
    if os.path.exists(desktop):
        return desktop
        
    return os.getcwd()

def parse_config_md(config_path):
    if not os.path.exists(config_path):
        return {}
        
    stores = {}
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
                if re.match(r"^\|[\s:|#-]+\|$", line):
                    continue
                cols = [c.strip() for c in line.split("|")][1:-1]
                # 列構成: 店舗名 (0) | 座標 (1) | 住所 (2) | 電話番号 (3) | 駐車場 (4) | 営業時間 (5) | 特徴 (6) | 店長の一言 (7) | 画像URL (8) | 詳細URL (9)
                if len(cols) >= 10:
                    name = cols[0]
                    if not name:
                        continue
                        
                    # 座標文字列をパースして float のリストにする
                    coords_str = cols[1]
                    coords = None
                    if coords_str:
                        parts = [p.strip() for p in coords_str.split(",")]
                        if len(parts) == 2:
                            try:
                                coords = [float(parts[0]), float(parts[1])]
                            except ValueError:
                                pass
                                
                    # 座標が取得できない、または [0, 0] の場合はマップに載せないためスキップ
                    if not coords or (coords[0] == 0.0 and coords[1] == 0.0):
                        continue
                        
                    stores[name] = {
                        "coords": coords,
                        "address": cols[2],
                        "phone": cols[3],
                        "parking": cols[4],
                        "hours": cols[5],
                        "features": cols[6],
                        "manager": cols[7],
                        "image_url": cols[8],
                        "detail_url": cols[9]
                    }
    return stores

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    template_path = os.path.join(project_root, "map_only_template.html")
    config_path = os.path.join(project_root, "config.md")
    
    desktop = get_desktop_path()
    output_path = os.path.join(project_root, "ikari_map.html")

    if not os.path.exists(template_path):
        print(f"Error: {template_path} not found.")
        return
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        return

    # config.md から座標とすべての詳細情報をパースして取得
    ikari_stores = parse_config_md(config_path)
    
    combined_data = {
        "ikari_stores": ikari_stores,
        "competitors": {}
    }
    
    combined_data_str = json.dumps(combined_data, ensure_ascii=False, indent=2)
    # </script> タグのインジェクションを防ぐため、'</' を '\u003c/' にエスケープする
    combined_data_str = combined_data_str.replace('</', '\\u003c/')

    import base64
    logo_path = r"C:\Users\yutat\.gemini\antigravity\brain\705f0ccf-67fb-4770-a6a3-18b561a5ae03\media_seamless.png"
    anchor_path = r"C:\Users\yutat\.gemini\antigravity\brain\705f0ccf-67fb-4770-a6a3-18b561a5ae03\scratch\anchor_logo.png"
    text_path = r"C:\Users\yutat\.gemini\antigravity\brain\705f0ccf-67fb-4770-a6a3-18b561a5ae03\scratch\ikari_text.png"

    base64_logo = ""
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            base64_logo = "data:image/png;base64," + base64.b64encode(image_file.read()).decode('utf-8')
    else:
        print(f"Warning: Logo image not found at {logo_path}")

    base64_anchor = ""
    if os.path.exists(anchor_path):
        with open(anchor_path, "rb") as image_file:
            base64_anchor = "data:image/png;base64," + base64.b64encode(image_file.read()).decode('utf-8')
    else:
        print(f"Warning: Anchor image not found at {anchor_path}")

    base64_text = ""
    if os.path.exists(text_path):
        with open(text_path, "rb") as image_file:
            base64_text = "data:image/png;base64," + base64.b64encode(image_file.read()).decode('utf-8')
    else:
        print(f"Warning: Text logo image not found at {text_path}")

    # テンプレートの読み込み
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # プレースホルダを置換
    dynamic_html = html_content.replace("/*STORE_DATA_PLACEHOLDER*/", combined_data_str.strip())
    dynamic_html = dynamic_html.replace("/*REPORT_DATA_PLACEHOLDER*/", "{}")
    dynamic_html = dynamic_html.replace("/*HEADER_BG_PLACEHOLDER*/", base64_logo)
    dynamic_html = dynamic_html.replace("/*ANCHOR_LOGO_PLACEHOLDER*/", base64_anchor)
    dynamic_html = dynamic_html.replace("/*IKARI_TEXT_PLACEHOLDER*/", base64_text)

    # デスクトップに書き出し
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dynamic_html)

    print(f"Successfully generated independent map page: {output_path}")

    # Windows環境の場合、アドレスバーなしで起動するアプリモード用のショートカットを作成
    if os.name == 'nt':
        try:
            shortcut_path = os.path.join(desktop, "ikari_map.lnk")
            # Edgeの標準的なインストールパスを確認して設定
            edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            if not os.path.exists(edge_path):
                edge_path = "msedge.exe" # フォールバック
                
            escaped_html_path = output_path.replace(os.sep, "/")
            
            # クォーテーションのエスケープ崩れを防ぐため、一時的な.ps1ファイルを書き出して実行する
            ps1_path = os.path.join(desktop, "create_shortcut.ps1")
            with open(ps1_path, "w", encoding="utf-8-sig") as f: # UTF-8 with BOM for PowerShell
                f.write(
                    f'$WshShell = New-Object -ComObject WScript.Shell\n'
                    f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")\n'
                    f'$Shortcut.TargetPath = "{edge_path}"\n'
                    f'$Shortcut.Arguments = \'--app="{output_path}"\'\n'
                    f'$Shortcut.IconLocation = "{edge_path}, 0"\n'
                    f'$Shortcut.Save()\n'
                )
            
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps1_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(ps1_path)
            print(f"Successfully created app-mode desktop shortcut: {shortcut_path}")
        except Exception as e:
            print(f"Warning: Failed to create desktop shortcut: {e}")

if __name__ == "__main__":
    main()
