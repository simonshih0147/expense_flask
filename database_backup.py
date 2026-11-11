# -*- coding: utf-8 -*-
"""MyDB03 one-click SQL backup; local-only, POST-only, no database writes."""
import os
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from flask import Blueprint, abort, render_template, request, session, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

bp = Blueprint("database_backup", __name__, url_prefix="/database-backup")

def local_only():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403, "資料庫備份僅允許在本機操作。")

def config():
    secret = os.getenv("APP_SECRET_KEY", "")
    if len(secret) < 24:
        raise RuntimeError("請在 .env 設定至少 24 字元的 APP_SECRET_KEY。")
    database = os.getenv("DB_NAME", "mydb03")
    if database.lower() != "mydb03":
        raise RuntimeError("安全限制：僅允許備份 MyDB03。")
    return secret, database

def executable():
    configured = os.getenv("MYSQLDUMP_PATH", "").strip().strip('"')
    if configured:
        p = Path(configured)
        if not p.is_file():
            raise RuntimeError("MYSQLDUMP_PATH 指定的 mysqldump.exe 不存在。")
        return str(p)
    found = shutil.which("mysqldump")
    if found:
        return found
    # Common Windows installation paths.
    for base in (Path("C:/Program Files/MySQL"), Path("C:/xampp/mysql/bin"),
                 Path("C:/laragon/bin/mysql")):
        if base.is_file() and base.name.lower() == "mysqldump.exe":
            return str(base)
        if base.is_dir():
            matches = sorted(base.rglob("mysqldump.exe"), reverse=True)
            if matches:
                return str(matches[0])
    raise RuntimeError("找不到 mysqldump.exe；請在 .env 設定 MYSQLDUMP_PATH。")

def template():
    return """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MyDB03 一鍵備份</title>
<style>body{font-family:"Microsoft JhengHei",sans-serif;background:#f0f4fa;color:#173453}
main{max-width:760px;margin:35px auto;padding:28px;background:white;border-radius:15px;box-shadow:0 4px 18px #1232}
a{color:#1768b4}button{background:#1768b4;color:white;border:0;padding:14px 24px;border-radius:9px;font-size:18px;cursor:pointer}
.info{padding:12px;background:#f2f6fc;border-radius:8px;overflow-wrap:anywhere}
.ok{color:#17653b}.error{color:#b02b24}</style></head><body><main>
<p><a href="/">系統首頁</a>　<a href="/dashboard-center">統計分析中心 V5.4</a></p>
<h1>MyDB03 一鍵備份</h1><p>只匯出 SQL 備份，不修改、刪除或覆蓋 MySQL 資料。</p>
<p class="info">備份位置：{{ folder }}</p>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
{% if result %}<p class="ok">備份成功：{{ result.name }}（{{ result.size }} bytes）</p>
<p>備份檔位置：{{ result.path }}</p>{% endif %}
<form method="post"><input type="hidden" name="token" value="{{ token }}">
<button type="submit">一鍵備份 MyDB03</button></form>
<p>請妥善保存 SQL 備份檔；建議定期將備份複製到其他硬碟。備份成功不等於已驗證可還原。</p>
</main></body></html>"""

@bp.route("/", methods=["GET", "POST"])
def home():
    local_only()
    error = None
    result = None
    folder = Path(os.getenv("MYSQL_BACKUP_DIR", r"E:\MySQL_Recovery_Archive"))
    try:
        secret, database = config()
        signer = URLSafeTimedSerializer(secret, salt="mysql-backup-form")
        if request.method == "POST":
            signed = request.form.get("token", "")
            try:
                expected = signer.loads(signed, max_age=900)
            except (BadSignature, SignatureExpired):
                abort(400, "備份操作驗證逾時，請重新整理頁面。")
            if expected != "backup-mydb03":
                abort(400, "備份操作驗證失敗。")
            dump = executable()
            folder.mkdir(parents=True, exist_ok=True)
            filename = f"MyDB03_Backup_{datetime.now():%Y%m%d_%H%M%S}_{secrets.token_hex(3)}.sql"
            final_path = folder / filename
            # An isolated defaults file avoids global my.ini options such as no-beep,
            # while keeping the password off the process command line.
            defaults_path = None
            temp_path = None
            try:
                fd, defaults_path = tempfile.mkstemp(prefix="mysql_backup_", suffix=".cnf")
                with os.fdopen(fd, "w", encoding="utf-8") as cfg:
                    cfg.write("[client]\n")
                    for key, val in (("host", os.getenv("DB_HOST", "127.0.0.1")),
                                     ("port", os.getenv("DB_PORT", "3306")),
                                     ("user", os.getenv("DB_USER", "root")),
                                     ("password", os.getenv("DB_PASSWORD", ""))):
                        # Quote and escape option-file values.
                        cfg.write(f'{key}="{str(val).replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"\n')
                fd, temp_path = tempfile.mkstemp(prefix="backup_in_progress_", suffix=".sql", dir=str(folder))
                os.close(fd)
                cmd = [dump, f"--defaults-file={defaults_path}",
                       "--single-transaction", "--quick", "--routines", "--triggers",
                       "--set-charset", "--databases", database,
                       f"--result-file={temp_path}"]
                completed = subprocess.run(cmd, capture_output=True, text=True,
                                           timeout=180, check=False)
                if completed.returncode != 0:
                    raise RuntimeError("mysqldump 失敗，請確認資料庫連線、帳號權限及 mysqldump 版本。"
                                       + (" " + completed.stderr[:300] if completed.stderr else ""))
                size = Path(temp_path).stat().st_size
                if size < 100:
                    raise RuntimeError("備份檔過小，已停止儲存；請檢查資料庫內容。")
                with open(temp_path, "rb") as check:
                    if b"CREATE TABLE" not in check.read(2_000_000):
                        raise RuntimeError("備份檔未找到資料表結構，請人工確認。")
                os.replace(temp_path, final_path)
                temp_path = None
                result = {"name": filename, "size": f"{size:,}", "path": str(final_path)}
            finally:
                for temp in (defaults_path, temp_path):
                    if temp:
                        try: os.remove(temp)
                        except OSError: pass
    except Exception as exc:
        current_app.logger.exception("MySQL 備份失敗")
        error = str(exc)
        signer = None
    token = signer.dumps("backup-mydb03") if signer else ""
    return render_template_string_safe(template(), folder=str(folder), token=token,
                                       error=error, result=result)

def render_template_string_safe(source, **context):
    from flask import render_template_string
    return render_template_string(source, **context)
