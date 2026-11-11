"""Additive expense automation blueprint: does not change existing routes."""
from flask import Blueprint, request, render_template_string, current_app
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO, TextIOWrapper
from collections import defaultdict
import csv, hashlib, os, secrets
import mysql.connector
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

bp = Blueprint('automation', __name__, url_prefix='/auto')
FIELDS = ['交通費','電話費','房貸','用餐','保險','醫療','水費','電費','瓦斯費','其他','加油費','稅費','有線電視','照顧家人']

BASE = '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>消費自動化</title><style>body{font-family:system-ui,"Microsoft JhengHei",sans-serif;background:#f1f5f9;color:#183153;margin:0}main{max-width:880px;margin:32px auto;padding:26px;background:white;border-radius:16px;box-shadow:0 2px 15px #0001}h1{margin-top:0}input,select,textarea,button{font:inherit;padding:10px;border:1px solid #b9c7d6;border-radius:8px}input,select,textarea{max-width:100%;box-sizing:border-box}label{display:block;margin:12px 0 5px}button{background:#1769aa;color:white;cursor:pointer;margin-top:15px}a{color:#1769aa}table{border-collapse:collapse;width:100%;margin:16px 0}td,th{border-bottom:1px solid #ddd;padding:8px;text-align:left}small,.muted{color:#52677b}.warn{color:#a34700}.error{color:#a40000}.success{color:#116a39}.nav{display:flex;gap:20px;flex-wrap:wrap}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:600px){.grid{grid-template-columns:1fr}}</style><main><nav class="nav"><a href="/">原系統首頁</a><a href="/auto/">自動化首頁</a><a href="/auto/add">逐筆新增</a><a href="/auto/import">批次匯入</a></nav><hr>CONTENT</main></html>'''

def page(content, **kwargs):
    from flask import render_template_string
    return render_template_string(BASE.replace('CONTENT',content), **kwargs)

def db():
    return mysql.connector.connect(host=os.getenv('DB_HOST','127.0.0.1'),port=int(os.getenv("DB_PORT", "3306")),user=os.getenv('DB_USER'),password=os.getenv('DB_PASSWORD'),database=os.getenv('DB_NAME','mydb03'))

def parse_amount(raw, allow_zero=False):
    try:
        d=Decimal(str(raw).strip())
        if not d.is_finite() or d != d.to_integral_value() or d < 0 or d > 10000000 or (not allow_zero and d == 0): raise ValueError()
        return int(d)
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError('金額必須是 1～10,000,000 的整數' if not allow_zero else '金額必須是 0～10,000,000 的整數')

def parse_date(raw):
    return date.fromisoformat(str(raw).strip()[:10])

@bp.route('/')
def home():
    return page('''<h1>消費記帳自動化 C 方案</h1><p>新功能與原系統並存，不會覆蓋歷史資料。</p><p><a href="/auto/add">逐筆輸入，自動分類加總</a></p><p><a href="/auto/import">Excel / CSV 批次匯入（先預覽）</a></p><p class="warn">正式使用前，請先執行 schema.sql，並完成 SQL 備份。</p>''')

