# MEASURE OS 各条文スケルトンメモ

## 概要

各条文の実装入口を先にそろえるための最小構成メモ。

## 第1条（入口）スケルトン

### やること

```javascript
function rule_1_entry_control(event) {
  if (!rule_1_enabled) return

  // TODO: 入力経路チェック（未実装）
}
```

### 最低限持つもの

- input_source（web / 紙 / etc）
- user_role

### やるだけ

- 入口制御する場所だけ用意

### やらない

- ブロック処理
- UI 制御

## 第2条（キャパ）スケルトン

### やること

```javascript
function rule_2_capacity(event) {
  if (!rule_2_enabled) return

  // TODO: 件数カウント（未実装）
}
```

### 最低限

- planned_value / actual_value
- 集計単位（task_id or process_id）

### やるだけ

- 上限チェックする場所だけ確保

### やらない

- 上限ロジック
- 通知

## 第4条（監査）スケルトン

### やること

```javascript
function rule_4_audit(event) {
  if (!rule_4_enabled) return

  // TODO: 抽出・フラグ処理（未実装）
}
```

### 最低限

- 在庫 or 対象データの参照口
- is_unresolved フラグ（未修正）

### やるだけ

- 監査でフラグ立てる場所だけ用意

### やらない

- パレート
- ランダム抽出
- 棚卸ロジック

## 第6条（緊急）スケルトン

### やること

```javascript
function rule_6_emergency(event) {
  if (!rule_6_enabled) return

  // TODO: 緊急判定（未実装）
}
```

### 最低限

- is_emergency フラグ

### やるだけ

- 緊急扱いの入口だけ用意

### やらない

- 通知
- 全体連携

## 第7条（優先度）スケルトン

### やること

```javascript
function rule_7_priority(event) {
  if (!rule_7_enabled) return

  // TODO: 優先度計算（未実装）
}
```

### 最低限

- due_date（納期）
- priority_flag（仮）

### やるだけ

- 優先度を決める場所だけ用意

### やらない

- ソート
- 色分け

## イベント駆動（全条文共通）

```javascript
function handleEvent(event) {
  rule_1_entry_control(event)
  rule_2_capacity(event)
  rule_3_deadline(event)
  rule_4_audit(event)
  rule_5_core(event)
  rule_6_emergency(event)
  rule_7_priority(event)
}
```

- 全条文を同時に評価する
- 順番依存は持たせない

## フラグ管理

```javascript
const rules = {
  rule_1_enabled: false,
  rule_2_enabled: false,
  rule_3_enabled: false,
  rule_4_enabled: false,
  rule_6_enabled: false,
  rule_7_enabled: false,
}
```

## anomalies（共通）

```javascript
createAnomaly({
  rule_type: 'rule_4',
  type: 'unresolved_inventory',
})
```
