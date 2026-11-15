# ARIake EVENT CALENDAR

有明エリアの主要4施設（東京ビッグサイト／東京ガーデンシアター／有明アリーナ／有明ガーデン）のイベント情報を、1つのページで確認できる静的Webサイトです。

## 構成

```
ariake-events/
├── index.html      ページの骨組み
├── events.json     施設情報とイベント情報（データ）
├── css/style.css   デザイン
├── js/app.js       表示・絞り込み・検索の処理
└── README.md
```

HTML・CSS・JavaScript・JSONはVanilla構成で、外部ライブラリやバックエンドは使いません。GitHub Pagesで公開できるよう、パスはすべて相対パスです。

## ローカルで確認する

`index.html` を直接開くと、ブラウザの制限でJSONを読めません。簡易サーバーを使ってください。

```bash
python -m http.server 8000
```

ブラウザで http://localhost:8000/ を開きます。

## events.json の構造（schema 2.0）

- `metadata`：`schema_version`、`last_updated`（データ更新日時）、`timezone`
- `facilities`：`id`、`name`、`color`（表示色）、`source_url`（公式イベント一覧）
- `events`：1件ごとに次の項目を持ちます。不明な項目は `null` にします。

| 項目 | 内容 |
|---|---|
| `id` | 一意のID |
| `facility_id` | `facilities` のid（固定値） |
| `title` | イベント名 |
| `start_date` / `end_date` | `YYYY-MM-DD`（複数日は開始日と終了日） |
| `start_time` / `end_time` | `HH:mm` |
| `time_text` | 自由記述の時間（複数公演など） |
| `category`, `venue_detail`, `description` | カテゴリ、会場詳細、説明文 |
| `official_url` | イベントの公式ページ |
| `source_url` | 情報の取得元ページ |
| `last_checked` | 最終確認日時 |

`official_url` が `null` の場合、カードには施設の公式イベント一覧へのリンクを表示します。

## イベントを更新する

`events.json` を編集して保存し、GitHubへpushします。ページは開くたび、また10分ごとにJSONを読み直します。更新したら `metadata.last_updated` も書き換えてください。

## 公開（GitHub Pages）

Settings → Pages で、Source を「Deploy from a branch」、Branch を `main` / `(root)` にします。

## 今後の予定

PythonとGitHub Actionsで、毎日午前9時（日本時間）に各施設の公式サイトから取得して `events.json` を更新する予定です（未実装）。
