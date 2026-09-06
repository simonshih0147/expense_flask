from flask import Flask, render_template, request
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


# ==============================
# MySQL 資料庫連線
# ==============================
def get_db_connection():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    return conn


# ==============================
# 首頁
# ==============================
@app.route("/")
def index():
    return render_template("index.html")


# ==============================
# 新增資料表單
# ==============================
@app.route("/insert", methods=["GET"])
def insert_page():
    return render_template("insert.html")


# ==============================
# 新增資料
# 只接受 POST
# ==============================
@app.route("/insert", methods=["POST"])
def insert():

    conn = None
    cursor = None

    try:
        日期 = request.form["日期"]
        交通費 = request.form["交通費"]
        電話費 = request.form["電話費"]
        房貸 = request.form["房貸"]
        用餐 = request.form["用餐"]
        保險 = request.form["保險"]
        醫療 = request.form["醫療"]
        水費 = request.form["水費"]
        電費 = request.form["電費"]
        瓦斯費 = request.form["瓦斯費"]
        其他 = request.form["其他"]
        加油費 = request.form["加油費"]
        稅費 = request.form["稅費"]
        有線電視 = request.form["有線電視"]
        照顧家人 = request.form["照顧家人"]
        備註 = request.form.get("備註", "")

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO `expense_data`
        (
            `日期`,
            `交通費`,
            `電話費`,
            `房貸`,
            `用餐`,
            `保險`,
            `醫療`,
            `水費`,
            `電費`,
            `瓦斯費`,
            `其他`,
            `加油費`,
            `稅費`,
            `有線電視`,
            `照顧家人`,
            `備註`
        )
        VALUES
        (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """

        values = (
            日期,
            交通費,
            電話費,
            房貸,
            用餐,
            保險,
            醫療,
            水費,
            電費,
            瓦斯費,
            其他,
            加油費,
            稅費,
            有線電視,
            照顧家人,
            備註
        )

        cursor.execute(sql, values)
        conn.commit()

        return render_template(
            "message.html",
            message="新增成功",
            message_type="success"
        )

    except Exception as e:

        return render_template(
            "message.html",
            message="新增失敗：" + str(e),
            message_type="error"
        )

    finally:

        if cursor is not None:
            cursor.close()

        if conn is not None and conn.is_connected():
            conn.close()

# ==============================
# 查詢頁面
# ==============================
@app.route("/query", methods=["GET"])
def query_page():
    return render_template("query.html")


# ==============================
# 執行查詢
# ==============================
@app.route("/query", methods=["POST"])
def query():

    try:

        fields = [
            "日期",
            "交通費",
            "電話費",
            "房貸",
            "用餐",
            "保險",
            "醫療",
            "水費",
            "電費",
            "瓦斯費",
            "其他",
            "加油費",
            "稅費",
            "有線電視",
            "照顧家人",
            "備註"
        ]

        sql = """
        SELECT 日期, 交通費, 電話費, 房貸, 用餐,
               保險, 醫療, 水費, 電費, 瓦斯費, 其他,
               加油費 , 稅費 , 有線電視 , 照顧家人 , 備註
        FROM expense_data
        """

        conditions = []
        values = []

        for field in fields:

            value = request.form.get(field, "").strip()

            if value != "":

                if field == "日期":

                    conditions.append(
                        "CAST(日期 AS CHAR) LIKE %s"
                    )

                    values.append(value + "%")
                elif field == "備註":

                    conditions.append(
                        "`備註` LIKE %s"
                    )
                    values.append("%" + value + "%")

                else:

                    conditions.append(
                        f"`{field}` = %s"
                    )

                    values.append(value)

        if conditions:

            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY 日期 DESC"

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(sql, values)

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template(
            "query.html",
            rows=rows,
            searched=True
        )

    except Exception as e:

        return render_template(
            "message.html",
            message="查詢失敗：" + str(e),
            message_type="error"
        )

@app.route("/dashboard")
def dashboard():

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ==========================
        # 1. 本月總支出
        # ==========================
        sql_total = """
        SELECT
            SUM(
                `交通費`
                + `電話費`
                + `房貸`
                + `用餐`
                + `保險`
                + `醫療`
                + `水費`
                + `電費`
                + `瓦斯費`
                + `其他`
                + `加油費`
                + `稅費`
                + `有線電視`
                + `照顧家人`
            )
        FROM `expense_data`
        WHERE YEAR(`日期`) = YEAR(CURDATE())
          AND MONTH(`日期`) = MONTH(CURDATE())
        """

        cursor.execute(sql_total)
        result = cursor.fetchone()

        monthly_total = result[0] if result[0] is not None else 0


        # ==========================
        # 2. 本月統計起訖日期
        # ==========================
        sql_period = """
        SELECT
            DATE_FORMAT(MIN(`日期`), '%Y/%m/%d'),
            DATE_FORMAT(MAX(`日期`), '%Y/%m/%d')
        FROM `expense_data`
        WHERE YEAR(`日期`) = YEAR(CURDATE())
        AND MONTH(`日期`) = MONTH(CURDATE())
        """ 

        cursor.execute(sql_period)
        period_result = cursor.fetchone()

        start_date = period_result[0]
        end_date = period_result[1]


        # ==========================
        # 3. 本月各項支出合計
        # ==========================
        sql_category = """
        SELECT
            SUM(`交通費`),
            SUM(`電話費`),
            SUM(`房貸`),
            SUM(`用餐`),
            SUM(`保險`),
            SUM(`醫療`),
            SUM(`水費`),
            SUM(`電費`),
            SUM(`瓦斯費`),
            SUM(`其他`),
            SUM(`加油費`),
            SUM(`稅費`),
            SUM(`有線電視`),
            SUM(`照顧家人`)
        FROM `expense_data`
        WHERE YEAR(`日期`) = YEAR(CURDATE())
          AND MONTH(`日期`) = MONTH(CURDATE())
        """

        cursor.execute(sql_category)
        category_result = cursor.fetchone()

        category_labels = [
            "交通費",
            "電話費",
            "房貸",
            "用餐",
            "保險",
            "醫療",
            "水費",
            "電費",
            "瓦斯費",
            "其他",
            "加油費",
            "稅費",
            "有線電視",
            "照顧家人"
        ]

        category_values = [
            value if value is not None else 0
            for value in category_result
        ]
                # ==========================
        # 4. 每月支出趨勢
        # ==========================
        sql_monthly_trend = """
        SELECT
            DATE_FORMAT(`日期`, '%Y-%m') AS 月份,
            SUM(
                `交通費`
                + `電話費`
                + `房貸`
                + `用餐`
                + `保險`
                + `醫療`
                + `水費`
                + `電費`
                + `瓦斯費`
                + `其他`
                + `加油費`
                + `稅費`
                + `有線電視`
                + `照顧家人`
            ) AS 月總支出
        FROM `expense_data`
        GROUP BY
            YEAR(`日期`),
            MONTH(`日期`)
        ORDER BY
            YEAR(`日期`),
            MONTH(`日期`)
        """

        cursor.execute(sql_monthly_trend)
        trend_rows = cursor.fetchall()

        print("trend_rows =", trend_rows)

        trend_labels = []
        trend_values = []

        for row in trend_rows:
            trend_labels.append(row[0])
            trend_values.append(
                int(row[1]) if row[1] is not None else 0
            )

        print("trend_labels =", trend_labels)
        print("trend_values =", trend_values)

        # ==========================================
        # 5. 7、8、9 月累積支出
        # ==========================================
        sql_three_month = """
        SELECT
            SUM(`交通費`),
            SUM(`電話費`),
            SUM(`房貸`),
            SUM(`用餐`),
            SUM(`保險`),
            SUM(`醫療`),
            SUM(`水費`),
            SUM(`電費`),
            SUM(`瓦斯費`),
            SUM(`其他`),
            SUM(`加油費`),
            SUM(`稅費`),
            SUM(`有線電視`),
            SUM(`照顧家人`)
        FROM `expense_data`
        WHERE `日期` >= '2026-07-01'
          AND `日期` < DATE_ADD(CURDATE(), INTERVAL 1 DAY)
        """

        cursor.execute(sql_three_month)
        three_month_result = cursor.fetchone()

        three_month_values = [
            int(value) if value is not None else 0
            for value in three_month_result
        ]


        # ==========================================
        # 6. 全部期間支出
        # ==========================================
        sql_all_period = """
        SELECT
            SUM(`交通費`),
            SUM(`電話費`),
            SUM(`房貸`),
            SUM(`用餐`),
            SUM(`保險`),
            SUM(`醫療`),
            SUM(`水費`),
            SUM(`電費`),
            SUM(`瓦斯費`),
            SUM(`其他`),
            SUM(`加油費`),
            SUM(`稅費`),
            SUM(`有線電視`),
            SUM(`照顧家人`)
        FROM `expense_data`
        """

        cursor.execute(sql_all_period)
        all_period_result = cursor.fetchone()

        all_period_values = [
            int(value) if value is not None else 0
            for value in all_period_result
        ]


        # ==========================================
        # 7. 全部資料起訖日期
        # ==========================================
        sql_all_dates = """
        SELECT
            DATE_FORMAT(MIN(`日期`), '%Y/%m/%d'),
            DATE_FORMAT(MAX(`日期`), '%Y/%m/%d')
        FROM `expense_data`
        """

        cursor.execute(sql_all_dates)
        all_dates = cursor.fetchone()

        all_start_date = all_dates[0]
        all_end_date = all_dates[1]

        return render_template(
            "dashboard.html",
            monthly_total=monthly_total,
            start_date=start_date,
            end_date=end_date,

            category_labels=category_labels,
            category_values=category_values,

            trend_labels=trend_labels,
            trend_values=trend_values,

            three_month_values=three_month_values,

            all_period_values=all_period_values,
            all_start_date=all_start_date,
            all_end_date=all_end_date
        )

    except Exception as e:
        return render_template(
            "message.html",
            message="Dashboard 查詢失敗：" + str(e),
            message_type="error"
        )

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None and conn.is_connected():
            conn.close()
# 啟動 Flask
# ==============================
if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )