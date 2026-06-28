# MEASURE OS Package A — Part2 調査整理

| 項目 | 内容 |
|------|------|
| 文書種別 | QA 外注用機能仕様書のための調査整理（Part2） |
| 対象範囲 | ④ CSV取込 / ⑤ 第7条 |
| 根拠 | リポジトリ `measureos-site` の実装コード |
| 注意 | 本書は仕様書ではない。コードから読み取った事実の整理 |

**責務分界**

- Part3: 優先度監視盤（Priority）画面 UI 詳細
- Part4: API 詳細・DB 定義・HTTP エラー仕様

---

## 調査対象ファイル一覧

| 区分 | ファイル |
|------|---------|
| 画面 | `frontend/stock_import_v2.html`, `frontend/shipment_import_v2.html`, `frontend/priority_input_v2.html` |
| static | `frontend/static/article7-csv-import-flow.js`, `frontend/static/csv_header_resolver.js` |
| router | `app/routers/stock.py`, `app/routers/shipment.py`, `app/routers/csv_import_meta.py`, `app/routers/priority.py` |
| service | `app/services/stock_csv.py`, `app/services/shipment_csv.py`, `app/services/csv_header_normalizer.py`, `app/services/priority_rebuild.py`, `app/services/article7_safety_stock.py`, `app/services/article7_priority_phase1.py`, `app/services/priority_article7_context.py`, `app/services/article7_deviation.py`, `app/services/article3_cutoff_observe.py`, `app/services/product_master.py`（`ensure_product_master_entries`） |
| model | `app/models.py`（`StockItem`, `ShipmentPlanItem`, `PriorityItem`） |
| schema | `app/schemas.py`（Priority / Stock / Shipment 関連） |
| ルート | `app/main.py`（画面ルート） |
| test | `tests/test_stock_shipment_import_session_scope.py`, `tests/test_csv_header_normalizer.py`, `tests/test_article7_safety_stock.py`, `tests/test_article7_shortage_reason.py` |

---

# ④ CSV取込

## ■ 画面

### 1. 在庫 CSV 取込

| 項目 | 内容 |
|------|------|
| **URL** | `/stock/import/v2` |
| **HTML** | `frontend/stock_import_v2.html` |
| **利用者** | 事務担当（導入企業）。セッション必須 |
| **タイトル** | MEASURE OS — 第7条 在庫CSV取込 |

**画面項目**

- ヘッダー（説明・v2·第7条 バッジ）
- 関連画面ナビ: 第7条入力、出荷CSV取込、優先順位、事務v2
- CSV ガイド（取込ファイル例・不可例・必要列: 商品コード/商品名/現在庫数）
- ドロップゾーン + ファイル選択（`.csv,text/csv,text/plain`）
- ファイル状態（未選択 / 選択済み + 選択解除）
- メッセージ欄 `#msg`
- 第7条フロー領域 `#article7-flow`（取込成功後表示）
  - 準備状態（在庫CSV ✓/×、出荷CSV ✓/×）
  - ヒント文
  - 「第7条を再計算する」ボタン
  - 再計算ステータス
  - 「優先度監視盤を見る」リンク → `/priority/v2`（再計算成功後）
- CSV プレビューテーブル（行, product_code, label, stock_qty, safety_stock, 状態）
- 「在庫CSVを取り込む」ボタン

**操作**

1. CSV 選択（D&D / ファイル選択 / キーボード Enter・Space）
2. クライアント側プレビュー表示
3. 「在庫CSVを取り込む」→ `POST /v2/stock/import`
4. 成功後: 第7条フロー表示、`localStorage` に在庫取込済みフラグ
5. 在庫+出荷両方取込済みなら再計算ボタン有効化
6. 再計算 → `POST /v2/priority/rebuild`
7. 再計算成功後: 再計算ボタン非表示、「優先度監視盤を見る」表示

**画面遷移**

| 起点 | 遷移先 |
|------|--------|
| 未認証 | `/office/v2?return_to=/stock/import/v2` |
| 関連ナビ | `/priority/input/v2`, `/shipment/import/v2`, `/priority/v2`, `/office/v2` |
| 第7条フロー | 不足時 `/shipment/import/v2` へリンク |
| 再計算完了 | `/priority/v2`（Part3 画面） |

**セッション**

