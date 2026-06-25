/**
 * CSV 取込プレビュー用ヘッダー解決（サーバー GET /v2/csv/import-schemas/* と同じ別名辞書を利用）。
 */
(function (global) {
  "use strict";

  function normalizeHeaderCell(raw) {
    var t = String(raw == null ? "" : raw).trim().normalize("NFKC").toLowerCase();
    t = t.replace(/[\s\u3000]+/g, "");
    return t;
  }

  function buildAliasSets(schemaPayload) {
    var aliases = (schemaPayload && schemaPayload.aliases) || {};
    var sets = {};
    Object.keys(aliases).forEach(function (field) {
      sets[field] = {};
      (aliases[field] || []).forEach(function (a) {
        var n = normalizeHeaderCell(a);
        if (n) sets[field][n] = true;
      });
    });
    return sets;
  }

  function fieldOrder(schemaPayload) {
    var req = (schemaPayload && schemaPayload.required) || [];
    var opt = (schemaPayload && schemaPayload.optional) || [];
    return req.concat(opt);
  }

  function resolveHeaderIndices(headerCells, schemaPayload) {
    if (!schemaPayload) return null;
    var aliasSets = buildAliasSets(schemaPayload);
    var order = fieldOrder(schemaPayload);
    var out = {};
    for (var i = 0; i < headerCells.length; i++) {
      var n = normalizeHeaderCell(headerCells[i]);
      if (!n) continue;
      for (var k = 0; k < order.length; k++) {
        var field = order[k];
        if (out[field] !== undefined) continue;
        if (aliasSets[field] && aliasSets[field][n]) {
          out[field] = i;
          break;
        }
      }
    }
    var req = schemaPayload.required || [];
    for (var r = 0; r < req.length; r++) {
      if (out[req[r]] === undefined) return null;
    }
    return out;
  }

  global.CsvHeaderResolver = {
    normalizeHeaderCell: normalizeHeaderCell,
    buildAliasSets: buildAliasSets,
    resolveHeaderIndices: resolveHeaderIndices,
  };
})(typeof window !== "undefined" ? window : globalThis);
