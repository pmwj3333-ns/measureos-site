# MEASURE OS Package A — Part3 調査整理

| 項目 | 内容 |
|------|------|
| 文書種別 | QA 外注用機能仕様書のための調査整理（Part3） |
| 対象範囲 | ⑥ Priority / ⑦ 現場盤 / ⑧ Observe / ⑨ 管理者画面 |
| 根拠 | リポジトリ `measureos-site` の実装コード |
| 注意 | 本書は仕様書ではない。コードから読み取った事実の整理 |

**責務分界**

- Part2: 第7条の再計算・手入力・CSV取込（Priority データの生成・更新）
- Part4: API 詳細・DB 定義・HTTP エラー仕様

---

## 調査対象ファイル一覧

| 区分 | ファイル |
|------|---------|
| 画面 | `frontend/priority_view.html`, `frontend/field_v2.html`, `frontend/sr_v2.html`, `frontend/sr_monthly.html`, `frontend/admin_companies.html`, `frontend/debug_v2.html`, `frontend/debug.html` |
| static | `frontend/static/priority-tier-due.js`, `frontend/static/anomaly-classification.js`, `frontend/static/sr_v2_company_context.js`, `frontend/static/sr_monthly_url_state.js`, `frontend/static/format-jst-datetime.js` |
| router | `app/routers/priority.py`, `app/routers/work.py`, `app/routers/sr_observe.py`, `app/routers/sr_monthly.py`, `app/routers/admin_companies.py`, `app/routers/test_control.py` |
| service | `app/services/package_a_observe.py`, `app/services/article7_priority_phase1.py`, `app/services/article7_deviation.py`, `app/services/priority_article7_context.py`, `app/services/anomaly_classification.py`, `app/services/field_users.py`, `app/services/work_unit_clone.py` |
| model | `app/models.py`（`PriorityItem`, `WorkUnit`, `CompanyMaster`, `CompanySettings` 等） |
| schema | `app/schemas.py`（Priority / Work / Observe / Monthly 関連） |
| ルート | `app/main.py`（画面ルート・session bootstrap） |
| test | `tests/test_priority_session_company.py`, `tests/test_field_session_company.py`, `tests/test_sr_observe_dashboard.py`, `tests/test_planned_registration.py`, `tests/test_field_classification_aggregate.py`, `tests/test_sr_monthly_url_state.py` |

---

# ⑥ Priority（優先度監視盤）

## ■ 画面

| 項目 | 内容 |
|------|------|
| **画面名** | 優先度監視盤 |
| **URL** | `/priority/v2` |
| **HTML** | `frontend/priority_view.html` |
| **利用者** | 事務担当（導入企業）。ログイン中の会社の open 第7条を監視 |
| **認証** | **セッション必須**。未ログイン時は `/office/v2?return_to=/priority/v2` へ 307 リダイレクト |
| **タイトル** | MEASURE OS — 優先度監視盤（第7条） |

**画面項目**

- ヘッダー（説明: 表示のみ・現場は変更しない / v2·監視OS バッジ）
- パネル見出し「優先順位一覧」+ 説明文
- 更新時刻 `#updated-at`（ページ読み込み時のローカル時刻 HH:mm）
- 関連リンク: 第7条入力、現場 v2、事務 v2、管理者 v2、debug v2
- エラー欄 `#msg`
- 一覧 `#root`（監視ボード `.monitor-board`）

**各行の表示項目**

- 優先度バッジ（high / mid / low）— 左ボーダー色も tier 連動
- 生産モード pill（自社製造 / 商社・仕入）
- 「締切後投入」バッジ（`is_after_cutoff === true` のとき）
- 商品名（label）
- メトリクス: 不足（prod_value）/ 在庫 / 基準在庫未設定バッジ / 予定（ship_value）/ 使用可能 / 締切（当日以前は強調表示）/ 不足理由（ラベル＋数量）

**画面操作**

1. ページ表示時に自動読み込み（手動更新ボタンなし・自動ポーリングなし）
2. 一覧は**読取専用**（編集・クローズ・再計算ボタンなし）
3. 関連リンクで他画面へ遷移

