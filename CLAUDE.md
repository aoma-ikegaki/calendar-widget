# Googleカレンダー デスクトップウィジェット

## プロジェクト概要

Windowsデスクトップに常駐するGoogleカレンダーウィジェットアプリケーション。
Python + tkinter + Google Calendar APIで実装する軽量なデスクトップアプリ。

**目的**: デスクトップで常にカレンダー予定を確認できるようにする  
**技術スタック**: Python 3.8+, tkinter, Google Calendar API v3

## 技術仕様

### 開発環境
- **言語**: Python 3.8以上
- **UI**: tkinter (標準ライブラリ)
- **API**: Google Calendar API v3
- **認証**: OAuth 2.0

### 必要なライブラリ
```
google-auth
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
```

## ファイル構成

```
calendar_widget/
├── calendar_widget.py          # メインアプリケーション
├── requirements.txt            # 依存ライブラリ
├── README.md                   # セットアップガイド
├── CLAUDE.md                   # このファイル
└── .gitignore                  # Git除外設定
```

## コーディング規約

1. **スタイル**: PEP 8準拠
2. **命名規則**:
   - クラス名: PascalCase（例: `CalendarWidget`）
   - 関数・変数名: snake_case（例: `fetch_events`）
3. **ドキュメント**:
   - docstringは日本語で記述
   - クラス・関数名は英語
   - コメントは日本語
4. **型ヒント**: 可能な限り使用

## UIデザイン仕様

### ウィンドウ
- サイズ: 350px × 500px
- デフォルト位置: 画面右上（右端から20px、上端から20px）
- タイトルバー: あり（ドラッグ移動可能）

### カラースキーム
```python
COLORS = {
    'bg_primary': '#fafaf9',      # 背景
    'bg_secondary': '#ffffff',    # カード背景
    'text_primary': '#1c1917',    # メインテキスト
    'text_secondary': '#78716c',  # サブテキスト
    'text_tertiary': '#a8a29e',   # 補助テキスト
    'border': '#e7e5e4',          # ボーダー
    
    # イベント色
    'event_allday': '#dc2626',    # 終日イベント（赤）
    'event_interview': '#7c3aed', # 面接（紫）
    'event_work': '#0891b2',      # バイト（青緑）
    'event_default': '#525252'    # その他（グレー）
}
```

### フォント
- 日本語: `Yu Gothic UI`
- サイズ範囲: 8px - 16px
- タイトル: 14px bold
- 本文: 10-11px regular

## 実装の優先順位

### Phase 1: MVP（最優先）
1. 基本的なtkinter UIの構築
2. デモデータでのイベント表示
3. Google Calendar API認証の実装
4. 実際のイベント取得と表示
5. 自動更新機能（5分ごと）
6. 設定の保存・読み込み（ウィンドウ位置、最前面設定）

### Phase 2: UX改善
1. イベントカードクリックでブラウザを開く
2. エラーハンドリングの改善
3. ローディング状態の表示

### Phase 3: 機能拡張（オプション）
1. 複数カレンダー対応
2. フィルタ機能
3. 通知機能

## 重要な実装ポイント

### 1. Google Calendar API連携

**認証フロー**:
1. `credentials.json`の確認（ユーザーが手動で配置）
2. `token.json`の確認（初回は存在しない）
3. 初回または期限切れの場合 → ブラウザで認証
4. トークンを`~/.calendar_widget/token.json`に保存

**APIリクエスト**:
```python
# 今後2週間のイベントを取得
now = datetime.utcnow()
time_min = now.isoformat() + 'Z'
time_max = (now + timedelta(days=14)).isoformat() + 'Z'

events_result = service.events().list(
    calendarId='primary',
    timeMin=time_min,
    timeMax=time_max,
    maxResults=50,
    singleEvents=True,
    orderBy='startTime'
).execute()
```

### 2. 非同期処理

**重要**: Google Calendar APIの呼び出しは必ずバックグラウンドスレッドで実行し、UIスレッドをブロックしないこと。

