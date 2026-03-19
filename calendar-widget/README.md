# Googleカレンダー デスクトップウィジェット

Windowsデスクトップに常駐する軽量なGoogleカレンダーウィジェットです。
今後2週間の予定を常に確認できます。

---

## 機能

- 今後2週間の予定を時系列で表示
- 日付ごとにグループ化した見やすいレイアウト
- イベントタイプ別の色分け（終日・面接・バイトなど）
- スクロール可能なイベントリスト
- 最前面表示のオン/オフ切り替え
- 手動更新ボタン
- 5分ごとの自動更新
- ウィンドウ位置・設定の自動保存
- API未設定時はデモデータで動作

---

## セットアップ

### 1. Python環境の確認

Python 3.8以上が必要です。

```bash
python --version
```

### 2. ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 3. Google Calendar API の設定

#### 3-1. Google Cloud Console でプロジェクトを作成

1. [Google Cloud Console](https://console.cloud.google.com/) を開く
2. 「プロジェクトを選択」→「新しいプロジェクト」をクリック
3. プロジェクト名を入力して作成

#### 3-2. Google Calendar API を有効化

1. 左メニュー「APIとサービス」→「ライブラリ」を開く
2. 「Google Calendar API」を検索してクリック
3. 「有効にする」をクリック

#### 3-3. OAuth 2.0 認証情報を作成

1. 左メニュー「APIとサービス」→「認証情報」を開く
2. 「認証情報を作成」→「OAuth クライアント ID」をクリック
3. 初回の場合は「同意画面を設定」が必要：
   - 「外部」を選択して作成
   - アプリ名・メールアドレスを入力して保存
   - 「テストユーザー」に自分のGoogleアカウントを追加
4. アプリケーションの種類：「デスクトップアプリ」を選択
5. 名前を入力して「作成」をクリック
6. 「JSONをダウンロード」をクリック

#### 3-4. credentials.json を配置

ダウンロードしたファイルを `credentials.json` にリネームして、以下のいずれかに配置：

```
C:\Users\ユーザー名\.calendar_widget\credentials.json
```

または、アプリと同じフォルダに配置（起動時に自動でコピーされます）：

```
calendar_widget\credentials.json
```

---

## 起動方法

```bash
python calendar_widget.py
```

初回起動時はブラウザが開き、Googleアカウントでの認証が求められます。
認証後はトークンが自動保存され、次回以降は不要です。

---

## 使い方

| 操作 | 説明 |
|------|------|
| 📌 ボタン | 最前面表示のオン/オフ |
| 🔄 ボタン | 手動でカレンダーを更新 |
| マウスホイール | イベントリストをスクロール |
| ウィンドウをドラッグ | 好きな位置に移動（位置は自動保存） |

---

## 自動起動の設定（オプション）

Windowsのスタートアップにアプリを登録することで、PC起動時に自動で起動します。

1. `Win + R` で「ファイル名を指定して実行」を開く
2. `shell:startup` と入力してEnter
3. 開いたフォルダにショートカットを作成：
   - `calendar_widget.py` を右クリック → 「ショートカットの作成」
   - 作成したショートカットをスタートアップフォルダに移動

または、`.bat` ファイルを作成してショートカットを登録する方法：

```bat
@echo off
pythonw C:\path\to\calendar_widget.py
```

---

## ファイル構成

```
calendar-widget/
├── calendar_widget.py      # メインアプリケーション
├── requirements.txt        # 依存ライブラリ
├── README.md               # このファイル
├── CLAUDE.md               # 開発者向けドキュメント
└── .gitignore              # Git除外設定

C:\Users\ユーザー名\.calendar_widget\
├── config.json             # ウィンドウ設定（自動生成）
├── token.json              # 認証トークン（自動生成）
└── credentials.json        # API認証情報（手動配置）
```

---

## トラブルシューティング

### Q: 「Google APIライブラリが見つかりません」と表示される
**A:** ライブラリをインストールしてください。
```bash
pip install -r requirements.txt
```

### Q: 「credentials.jsonが見つかりません」と表示される
**A:** `~/.calendar_widget/credentials.json` にファイルを配置してください。
デモモードで動作は継続します。

### Q: 認証画面が「このアプリはGoogleで確認されていません」と表示される
**A:** テストモードのため表示されます。「詳細」→「安全ではないページに移動」をクリックして進んでください。

### Q: イベントが表示されない
**A:**
1. インターネット接続を確認
2. Googleカレンダーに今後2週間以内の予定が登録されているか確認
3. `~/.calendar_widget/token.json` を削除して再認証

### Q: tkinterのインポートエラーが発生する
**A:** Pythonインストール時に「tcl/tk and IDLE」がインストールされているか確認してください。
Pythonを再インストールする場合は「カスタムインストール」でチェックを入れてください。

### Q: ウィンドウが画面外に消えた
**A:** `~/.calendar_widget/config.json` を削除して再起動すると、デフォルト位置（右上）に表示されます。

---

## ライセンス

MIT License