- `__MO_BOOTSTRAP_COMPANY__` 注入
- 書込前に `GET /v2/office/session` で live company と bootstrap 一致を確認
- 不一致時: 「ページを再読み込みしてから操作してください」

---

### 2. 出荷 CSV 取込

| 項目 | 内容 |
|------|------|
| **URL** | `/shipment/import/v2` |
| **HTML** | `frontend/shipment_import_v2.html` |
| **利用者** | 事務担当。セッション必須 |
| **タイトル** | MEASURE OS — 第7条 出荷CSV取込 |

**画面項目**（在庫取込と同構成。差分のみ）

- 説明: 全置換保存。**在庫突合・製造必要数・第7条自動生成は行わない**
- 必要列: 商品コード/商品名/出荷予定数/納期
- プレビュー列: 行, product_code, label, ship_qty, due_date, ordered_at, 状態
- ボタン: 「出荷予定CSVを取り込む」
- 第7条フロー: 不足時 `/stock/import/v2` へリンク

**操作・遷移**

- 在庫取込と同パターン（API は `POST /v2/shipment/import`）
- 成功メッセージに「同一 product_code + 同一納期は後勝ちでユニーク件数」と明記

---

### 3. CSV ヘッダースキーマ（画面から利用）

| 項目 | 内容 |
|------|------|
| **利用画面** | 在庫・出荷取込画面（プレビュー用） |
| **取得** | `GET /v2/csv/import-schemas/stock` / `shipment` |
| **用途** | 列名別名解決（サーバーと同じ辞書をクライアントでも使用） |

---

## ■ 処理（CSV取込）

### 共通フロー

```
CSVファイル
  → デコード（utf-8-sig → utf-8 replace）
  → パース（ヘッダー解決 → データ行検証）
  → fatal あれば全体失敗
  → 重複排除
  → 当該 company の既存行を全削除
  → 新行 INSERT
  → ensure_product_master_entries（追加のみ）
  → commit
```

### 在庫 CSV（`POST /v2/stock/import`）

| 項目 | 内容 |
|------|------|
| **認証** | セッション必須 + `company_id` 一致 + `validate_company_id` |
| **入力** | `file`（UploadFile）, `company_id`（Form） |
| **出力** | `{ ok, success_count, error_count }` |

**パース（`parse_stock_csv_text`）**

| 項目 | ルール |
|------|--------|
| 空ファイル | fatal: `CSVが空です` |
| ヘッダーなし | fatal: `データ行がありません` |
| 必須列不足 | fatal: `1行目に在庫CSVの必須列（…）が見つかりません。内部キー: product_code, label, stock_qty` |
| 必須列 | `product_code`, `label`, `stock_qty` |
| 任意列 | `safety_stock` |
| 行スキップ条件 | product_code または label 空 / stock_qty 非数値 / safety_stock 指定時に非数値 |
| 空行 | 無視 |
| 数値正規化 | NFKC、カンマ除去、空白除去 |

**重複排除**

- `dedupe_by_product_code`: 同一 `product_code` は**後勝ち**

**保存**

- `stock_item` を company 単位で**全削除**後、有効行を INSERT
- 保存フィールド: `product_code`, `label`, `stock_qty`, `safety_stock`（任意）, `created_at`
- **計算・出荷突合は行わない**（router docstring）

**商品マスタ連携**

- `ensure_product_master_entries`: 未存在 label/code のみ INSERT。既存行は更新しない

**例外**

- fatal → HTTP 422 + detail 文字列
- DB 例外 → rollback + 再 raise
- セッションなし → 401、company 不一致 → 403

---

### 出荷 CSV（`POST /v2/shipment/import`）

| 項目 | 内容 |
|------|------|
| **認証** | 在庫と同様（セッション必須） |
| **入力** | `file`, `company_id` |
| **出力** | `{ ok, success_count, error_count }`（success_count = 重複排除後件数） |

**パース（`parse_shipment_csv_text`）**

| 項目 | ルール |
|------|--------|
| 必須列 | `product_code`, `label`, `ship_qty`, `due_date` |
| 任意列 | `ordered_at` |
| 行スキップ | product_code/label 空 / ship_qty 非数値 / due_date 解釈不可 |
| ordered_at | パース不可でも行エラーに**しない**（None のまま保存） |

**納期正規化（`parse_due_date`）**

