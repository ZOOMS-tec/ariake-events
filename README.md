# ARIake EVENT CALENDAR

有明エリアの5施設（東京ビッグサイト／東京ガーデンシアター／有明アリーナ／有明ガーデン／有明アーバンスポーツパーク）のイベント情報を、1つのページで確認できる静的Webサイトです。イベント情報は、GitHub Actionsが公式サイトから取得して `events.json` を更新します。

## ディレクトリ構成

```
ariake-events/
├── index.html / css/style.css / js/app.js   表示（Vanilla JS、GitHub Pagesで公開）
├── events.json                              施設情報とイベント情報（schema 2.0）
├── requirements.txt                         requests / beautifulsoup4 / lxml / pytest
├── scripts/
│   ├── main.py                              取得→検証→安全な更新のエントリポイント
│   ├── common.py                            取得（リトライ等）・ID生成・検証・重複排除・JSON書き込み
│   ├── collect_html.py                      調査用：公式ページのHTMLを保存
│   └── scrapers/                            施設別スクレイパー（独立）
├── tests/                                   保存したHTML（tests/fixtures）を使った単体テスト
└── .github/workflows/
    ├── update-events.yml                    イベント自動更新
    └── collect-html.yml                     HTML収集（調査用・手動）
```

## 取得元とスクレイパー

| 施設 | 取得元 | 方式 |
|---|---|---|
| 東京ビッグサイト | https://www.bigsight.jp/visitor/event/ | 一覧を「次へ」リンクが無くなるまでたどる。ページ上部の「検索結果 N件」と解析件数を照合（不一致は失敗）。有明GYM-EXなど対象外施設は除外 |
| 東京ガーデンシアター | https://www.shopping-sumitomo-rd.com/tokyo_garden_theater/schedule/ | 月別ページ（`?date=YYYY-MM`）と「次の期間」リンクをたどる。タイトルが Private の予定は除外 |
| 有明アリーナ | https://ariake-arena.tokyo/event/ | 月別ページをたどる。日ごとの開場・開演時間、1日複数公演の行をそのまま保持 |
| 有明アーバンスポーツパーク | https://ariake-usp.com/event | 一覧はJavaScriptで読み込まれHTMLに無いため、サイトマップのイベント詳細ページを1件ずつ取得し、埋め込みデータ（`__NUXT_DATA__`）からタイトルと開催日を読む。日付表記を確定できないものは除外してログに残す。開催時間・カテゴリは取得しない |
| 有明ガーデン | https://ariake.shopping-sumitomo-rd.com/event/ | 一覧1ページ。開催期間は `data-periods`、カテゴリは各カードのラベル。特集記事・期間不明・150日を超える常設掲載は除外し、ログに残す |

取得できていない項目：ガーデンシアターの開場・開演時間、有明ガーデンの開催時間・会場（詳細ページのHTMLを未確認のため）、有明アーバンスポーツパークの開催時間・カテゴリ（構造化されていないため）。

## events.json

- `metadata.last_updated`：データ更新日時（現在時刻とは別）
- `facilities`：施設ID・名前・表示色・公式URL（IDは固定）
- `events`：`id` / `facility_id` / `title` / `start_date` / `end_date` / `start_time` / `end_time` / `time_text` / `category` / `venue_detail` / `description` / `official_url` / `source_url` / `last_checked`。不明な値は `null`
- 飛び飛びの開催日は、連続する期間ごとに別のイベントとして登録します。
- 終了日が今日より前のイベントは、更新時に除外します（開催中は残します）。

## ローカルでの実行（Pythonが入っている場合）

```bash
pip install -r requirements.txt
python -m pytest                    # テスト（外部通信なし）
python -m scripts.main --dry-run    # 取得・検証のみ（events.jsonは変更しない）
python -m scripts.main              # events.jsonを更新
```

## GitHub Actionsでの自動更新

- `update-events.yml`：テスト→取得→（変更があれば）コミット。`GITHUB_TOKEN` のみ使用。コミットは `github-actions[bot]`、メッセージは `chore: update event data YYYY-MM-DD`。
- **手動実行**：リポジトリの Actions → 「イベント情報の自動更新」→ Run workflow。
- **自動実行**：ファイル内の `schedule`（日本時間 9:17、`timezone: "Asia/Tokyo"`）はコメントアウトしてあります。動作確認後に有効にしてください。

## 取得に失敗したとき

全施設のうち1つでも失敗（通信エラー、構造変更、予期しない0件、データ検証エラー、件数の不一致）すると、`events.json` は更新せず、ワークフローは失敗になります。サイトは前回の正常なデータを表示し続けます。件数が前回の半分以下になったときは警告をログに出します。

## トラブルシューティング

- Actions の失敗ログで、失敗した施設とエラー内容を確認します。「ページ構造が変わった可能性」と出た場合は、`collect-html.yml` でHTMLを収集し、該当スクレイパーを直します。
- スクレイパーが除外した情報は、ログの「除外/要確認」に出ます。
- Publicリポジトリは、リポジトリに活動がない状態が約60日続くと、スケジュール実行が自動で停止されます。Actions 画面に有効化の案内が出たら再開し、定期的に動いているか確認してください。