**画面遷移**

| 起点 | 遷移先 |
|------|--------|
| 未認証 | `/office/v2?return_to=/priority/v2` |
| リンク | `/priority/input/v2`（Part2）, `/genba/v2`, `/office/v2`, `/sr/v2`, `/debug/v2` |
| 空状態メッセージ内 | `/priority/input/v2` |

**会社スコープ**

- 画面に company 入力 UI なし
- サーバーが session の `company_id` を `__MO_BOOTSTRAP_COMPANY__` として HTML 注入
- bootstrap 欠落時は `GET /v2/office/session` を試し、成功なら reload、失敗なら事務ログインへ
- API 呼び出しは bootstrap の company_id のみ（URL クエリの company は不使用）

---

## ■ 機能（Priority 表示）

### データ取得

| 項目 | 内容 |
|------|------|
| **入力** | セッション company_id（bootstrap） |
| **API** | `GET /v2/priority/items?company_id={session}`（`article5_progress` は付けない） |
| **補助** | `GET /v2/company/{session}` で単位（unit、デフォルト「個」）取得 |
| **出力** | open の priority 行一覧（サーバー側ソート済み） |

### 表示フィルタ（クライアント）

- `due_date` が空の行は**一覧に出さない**
- API が 0 件 → 空状態「現在、製造の必要はありません / 在庫で出荷をカバーできています」
- API に行があるが due 付きが 0 件 → 「納期を表示できる項目がありません」+ 第7条入力へのリンク

### ソート（クライアント再ソート）

1. tier: high → mid → low
2. 締切日（due_date）昇順
3. 不足数（prod_value）降順

### 優先度 tier の決定

| 優先 | ソース |
|------|--------|
| 1 | API の `priority_level`（high / mid / low）が有効なら採用 |
| 2 | なければ `priority-tier-due.js` の納期ベース fallback |

**サーバー側 priority_level 算出**（`article7_priority_phase1.py`）

1. 納期が JST 今日より前 → 強制 high
2. 不足数 ≤ 0 → low
3. それ以外: `score = shortage_rate × due_weight` で high / mid / low 判定
   - due_weight: 納期まで ≤1 日 → 3、≤3 日 → 2、それ以外 → 1
   - score ≥ 1.5 → high、≥ 0.5 → mid、else low
   - shortage = prod_value（API 応答）または max(ship − stock, 0)

**クライアント fallback**（`priority-tier-due.js`、納期のみ）

- ローカル暦日差 diff: diff ≤ 1 → high、≤ 3 → mid、else low
- 期限超過（diff < 0）も high

### 表示内容の算出フィールド

- `usable_stock_qty`, `shortage_from_ship_qty`, `shortage_from_safety_qty`, `shortage_reason_labels` は API 応答をそのまま表示
- `stock_qty` 欠落時は max(ship − prod, 0) をクライアント補完
- `safety_stock_unset === true` のとき「基準在庫未設定」バッジ

### 状態遷移

- 本画面は状態を**変更しない**（表示のみ）
- closed 行は API が返さないため表示されない

### バリデーション・例外（画面）

| 条件 | 挙動 |
|------|------|
| セッション company なし | エラー「会社セッションがありません」 |
| items API 失敗 | `#msg` に detail または status |
| ネットワーク例外 | 「読み込みに失敗しました」 |

---

## ■ 業務ルール（Priority 表示）

| 区分 | ルール |
|------|--------|
| **表示対象** | 当該 company の status=open の第7条のみ |
| **登録・更新・削除** | 本画面では不可（Part2: 再計算・手入力・クローズ） |
| **再計算** | 本画面では不可 |
| **表示ルール** | 納期必須（due なしは非表示）。tier はサーバー優先、納期 fallback。製造モード・締切後投入・不足理由を併記 |
| **連携** | 第7条データは Part2 で生成。現場盤は同 API を `article5_progress=1` 付きで別用途利用 |
| **制約** | ログイン会社固定。他社データは表示不可 |

---

## ■ 使用データ（Priority 表示）

