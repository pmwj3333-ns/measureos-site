window.MO_TEAM_REVIEW_SEARCH = (() => {
  function normalizeText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function buildReviewSearchResults(reviewHistory, query) {
    const needle = normalizeText(query);
    if (!needle) return [];

    return (Array.isArray(reviewHistory) ? reviewHistory : [])
      .filter((entry) => normalizeText(entry.reviewText).includes(needle))
      .map((entry) => ({
        ...entry,
        excerpt: buildExcerpt(entry.reviewText, needle),
      }));
  }

  function buildExcerpt(text, needle) {
    const source = String(text || "");
    const lower = source.toLowerCase();
    const index = lower.indexOf(needle);
    if (index < 0) return source.slice(0, 120);

    const start = Math.max(0, index - 24);
    const end = Math.min(source.length, index + needle.length + 48);
    const prefix = start > 0 ? "…" : "";
    const suffix = end < source.length ? "…" : "";
    return `${prefix}${source.slice(start, end)}${suffix}`;
  }

  return {
    buildReviewSearchResults,
  };
})();
