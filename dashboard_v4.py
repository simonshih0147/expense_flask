"""Additive read-only expense dashboard. Register with app.register_blueprint(dashboard_v4_bp)."""
import os
from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template_string, request
import mysql.connector


dashboard_v4_bp = Blueprint('dashboard_v4', __name__)
CATEGORIES = ['交通費','電話費','房貸','用餐','保險','醫療','水費','電費','瓦斯費','其他','加油費','稅費','有線電視','照顧家人']

PAGE = r'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>年度消費分析 Dashboard V4</title><script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>*{box-sizing:border-box}body{margin:0;background:#f0f4fa;color:#173453;font-family:Arial,'Microsoft JhengHei',sans-serif}.wrap{max-width:1160px;margin:25px auto;padding:0 18px}h1{text-align:center;font-size:28px}.panel{background:#fff;border-radius:14px;padding:24px;box-shadow:0 3px 16px #1c3d5912;margin:20px 0}.filters{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}label{display:block;font-weight:bold;margin-bottom:8px}select,button{width:100%;padding:11px;border:1px solid #b9c7d8;border-radius:7px;background:white;font-size:16px}button{background:#1768b4;color:white;cursor:pointer;border:0}.stats{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}.amount{font-size:34px;color:#1768b4;font-weight:bold}.sub{color:#64748b;font-size:14px}.chart-box{height:430px;position:relative}.back{color:#1768b4}.notice{background:#fff5dc;padding:10px;border-radius:8px;margin-top:10px}@media(max-width:760px){.filters{grid-template-columns:repeat(2,minmax(0,1fr))}.chart-box{height:320px}}</style></head><body><main class="wrap"><a class="back" href="/dashboard">← 返回原 Dashboard</a><h1>個人消費記帳及統計｜年度分析 V4</h1>
<section class="panel"><form method="get" action="{{ url_for('dashboard_v4.dashboard_v4') }}" class="filters"><div><label for="year">年度</label><select name="year" id="year">{% for y in years %}<option value="{{y}}" {% if y==year %}selected{% endif %}>{{y}} 年</option>{% endfor %}</select></div><div><label for="category">消費分類</label><select name="category" id="category"><option value="全部分類" {% if category=='全部分類' %}selected{% endif %}>全部分類</option>{% for c in categories %}<option value="{{c}}" {% if c==category %}selected{% endif %}>{{c}}</option>{% endfor %}</select></div><div><label for="chart">圖表</label><select name="chart" id="chart"><option value="line" {% if chart=='line' %}selected{% endif %}>折線圖</option><option value="bar" {% if chart=='bar' %}selected{% endif %}>長條圖</option></select></div><div><label>&nbsp;</label><button type="submit">查詢統計</button></div></form></section>
<section class="panel"><div class="stats"><div><div class="sub">{{year}} 年｜{{category}}｜年度累計</div><div class="amount">NT$ {{'{:,.0f}'.format(total)}}</div></div><div><div class="sub">資料筆數</div><strong>{{row_count}} 筆</strong><div class="sub">期間：{{year}}/01/01～{{year}}/12/31</div></div></div>{% if row_count == 0 %}<div class="notice">此年度尚無資料，圖表會顯示零值；不代表全年支出為零。</div>{% endif %}</section>
<section class="panel"><h2>{{year}} 年各月份{{category}}支出趨勢</h2><div class="chart-box"><canvas id="expenseChart" role="img" aria-label="年度各月支出統計"></canvas></div><p class="sub">資料來源：MySQL mydb03.expense_data。未有資料的月份以 0 顯示；尚未結束的月份不代表完整月結算。</p></section></main>
<script>const labels={{labels|tojson}};const values={{values|tojson}};const chartType={{chart|tojson}};const ctx=document.getElementById('expenseChart');new Chart(ctx,{type:chartType,data:{labels,datasets:[{label:'支出金額（NT$）',data:values,borderColor:'#247fca',backgroundColor:'rgba(52,152,219,.3)',borderWidth:3,fill:chartType==='line',tension:.25,pointRadius:5}]},options:{responsive:true,maintainAspectRatio:false,plugins:{tooltip:{callbacks:{label:c=>'NT$ '+Number(c.raw).toLocaleString('zh-TW')}},legend:{position:'top'}},scales:{y:{beginAtZero:true,ticks:{callback:v=>'NT$ '+Number(v).toLocaleString('zh-TW')}},x:{title:{display:true,text:'月份'}}}}});</script></body></html>'''


def connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST','127.0.0.1'),
        port=int(os.getenv('DB_PORT','3306')),
        user=os.getenv('DB_USER','root'),
        password=os.getenv('DB_PASSWORD',''),
        database=os.getenv('DB_NAME','mydb03'),
        connection_timeout=10,
    )


@dashboard_v4_bp.route('/dashboard-v4', methods=['GET'])
def dashboard_v4():
    today_year = date.today().year
    years = list(range(2016, max(today_year,2026)+1))
    try:
        year = int(request.args.get('year','2026'))
    except (TypeError,ValueError):
        year = 2026
    if year not in years:
        year = 2026
    category = request.args.get('category','全部分類')
    if category not in CATEGORIES and category != '全部分類':
        category = '全部分類'
    chart = request.args.get('chart','line')
    if chart not in ('line','bar'):
        chart = 'line'

    # Category names are whitelisted; values are SQL parameters. No user SQL is interpolated.
    expr = (' + '.join('COALESCE(`'+c+'`,0)' for c in CATEGORIES)
            if category == '全部分類' else 'COALESCE(`'+category+'`,0)')
    sql = f'''SELECT MONTH(`日期`) AS m, COUNT(*) AS n, SUM({expr}) AS amount
              FROM `expense_data` WHERE `日期` >= %s AND `日期` < %s
              GROUP BY MONTH(`日期`) ORDER BY m'''
    conn = None
    cursor = None
    try:
        conn = connection()
        cursor = conn.cursor()
        cursor.execute(sql, (f'{year}-01-01',f'{year+1}-01-01'))
        rows = cursor.fetchall()
    except mysql.connector.Error as exc:
        return '資料庫查詢失敗：請確認 .env、MySQL 服務及資料表欄位。錯誤類型：'+type(exc).__name__, 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    values = [0]*12
    count = 0
    for m,n,amount in rows:
        values[int(m)-1] = float(amount or Decimal(0))
        count += int(n)
    return render_template_string(PAGE, years=years, year=year, categories=CATEGORIES,
                                  category=category, chart=chart, labels=[f'{i} 月' for i in range(1,13)],
                                  values=values, total=sum(values), row_count=count)
