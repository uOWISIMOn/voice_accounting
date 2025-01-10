import tkinter as tk
import pyaudio
import wave
import threading
import sqlite3
import os
from datetime import datetime

from google.cloud import speech
import openai

# --------- Google Cloud & OpenAI 認証情報の設定 ------------
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""
openai.api_key = ""

DB_NAME = "records.db"
TABLE_NAME = "records"
category = ["飲食", "日用品", "ライフライン", "家賃", "娯楽消費", "ショッピング"]
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def init_db():
    """データベースを初期化（存在しない場合は作成）し、テーブルを作成"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dateTime TEXT,
            itemName TEXT,
            amount REAL,
            currency TEXT,
            category TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_record(record):
    """データベースにレコードを挿入"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO {TABLE_NAME}(dateTime, itemName, amount, currency, category)
        VALUES (?, ?, ?, ?, ?)
    """, (record.get("dateTime", ""),
          record.get("itemName", ""),
          record.get("amount", 0),
          record.get("currency", ""),
          record.get("category", "")))
    conn.commit()
    conn.close()

def get_all_records():
    """データベース内の全てのレコードを取得"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE_NAME}")
    rows = cursor.fetchall()
    conn.close()
    return rows

def clear_all_records():
    """データベース内の全てのレコードを削除"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {TABLE_NAME}")
    conn.commit()
    conn.close()

def analyze_records():
    """
    データベース内の総額およびカテゴリごとの金額と割合を統計。
    戻り値：(total_amount, [(category, cat_amount, ratio), ...]) 
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. 総額を統計
    cursor.execute(f"SELECT SUM(amount) FROM {TABLE_NAME}")
    row = cursor.fetchone()
    total_amount = row[0] if row[0] else 0.0

    # 2. カテゴリごとに金額を統計
    cursor.execute(f"SELECT category, SUM(amount) FROM {TABLE_NAME} GROUP BY category")
    cat_rows = cursor.fetchall()  # [(category, cat_sum), ...]
    conn.close()

    # 3. 割合を計算
    results = []
    for cat, cat_sum in cat_rows:
        if cat_sum is None:
            cat_sum = 0.0
        ratio = 0.0 if total_amount == 0 else (cat_sum / total_amount * 100)
        results.append((cat, cat_sum, ratio))

    return total_amount, results

def call_google_stt(wav_filename, rate=16000):
    """Google Cloud Speech-to-Text を呼び出して音声ファイルを認識し、文字列を返す"""
    client = speech.SpeechClient()
    with open(wav_filename, 'rb') as f:
        audio_data = f.read()

    audio = speech.RecognitionAudio(content=audio_data)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=rate,
        language_code='ja-JP'
    )

    response = client.recognize(config=config, audio=audio)
    transcript = ""
    for result in response.results:
        transcript += result.alternatives[0].transcript
    return transcript.strip()