- `YYYY年M月D日` → ISO
- `YYYY-MM-DD`, `YYYY/MM/DD`, `YYYY.MM.DD`
- ISO8601 日時 → 日部分のみ
- 成功時 `YYYY-MM-DD`

**重複排除**

- `dedupe_by_product_code_and_due_date`: キー `(product_code, due_date)` で**後勝ち**

**保存**

- `shipment_plan_item` を company 単位**全削除**後 INSERT
- フィールド: `product_code`, `label`, `ship_qty`, `due_date`, `ordered_at`, `created_at`
- **在庫突合・第7条計算は行わない**

---

### ヘッダー正規化（`csv_header_normalizer.py`）

**在庫スキーマ `stock`**

| canonical | 必須 | 別名例 |
|-----------|------|--------|
| product_code | ○ | 商品コード, 品番, code, 商品CD … |
| label | ○ | 商品名, 品名, name, ラベル … |
| stock_qty | ○ | 在庫数, 現在庫, qty, stock … |
| safety_stock | 任意 | 安全在庫, min … |

**出荷スキーマ `shipment`**

| canonical | 必須 | 別名例 |
|-----------|------|--------|
| product_code | ○ | 同上 |
| label | ○ | 同上 |
| ship_qty | ○ | 出荷予定数, 出荷数, quantity … |
| due_date | ○ | 納期, 出荷予定日, delivery_date … |
| ordered_at | 任意 | 受注時刻, order_at … |

- 列順は任意（名前で解決）
- 会社別 override 用の拡張点あり（現状 UI/API からは未使用）
- `product_master` スキーマ定義あり。**import endpoint なし**

---

### 第7条フロー UI（`article7-csv-import-flow.js`）

| 項目 | 内容 |
|------|------|
| **保存先** | `localStorage` キー `measureos:article7-csv:{company_id}` |
| **内容** | `{ stock: bool, shipment: bool }` |
| **再計算条件** | 両方 true（API 側は DB 実データを見る。localStorage は UI ガイド用） |
| **再計算 API** | `POST /v2/priority/rebuild` body `{ company_id }` |
| **完了後** | 再計算ボタン非表示、「優先度監視盤を見る」表示 |

---

## ■ 業務ルール（CSV取込）

| ルール | 内容 |
|--------|------|
| 保存方式 | 会社単位**全置換**（他社データに影響なし） |
| 在庫 CSV | 計算なし・投入のみ |
| 出荷 CSV | 在庫突合なし・投入のみ |
| 行エラー | スキップして続行。`error_count` に加算 |
| fatal | 取込全体失敗（0件保存） |
| 商品マスタ | CSV 取込時に**追加のみ**。更新・削除なし |
| 在庫 CSV の safety_stock | `stock_item.safety_stock` に保存されるが、**第7条再計算では未使用**（再計算は商品マスタ `safety_stock_value` を参照） |
| 第7条再計算 | CSV 取込自体では実行しない。別操作 |

---

## ■ 使用データ（CSV取込）

| データ | 用途 | 操作 |
|--------|------|------|
| `stock_item` | 在庫 CSV 保存先 | 全置換 |
| `shipment_plan_item` | 出荷 CSV 保存先 | 全置換 |
| `product_master` | CSV 商品の辞書追加 | ensure（追加のみ） |
| `localStorage` measureos:article7-csv:* | UI 上の取込準備状態 | クライアントのみ |

---

## ■ 未実装（CSV取込）

| 項目 | 根拠 |
|------|------|
| 商品マスタ CSV 一括取込 API | `IMPORT_SCHEMAS` に `product_master` 定義のみ。router なし |
| 会社別ヘッダー override（DB） | `company_overrides` 拡張点のみ |
| CSV 取込時の第7条自動再計算 | 取込 router に rebuild 呼び出しなし |
| 部分更新・差分取込 | 全置換のみ |

---

# ⑤ 第7条

## ■ 画面

### 1. 第7条入力（手入力・専用 CSV・クローズ）

| 項目 | 内容 |
|------|------|
| **URL** | `/priority/input/v2` |
| **HTML** | `frontend/priority_input_v2.html` |
| **利用者** | 事務・営業（コード上の表記） |
| **セッション** | **不使用**（`main.py` で bootstrap なし） |

**画面項目**