@bp.route('/add',methods=['GET','POST'])
def add():
    msg=''
    if request.method=='POST':
        conn=None
        try:
            day=parse_date(request.form.get('日期',''))
            cat=request.form.get('分類','')
            if cat not in FIELDS: raise ValueError('請選擇正確分類')
            amount=parse_amount(request.form.get('金額',''))
            note=request.form.get('備註','').strip()
            if len(note)>255: raise ValueError('備註最多255字')
            token=request.form.get('防重複碼','')
            if not token or len(token)>64: raise ValueError('缺少防重複碼')
            conn=db(); conn.start_transaction(); cur=conn.cursor()
            # Lock the daily aggregate; unique date PK serializes concurrent inserts.
            cur.execute('SELECT `日期` FROM `expense_data` WHERE `日期`=%s FOR UPDATE',(day,))
            exists=cur.fetchone() is not None
            cur.execute( 'INSERT IGNORE INTO `expense_detail` ''(`expense_date`, `category`, `amount`, `note`, `request_token`) ''VALUES (%s, %s, %s, %s, %s)',(day, cat, amount, note, token))
            if cur.rowcount==0:
                conn.rollback(); msg='<p class="warn">這筆提交已處理過，未重複記帳。</p>'
            else:
                if exists:
                    cur.execute(f'UPDATE `expense_data` SET `{cat}`=`{cat}`+%s WHERE `日期`=%s',(amount,day))
                else:
                    cols=['日期']+FIELDS+['備註']; vals=[day]+[amount if f==cat else 0 for f in FIELDS]+[None]
                    sql='INSERT INTO `expense_data` ('+','.join('`'+x+'`' for x in cols)+') VALUES ('+','.join(['%s']*len(cols))+')'
                    cur.execute(sql,vals)
                conn.commit(); msg='<p class="success">新增成功：'+str(day)+' '+cat+' '+str(amount)+' 元。Dashboard 已可重新整理查看。</p>'
        except Exception as e:
            if conn: conn.rollback()
            current_app.logger.exception('新增失敗')
            msg='<p class="error">新增失敗，沒有寫入資料。請檢查輸入與資料表是否建立。</p>'
        finally:
            if conn: conn.close()
    return page('''<h1>逐筆新增消費</h1>'''+msg+'''<form method="post"><label>日期</label><input name="日期" type="date" required value="{{today}}"><div class="grid"><div><label>分類</label><select name="分類">{% for f in fields %}<option>{{f}}</option>{% endfor %}</select></div><div><label>金額（元）</label><input name="金額" type="number" min="1" max="10000000" step="1" required></div></div><label>消費明細／備註</label><input name="備註" maxlength="255" placeholder="例如：停車費120元"><input type="hidden" name="防重複碼" value="{{token}}"><p class="muted">同一天可多次新增；系統會累加到原有分類金額，不會覆蓋舊資料。</p><button type="submit">確認新增</button></form>''',today=date.today().isoformat(),fields=FIELDS,token=secrets.token_hex(16))

def read_file(file):
    name=file.filename.lower(); data=file.read()
    if not data or len(data)>3*1024*1024: raise ValueError('檔案不可為空且需小於 3MB')
    if name.endswith('.csv'):
        text=data.decode('utf-8-sig'); rows=list(csv.DictReader(StringIO(text)))
    elif name.endswith('.xlsx'):
        try: from openpyxl import load_workbook
        except ImportError: raise ValueError('請先安裝 openpyxl：py -m pip install openpyxl')
        wb=load_workbook(BytesIO(data),read_only=True,data_only=True)
        sheet=wb.active; it=sheet.iter_rows(values_only=True)
        headers=[str(x).strip() if x is not None else '' for x in next(it)]
        rows=[dict(zip(headers, row)) for row in it if any(v is not None for v in row)]
        wb.close()
    else: raise ValueError('僅接受 CSV 或 XLSX')
    if not rows or len(rows)>1000: raise ValueError('每次匯入需有 1～1000 列')
    if '日期' not in rows[0]: raise ValueError('缺少「日期」欄位')
    for f in FIELDS:
        if f not in rows[0]: raise ValueError('缺少欄位：'+f)
    normalized=[]; seen=set()
    for i,r in enumerate(rows,2):
        try:
            raw=r['日期']
            if isinstance(raw,(datetime,date)): day=raw.date() if isinstance(raw,datetime) else raw
            else: day=parse_date(raw)
            if day in seen: raise ValueError('檔案內日期重複')
            seen.add(day)
            vals={f:parse_amount(r.get(f,0) if r.get(f,0) not in (None,'') else 0,True) for f in FIELDS}
            normalized.append((day,vals))
        except Exception as e: raise ValueError(f'第 {i} 列：{e}')
    return normalized, hashlib.sha256(data).hexdigest()

