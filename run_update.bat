@echo off
cd /d %~dp0
echo ===================================================
echo  いかりスーパー周辺 競合環境マップ 更新ツール
echo ===================================================
echo.
echo 1. いかりスーパー公式サイトから最新の店舗情報を取得中...
uv run src/update_store_db.py
if %ERRORLEVEL% neq 0 (
    echo [エラー] 店舗情報のスクレイピングに失敗しました。
    goto error
)

echo.
echo 2. 店舗情報を反映したマップページ (index.html) を再生成中...
uv run src/generate_map.py
if %ERRORLEVEL% neq 0 (
    echo [エラー] マップページの生成に失敗しました。
    goto error
)

echo.
echo ===================================================
echo  [成功] 更新が完了しました。index.html を開いてください。
echo ===================================================
goto end

:error
echo.
echo 更新処理の途中でエラーが発生しました。
echo.

:end
pause