- company_id 入力 + 「読み込み」
- 「CSVから第7条を再生成」ボタン
- メッセージ欄
- **CSV インポート（全置換・第7条専用）**
  - ヘッダ固定: `due_date,label,ship_value,prod_value`
  - ファイル選択 → プレビュー → 「CSV を一括保存（全置換）」
- **手入力**
  - 行ブロック: 商品, 出荷数, 製造数, 納期(date), クローズ(既存行のみ), 行削除
  - 「＋ 行を追加」
  - 「保存（全置換）」

**操作**

| 操作 | 処理 |
|------|------|
| 読み込み | `GET /v2/priority/items?company_id=` → open 行を手入力フォームに反映 |
| 保存（手入力） | confirm → `POST /v2/priority/create` |
| CSV 一括保存 | confirm → `POST /v2/priority/create` |
| クローズ | confirm → `POST /v2/priority/close`（行 ID 指定） |
| 再生成 | `POST /v2/priority/rebuild` |

**company ソース**

- 画面 `#company` 入力
- URL `?company=`
- `localStorage` キー `priority_input_v2_company`

**画面遷移**

- 関連リンク: `/priority/v2`, `/stock/import/v2`, `/shipment/import/v2`, `/office/v2`, `/debug/v2`, `/genba/v2`

---

### 2. 在庫/出荷 CSV 取込画面内の第7条フロー

- ④参照。再計算 + 監視盤リンクのみ

---

### 3. 優先度監視盤（Part3）

- `/priority/v2` へのリンク・遷移のみ Part2 範囲
- 表示 UI・一覧仕様は Part3

---

## ■ 処理（第7条）

### データモデル `priority_item`（概要）

| フィールド | 意味 |
|-----------|------|
| company_id | 会社 |
| product_code | 商品コード（rebuild 行は必須、手入力は空） |
| label | 商品名 |
| ship_value | 出荷数 |
| stock_qty | 在庫数（rebuild 時は stock_map から、手入力時は max(0, ship-prod)） |
| prod_value | 製造必要数（不足数） |
| due_date | 納期 ISO 文字列 |
| status | `open` / `closed` |
| is_after_cutoff | 受注締切後生成フラグ（観測用） |
| value | 旧互換（INSERT 時 ship_value と同値） |

---

### A. 再計算（`POST /v2/priority/rebuild`）

| 項目 | 内容 |
|------|------|
| **認証** | セッション検証**なし**。`validate_company_id` のみ |
| **入力** | `{ company_id }` |
| **出力** | `{ ok, success_count, warning_count, detail }` |

**処理手順**

1. `stock_item` から `product_code → stock_qty` マップ構築（code 空は除外）
2. `product_master`（active）から `product_code → safety_stock_value` 取得（NULL → 計算0, is_unset=true）
3. `shipment_plan_item` を id 昇順で走査
4. 各行:
   - product_code 空 → スキップ（warning）
   - `required_qty = shortage_qty(stock, safety, ship_qty)`  
     `shortage_qty`: `available = stock - safety - ship; max(0, -available)`
   - required_qty ≤ 0 → スキップ（「使用可能在庫で賄える」）
   - due_date 解釈不可 → スキップ（warning + ログ）
   - それ以外 → 挿入候補
5. **open の priority_item のみ削除**（closed 温存）
6. 候補を INSERT（status=open, is_after_cutoff=締切判定）
7. commit

**重要な計算特性**

- 同一 product_code の複数出荷行は、**それぞれ同じ stock_qty**（在庫マップ値）で独立計算
- 在庫未登録 product_code → stock=0 として計算
- 基準在庫は **商品マスタ** のみ参照（在庫 CSV の safety_stock 列は不使用）

**warning_count 内訳**

- 商品コード空欄
- 使用可能在庫で賄える出荷
- 納期解釈不可

---

### B. 手入力・専用 CSV 保存（`POST /v2/priority/create`）

| 項目 | 内容 |
|------|------|
| **認証** | セッション検証なし。`validate_company_id` |
| **入力** | `{ company_id, items[] }` 各 item: label, ship_value, prod_value, due_date |

**行ごとの検証**

| 条件 | 結果 |
|------|------|
| label 空 | スキップ（黙って除外） |
| ship/prod 非数値・非有限 | 422 |
| prod > ship | 422 |
| due_date 指定時 ISO 不正 | 422 |
| due_date 空 | null 許可 |

**保存**

