import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import re
import numpy as np
from PIL import Image
from datetime import datetime
import easyocr

# データベース接続
con = sqlite3.connect("room.db")
cur = con.cursor()

# テーブル作成
cur.execute("""
CREATE TABLE IF NOT EXISTS follow_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    follow_count INTEGER NOT NULL,
    follower_count INTEGER NOT NULL
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS monthly_goals (
    month TEXT PRIMARY KEY,
    follow_goal INTEGER,
    follower_goal INTEGER
)""")

con.commit()

# サイドバー
st.sidebar.title("メニュー")
page = st.sidebar.radio("ページを選択", ["ホーム", "フォロ活：目標設定", "フォロ活：データ記録", "商品データ記録", "CSVアップロード", "グラフ表示"])

# ホーム
if page == "ホーム":
    st.title("楽天ROOM フォロワー推移記録アプリ")
    st.markdown("""
        このアプリでは、楽天ROOMのフォロー数・フォロワー数を記録し、
        時系列でグラフ表示・CSVの保存ができます。
        左のメニューから操作してください。
    """)

# 目標設定
elif page == "フォロ活：目標設定":
    st.title("🎯 フォロ活：目標設定")
    goal_date = st.date_input("目標の年月を選択")
    goal_month = goal_date.strftime("%Y-%m")
    follow_goal = st.number_input("フォロー数の目標", min_value=0)
    follower_goal = st.number_input("フォロワー数の目標", min_value=0)

    if st.button("目標を保存"):
        cur.execute("REPLACE INTO monthly_goals(month, follow_goal, follower_goal) VALUES(?,?,?)",
                    (goal_month, follow_goal, follower_goal))
        con.commit()
        st.success("目標を保存しました！")

# データ記録
elif page == "フォロ活：データ記録":
    st.title("📋 フォロ活：データ記録")
    date = st.date_input("日付を選択")
    follow = st.number_input("フォロー数", min_value=0)
    follower = st.number_input("フォロワー数", min_value=0)

    if st.button("記録する"):
        cur.execute("INSERT INTO follow_stats(date, follow_count, follower_count) VALUES(?,?,?)",
                    (str(date), follow, follower))
        con.commit()
        st.success("記録しました！")

    st.markdown("---")
    df = pd.read_sql_query("SELECT * FROM follow_stats ORDER BY date", con)
    st.subheader("記録済データ")
    st.dataframe(df)

    st.subheader("データ削除")
    if not df.empty:
        options = df.apply(lambda row: f"{row['id']}:  {row['date']} (F: {row['follow_count']} / Fr: {row['follower_count']})", axis=1)
        selected = st.selectbox("削除するデータを選択", options)
        selected_id = int(selected.split(":")[0])
        if st.button("削除する"):
            cur.execute("DELETE FROM follow_stats WHERE id = ?", (selected_id,))
            con.commit()
            st.success(f"id = {selected_id} のデータを削除しました！")

# データ記録2（OCR）
elif page == "商品データ記録":
    st.title("楽天ROOM 分析データ更新")

    # --- ① 画像アップロード＆OCR処理 ---
    st.subheader("🖼️ 商品画像から情報抽出")
    uploaded_image = st.file_uploader("商品画像をアップロード", type=["png", "jpg", "jpeg"])
    

    if uploaded_image:
        image = Image.open(uploaded_image)
        st.image(image, caption="アップロードされた画像", use_container_width=True)

        reader = easyocr.Reader(['ja'], gpu=False)
        result = reader.readtext(np.array(image), detail=0)
        text = "\n".join(result)

        # st.markdown("#### 抽出されたテキスト")
        # st.code(text)

        match1 = re.search(r'(\d+)\s*口', text)
        match2 = re.search(r'価\s*(.+)', text)
        likes_detected = int(match1.group(1)) if match1 else None
        shop_detected = match2.group(1) if match2 else ""

        st.markdown(f"**抽出されたいいね数**: {likes_detected if likes_detected else '未検出'}")
        st.markdown(f"**抽出されたショップ名（OCR）**: {shop_detected if shop_detected else '未検出'}")

        likes_input = st.text_input("いいね数を入力（必要に応じて入力）", value=likes_detected)
        shop_name_input = st.text_input("ショップ名を入力（必要に応じて入力）", value=shop_detected)
        memo_text = st.text_area("画像に関するメモを入力", key="memo_input")

        if st.button("この情報をデータベースに登録"):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    filename TEXT,
                    likes INTEGER,
                    shop TEXT,
                    memo TEXT,
                    created_date TEXT,
                    PRIMARY KEY (filename, likes, created_date)
                )
            """)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                "INSERT INTO posts (filename, likes, shop, memo, created_date) VALUES (?, ?, ?, ?, ?)",
                (uploaded_image.name, int(likes_input), shop_name_input, memo_text, now)
            )
            con.commit()
            st.success("画像情報をデータベースに登録しました！")

elif page == "CSVアップロード":
    st.subheader("📄 shop.csvをアップロードして登録")
    uploaded_csv = st.file_uploader("shop.csv をアップロード", type=["csv"], key="csv_uploader")

    if uploaded_csv:
        df_csv = pd.read_csv(uploaded_csv)
        st.dataframe(df_csv)

        if st.button("CSVデータをデータベースに保存"):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS shop_csv (
                    shop_name TEXT,
                    clicks INTEGER
                )
            """)
            cur.execute("DELETE FROM shop_csv")
            for _, row in df_csv.iterrows():
                cur.execute("INSERT INTO shop_csv (shop_name, clicks) VALUES (?, ?)", (row["shop_name"], row["clicks"]))
            con.commit()
            st.success("CSVデータをshop_csvテーブルに保存しました！")

