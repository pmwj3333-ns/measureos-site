# MEASURE OS

現場の行動ログを記録・可視化するシステム

- 予告
- 着手
- 実績
- 異常検知

フェーズ1：ログ取得

---

## 本番運用フロー

本番サーバー（`/var/www/measureos-site`）のコードは **GitHub を唯一の正** とし、サーバー上での直接編集は行いません。

### 通常デプロイ手順

1. **Cursor で修正**（ローカル / リポジトリ）
2. **テスト** — `python3 -m pytest`
3. **commit**
4. **push** — ブランチ `milestone/package-a-phase1`（本番追従ブランチ）
5. **サーバーへ SSH**
6. **`deploy-measureos`** — `git pull` 成功時のみ `measureos.service` を再起動

```bash
ssh root@162.43.48.122
deploy-measureos
```

### 運用ルール

| ルール | 内容 |
|--------|------|
| サーバー直接編集 **禁止** | `app/main.py`・`run.py` 等を本番で `vim` 等で直さない |
| 修正は GitHub 経由 | 必ずローカルで修正 → commit → push → deploy |
| pull 失敗時 | **restart しない**。`git status` で原因確認（ローカル差分・ブランチ不一致等） |
| 緊急時のみ例外 | 障害復旧の一時対応は可。復旧後 **必ず GitHub に反映** し、サーバー差分を `git checkout --` で破棄 |

### deploy-measureos の初回インストール / 更新

リポジトリ内スクリプトを `/usr/local/bin` に配置します（pull 後に再実行）。

```bash
cd /var/www/measureos-site
git pull origin milestone/package-a-phase1
sudo install -m 755 scripts/deploy-measureos.sh /usr/local/bin/deploy-measureos
```

### pull が失敗したとき

```bash
cd /var/www/measureos-site
git status
git diff app/main.py   # 例: サーバー手修正の確認
git checkout -- app/main.py run.py   # 手修正を破棄（GitHub 版に戻す）
deploy-measureos
```

`deploy-measureos` は **tracked ファイルにローカル変更がある場合も pull 前に停止** します。未追跡ファイル（`__pycache__` 等）だけでは停止しません。

### 環境変数（任意）

| 変数 | 既定 | 説明 |
|------|------|------|
| `MEASUREOS_APP_DIR` | `/var/www/measureos-site` | リポジトリルート |
| `MEASUREOS_BRANCH` | `milestone/package-a-phase1` | pull 対象ブランチ |
| `MEASUREOS_SERVICE` | `measureos.service` | systemd ユニット名 |

---

## ローカル開発

```bash
python3 -m pytest
python3 run.py   # http://127.0.0.1:8002 （開発専用。本番では使用しない）
```

`run.py` はローカル開発用です。本番は `measureos.service` が `app.main:app` を直接起動します。
