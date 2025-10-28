import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import os
from PIL import Image
import pytesseract
import re
from datetime import datetime
import plotly.express as px

con = sqlite3.connect("room.db")
cur = con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS follow_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    follow_count INTEGER NOT NULL,
    follower_count INTEGER NOT NULL
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS monthly_goals (
    month TEXT PRIMARY KEY,
    follow_goal INTEGER,
    follower_goal INTEGER
)""")

con.commit()

#サイドバーでページ選択
st.sidebar.title("メニュー")
page = st.sidebar.radio("ページを選択", ["ホーム", "目標設定", "データ記録", "データ記録2", "グラフ表示"])

#ホームページ
if page == "ホーム":
    st.title("楽天ROOM フォロワー推移記録アプリ")
    st.markdown("""
                このアプリでは、楽天ROOMのフォロー数・フォロワー数を記録し、
                時系列でグラフ表示・CSVの保存ができます。
                左のメニューから操作してください。
                """)
    
#目標設定ページ
elif page == "目標設定":
    st.title("🎯 目標設定")
    goal_date = st.date_input("目標の年月を選択")
    goal_month = goal_date.strftime("%Y-%m")
    follow_goal = st.number_input("フォロー数の目標", min_value=0)
    follower_goal = st.number_input("フォロワー数の目標", min_value=0)

    if st.button("目標を保存"):
                cur.execute("REPLACE INTO monthly_goals(month, follow_goal, follower_goal) VALUES(?,?,?)",
                            (goal_month, follow_goal,follower_goal))
                con.commit()
                st.success("目標を保存しました！")

#データ記録ページ
elif page == "データ記録":
    st.title("📋 データ記録")
    date = st.date_input("日付を選択")
    follow = st.number_input("フォロー数", min_value=0)
    follower = st.number_input("フォロワー数", min_value = 0)

    if st.button("記録する"):
        cur.execute("INSERT INTO follow_stats(date, follow_count, follower_count) VALUES(?,?,?)",
                    (str(date), follow, follower))
        con.commit()
        st.success("記録しました！")

    st.markdown("---")
    #データ一覧表示
    df= pd.read_sql_query("SELECT * FROM follow_stats ORDER BY date", con)
    st.subheader("記録済データ")
    st.dataframe(df)

    #削除機能
    st.subheader("データ削除")
    if not df.empty:
        #削除対象を選択(idと日付で表示)
        options = df.apply(lambda row:f"{row['id']}:  {row['date']} (  F : {row['follow_count']} /   Fr : {row['follower_count']})",axis=1)
        selected = st.selectbox("削除するデータを選択", options)

        #選択されたidを抽出
        selected_id = int(selected.split(":")[0])
        if st.button("削除する"):
            cur.execute("DELETE FROM follow_stats WHERE id = ?", (selected_id,))
            con.commit()
            st.success(f"id = {selected_id}のデータを削除しました！")

# 商品情報_データ記録
elif page == "データ記録2":
    st.title("楽天ROOM 分析データ更新")
    # memo_input = st.text_area("商品名を入力してください","")

     # 画像フォルダのパス（Pythonファイルと同階層の image フォルダ）
    folder_path = "image"

    # フォルダ内の画像一覧を表示
    image_files = [f for f in os.listdir(folder_path) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    memo_dict = {} #画像ごとのメモを格納する辞書

    if image_files:
        st.subheader("登録予定の画像一覧")
        for i, filename in enumerate(image_files):
            image_path = os.path.join(folder_path, filename)
            st.image(image_path, caption=filename, use_container_width=True)
            memo_key = f"memo_{filename}"
            memo_text = st.text_area(f"{filename} のメモを入力", key=memo_key)
            memo_dict[filename] = memo_text
        st.info("上記の画像をデータベースに登録します。内容をご確認ください。")  
          
    else:
         st.warning("画像フォルダに登録対象の画像がありません。")

    if st.button("画像フォルダをスキャンしてデータベースに登録"):
        # データベース接続とテーブル作成
        conn = sqlite3.connect("room.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                filename TEXT,
                likes INTEGER,
                shop TEXT,
                memo TEXT,
                created_date TEXT,
                PRIMARY KEY (filename, likes, created_date)
            )
        """)
    
        # フォルダ内の画像を処理
        for filename in os.listdir(folder_path):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                image_path = os.path.join(folder_path, filename)
                img = Image.open(image_path)

                # OCRでテキスト抽出
                text = pytesseract.image_to_string(img, lang='jpn')

                # いいね数の抽出（♡数字）
                match1 = re.search(r'[♡♥❤〇の]\s*(\d+)', text)
                match2 = re.search(r'価 \s*(.+)', text)
                likes = int(match1.group(1)) if match1 else None
                shop = match2.group(1) if match2 else None

                # 現在の日時を取得
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # データベースに保存
                memo = memo_dict.get(filename, "")
                cursor.execute(
                    "INSERT INTO posts (filename, likes, shop, memo, created_date) VALUES (?, ?, ?, ?, ?)",
                    (filename, likes, shop, memo, now)
                )

        # 保存して終了
        conn.commit()
        conn.close()

        st.success("商品情報の登録が完了しました！")

#グラフ表示ページ
elif page == "グラフ表示":
    st.title("📈 フォロ活の進捗")
    # 最新の記録を取得 
    latest = pd.read_sql_query("SELECT * FROM follow_stats ORDER BY date DESC LIMIT 1", con)
    latest_date = pd.to_datetime(latest["date"][0])
    latest_month = latest_date.strftime("%Y-%m")

    # 目標値を取得
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
    # CSVダウンロード
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("CSVをダウンロード", csv, "follow_stats.csv", "text/csv")
    
    #グラフ使用項目の作成
    df["follow_diff"] = df["follow_count"].diff().fillna(0)
    df["follower_diff"] = df["follower_count"].diff().fillna(0)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")
    df_diff = df.dropna(subset=["follow_diff", "follower_diff"])
 
    if not df.empty:    
        #表の作成
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["date_str"], y=df["follow_diff"], mode= 'lines+markers', name = 'フォロー数'))
        fig.add_trace(go.Scatter(x=df["date_str"], y=df["follower_diff"], mode= 'lines+markers', name = 'フォロワー数'))
        fig.update_layout(
            xaxis=dict(
                type="category"
            )
        )
        st.plotly_chart(fig)
        
        # グラフ画像保存（オプション）
        try:
            fig.write_image("follow_chart.png")
        except Exception as e:
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


        