# グラフ表示
elif page == "グラフ表示":
    st.title("📈 フォロ活の進捗")
    latest = pd.read_sql_query("SELECT * FROM follow_stats ORDER BY date DESC LIMIT 1", con)
    latest_date = pd.to_datetime(latest["date"][0])
    latest_month = latest_date.strftime("%Y-%m")
    goal = pd.read_sql_query("SELECT * FROM monthly_goals WHERE month = ?", con, params=(latest_month,))

    if not goal.empty:
        follow_now = latest["follow_count"][0]
        follower_now = latest["follower_count"][0]
        follow_goal = goal["follow_goal"][0]
        follower_goal = goal["follower_goal"][0]
        st.metric("フォロー数の進捗", f"{follow_now} / {follow_goal}", delta=f"{follow_now - follow_goal}")
        st.metric("フォロワー数の進捗", f"{follower_now} / {follower_goal}", delta=f"{follower_now - follower_goal}")
    else:
        st.warning(f"{latest_month}の目標が未設定です")

    df = pd.read_sql_query("SELECT * FROM follow_stats ORDER BY date", con)
    st.dataframe(df)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("CSVをダウンロード", csv, "follow_stats.csv", "text/csv")

    df["follow_diff"] = df["follow_count"].diff().fillna(0)
    df["follower_diff"] = df["follower_count"].diff().fillna(0)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    df_diff = df.dropna(subset=["follow_diff", "follower_diff"])

    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["date_str"], y=df["follow_diff"], mode='lines+markers', name='フォロー数'))
        fig.add_trace(go.Scatter(x=df["date_str"], y=df["follower_diff"], mode='lines+markers', name='フォロワー数'))
        fig.update_layout(xaxis=dict(type="category"))
        st.plotly_chart(fig)

        try:
            fig.write_image("follow_chart.png")
        except Exception:
            st.warning("画像保存には kaleido パッケージが必要です。`pip install -U kaleido` を実行してください。")

        #反応率ランキング
        st.title("📊 反応率ランキング TOP10")
        query = """
                SELECT
                a.shop_name,
                MAX(a.clicks) AS clicks,
                SUM(b.likes) AS total_likes,
                CAST(MAX(a.clicks) AS FLOAT) / NULLIF(SUM(b.likes), 0) AS reaction_rate
                FROM shop_csv a
                LEFT JOIN (
                    SELECT p.filename, p.likes, p.shop, p.created_date
                    FROM posts p
                    INNER JOIN (
                        SELECT filename, shop, MAX(created_date) AS max_date
                        FROM posts
                        GROUP BY filename, shop
                        ) latest
                ON p.filename = latest.filename AND p.shop = latest.shop AND p.created_date = latest.max_date
                ) b
                ON a.shop_name = b.shop
                GROUP BY a.shop_name
                ORDER BY reaction_rate DESC
                LIMIT 10;
                """
        df = pd.read_sql_query(query, con)
        con.close()
        # データ表示
        st.dataframe(df)
        # グラフ表示（Plotly）
        fig = px.bar(df, x="reaction_rate", y="shop_name", orientation="h",
             labels={"reaction_rate": "反応率", "shop_name": "ショップ名"},
             title="反応率ランキング TOP10")
        fig.update_layout(yaxis=dict(autorange="reversed"))  # 上位を上に
        st.plotly_chart(fig)


        
