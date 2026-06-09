# Domain Management DP2 — UX Improvements Design

**Date**: 2026-06-09  
**Status**: Approved  
**Scope**: 5 independent UX/operational improvements to the domain management app

---

## 1. 背景と目的

DP1（基盤実装）完了後、以下4点の操作性改善を DP2 として実装する。

1. ドメイン台帳の一覧/ツリーエリアのみをスクロール可能にし、フィルターと右ペインを固定する
2. 収集リクエストボタン押下後も一覧/ツリーの選択状態を維持する
3. `/import/` ページからテキスト貼り付けで複数ドメインを一括登録できるようにする
4. 情報収集バッチを30分間隔で実行する
5. 右ペインの幅をドラッグハンドルで可変にし、幅を localStorage に保存する

---

## 2. Req 1: スクロールレイアウト

### 要件

- フィルターバー（ステータスチップ + 検索）はスクロールに追従せず画面上部に固定
- 一覧/ツリーエリアはビューポート内で独立スクロール
- 右ペイン（ドメイン詳細）は一覧と同期せず独立スクロール

### 設計

`base.html` は変更しない。`ledger.html` の `<style>` ブロックで `.main-content` を上書きし、他ページへの影響をゼロに抑える。

#### CSS

```css
/* ledger.html <style> ブロックに追加 */
body { overflow: hidden; }
.main-content {
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding-bottom: 0;
}
.ledger-body {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.ledger-grid {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}
.ledger-scroll-left  { overflow-y: auto; height: 100%; }
.ledger-scroll-right { overflow-y: auto; height: 100%; }
```

#### HTML構造

```
.main-content (height:100vh; flex-col; overflow:hidden)
  └ div.ledger-body
      ├ ページヘッダー（固定）
      ├ フィルターチップ行（固定）
      └ .ledger-grid（flex:1 で残り高さを占有）
          ├ .ledger-scroll-left（一覧/ツリー: overflow-y:auto）
          └ .drawer-card.ledger-scroll-right（右ペイン: overflow-y:auto）
```

`.drawer-card` の既存 `min-height: 300px` は `min-height: 0` に変更する（親コンテナが高さを制御するため）。

#### 変更ファイル

- `templates/domains/ledger.html`（CSS追加 + HTML構造変更）

---

## 3. Req 2: 収集リクエスト後の選択状態維持

### 根本原因

`updatePanel()` が `fetch()` + `drawer.innerHTML = html` でパネルを差し替える際、htmx の MutationObserver がパネル内の `hx-post` フォームを再処理しないことがある。結果としてボタンがネイティブ `<form>` サブミットにフォールバックし、ブラウザがページ遷移することで JS 選択状態が失われる。

### 修正

`updatePanel()` の末尾に1行追加:

```javascript
function updatePanel(item) {
  if (!item || !item.dataset.panelUrl || !drawer) return Promise.resolve();
  return fetch(item.dataset.panelUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then(r => r.text())
    .then(html => {
      drawer.innerHTML = html;
      if (typeof htmx !== 'undefined') htmx.process(drawer); // ← 追加
    });
}
```

`htmx.process(drawer)` を呼ぶことで、動的注入された `hx-post` フォームが htmx に確実に登録される。htmx 未ロード時のガードも含む。

#### 変更ファイル

- `templates/domains/ledger.html`（`<script>` ブロック 1行追加）

---

## 4. Req 3: テキスト貼り付け一括登録

### 要件

- `/import/` ページからFQDNを改行区切りで貼り付けて登録できる
- 既存ドメインとの重複チェックをプレビュー画面で確認してから確定する
- 管理単位は指定せず登録し、後から個別に設定する

### フロー

```
/import/ → [file_type=text 選択 + テキスト貼り付け] → [プレビュー ボタン]
         → /import/preview/ (HTMX) → チェック結果テーブル表示
         → [登録ボタン] → /import/commit/ → 台帳へリダイレクト
```

### UI変更（`import_form.html`）