def call_openai_gpt(transcript):
    """OpenAI GPT（gpt-3.5-turbo）を呼び出して音声テキストを解析し、JSON形式の記帳情報を返す"""
    # prompt内でGPTにJSONを返すよう指示
    prompt = f"""
あなたは記帳アシスタントであり、ユーザーの自然言語から記帳情報を解析する必要があります。以下のJSON形式で返してください：
{{
  "dateTime": "YYYY-MM-DD HH:mm:ss",
  "itemName": "...",
  "amount": 0,
  "currency": "...",
  "category": "..."
}}
ユーザーが話した内容: "{transcript}"
datetimeを{current_time}とし、以下のカテゴリから選んでください："{category}"。
"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
          {"role": "system", "content": "You are a helpful accounting assistant."},
          {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=300
    )
    answer = response.choices[0].message["content"].strip()

    import json
    try:
        record = json.loads(answer)
        return record
    except:
        return {
            "dateTime": "",
            "itemName": "",
            "amount": 0,
            "currency": "",
            "category": ""
        }
        
class VoiceRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("音声記帳デモ")

        # データベースの初期化
        init_db()

        # 録音関連のパラメータ
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.output_filename = "recorded.wav"

        # PyAudioの設定
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []

        # 録音状態のフラグ
        self.is_recording = False

        # GUI: 状態ラベル
        self.status_label = tk.Label(root, text="録音準備中...", fg="blue")
        self.status_label.pack(pady=5)

        # 録音ボタン
        self.record_button = tk.Button(root, text="開始録音", command=self.toggle_recording)
        self.record_button.pack(pady=5)

        # 結果表示ラベル
        self.result_label = tk.Label(root, text="", fg="green", wraplength=400)
        self.result_label.pack(pady=5)

        # データベース削除ボタン
        self.clear_db_button = tk.Button(root, text="データベースをクリア", command=self.clear_database)
        self.clear_db_button.pack(pady=5)
        
        self.delete_button = tk.Button(root, text="選択したデータを削除", command=self.delete_selected_record)
        self.delete_button.pack(pady=5)

        # データ分析ボタン
        self.analyze_button = tk.Button(root, text="データを分析", command=self.analyze_data)
        self.analyze_button.pack(pady=5)

        # データベースの記録を表示するリストボックス
        self.records_listbox = tk.Listbox(root, width=80)
        self.records_listbox.pack(pady=5)

        # 初期状態での記録表示
        self.show_all_records()

    def toggle_recording(self):
        """録音の開始・停止を切り替える"""
        if self.is_recording:
            # 現在録音中 → 録音を停止
            self.stop_recording()
            self.record_button.config(text="開始録音")
        else:
            # 現在録音中ではない → 録音を開始
            self.start_recording()
            self.record_button.config(text="停止録音")

    def start_recording(self):
        """録音を開始"""
        self.stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        self.frames = []
        self.is_recording = True
        self.status_label.config(text="録音中...", fg="red")

        # 録音スレッドを開始
        self.record_thread = threading.Thread(target=self.record)
        self.record_thread.start()

    def record(self):
        """録音データを収集"""
        while self.is_recording:
            data = self.stream.read(self.chunk)
            self.frames.append(data)
        # 録音終了後、データを保存
        self.save_wav()

    def stop_recording(self):
        """録音を停止"""
        self.is_recording = False
        self.status_label.config(text="録音停止、認識中...", fg="blue")

    def save_wav(self):
        """録音データを保存して音声処理を開始"""
        self.stream.stop_stream()
        self.stream.close()
        wf = wave.open(self.output_filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.audio.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.frames))
        wf.close()

        # 録音保存後、Google STTで処理
        self.root.after(500, self.process_speech)

    def process_speech(self):
        """音声認識を処理"""
        try:
            transcript = call_google_stt(self.output_filename, self.rate)
            if not transcript:
                self.status_label.config(text="音声が認識されませんでした", fg="orange")
                self.result_label.config(text="")
                return

            self.status_label.config(text="認識結果：" + transcript, fg="green")
            # GPTで解析
            record_data = call_openai_gpt(transcript)
            insert_record(record_data)

            self.result_label.config(text=f"GPT解析結果:\n{record_data}")

            # 記録を更新
            self.show_all_records()

        except Exception as e:
            self.status_label.config(text="エラーが発生しました: " + str(e), fg="red")

    def show_all_records(self):
        """リストボックス内のすべての記録を更新"""
        self.records_listbox.delete(0, tk.END)
        rows = get_all_records()
        for row in rows:
            item_str = f"ID:{row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]}"
            self.records_listbox.insert(tk.END, item_str)

    def clear_database(self):
        """データベース内のすべての記録を削除"""
        clear_all_records()
        self.result_label.config(text="データベースをクリアしました")
        self.show_all_records()
    
    def delete_selected_record(self):
        """選択されたデータを削除"""
    # Listboxで選択された項目を取得
        selected_item = self.records_listbox.curselection()
        if not selected_item:
            self.result_label.config(text="削除するデータを選択してください", fg="orange")
            return

        # 選択された行のテキストを取得
        item_text = self.records_listbox.get(selected_item)
        try:
            # レコードIDを取得（フォーマットに依存：ID:{id}～）
            record_id = int(item_text.split('|')[0].split(':')[1].strip())
            # データベースから削除
            self.delete_record_from_db(record_id)
            self.result_label.config(text=f"データ(ID:{record_id})を削除しました", fg="green")
            # リストを更新
            self.show_all_records()
        except Exception as e:
            self.result_label.config(text=f"削除エラー: {str(e)}", fg="red")

    def delete_record_from_db(self, record_id):
        """指定されたIDのレコードをデータベースから削除"""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

    def analyze_data(self):
        """データを統計し、結果を表示"""
        total_amount, cat_results = analyze_records()
        if total_amount == 0:
            analyze_text = "記録がないか、総金額が0のため統計できません。"
        else:
            analyze_text = f"総金額: {total_amount}\nカテゴリ統計:\n"
            for cat, cat_sum, ratio in cat_results:
                analyze_text += f"  {cat}: {cat_sum} ({ratio:.2f}%)\n"

        self.result_label.config(text=analyze_text)


def main():
    # 必要に応じて認証情報を設定
    # os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"/path/to/credentials.json"
    # openai.api_key = "sk-xxx"

    root = tk.Tk()
    app = VoiceRecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