```python
def refresh_events(self):
    """イベントを非同期で更新"""
    def fetch_data():
        self.events = self.fetch_events_from_api()
        # UIスレッドで更新
        self.root.after(0, self.update_event_list)
    
    thread = threading.Thread(target=fetch_data, daemon=True)
    thread.start()
```

### 3. エラーハンドリング

すべてのAPI呼び出し、ファイルI/O、JSON解析は`try-except`で保護し、エラー時もアプリが落ちないようにする。

```python
try:
    # API呼び出し
except Exception as e:
    print(f"エラー: {e}")
    # デモデータで継続
    return self.get_demo_events()
```

### 4. 設定ファイルの配置

すべての設定ファイルは`~/.calendar_widget/`ディレクトリに保存:
- `config.json`: ウィンドウ設定
- `token.json`: 認証トークン（自動生成）
- `credentials.json`: API認証情報（ユーザーが手動配置）

### 5. UIの構造

```
CalendarWidget
├── setup_window()          # ウィンドウ初期設定
├── create_widgets()        # UI構築
│   ├── ヘッダー
│   │   ├── タイトル
│   │   ├── 📌ボタン（最前面切り替え）
│   │   └── 🔄ボタン（手動更新）
│   ├── イベントリスト（スクロール可能）
│   │   └── 日付ごとのセクション
│   │       └── イベントカード
│   └── フッター
│       └── 最終更新時刻
├── get_calendar_service()  # API認証
├── fetch_events_from_api() # イベント取得
├── refresh_events()        # 更新処理
├── update_event_list()     # UI更新
└── create_event_card()     # イベントカード生成
```

## テスト項目

### 基本機能
- [ ] アプリケーション起動
- [ ] 初回認証フロー（ブラウザが開く）
- [ ] イベントの正常表示
- [ ] スクロール動作
- [ ] 更新ボタンの動作
- [ ] 最前面切り替えの動作

### 設定の永続化
- [ ] ウィンドウ位置の保存・復元
- [ ] 最前面設定の保存・復元

### エラーハンドリング
- [ ] ネットワーク切断時の動作
- [ ] credentials.json未設定時の動作
- [ ] 無効なトークン時の再認証

### 自動更新
- [ ] 5分後に自動更新されるか
- [ ] 更新中もUIが応答するか

## よくある問題と解決方法

### Q: tkinterのインポートエラー
A: Pythonインストール時に「tcl/tk and IDLE」がインストールされているか確認

### Q: Google認証画面が開かない
A: `credentials.json`が正しい場所に配置されているか確認

### Q: イベントが表示されない
A: 
1. インターネット接続を確認
2. Googleカレンダーに予定が登録されているか確認
3. 認証トークンが有効か確認（`token.json`を削除して再認証）

## 開発の進め方

1. **初期セットアップ**:
   - プロジェクトディレクトリ作成
   - requirements.txt作成
   - .gitignore作成

2. **UI実装**:
   - まずデモデータで動作確認
   - レイアウトとデザインを完成させる

3. **API連携**:
   - 認証フロー実装
   - イベント取得実装
   - エラーハンドリング追加

4. **自動更新**:
   - 非同期処理実装
   - 5分ごとの自動更新

5. **設定保存**:
   - config.jsonの読み書き
   - ウィンドウ設定の復元

6. **ドキュメント**:
   - README.md完成
   - セットアップ手順の詳細化

## 参考リンク

- Google Calendar API: https://developers.google.com/calendar/api/v3/reference
- tkinter: https://docs.python.org/ja/3/library/tkinter.html
- Google Auth: https://google-auth.readthedocs.io/

## 注意事項

1. **セキュリティ**:
   - `credentials.json`と`token.json`は絶対にGitにコミットしない
   - `.gitignore`に必ず追加

2. **パフォーマンス**:
   - API呼び出しは必要最小限に
   - UIスレッドをブロックしない
   - デモデータでフォールバック

3. **ユーザビリティ**:
   - エラーメッセージは日本語でわかりやすく
   - 初回セットアップのドキュメントを充実させる
   - トラブルシューティングを用意