「ファイル種別」セレクトに `text`（テキスト直接入力）オプションを追加。`text` 選択時:
- ファイル選択欄を非表示
- テキストエリア（FQDN改行区切り）を表示
- フォームの `hx-encoding` を `application/x-www-form-urlencoded` に切り替え（ファイルアップロード不要なため）

既存の `onchange` ハンドラを拡張し、`text` 選択時は `form.removeAttribute('hx-encoding')`、それ以外は `form.setAttribute('hx-encoding', 'multipart/form-data')` を実行する。

`csv` / `zone` 選択時は従来通り `multipart/form-data`。

```html
<!-- 追加UI（概略）-->
<select name="file_type" id="file-type-select">
  <option value="csv">ドメインリスト CSV</option>
  <option value="zone">DNS ゾーンファイル（BIND形式）</option>
  <option value="text">テキスト直接入力（FQDN改行区切り）</option>
</select>

<!-- text 選択時のみ表示 -->
<textarea name="text_input" rows="10"
  placeholder="example.co.jp&#10;sub.example.co.jp&#10;..."></textarea>
```

### バックエンド変更

#### `importers.py` — 新関数

```python
def parse_text_input(content: str) -> list[ImportResult]:
    """改行区切りFQDNをImportResultリストに変換。空行・コメント行(#)は無視。"""
```

各行を正規化（strip、lower）し、以下の条件で判定する:
- **有効（`action="create"`）**: 1つ以上のドットを含み、英数字・ハイフン・ドットのみで構成されるFQDN
- **無効（`action="error"`）**: 空行・`#`コメント行以外で上記条件を満たさない行
- **スキップ**: 空行・`#`コメント行は `ImportResult` を生成しない

既存ドメインとの重複チェックは `import_preview` view 側（既存ロジック）で行う。

#### `views.py` — `import_preview`

`file_type == "text"` の場合:
```python
content = request.POST.get("text_input", "")
results = parse_text_input(content)
```

以降は既存の重複チェック・セッション保存ロジックをそのまま流用する。

#### `views.py` — `import_commit`

`file_type == "text"` の場合:
- `management_unit_id` は未送信
- 既存の fallback ロジック（`ManagementUnit.objects.order_by("fqdn_reversed").first()`）を使用
- プレビュー画面に注記: 「管理単位は一時的に既存の最初の管理単位を割り当てます。登録後に個別設定してください」

#### 変更ファイル

- `templates/domains/import_form.html`（タブ UI + テキストエリア追加）
- `domains/importers.py`（`parse_text_input()` 追加）
- `domains/views.py`（`import_preview` / `import_commit` に `file_type=text` 分岐追加）

---

## 5. Req 4: バッチ30分間隔

### 変更内容

```cron
# 変更前
0 * * * * python /app/manage.py run_batch_collection

# 変更後
*/30 * * * * python /app/manage.py run_batch_collection
```

`run_batch_collection` は既に実行中バッチの重複起動ガードを内包しているため、追加の変更は不要。

#### 変更ファイル

- `app/crontab`（1行変更）

---

## 6. Req 5: 右ペイン幅ドラッグリサイズ

### 要件

- 一覧/ツリーと右ペインの境界にドラッグハンドルを設置
- マウスドラッグで任意の幅に調整できる（min 240px / max 640px / default 360px）
- 設定した幅を `localStorage` に保存し、次回訪問時も維持する

### HTML構造変更

`.ledger-grid` の2列構成（`1fr 360px`）にハンドル列を加え3列構成にする:

```html
<div class="ledger-grid" id="ledger-grid">
  <div class="ledger-scroll-left"><!-- 一覧/ツリー --></div>
  <div class="panel-resize-handle" id="panel-resize-handle"></div>
  <div class="drawer-card ledger-scroll-right" id="drawer"><!-- 右ペイン --></div>
</div>
```

### CSS

