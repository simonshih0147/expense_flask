"""Read-only annual dashboard V5; preserves existing V4 and original dashboard."""
import os
from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template, request
import mysql.connector

bp = Blueprint('dashboard_v5', __name__)
CATEGORIES = ['交通費','電話費','房貸','用餐','保險','醫療','水費','電費','瓦斯費','其他','加油費','稅費','有線電視','照顧家人']
CHARTS = ('line','bar','pie','pareto')


def get_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST', '127.0.0.1'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'mydb03'),
        connection_timeout=10,
    )


@bp.route('/dashboard-v5', methods=['GET'])
def dashboard_v5():
    years = list(range(2016, max(date.today().year, 2026) + 1))
    try:
        year = int(request.args.get('year', '2026'))
    except (TypeError, ValueError):
        year = 2026
    if year not in years:
        year = 2026
    category = request.args.get('category', '全部分類')
    if category != '全部分類' and category not in CATEGORIES:
        category = '全部分類'
    chart = request.args.get('chart', 'line')
    if chart not in CHARTS:
        chart = 'line'

    # One parameterized, read-only SQL query retrieves all 14 categories by month.
    sql = ('SELECT MONTH(`日期`) AS month_no, COUNT(*) AS days, '
           + ', '.join('SUM(COALESCE(`'+c+'`,0))' for c in CATEGORIES)
           + ' FROM `expense_data` WHERE `日期` >= %s AND `日期` < %s '
           'GROUP BY MONTH(`日期`) ORDER BY month_no')
    conn = cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (f'{year}-01-01', f'{year+1}-01-01'))
        rows = cursor.fetchall()
    except mysql.connector.Error:
        return '資料庫查詢失敗：請確認 MySQL、.env 與資料表欄位。', 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    month_categories = [[0] * len(CATEGORIES) for _ in range(12)]
    month_counts = [0] * 12
    for month, days, *amounts in rows:
        idx = int(month) - 1
        month_counts[idx] = int(days)
        month_categories[idx] = [int(x or 0) for x in amounts]
    totals = [sum(month_categories[m][i] for m in range(12)) for i in range(len(CATEGORIES))]
    selected_index = CATEGORIES.index(category) if category != '全部分類' else None
    month_values = [sum(row) if selected_index is None else row[selected_index]
                    for row in month_categories]
    year_total = sum(totals)
    selected_total = sum(month_values)
    return render_template('dashboard_v5.html', years=years, year=year,
                           category=category, categories=CATEGORIES, chart=chart,
                           row_count=sum(month_counts), year_total=year_total,
                           selected_total=selected_total, month_values=month_values,
                           category_totals=totals)