| 業務データ | 用途 |
|-----------|------|
| 第7条 open 行（商品名・出荷数・製造数・在庫・納期・締切後フラグ等） | 一覧の主データ |
| 商品マスタ基準在庫 | 使用可能在庫・不足理由分解の表示 |
| 生産モード（商品マスタ） | 自社製造 / 商社・仕入 pill |
| 会社設定（unit） | 数量単位表示 |
| 第5条進捗 | **本画面では未使用**（`article5_progress=0`） |

---

## ■ 未実装（Priority 表示）

| 項目 | 根拠 |
|------|------|
| 手動更新・自動リフレッシュ | `priority_view.html` にタイマー・更新ボタンなし |
| 画面からの第7条編集 | 読取専用 UI |
| 優先度閾値の company 別設定 | `article7_priority_phase1.py` コメント |
| セッションなしでの閲覧 | `main.py` `_priority_v2_html_response` |

---

# ⑦ 現場盤（field v2）

## ■ 画面

| 項目 | 内容 |
|------|------|
| **画面名** | 現場入力（第5条） |
| **URL** | `/field/v2`, `/現場/v2`, `/genba/v2`（同一 HTML） |
| **HTML** | `frontend/field_v2.html` |
| **利用者** | 現場班長（導入企業） |
| **認証** | **セッション必須** + 班長マスタ文字列 `__MO_FIELD_USERS_RAW__` 注入 |
| **タイトル** | MEASURE OS — 現場入力（第5条） |

**サブ画面構成**

| 画面 | ID | 用途 |
|------|-----|------|
| 班長選択オーバーレイ | `#overlay` | 初回・担当者変更時 |
| 予告 | `#screen-planned` | 翌営業日予告入力 |
| 実績 | `#screen-actual` | 着手後の実績報告 |

**共通 UI**

- ヘッダー（担当者名ボタン → 班長変更）
- 折りたたみ「初期設定（作業・工程）」: 作業 ID・工程 ID（localStorage 保存）
- トースト通知

**予告画面項目**

- 第7条参照パネル（high/mid/low 区分・タップで予告行へ反映）
- 予告入力（製造: 1行=1商品 / 物流モード時は別ブロック）
- 「＋ 商品追加」「予告を登録」「着手して実績報告へ」

**実績画面項目**

- 予告内容サマリー（読取）
- 折りたたみ「第7条詳細を見る」
- 実績入力（1行=1商品、使用物、行メモ）
- 折りたたみ「異常・逸脱の記録」（第7条逸脱理由、A/B 分類チェック）
- 全体メモ（任意）
- 「実績を報告」

**画面操作（主要フロー）**

```
班長選択確定
  → POST /v2/work（壳取得）
  → 状態に応じた画面:
       actual_at あり → 新 shell 作成 → 予告画面（空予告）
       started_at あり → 実績画面
       それ以外 → 予告画面

予告を登録 → POST /v2/work/{id}/planned
着手して実績報告へ → POST /v2/work/{id}/start → 実績画面
実績を報告 → POST /v2/work/{id}/actual → 新 shell → 予告画面
```

**画面遷移**

| 起点 | 遷移先 |
|------|--------|
| 未認証 | `/office/v2?return_to={現場パス}` |
| 班長未確定 | オーバーレイ表示（本体画面は裏） |
| 予告 ↔ 実績 | `show("planned")` / `show("actual")`（同一 URL） |
| 実績報告成功 | 自動で予告画面（次サイクル） |

**会社スコープ**

- company は session bootstrap のみ（URL `company` クエリは **無視**、テストで確認）
- task / process は localStorage + URL クエリ fallback（デフォルト task_01 / proc_01）
- 班長名は company 別 localStorage キー `field_v2_last_user:{company_id}`

---

## ■ 機能（現場盤）

### 班長選択

| 項目 | 内容 |
|------|------|
| **入力** | 班長 combobox（サーバー注入 `field_users` 候補 + 自由入力） |
| **形式** | `名前` または `名前:工程`（全角コロン可） |
| **処理** | 確定後 localStorage 保存 → `bootstrapWork()` |
| **出力** | ヘッダー担当者表示、以降 API の `user_id` |

