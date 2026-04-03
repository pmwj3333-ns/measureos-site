# MEASURE OS 第3条 締切制御モジュールメモ

## 目的

営業・事務による無理な割り込みや後出し指示を防止する。

## トリガー

- planned_created（予告）
- actual_created（実績）
- day_changed（営業日切替）
- scheduled_check（定時）

## 判定

- 締切時刻（`judgement_time` など）を超えた後の変更・追加

## 出力

- anomaly（締切違反）
- is_late_instruction（遅延指示フラグ）