- `stock_qty = max(0, ship - prod)`
- product_code = 空文字
- **open 行のみ全削除** → 新規 INSERT
- closed 行は温存
- is_after_cutoff = `is_after_order_cutoff(now, order_cutoff_time)`

**出力**

- 保存後の open 行一覧（GET items と同形式の enrich 付き）

---

### C. クローズ（`POST /v2/priority/close`）

| 項目 | 内容 |
|------|------|
| **認証** | セッション検証なし |
| **入力** | `{ company_id, item_ids[] }` |
| **処理** | 該当 company の指定 ID を status=closed に（既に closed はカウントしない） |
| **出力** | `{ ok, closed_count }` |
| **エラー** | company 空 / item_ids 空 / ID 不在 → 422 |

**仕様**

- 第5条実績は数量を変えない
- closed 行は `GET /v2/priority/items` に**出ない**

---

### D. 一覧取得（`GET /v2/priority/items`）— 第7条データ参照

| 項目 | 内容 |
|------|------|
| **認証** | セッション検証なし |
| **入力** | `company_id`（必須）, `article5_progress`（任意 bool） |
| **対象** | status=open のみ |
| **ソート** | priority_level（high→mid→low）, due_date 昇順, id 昇順 |

**GET 時に付与（DB は変更しない）**

| 付与項目 | 算出元 |
|---------|--------|
| priority_level / priority_score | `compute_article7_priority_phase1` |
| safety_stock_value / safety_stock_unset / usable_stock_qty | 商品マスタ |
| shortage_from_ship_qty / shortage_from_safety_qty / shortage_reason_labels | `decompose_shortage_for_display` |
| article7_actual_hint / article7_notices | 第5条 WorkUnit 実績（表示メタ） |
| article5_* 数量 | `article5_progress=true` 時のみ |
| production_mode | 商品マスタ |

※ Priority 監視盤での表示方法は Part3

---

### E. 優先度計算（`compute_article7_priority_phase1`）

**入力:** ship_qty, stock_qty, due_date, shortage_qty（prod_value 優先）

**ルール優先順**

1. 納期 < JST 今日 → **強制 high**
2. shortage ≤ 0 → **low**（score 0）
3. それ以外: `score = shortage_rate × due_weight`
   - shortage_rate = shortage / ship（ship>0 時）
   - due_weight: 納期≤1日=3, ≤3日=2, それ以外=1
   - score ≥ 1.5 → high, ≥ 0.5 → mid, else low

**閾値**は company_settings 未接続（定数固定）

---

### F. 不足内訳表示（`decompose_shortage_for_display`）

| パターン | ship_part | safety_part | ラベル |
|---------|-----------|-------------|--------|
| rebuild 行・出荷不足のみ | max(0, ship-stock) | max(0, prod-ship_part) | 出荷不足 / 基準在庫不足 |
| 基準在庫未設定 | safety_part 計算上は出るがラベル「基準在庫不足」は出さない |
| 手入力（product_code 空） | prod 全体 | 0 | 出荷不足（手入力） |

---

### G. 第5条連携（表示のみ）

**article7_context_for_priority_items**

- 本日/直近の実績ヒント・注意 notices（最大3件）
- PriorityItem の数量・status は**変更しない**

**article7_deviation（第5条側から利用）**

- open 第7条に存在しない商品で実績入力 → 逸脱
- 突合: 両方 product_code あり→コード一致、両方空→label 一致、片方のみコード→不一致

---

### H. 受注締切観測（`is_after_order_cutoff`）

- `company_settings.order_cutoff_time` と生成時刻（JST）比較
- 締切未設定 → 常に false
- priority_item.is_after_cutoff に保存（制御は行わない）

---

## ■ 業務ルール（第7条）

### 登録経路

| 経路 | 方式 | product_code |
|------|------|--------------|
| 在庫 CSV → 出荷 CSV → 再計算 | rebuild | あり（出荷行から） |
| 第7条入力・手入力 | create（open 全置換） | 空 |
| 第7条入力・専用 CSV | create（open 全置換） | 空 |
| 在庫/出荷 CSV 直接 | priority_item 生成しない | — |

### 更新

- rebuild: open 行を削除して再生成（closed 温存）
- create: open 行を削除して差替（closed 温存）
- GET items: 計算フィールドは都度算出（DB 更新なし）

### 削除

- 物理削除 API なし
- open → closed で論理クローズ
- CSV 取込は stock_item / shipment_plan_item を全置換（priority_item 自体は触らない）