### 予告登録

| 項目 | 内容 |
|------|------|
| **入力** | 商品行（label, value 任意, product_code 内部解決, used_materials 任意） |
| **クライアント検証** | 空行スキップ。数量のみ・不正数量はエラートースト |
| **空予告** | 確認モーダル「予告内容がありません / このまま予告なしで登録しますか？」 |
| **充足済み警告** | 第7条で article5_remaining ≤ 0 の商品が含まれる場合、確認モーダル |
| **API** | `POST /v2/work/{unit_id}/planned` body `{ lines: [...] }` |
| **サーバー** | append-only clone。`planned_registered_at` 必ず設定。空 lines でも登録可（Package A） |
| **出力** | 更新された work 行。成功トースト「予告を保存しました」 |

### 着手

| 項目 | 内容 |
|------|------|
| **前提** | `planned_registered_at` あり。予告 DOM と保存済み fingerprint 一致 |
| **未保存** | 「予告内容が未保存です。先に「予告を登録」してください。」 |
| **未登録** | 「先に予告登録を行ってください」 |
| **API** | `POST /v2/work/{unit_id}/start` |
| **サーバー** | `planned_registered_at` なし → 422 |
| **出力** | `started_at` 設定 → 実績画面（実績入力欄は空） |

### 実績報告

| 項目 | 内容 |
|------|------|
| **入力** | 実績 lines（数量必須）, pattern_a/b, anomaly_classification, actual_memo, deviation_reason（条件付き） |
| **クライアント検証** | 数量必須。第7条逸脱時は理由必須 |
| **第7条逸脱判定（クライアント）** | 実績行の product_code または label が open 第7条に存在しない |
| **第7条逸脱判定（サーバー）** | `is_actual_deviation_from_article7`（product_code 優先、両方コード無しは label） |
| **逸脱時** | 422「7条に無い作業です。理由を入力してください」 |
| **API** | `POST /v2/work/{unit_id}/actual` |
| **出力** | `actual_at` 設定。過去実績改訂時はトースト追記。続けて新 shell POST → 予告画面 |

### 第7条参照パネル

| 項目 | 内容 |
|------|------|
| **取得** | `GET /v2/priority/items?company_id={session}&article5_progress=1` |
| **併用** | `GET /v2/product-master`, `GET /v2/work/list`（候補・product_code 解決） |
| **予告側表示** | `production_mode !== purchase` のみ（商社・仕入は非表示） |
| **タップ** | 予告行へ商品名反映（参照のみ、第7条自体は変更しない） |
| **進捗表示** | article5_completed_qty, remaining, effective_usable, margin_after_ship |

### 異常・逸脱パネル（実績）

自動表示条件（いずれか）:

- 第7条に無い商品（逸脱）
- 予告数量と実績数量の差
- 予告なし実績

| 分類 | 内容 |
|------|------|
| A プロセス不備 | 入力忘れ / 順序飛び / 後回し / 引継ぎ漏れ / その他 |
| B 結果不備 | 材料不足 / 設備停止 / 作業ミス / 見立て違い / 突発優先変更 / その他 |

### input_mode（会社設定）

| 値 | 予告・実績 UI |
|----|--------------|
| manufacturing（デフォルト） | 製造ブロック（商品名+数量） |
| logistics | 物流ブロック（作業ラベル中心） |

### 状態遷移（作業行）

```
[壳] planned_registered_at なし
  → 予告登録 → planned_registered_at あり
  → 着手 → started_at あり
  → 実績 → actual_at あり
  → 新壳（予告欄空）→ 次サイクル
```

- 各 POST は append-only（新 WorkUnit 行 INSERT）
- closed 行は `raise_if_closed` で更新拒否

### 実績ドラフト

- localStorage に入力ドラフト保存（company/task/process/user 単位）
- 着手・報告の正は DB。ドラフトは UI 復元用

### バリデーション・例外（代表）

