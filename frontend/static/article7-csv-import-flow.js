/**
 * 第7条 CSV取込 → 再計算 → 優先度監視盤 の UI フロー（在庫・出荷取込画面共通）
 * 取込状態は company 単位で localStorage に保持（API 変更なし）。
 */
(function (global) {
  "use strict";

  var STORAGE_PREFIX = "measureos:article7-csv:";

  function storageKey(companyId) {
    return STORAGE_PREFIX + String(companyId || "").trim();
  }

  function readState(companyId) {
    try {
      var raw = localStorage.getItem(storageKey(companyId));
      if (!raw) return { stock: false, shipment: false };
      var parsed = JSON.parse(raw);
      return {
        stock: parsed.stock === true,
        shipment: parsed.shipment === true,
      };
    } catch (_) {
      return { stock: false, shipment: false };
    }
  }

  function writeState(companyId, patch) {
    var cur = readState(companyId);
    var next = {
      stock: patch.stock != null ? !!patch.stock : cur.stock,
      shipment: patch.shipment != null ? !!patch.shipment : cur.shipment,
    };
    try {
      localStorage.setItem(storageKey(companyId), JSON.stringify(next));
    } catch (_) { /* ignore quota */ }
    return next;
  }

  function markStockImported(companyId) {
    return writeState(companyId, { stock: true });
  }

  function markShipmentImported(companyId) {
    return writeState(companyId, { shipment: true });
  }

  function readinessHtml(stockOk, shipmentOk) {
    function mark(ok) {
      return ok
        ? '<span class="readiness-mark readiness-ok">✓</span>'
        : '<span class="readiness-mark readiness-ng">×</span>';
    }
    return (
      '<span class="readiness-item">在庫CSV：' +
      mark(stockOk) +
      "</span>" +
      '<span class="readiness-item">出荷CSV：' +
      mark(shipmentOk) +
      "</span>"
    );
  }

  function disabledReason(stockOk, shipmentOk, pageKind) {
    if (stockOk && shipmentOk) return "";
    if (!stockOk && !shipmentOk) {
      return "在庫CSVと出荷CSVの両方を取り込むと、第7条を再計算できます。";
    }
    if (!stockOk) {
      return "在庫CSVを取り込むと再計算できます。";
    }
    if (!shipmentOk) {
      return "出荷CSVを取り込むと再計算できます。";
    }
    if (pageKind === "stock" && !shipmentOk) {
      return "出荷CSVを取り込むと再計算できます。";
    }
    if (pageKind === "shipment" && !stockOk) {
      return "在庫CSVを取り込むと再計算できます。";
    }
    return "";
  }

  function otherCsvLink(pageKind) {
    if (pageKind === "stock") {
      return '<a class="article7-flow-link" href="/shipment/import/v2">出荷CSV取込へ</a>';
    }
    return '<a class="article7-flow-link" href="/stock/import/v2">在庫CSV取込へ</a>';
  }

  /**
   * @param {object} opts
   * @param {"stock"|"shipment"} opts.pageKind
   * @param {() => Promise<{ok:boolean,message:string,company:string}>} opts.ensureSessionCompanyForWrite
   * @param {(text:string, cls?:string) => void} opts.setImportMsg
   */
  function initArticle7CsvImportFlow(opts) {
    var pageKind = opts.pageKind;
    var ensureSession = opts.ensureSessionCompanyForWrite;
    var setImportMsg = opts.setImportMsg;

    var flowEl = document.getElementById("article7-flow");
    var readinessEl = document.getElementById("article7-flow-readiness");
    var hintEl = document.getElementById("article7-flow-hint");
    var rebuildActionsEl = document.getElementById("article7-rebuild-actions");
    var rebuildBtn = document.getElementById("btn-rebuild-priority");
    var rebuildStatusEl = document.getElementById("article7-rebuild-status");
    var boardActionsEl = document.getElementById("article7-board-actions");

    if (!flowEl || !rebuildBtn) return;

    var rebuildState = "idle"; // idle | loading | done | error
    var flowVisible = false;

    function setRebuildStatus(text, cls) {
      if (!rebuildStatusEl) return;
      rebuildStatusEl.textContent = text || "";
      rebuildStatusEl.className = "hint article7-rebuild-status" + (cls ? " " + cls : "");
      rebuildStatusEl.hidden = !text;
    }

    function showRebuildActions(show) {
      if (rebuildActionsEl) rebuildActionsEl.hidden = !show;
    }

    function showBoardActions(show) {
      if (boardActionsEl) boardActionsEl.hidden = !show;
    }

    function resetRebuildButton() {
      rebuildBtn.classList.remove("is-loading");
      rebuildBtn.textContent = "第7条を再計算する";
    }

    /** 再計算ボタン領域は loading / idle / error のときのみ表示。done では必ず非表示。 */
    function syncActionUi(ready) {
      if (rebuildState === "done") {
        showRebuildActions(false);
        showBoardActions(true);
        resetRebuildButton();
        return;
      }

      showBoardActions(false);

      if (rebuildState === "loading") {
        showRebuildActions(true);
        rebuildBtn.textContent = "第7条を再計算中…";
        rebuildBtn.disabled = true;
        rebuildBtn.classList.add("is-loading");
        setRebuildStatus("", "");
        return;
      }

      showRebuildActions(true);
      resetRebuildButton();
      rebuildBtn.disabled = !ready;
    }

    function renderReadiness(companyId) {
      var st = readState(companyId);
      if (readinessEl) {
        readinessEl.innerHTML = readinessHtml(st.stock, st.shipment);
      }
      var ready = st.stock && st.shipment;
      var reason = disabledReason(st.stock, st.shipment, pageKind);
      if (hintEl) {
        if (rebuildState === "done") {
          hintEl.textContent = "再計算が完了しました。優先度監視盤で結果を確認してください。";
        } else if (ready) {
          hintEl.innerHTML =
            "在庫と出荷のデータが揃いました。第7条を再計算してから、優先度監視盤で確認してください。";
        } else {
          var extra = otherCsvLink(pageKind);
          hintEl.innerHTML = reason + (extra ? " " + extra : "");
        }
      }
      if (rebuildState === "idle") {
        setRebuildStatus("", "");
      }
      syncActionUi(ready);
    }

    function showFlow(companyId) {
      flowVisible = true;
      flowEl.hidden = false;
      renderReadiness(companyId);
    }

    function onImportSuccess(companyId) {
      if (pageKind === "stock") markStockImported(companyId);
      else markShipmentImported(companyId);
      showFlow(companyId);
      if (flowEl && flowEl.scrollIntoView) {
        flowEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }

    function bootFromStorage() {
      var cid =
        typeof global.__MO_BOOTSTRAP_COMPANY__ === "string"
          ? global.__MO_BOOTSTRAP_COMPANY__.trim()
          : "";
      if (!cid) return;
      var st = readState(cid);
      if (st.stock || st.shipment) {
        showFlow(cid);
      }
    }

    rebuildBtn.addEventListener("click", async function () {
      if (rebuildState === "loading" || rebuildState === "done") return;
      var check = await ensureSession();
      if (!check.ok) {
        setImportMsg(check.message, "err");
        return;
      }
      var company = check.company;
      var st = readState(company);
      if (!st.stock || !st.shipment) {
        renderReadiness(company);
        return;
      }

      rebuildState = "loading";
      syncActionUi(true);

      try {
        var res = await fetch("/v2/priority/rebuild", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ company_id: company }),
        });
        var data = {};
        try {
          data = await res.json();
        } catch (_) {}
        if (!res.ok) {
          var d = data.detail;
          if (typeof d !== "string") d = JSON.stringify(data.detail || data);
          rebuildState = "error";
          setRebuildStatus("再計算に失敗しました: " + (d || res.statusText), "err");
          syncActionUi(st.stock && st.shipment);
          return;
        }
        var n = data.success_count != null ? data.success_count : 0;
        var line = "✓ 第7条データを再計算しました（" + n + "件）";
        var det = data.detail != null ? String(data.detail).trim() : "";
        if (det) line += "。" + det;
        rebuildState = "done";
        setRebuildStatus(line, "ok");
        syncActionUi(true);
        if (hintEl) {
          hintEl.textContent = "再計算が完了しました。優先度監視盤で結果を確認してください。";
        }
      } catch (e) {
        rebuildState = "error";
        setRebuildStatus(String(e.message || e), "err");
        syncActionUi(st.stock && st.shipment);
      }
    });

    bootFromStorage();

    return {
      onImportSuccess: onImportSuccess,
      refresh: function (companyId) {
        if (flowVisible || readState(companyId).stock || readState(companyId).shipment) {
          showFlow(companyId);
        }
      },
    };
  }

  global.Article7CsvImportFlow = {
    readState: readState,
    markStockImported: markStockImported,
    markShipmentImported: markShipmentImported,
    init: initArticle7CsvImportFlow,
  };
})(typeof window !== "undefined" ? window : this);
