"""Dashboard V5.3: read-only cross-year/category trends; independent of V5.2."""
from datetime import date, timedelta
from flask import Blueprint, render_template, request
import mysql.connector
from dashboard_v5 import CATEGORIES, get_connection

bp = Blueprint('dashboard_v53', __name__)

@bp.route('/dashboard-v53', methods=['GET'])
def dashboard_v53():
    today = date.today()
    category = request.args.get('category', '全部分類')
    if category not in CATEGORIES and category != '全部分類':
        category = '全部分類'
    granularity = request.args.get('granularity', 'month')
    if granularity not in ('year', 'month', 'day'):
        granularity = 'month'
    chart_type = request.args.get('chart_type', 'line')
    if chart_type not in ('line', 'bar', 'area', 'pie', 'pareto'):
        chart_type = 'line'
    default_start = date(today.year - 2, 1, 1)
    def parse_date(value, default):
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            return default
    start = parse_date(request.args.get('start'), default_start)
    end = parse_date(request.args.get('end'), today)
    if start > end:
        start, end = end, start
    # Bound the requested range so charts stay usable, including daily mode.
    if (end - start).days > 365 * 15 + 4:
        start = end - timedelta(days=365 * 15 + 4)
    # Column names are selected exclusively from the trusted whitelist above.
    amount_expr = (' + '.join(f'COALESCE(`{c}`,0)' for c in CATEGORIES)
                   if category == '全部分類' else f'COALESCE(`{category}`,0)')
    date_expr = {'year': 'DATE_FORMAT(`日期`, %s)',
                 'month': 'DATE_FORMAT(`日期`, %s)',
                 'day': 'DATE_FORMAT(`日期`, %s)'}[granularity]
    date_format = {'year': '%Y', 'month': '%Y-%m', 'day': '%Y-%m-%d'}[granularity]
    sql = (f'SELECT {date_expr} AS period, SUM({amount_expr}) AS amount, COUNT(*) AS cnt '
           'FROM `expense_data` WHERE `日期` >= %s AND `日期` < %s '
           'GROUP BY period ORDER BY period')
    conn = cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (date_format, start.isoformat(), (end + timedelta(days=1)).isoformat()))
        rows = cursor.fetchall()
    except mysql.connector.Error:
        return '資料庫查詢失敗，請檢查 MySQL 與資料表設定。', 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
    # Category Pareto: compare expense categories across the entire selected date range.
    # Column identifiers are strictly taken from CATEGORIES; date values are parameters.
    pareto_labels = list(CATEGORIES)
    pareto_amounts = []
    if chart_type == 'pareto':
        sums = ', '.join(f'SUM(COALESCE(`{c}`, 0))' for c in CATEGORIES)
        category_sql = (f'SELECT {sums} FROM `expense_data` '
                        'WHERE `日期` >= %s AND `日期` < %s')
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(category_sql, (start.isoformat(), (end + timedelta(days=1)).isoformat()))
            result = cursor.fetchone()
            pareto_amounts = [float(v or 0) for v in result] if result else [0] * len(CATEGORIES)
        except mysql.connector.Error:
            return '分類柏拉圖查詢失敗，請檢查 MySQL 與資料表設定。', 500
        finally:
            if cursor is not None:
                cursor.close()
                cursor = None
            if conn is not None:
                conn.close()
                conn = None
    # Fill missing periods with 0 only between the requested start and end.
    values = {str(k): int(v or 0) for k, v, _ in rows}
    labels = []
    cursor_date = start
    while cursor_date <= end:
        if granularity == 'year':
            key = cursor_date.strftime('%Y')
            cursor_date = date(cursor_date.year + 1, 1, 1)
        elif granularity == 'month':
            key = cursor_date.strftime('%Y-%m')
            cursor_date = (date(cursor_date.year + 1, 1, 1) if cursor_date.month == 12
                           else date(cursor_date.year, cursor_date.month + 1, 1))
        else:
            key = cursor_date.strftime('%Y-%m-%d')
            cursor_date += timedelta(days=1)
        labels.append(key)
    amounts = [values.get(k, 0) for k in labels]
    return render_template('dashboard_v53.html', categories=CATEGORIES,
                           category=category, granularity=granularity, chart_type=chart_type,
                           start=start.isoformat(), end=end.isoformat(),
                           labels=labels, amounts=amounts,
                           pareto_labels=pareto_labels, pareto_amounts=pareto_amounts,
                           total=sum(amounts), row_count=sum(int(row[2]) for row in rows),
                           latest_period=end >= today.replace(day=1))