| 層 | 条件 | 結果 |
|----|------|------|
| 画面 | 班長未選択 | オーバーレイ |
| 画面 | 行入力不正 | トースト（日本語メッセージ） |
| API | 行なし 404 | 「作業記録が見つかりません」 |
| API | closed | 更新拒否 |
| API | 着手前に start | 422 予告登録必須 |
| API | 第7条逸脱・理由なし | 422 |

---

## ■ 業務ルール（現場盤）

| 区分 | ルール |
|------|--------|
| **登録** | 予告は空でも可（登録操作で `planned_registered_at` を記録）。実績は行+数量必須 |
| **更新** | 予告・着手・実績はいずれも新行追加（上書き更新ではない） |
| **削除** | 画面からの削除操作なし |
| **表示** | 第7条は manufacture のみ現場ボード表示。purchase は除外 |
| **再計算** | 現場から第7条再計算不可 |
| **連携** | 第7条 open 行と実績突合 → 逸脱フラグ・理由。第5条進捗は article5_progress API |
| **制約** | session company 固定。班長は company_settings.field_users 由来候補 |

---

## ■ 使用データ（現場盤）

| 業務データ | 用途 |
|-----------|------|
| 作業行（WorkUnit） | 予告・着手・実績の主データ |
| 第7条 open 行 + 第5条進捗 | 参照パネル・逸脱判定 |
| 商品マスタ | product_code 解決・入力候補 |
| 過去作業一覧 | 入力候補・コードヒント |
| 会社設定（input_mode, field_users, tolerance 等） | UI モード・班長候補・サーバー判定 |
| 異常分類マスタ（固定コード） | A/B チェックボックス |

---

## ■ 未実装（現場盤）

| 項目 | 根拠 |
|------|------|
| 現場からの第7条編集 | UI なし |
| 予告画面からの第7条 due_date 編集 | debug v2 の planned-due のみ |
| work API のセッション認証 | router に session ガードなし（画面側 bootstrap で company 固定） |
| 班長のサーバー側厳密照合のみ運用 | 自由入力も combobox で可能 |

---

# ⑧ Observe（管理者観測）

## ■ 画面構成

Observe は **管理者 v2**（`frontend/sr_v2.html`）内の機能群。独立 URL は会社詳細モードのみ。

| 画面 | URL | 用途 |
|------|-----|------|
| 管理者 v2・設定タブ | `/sr/v2`（デフォルト） | 会社設定（Observe データ源の設定） |
| 運営ダッシュボード | `/sr/v2?tab=ops`, `/sr/v2/ops`（307→ops） | 全社ポートフォリオ |
| 会社詳細 Observe | `/sr/v2?tab=observe&company={id}` | 単社観測ダッシュボード |

| 項目 | 内容 |
|------|------|
| **利用者** | MEASURE OS 運用者・管理者（導入支援側） |
| **認証** | **なし**（HTML 直配信・API も session ガードなし） |
| **会社指定** | URL クエリ `company` + localStorage `sr_v2_last_company`（`sr_v2_company_context.js`） |

---

## ■ 運営ダッシュボード（L1）

**画面項目**

- サマリータイル: 契約会社数 / 正常 / 要観察 / 危険
- 運営観測カード: 危険度上位 / 更新停止
- 全社一覧テーブル（状態・危険度・company_id・会社名・青件数・青率・最終更新・詳細）
- 状態フィルタ（すべて / 正常 / 要観察 / 危険）

**操作**

- 「一覧を更新」→ `GET /v2/sr/observe-portfolio?active_only=true`
- 行クリック or 詳細 → `/sr/v2?tab=observe&company={id}`

**表示ルール（danger_score → status）**

| status | 条件（danger_score） |
|--------|---------------------|
| 危険 | ≥ 10 |
| 要観察 | ≥ 1 かつ < 10 |
| 正常 | 0 |

danger_score = 青件数×2 + 前営業日未完了×3 + 締切後投入×5

**週報対象フラグ**（`weekly_report_target`）: API 応答に含むが L1 テーブル列としては非表示

---

## ■ 会社詳細 Observe（L2）

**画面項目**

