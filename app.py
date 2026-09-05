from flask import Flask, render_template, request
import mysql.connector

app = Flask(__name__)


# ==============================
# MySQL 資料庫連線
# ==============================
def get_db_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="mysql12345",
        database="myDB03"
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

        # 建立資料庫連線
        conn = get_db_connection()

        # 建立 Cursor
        cursor = conn.cursor()

        # INSERT SQL
        sql = """
        INSERT INTO expense_data
        (
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
            其他
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
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
            其他
        )

        # 執行 INSERT
        cursor.execute(sql, values)

        # 確認寫入資料庫
        conn.commit()

        # 關閉
        cursor.close()
        conn.close()

        # 顯示成功訊息
        return render_template(
            "message.html",
            message="新增成功",
            message_type="success"
        )

    except Exception as e:

        # 顯示錯誤訊息
        return render_template(
            "message.html",
            message="新增失敗：" + str(e),
            message_type="error"
        )

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
            "其他"
        ]

        sql = """
        SELECT 日期, 交通費, 電話費, 房貸, 用餐,
               保險, 醫療, 水費, 電費, 瓦斯費, 其他
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
# ==============================
# 啟動 Flask
# ==============================
if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )