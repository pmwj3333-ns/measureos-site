(function () {
  const STATUS_RANK = {
    green: 0,
    yellow: 1,
    orange: 2,
    red: 3,
  };

  function statusRank(status) {
    return STATUS_RANK[status] ?? 0;
  }

  function worstStatus(reasons) {
    return (reasons || []).reduce((worst, reason) => (
      statusRank(reason?.status) > statusRank(worst) ? reason.status : worst
    ), "green");
  }

  function reasonKeySuffix(reasonKey) {
    const parts = String(reasonKey || "").split(".");
    return parts.length >= 3 ? parts.slice(2).join(".") : "";
  }

  function hasSuffixPattern(reasons, pattern) {
    return (reasons || []).some((reason) => reasonKeySuffix(reason.reasonKey).includes(pattern));
  }

  function stripWindowPrefix(text) {
    return String(text || "").replace(/^直近\d+分、/, "");
  }

  window.MO_COMPOSITE_REASON_HELPERS = {
    STATUS_RANK,
    statusRank,
    worstStatus,
    reasonKeySuffix,
    hasSuffixPattern,
    stripWindowPrefix,
  };
})();