1. **現場状態サマリー**: 青件数 / 締切後投入 / 前営業日未完了 / 未着手予告 / 結果不備 / 例外入力
2. **現場分類（任意入力）**: プロセス不備・結果不備の件数内訳
3. **最新異常一覧**: 時刻・班長・工程・種類・内容（最大 40 件）
4. **工程別観測**: 工程・青件数・青率・締切後投入・未完了数
5. **第7条状態**: 不足件数 / 自社製造不足 / 商社仕入不足 / 締切後投入 / 基準在庫未設定 / 優先度集中状態

**操作**

- 「観測を更新」→ `GET /v2/sr/observe-dashboard?company_id={id}`
- 「← 運営ダッシュボードへ戻る」→ `/sr/v2?tab=ops`

**異常種類（代表）**

未登録ユーザー / 例外入力 / 結果不備 / 順序不備 / 未着手予告 / 前営業日未完了 / 未入力 / 要注意 / 要注意（青）

**読取専用**

- ダッシュボード説明・コードコメント: 制御なし・推論なし・観測のみ

---

## ■ 機能（Observe）

| 項目 | 内容 |
|------|------|
| **入力** | company_id（URL / 設定タブで選択した会社） |
| **処理** | `build_package_a_dashboard` / `build_observe_portfolio` で WorkUnit・PriorityItem 等を集計 |
| **出力** | JSON → 画面描画 |
| **データ源上限** | WorkUnit 最新 500 件（会社詳細）。一覧は natural key 最新化 |

### 青件数のカウント

- audit 行の status=blue かつ `passes_observe_anomaly_display` を満たすもの
- 事務 v2 の異常表示条件と同等（持ち越し青・未登録ユーザー・逸脱・diff・invalid_flow・missing・system_pattern 等）

---

## ■ 業務ルール（Observe）

| 区分 | ルール |
|------|--------|
| **表示** | 全 active 会社をポートフォリオ対象（Package コードで API フィルタなし） |
| **登録・更新・削除** | Observe 画面からは不可 |
| **連携** | 現場・事務の入力結果を読取反映。第7条状態は open PriorityItem から集計 |
| **制約** | 認証なし。company_id 知っていれば API 直接呼び出し可能 |

---

## ■ 導入企業との違い（Observe）

| 観点 | 導入企業（事務・現場） | Observe（管理者） |
|------|----------------------|------------------|
| 認証 | 事務・現場は session 必須（会社ログイン） | 認証なし |
| 会社スコープ | session の 1 社のみ | URL / 検索で任意会社。全社ポートフォリオ可 |
| 目的 | 入力・監視（Priority）・完了処理（事務 v2） | 読取専用の観測・運営一覧 |
| Package 設定 | 契約表示（設定タブ） | 同左。Observe 集計は Package 値で分岐しない |
| 操作 | 予告・実績・第7条フロー（Part2/7） | 更新ボタンのみ（再取得） |

**Package A/B/C セレクタ**（設定タブ）: 契約段階の表示切替 UI。コメント上「Package 自体は制御を行いません」。

---

## ■ 使用データ（Observe）

| 業務データ | 用途 |
|-----------|------|
| WorkUnit（最新群） | 青・異常・工程別・分類集計 |
| PriorityItem（open） | 第7条状態・締切後・不足・集中ラベル |
| CompanyMaster | ポートフォリオ会社一覧 |
| CompanySettings | 業務日・異常表示判定 |
| 商品マスタ | 生産モード・基準在庫未設定カウント |
| 現場異常分類（保存済み） | 分類内訳 |

---

## ■ 未実装（Observe）

| 項目 | 根拠 |
|------|------|
| Observe からの現場制御 | read-only 設計 |
| 週次スナップショット UI | `ops_portfolio_snapshot` モデルは Phase 2 基盤・レポート未実装 |
| Package 別 Observe 切替 | portfolio は active 会社全件 |
| 認証・権限 | router にガードなし |

---

# ⑨ 管理者画面

Part3 に含む管理者向け画面: **Company 管理**, **管理者 v2（設定）**, **Monthly**, **Debug**。

---

