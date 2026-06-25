/** 第5条: 現場 A/B 中分類（field_v2 / office_v2 共通） */
(function (global) {
  const PROCESS_REASONS = [
    { code: "input_forgotten", label: "入力忘れ" },
    { code: "sequence_skip", label: "順序飛び" },
    { code: "deferred", label: "後回し" },
    { code: "handoff_missing", label: "引継ぎ漏れ" },
    { code: "other", label: "その他" },
  ];

  const RESULT_REASONS = [
    { code: "material_shortage", label: "材料不足" },
    { code: "equipment_stop", label: "設備停止" },
    { code: "work_error", label: "作業ミス" },
    { code: "estimate_wrong", label: "見立て違い" },
    { code: "priority_change", label: "突発優先変更" },
    { code: "other", label: "その他" },
  ];

  const PROCESS_LABELS = Object.fromEntries(
    PROCESS_REASONS.map((r) => [r.code, r.label]),
  );
  const RESULT_LABELS = Object.fromEntries(
    RESULT_REASONS.map((r) => [r.code, r.label]),
  );

  function normalizeClassification(raw) {
    const src = raw && typeof raw === "object" ? raw : {};
    const process = Array.isArray(src.process)
      ? src.process.filter((c) => PROCESS_LABELS[c])
      : [];
    const result = Array.isArray(src.result)
      ? src.result.filter((c) => RESULT_LABELS[c])
      : [];
    return { process, result };
  }

  function collectFromDom() {
    const pa = document.getElementById("pattern-a-cb");
    const pb = document.getElementById("pattern-b-cb");
    const parentA = pa && pa.checked === true;
    const parentB = pb && pb.checked === true;
    const out = { process: [], result: [] };
    if (parentA) {
      document
        .querySelectorAll('input[data-anomaly-side="process"][data-anomaly-code]:checked')
        .forEach((el) => {
          const code = el.getAttribute("data-anomaly-code");
          if (code && PROCESS_LABELS[code]) out.process.push(code);
        });
    }
    if (parentB) {
      document
        .querySelectorAll('input[data-anomaly-side="result"][data-anomaly-code]:checked')
        .forEach((el) => {
          const code = el.getAttribute("data-anomaly-code");
          if (code && RESULT_LABELS[code]) out.result.push(code);
        });
    }
    return out;
  }

  function applyToForm(data, opts) {
    const ro = opts && opts.readOnly === true;
    const cls = normalizeClassification(
      data && data.anomaly_classification ? data.anomaly_classification : null,
    );
    const pa = document.getElementById("pattern-a-cb");
    const pb = document.getElementById("pattern-b-cb");
    const parentA = data && data.pattern_a === true;
    const parentB = data && data.pattern_b === true;
    if (pa) pa.checked = parentA;
    if (pb) pb.checked = parentB;
    document
      .querySelectorAll("input[data-anomaly-side][data-anomaly-code]")
      .forEach((el) => {
        const side = el.getAttribute("data-anomaly-side");
        const code = el.getAttribute("data-anomaly-code");
        let checked = false;
        if (side === "process" && parentA) checked = cls.process.indexOf(code) !== -1;
        if (side === "result" && parentB) checked = cls.result.indexOf(code) !== -1;
        el.checked = checked;
        el.disabled = ro || (side === "process" ? !parentA : !parentB);
      });
    syncSubPanels({ readOnly: ro });
  }

  function clearForm() {
    const pa = document.getElementById("pattern-a-cb");
    const pb = document.getElementById("pattern-b-cb");
    if (pa) pa.checked = false;
    if (pb) pb.checked = false;
    document
      .querySelectorAll("input[data-anomaly-side][data-anomaly-code]")
      .forEach((el) => {
        el.checked = false;
      });
    syncSubPanels();
  }

  function syncSubPanels(opts) {
    const ro = opts && opts.readOnly === true;
    const pa = document.getElementById("pattern-a-cb");
    const pb = document.getElementById("pattern-b-cb");
    const subsA = document.getElementById("pattern-a-subs");
    const subsB = document.getElementById("pattern-b-subs");
    const parentA = pa && pa.checked === true;
    const parentB = pb && pb.checked === true;
    if (subsA) subsA.hidden = !parentA;
    if (subsB) subsB.hidden = !parentB;
    if (!parentA) {
      document
        .querySelectorAll('input[data-anomaly-side="process"][data-anomaly-code]')
        .forEach((el) => {
          el.checked = false;
        });
    }
    if (!parentB) {
      document
        .querySelectorAll('input[data-anomaly-side="result"][data-anomaly-code]')
        .forEach((el) => {
          el.checked = false;
        });
    }
    document
      .querySelectorAll('input[data-anomaly-side="process"][data-anomaly-code]')
      .forEach((el) => {
        el.disabled = ro || !parentA;
      });
    document
      .querySelectorAll('input[data-anomaly-side="result"][data-anomaly-code]')
      .forEach((el) => {
        el.disabled = ro || !parentB;
      });
  }

  function hasTimestamp(value) {
    return value != null && String(value).trim() !== "";
  }

  function systemPatternSegments(r) {
    const raw = r && r.system_pattern != null ? String(r.system_pattern).trim() : "";
    if (!raw) return [];
    return raw
      .replace(/;/g, ",")
      .replace(/，/g, ",")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  function rowHasFieldClassificationInput(r) {
    if (!r) return false;
    if (r.pattern_a === true || r.pattern_b === true) return true;
    const cls = normalizeClassification(
      r.anomaly_classification ? r.anomaly_classification : null,
    );
    return cls.process.length > 0 || cls.result.length > 0;
  }

  function inferAutoProcessDisplay(r) {
    if (!r) return false;
    if (r.is_invalid_flow === true) return true;
    if (hasTimestamp(r.actual_at) && !hasTimestamp(r.started_at)) return true;
    if (
      hasTimestamp(r.actual_at) &&
      !r.planned_registered_at &&
      !hasTimestamp(r.planned_at)
    )
      return true;
    if (r.is_missing === true) return true;
    return systemPatternSegments(r).indexOf("A*") !== -1;
  }

  function inferAutoResultDisplay(r) {
    if (!r) return false;
    if (r.is_diff_anomaly === true) return true;
    return systemPatternSegments(r).indexOf("B*") !== -1;
  }

  function isArticle7OnlyWithoutAb(r) {
    if (!r) return false;
    const segs = systemPatternSegments(r);
    const art7 =
      r.is_article7_deviation === true ||
      r.is_deviation === true ||
      segs.indexOf("7条逸脱") !== -1;
    if (!art7) return false;
    return !inferAutoProcessDisplay(r) && !inferAutoResultDisplay(r);
  }

  function resolveDisplay(r) {
    if (rowHasFieldClassificationInput(r)) {
      return {
        mode: "field",
        sectionLabel: "現場分類",
        row: r,
      };
    }
    if (isArticle7OnlyWithoutAb(r)) {
      return { mode: "none", sectionLabel: "", row: r };
    }
    const autoA = inferAutoProcessDisplay(r);
    const autoB = inferAutoResultDisplay(r);
    if (!autoA && !autoB) {
      return { mode: "none", sectionLabel: "", row: r };
    }
    return {
      mode: "auto",
      sectionLabel: "現場分類（自動判定）",
      autoProcess: autoA,
      autoResult: autoB,
      row: r,
    };
  }

  function formatDetailHtml(r, escFn) {
    const block = formatDetailBlock(r, escFn);
    return block ? block.html : "";
  }

  function formatDetailBlock(r, escFn) {
    const esc = escFn || function (s) {
      return String(s);
    };
    const display = resolveDisplay(r);
    if (display.mode === "none") {
      return null;
    }
    if (display.mode === "auto") {
      let html = "";
      if (display.autoProcess) {
        html +=
          '<div class="office-anomaly-cls-auto">' +
          esc("A 順序不備") +
          "</div>";
      }
      if (display.autoResult) {
        html +=
          '<div class="office-anomaly-cls-auto">' +
          esc("B 結果不備") +
          "</div>";
      }
      return { sectionLabel: display.sectionLabel, html: html };
    }
    const row = display.row;
    const cls = normalizeClassification(
      row && row.anomaly_classification ? row.anomaly_classification : null,
    );
    const parentA = row && row.pattern_a === true;
    const parentB = row && row.pattern_b === true;
    let html = "";
    if (parentA || cls.process.length) {
      html += '<div class="office-anomaly-cls-group">プロセス不備';
      if (cls.process.length) {
        html += '<ul class="office-anomaly-cls-list">';
        cls.process.forEach((code) => {
          html += "<li>・" + esc(PROCESS_LABELS[code] || code) + "</li>";
        });
        html += "</ul>";
      } else {
        html += '<div class="office-anomaly-cls-empty">・（中分類未選択）</div>';
      }
      html += "</div>";
    }
    if (parentB || cls.result.length) {
      html += '<div class="office-anomaly-cls-group">結果不備';
      if (cls.result.length) {
        html += '<ul class="office-anomaly-cls-list">';
        cls.result.forEach((code) => {
          html += "<li>・" + esc(RESULT_LABELS[code] || code) + "</li>";
        });
        html += "</ul>";
      } else {
        html += '<div class="office-anomaly-cls-empty">・（中分類未選択）</div>';
      }
      html += "</div>";
    }
    if (!html) return null;
    return { sectionLabel: display.sectionLabel, html: html };
  }

  global.MO_ANOMALY_CLASSIFICATION = {
    PROCESS_REASONS,
    RESULT_REASONS,
    PROCESS_LABELS,
    RESULT_LABELS,
    normalizeClassification,
    collectFromDom,
    applyToForm,
    clearForm,
    syncSubPanels,
    formatDetailHtml,
    formatDetailBlock,
    resolveDisplay,
    rowHasFieldClassificationInput,
    inferAutoProcessDisplay,
    inferAutoResultDisplay,
  };
})(typeof window !== "undefined" ? window : globalThis);