@bp.route('/import',methods=['GET','POST'])
def import_page():
    if request.method=='GET':
        return page('''<h1>批次匯入</h1><p>只新增資料庫尚未存在的日期；已存在日期不會覆蓋。需包含「日期」與14個費用欄位。</p><form method="post" enctype="multipart/form-data"><input type="hidden" name="stage" value="preview"><label>CSV 或 Excel (.xlsx)</label><input type="file" name="file" accept=".csv,.xlsx" required><button>預覽並檢查</button></form>''')
    conn=None
    try:
        upload=request.files.get('file')
        if not upload: raise ValueError('請選擇檔案')
        rows,digest=read_file(upload)
        conn=db(); cur=conn.cursor()
        dates=[x[0] for x in rows]
        placeholders=','.join(['%s']*len(dates))
        cur.execute('SELECT DATE(`日期`) FROM `expense_data` WHERE DATE(`日期`) IN ('+placeholders+')',dates)
        existing={r[0] for r in cur.fetchall()}
        fresh=[r for r in rows if r[0] not in existing]
        total=sum(sum(v.values()) for _,v in fresh)
        if request.form.get('stage')=='apply':
            signed=request.form.get('preview_token','')
            secret=os.getenv('APP_SECRET_KEY','')
            if len(secret)<24: raise ValueError('請在 .env 設定至少24字元的 APP_SECRET_KEY')
            try: expected=URLSafeTimedSerializer(secret,salt='expense-import').loads(signed,max_age=900)
            except (BadSignature,SignatureExpired): raise ValueError('預覽憑證已失效，請重新預覽')
            if expected != digest: raise ValueError('上傳檔案與預覽檔案不同，請重新預覽')
            # End preview SELECT transaction before beginning atomic import.
            conn.rollback()
            conn.start_transaction(); inserted=0; skipped=0
            for day,values in rows:
                cols=['日期']+FIELDS+['備註']; args=[day]+[values[f] for f in FIELDS]+[None]
                sql='INSERT IGNORE INTO `expense_data` ('+','.join('`'+c+'`' for c in cols)+') VALUES ('+','.join(['%s']*len(cols))+')'
                cur.execute(sql,args)
                if cur.rowcount: inserted+=1
                else: skipped+=1
            conn.commit()
            return page('<h1>匯入完成</h1><p class="success">新增 {{n}} 天；略過已存在 {{s}} 天。未覆蓋任何既有資料。</p>',n=inserted,s=skipped)
        secret=os.getenv('APP_SECRET_KEY','')
        if len(secret)<24: raise ValueError('請在 .env 設定至少24字元的 APP_SECRET_KEY')
        token=URLSafeTimedSerializer(secret,salt='expense-import').dumps(digest)
        return page('''<h1>匯入預覽</h1><p>檔案 {{count}} 天，已存在 {{old}} 天，預計新增 {{new}} 天；新增金額合計 NT$ {{total}}。</p><p class="warn">未覆蓋既有日期。請核對預覽後，再重新選取同一檔案按確認；此步驟尚未寫入資料。</p><table><tr><th>日期</th><th>金額合計</th><th>狀態</th></tr>{% for d,v in sample %}<tr><td>{{d}}</td><td>{{v}}</td><td>預計新增</td></tr>{% endfor %}</table><form method="post" enctype="multipart/form-data"><input type="hidden" name="stage" value="apply"><input type="hidden" name="preview_token" value="{{token}}"><label>重新選取同一檔案</label><input type="file" name="file" required><button type="submit">確認匯入（僅新增缺少日期）</button></form>''',count=len(rows),old=len(existing),new=len(fresh),total=f'{total:,}',sample=[(str(d),f'{sum(v.values()):,}') for d,v in fresh[:20]],token=token)
    except Exception as e:
        if conn: conn.rollback()
        return page('<h1>匯入未執行</h1><p class="error">{{error}}</p><p><a href="/auto/import">返回匯入</a></p>',error=str(e)),400
    finally:
        if conn: conn.close()