## 9-1. Company 管理

| 項目 | 内容 |
|------|------|
| **URL** | `/admin/companies/ui` |
| **HTML** | `frontend/admin_companies.html` |
| **利用者** | 内部運用（会社マスタ管理） |
| **認証** | **なし** |

**画面項目**

- 新規追加: company_id, company_name
- 一覧テーブル（id, company_id, company_name, 状態, 操作）
- 「有効のみ」チェック
- 各行: 有効/無効トグル

**操作**

- 追加 → `POST /admin/companies`
- 一覧 → `GET /admin/companies?active_only=true`（任意）
- 有効/無効 → `PATCH /admin/companies/{id}`

**画面遷移**

- トップ `/`、事務 v2 へのリンク

**注記（画面文言）**

- 「現場・事務の自由入力はまだ変更していません（第2段階で API 検証予定）」

---

## 9-2. 管理者 v2 — 設定タブ

| 項目 | 内容 |
|------|------|
| **URL** | `/sr/v2` |
| **HTML** | `frontend/sr_v2.html` `#panel-settings` |
| **認証** | **なし** |

**主要ブロック**

| ブロック | 設定内容 | 保存 API |
|---------|---------|---------|
| 会社 | 検索・新規作成・会社名・Package・ログイン ID 表示 | `POST /admin/companies`, `GET/PUT /v2/company/{id}/leaders` |
| 班長リスト | 名前＋工程行 | 同上 PUT leaders |
| 業務日切替 | 日勤/夜勤/24h → day_boundary_time | 同上 |
| 異常判定 | tolerance_value（許容差） | 同上 |
| 第7条・受注締切 | order_cutoff_time | 同上 |
| 営業日設定 | 基本曜日・例外日 | `PATCH /v2/company-settings/working-days` |

**付帯操作**

- 新規会社作成 → 初期パスワード表示・コピー
- パスワード再発行 → `POST /v2/company/{id}/password/reissue`
- 現場 v2 リンク（company クエリ付き）生成

**Package 選択**

- A / B / C（表示名・説明・ターゲット条文ラベル）
- 保存は `package_code` として company_settings に記録

**営業日**

- 画面注記: 「Package A では定義・表示のみ行い、制御は行いません」

---

## 9-3. Monthly（月報作成）

| 項目 | 内容 |
|------|------|
| **URL** | `/sr/monthly` |
| **HTML** | `frontend/sr_monthly.html` |
| **利用者** | 管理者（Observer コメント付き月報） |
| **認証** | **なし** |

**画面項目**

- 会社検索（`/admin/companies/search`）
- 対象月（month input）
- 集計結果パネル:
  - ① 作業状況（総作業数 / 実績入力済み / 実績未入力）— **actual_at 有無集計**
  - ② 異常発生状況（内訳）
  - ③ 監査観点内訳
  - 現場分類内訳
  - 工程別・班長別テーブル
- 自動生成サマリー（編集可）
- Observer コメント
- 保存 / PDF 出力

**操作**

| 操作 | API |
|------|-----|
| 集計 | `GET /v2/sr/monthly-report/aggregate?company_id&target_month` |
| 保存 | `POST /v2/sr/monthly-report` |
| PDF | `GET /v2/sr/monthly-report/print?...`（新規タブ） |

**URL 状態**

- `company`, `target_month` を URL と localStorage（`sr_monthly_url_state.js`）で同期
- URL 優先

---

## 9-4. Debug v2

| 項目 | 内容 |
|------|------|
| **URL** | `/debug/v2` |
| **HTML** | `frontend/debug_v2.html` |
| **利用者** | 開発・検証 |
| **認証** | **なし** |

**画面項目**

- company_id 入力 → 作業一覧表（最大 200 件・更新順・closed 含む全 status）
- 行クリック → status-history パネル
- planned line due_date マージ UI → `POST /v2/work/{id}/planned-due`
- JSON 表示 / 自動更新（3 秒）
- テスト専用・擬似現在時刻 → `POST /v2/test/clock`, `POST /v2/test/recompute`

**注記**

