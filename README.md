# voice_accounting
for homework

以下是规范化后的 `README.md`，并将中文部分翻译为日语：

---

# README

## 動作確認環境
- **MacOS**

## セットアップ手順

### 1. 依存関係のインストール
#### a. `pyaudio` のインストール
```bash
brew install portaudio
conda install -c anaconda pyaudio
```

#### b. OpenAI SDK（バージョン 0.28）のインストール
```bash
pip install openai==0.28
```

#### c. Google Cloud Speech-to-Text ライブラリのインストール
```bash
pip install google-cloud-speech
```

#### d. Google Cloud SDK のインストール
```bash
brew install --cask google-cloud-sdk
source "$(brew --prefix)/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/completion.zsh.inc"
source "$(brew --prefix)/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.zsh.inc"
```

---

### 2. API キーの取得と設定
#### a. Google Cloud のサービスアカウントキーの取得
1. [Google Cloud Console](https://console.cloud.google.com/iam-admin/serviceaccounts?inv=1&invt=AbmbTQ&project=valued-decker-446713-v9) に移動。
2. **[IAM と管理]** - **[サービスアカウント]** セクションでアカウントを作成。
3. JSON 形式でサービスアカウントキーをダウンロード。
4. スクリプト内で以下を追加し、ダウンロードしたキーの絶対パスを設定：
   ```python
   os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/credentials.json"
   ```

#### b. OpenAI API キーの取得
1. [OpenAI 個人ページ - API Keys](https://platform.openai.com/settings/organization/api-keys) に移動。
2. API キーを生成。
3. スクリプト内に以下を追加し、取得した API キーを設定：
   ```python
   openai.api_key = "sk-......"
   ```

---

この手順を完了すると、プロジェクトが正しく動作するようになります。