### 再計算

- 前提: stock_item + shipment_plan_item が DB に存在
- UI 上は localStorage で「両 CSV 取込済み」を示すが、API は DB を直接参照
- 再計算は**手動**（取込成功時に自動実行しない）

### 状態遷移

```
priority_item.status:
  open  ──(close API / 事務操作)──► closed
  closed ──(rebuild/create)──► 温存（削除されない）
  open   ──(rebuild/create)──► 削除され新規 open が生成
```

### 制約事項

| 制約 | 内容 |
|------|------|
| 手入力 prod ≤ ship | create 時必須 |
| rebuild 保存条件 | required_qty > 0 かつ due_date 解釈可 |
| closed 温存 | rebuild/create とも open のみ削除 |
| 他社データ | 触らない |
| 在庫 CSV safety_stock | 第7条計算に未使用 |
| 基準在庫 | 商品マスタ active 行の product_code 必須 |
| 優先度閾値 | 全社固定定数 |
| CSV 取込画面 rebuild | セッション必須画面から呼ぶが、rebuild API 自体はセッション不要 |
| 第7条入力 | セッションゲートなし |

---

## ■ 使用データ（第7条）

| データ | 読取 | 書込 | 備考 |
|--------|------|------|------|
| `stock_item` | rebuild | CSV 取込 | 在庫ソース |
| `shipment_plan_item` | rebuild | CSV 取込 | 出荷ソース |
| `product_master` | rebuild, GET enrich | CSV ensure | 基準在庫・製造区分 |
| `priority_item` | GET, close | rebuild, create, close | 第7条本体 |
| `company_settings` | order_cutoff, input_mode | — | 締切観測・第5条突合 |
| `work_unit` | article7_context, deviation | — | 表示メタのみ |
| `localStorage` | CSV フロー UI | CSV 取込成功時 | API 非連動 |

---

## ■ 未実装（第7条）

| 項目 | 根拠 |
|------|------|
| rebuild/create/close/items のセッション認証 | priority router に `require_session_company_match` なし |
| 優先度閾値の company 別設定 | `article7_priority_phase1` コメント |
| 在庫 CSV safety_stock を第7条計算へ反映 | rebuild が product_master のみ参照 |
| CSV 取込後の自動 rebuild | stock/shipment router |
| 商品マスタ CSV import | schema 定義のみ |
| priority_item 物理削除 API | router なし |
| 第7条入力画面のセッション連動 | `main.py` bootstrap なし |
| rebuild 時の在庫消費（出荷行間） | 同一 stock_qty を各行に適用 |

---

# Part2 全体フロー（業務）

```
[事務] 会社ログイン（セッション）
    │
    ├─► 在庫 CSV 取込 ──► stock_item 全置換 + product_master ensure
    │
    ├─► 出荷 CSV 取込 ──► shipment_plan_item 全置換 + product_master ensure
    │
    ├─► （任意）商品マスタで safety_stock_value 設定
    │
    ├─► 第7条再計算 ──► priority_item（open）再生成
    │       └─ closed 温存
    │
    ├─► 第7条入力で手修正 / クローズ
    │       └─ create（open 全置換）/ close
    │
    └─► 優先度監視盤で確認（Part3）
```

---

# Part4 へ移管する情報（整理のみ）

以下は Part2 QA 仕様書本文には載せず、Part4 で詳細化する想定。

- 各 API の HTTP ステータス・detail 文字列一覧
- リクエスト/レスポンス JSON スキーマ全フィールド
- `stock_item` / `shipment_plan_item` / `priority_item` テーブル定義
- Alembic マイグレーション経路
- セッション middleware 実装詳細

---

# Part2 QA 仕様書作成可否

**この整理だけで Part2 の QA 外注用機能仕様書を書ける状態。**

カバー済み:

- ④ 在庫/出荷 CSV 取込の画面・操作・遷移・パース・保存・例外・業務ルール
- ⑤ 第7条の再計算・手入力・クローズ・優先度/不足計算・状態遷移・データ依存
- CSV→第7条の連携フロー（localStorage UI + rebuild）
- Part3/Part4 との責務分界

Part2 仕様書執筆時に Part4 参照として脚注を付けるとよい項目: HTTP エラー詳細、DB カラム型、priority API の認証なし事実。