```css
.ledger-grid {
  grid-template-columns: minmax(0,1fr) 6px var(--panel-width, 360px);
}
.panel-resize-handle {
  cursor: col-resize;
  background: transparent;
  position: relative;
  z-index: 10;
}
.panel-resize-handle:hover,
.panel-resize-handle.is-dragging {
  background: #e0e7ff;
}
```

### JS（`ledger.html` `<script>` ブロックに追加）

```javascript
(() => {
  const STORAGE_KEY = 'domain-ledger-panel-width';
  const MIN = 240, MAX = 640, DEFAULT = 360;
  const grid = document.getElementById('ledger-grid');
  const handle = document.getElementById('panel-resize-handle');
  if (!grid || !handle) return;

  function setWidth(w) {
    const clamped = Math.max(MIN, Math.min(MAX, w));
    grid.style.setProperty('--panel-width', clamped + 'px');
    return clamped;
  }

  const saved = parseInt(localStorage.getItem(STORAGE_KEY), 10);
  if (!isNaN(saved)) setWidth(saved);

  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    handle.classList.add('is-dragging');
    function onMove(e) {
      setWidth(grid.getBoundingClientRect().right - e.clientX);
    }
    function onUp(e) {
      handle.classList.remove('is-dragging');
      localStorage.setItem(STORAGE_KEY, setWidth(grid.getBoundingClientRect().right - e.clientX));
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
})();
```

### 変更ファイル

- `templates/domains/ledger.html`（HTML + CSS + JS 追加）のみ

---

## 8. 変更ファイルまとめ

| ファイル | 変更内容 | 規模 |
|---------|---------|------|
| `templates/domains/ledger.html` | CSS スクロールレイアウト + `htmx.process()` 1行 + ドラッグリサイズ | 中 |
| `templates/domains/import_form.html` | テキスト入力タブ追加 | 小 |
| `domains/importers.py` | `parse_text_input()` 追加 | 小 |
| `domains/views.py` | `file_type=text` 分岐追加 | 小 |
| `app/crontab` | `*/30 * * * *` に変更 | 極小 |

---

## 9. 将来検討事項

### 右ペイン読み込みの htmx ネイティブ化

**技術的負債メモ**: `updatePanel()` は現在 `fetch()` + `drawer.innerHTML` でパネルを差し替えている。今回は `htmx.process()` 1行で対処するが、本質的には htmx の外側で DOM 操作しているため、将来的に htmx を活用した機能（リアルタイム更新・SSE等）を追加する際に摩擦になりうる。

将来の改善候補:
- `drawer` に `hx-get`/`hx-trigger` を設定し、カスタムイベントでパネル読み込みをトリガー
- `selectItem()` 内で `htmx.trigger(drawer, 'loadPanel', { url: panelUrl })` を呼ぶ
- htmx がパネル HTML を差し替えるため `htmx.process()` 呼び出しが不要になる

このリファクタは DP2 スコープ外。DP3以降の htmx 活用機能追加時に合わせて検討する。

---

## 10. テスト方針

### Req 1（レイアウト）
- ブラウザで台帳ページを開き、100件以上のドメインが存在する状態でスクロール動作を確認
- フィルターバーが固定されていること
- 右ペインが独立スクロールすること
- 他ページ（ダッシュボード等）でレイアウトが崩れていないこと

### Req 2（選択状態）
- ドメインを選択 → 収集リクエストボタンを押下 → 選択が維持されること
- トーストが表示されること
- ページが遷移しないこと

### Req 3（一括登録）
- テキストエリアに有効・無効・既存FQDNを混在させてプレビューを確認
- 新規 / スキップ / エラーが正しく分類されること
- 登録後に台帳でドメインが確認できること
- 既存の CSV / ゾーンファイルインポートが引き続き動作すること

### Req 4（バッチ）
- crontab の変更を確認
- コンテナ再起動後に30分おきに実行されること（ログで確認）

### Req 5（ドラッグリサイズ）
- ハンドルをドラッグして幅が変わること
- 240px / 640px の境界でクランプされること
- ページリロード後に幅が復元されること
- ツリー / 一覧どちらのビューモードでも動作すること