- 現場 v2 にはテスト時計 UI は出ない
- 一覧取得時にサーバー側で班長判定再計算→DB 反映後に返却

---

## 9-5. Debug（旧）

| 項目 | 内容 |
|------|------|
| **URL** | `/debug`, `/dev` |
| **HTML** | `frontend/debug.html` |
| **認証** | **なし** |

v1 系デバッグ画面（debug v2 とは別ファイル）。

---

## ■ 業務ルール（管理者画面）

| 区分 | ルール |
|------|--------|
| **Company 管理** | company_master の追加・有効/無効。物理削除 UI なし |
| **設定タブ** | 班長・業務ルール・Package・営業日を会社単位で保存 |
| **Observe** | 上記⑧参照 |
| **Monthly** | 月次集計の確認・コメント追記・保存・PDF。作業完了判定ではなく actual_at 集計 |
| **Debug** | DB 参照・検証用。本番運用フロー外 |

---

## ■ 使用データ（管理者画面）

| 業務データ | 主な利用画面 |
|-----------|-------------|
| company_master | Company 管理・検索 |
| company_settings（班長・境界時刻・許容差・Package・締切） | 設定タブ |
| working_calendar | 営業日設定 |
| WorkUnit 全履歴 | Debug v2・Monthly 集計 |
| PriorityItem | Observe 第7条状態 |
| monthly_report（保存实体） | Monthly 保存 |

---

## ■ 未実装（管理者画面）

| 項目 | 根拠 |
|------|------|
| 管理者画面の認証 | 各 HTML 直配信・API ガードなし |
| company 自由入力の API 厳密検証 | admin_companies.html 注記 |
| 運営スナップショットレポート UI | models コメント Phase 2 |
| Package による機能 ON/OFF | sr_v2 注記「制御を行いません」 |

---

# Part3 全体フロー（業務）

```
[事務] ログイン
    └─► 優先度監視盤（⑥）… open 第7条の監視のみ

[現場] ログイン
    └─► 班長選択 → 予告（⑦）→ 着手 → 実績
            ├─ 第7条参照（progress 付き API）
            └─ 逸脱時は理由必須

[管理者] 認証なし
    ├─► 設定タブ … 会社・班長・ルール
    ├─► 運営ダashboard（⑧ L1）… 全社
    ├─► 会社詳細 Observe（⑧ L2）… 単社
    ├─► Monthly … 月報
    ├─► Company 管理 … マスタ CRUD
    └─► Debug v2 … 検証
```

---

# Part4 へ移管する情報（整理のみ）

以下は Part3 QA 仕様書本文には載せず、Part4 で詳細化する想定。

- `GET/POST /v2/priority/*`, `/v2/work/*`, `/v2/sr/observe-*`, `/v2/sr/monthly-report/*`, `/admin/companies*` の HTTP ステータス・detail 一覧
- リクエスト/レスポンス JSON 全フィールド
- `priority_item`, `work_unit`, `company_master`, `company_settings` 等のテーブル定義
- append-only clone・status_history・judgement 昇格の内部実装
- session middleware・`__MO_BOOTSTRAP_COMPANY__` 注入の実装詳細

---

# Part3 QA 仕様書作成可否

**この整理だけで Part3 の QA 外注用機能仕様書を書ける状態。**

カバー済み:

- ⑥ 優先度監視盤: 画面・認証・表示ルール・tier・空状態・読取専用・データ依存
- ⑦ 現場盤: 予告/着手/実績・班長・第7条参照・逸脱・異常分類・状態遷移・入力検証
- ⑧ Observe: L1/L2 画面・利用方法・表示項目・導入企業との差・読取専用
- ⑨ 管理者: Company 管理・設定・Monthly・Debug・認証なし事実
- Part2（第7条生成）/ Part4（API・DB）との責務分界
- Package A 時点の未実装一覧

Part3 仕様書執筆時に Part4 参照として脚注を付けるとよい項目: 各 API の HTTP エラー詳細、WorkUnit 内部カラム、session 注入の実装、work API が router 層で session 必須でない事実（現場は HTML bootstrap で company 固定）。
