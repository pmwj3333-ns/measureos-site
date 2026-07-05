/**
 * Package A 導入企業向け画面共通: セッション切れ（401）時の UX
 */
(function (global) {
  "use strict";

  var MSG = "セッションが切れました。再度ログインしてください。";
  var REDIRECT_MS = 2400;
  var _scheduled = false;

  function redirectToOfficeLogin(returnTo) {
    var path =
      returnTo != null && String(returnTo).trim()
        ? String(returnTo).trim()
        : global.location.pathname || "/office/v2";
    global.location.replace(
      "/office/v2?return_to=" + encodeURIComponent(path)
    );
  }

  function ensureToastEl() {
    var id = "mo-session-expired-toast";
    var el = global.document.getElementById(id);
    if (el) return el;
    el = global.document.createElement("div");
    el.id = id;
    el.setAttribute("role", "status");
    el.style.cssText =
      "position:fixed;bottom:32px;left:50%;transform:translateX(-50%) translateY(20px);" +
      "background:rgba(28,28,30,0.88);color:#fff;padding:11px 22px;border-radius:30px;" +
      "font-size:0.88rem;opacity:0;transition:opacity 0.2s,transform 0.2s;" +
      "pointer-events:none;max-width:92vw;z-index:10000;text-align:center;line-height:1.4;";
    global.document.body.appendChild(el);
    return el;
  }

  function defaultNotify(message, durationMs) {
    var el = ensureToastEl();
    el.textContent = message;
    el.style.opacity = "1";
    el.style.transform = "translateX(-50%) translateY(0)";
    global.setTimeout(function () {
      el.style.opacity = "0";
      el.style.transform = "translateX(-50%) translateY(20px)";
    }, durationMs || REDIRECT_MS);
  }

  function handleSessionExpired(options) {
    if (_scheduled) return;
    _scheduled = true;
    var opts = options || {};
    var notify =
      typeof opts.notify === "function" ? opts.notify : defaultNotify;
    var returnTo = opts.returnTo;
    notify(MSG, REDIRECT_MS);
    global.setTimeout(function () {
      redirectToOfficeLogin(returnTo);
    }, REDIRECT_MS);
  }

  function isRedirectPending() {
    return _scheduled;
  }

  function isSessionExpiredError(err) {
    return Boolean(err && err._sessionExpired);
  }

  function createSessionExpiredError(data) {
    var err = new Error(MSG);
    err._sessionExpired = true;
    if (data !== undefined) err._data = data;
    return err;
  }

  function ifUnauthorized(res, options) {
    if (!res || res.status !== 401) return null;
    handleSessionExpired(options);
    return createSessionExpiredError();
  }

  function responseUrlPath(res) {
    try {
      return new URL(res.url, global.location.origin).pathname;
    } catch (_) {
      return "";
    }
  }

  function shouldIgnoreFetch401(res) {
    var path = responseUrlPath(res);
    if (path === "/v2/office/login" || path === "/v2/office/logout") return true;
    if (
      path === "/v2/office/session" &&
      global.location.pathname === "/office/v2"
    ) {
      return true;
    }
    return false;
  }

  function installFetch401Handler() {
    if (global.__MO_OFFICE_SESSION_FETCH_401_INSTALLED__) return;
    if (typeof global.fetch !== "function") return;
    global.__MO_OFFICE_SESSION_FETCH_401_INSTALLED__ = true;
    var originalFetch = global.fetch;
    global.fetch = function () {
      return originalFetch.apply(this, arguments).then(function (res) {
        if (res && res.status === 401 && !shouldIgnoreFetch401(res)) {
          handleSessionExpired();
        }
        return res;
      });
    };
  }

  global.OfficeSessionExpired = {
    MSG: MSG,
    REDIRECT_MS: REDIRECT_MS,
    redirectToOfficeLogin: redirectToOfficeLogin,
    handleSessionExpired: handleSessionExpired,
    isRedirectPending: isRedirectPending,
    isSessionExpiredError: isSessionExpiredError,
    createSessionExpiredError: createSessionExpiredError,
    ifUnauthorized: ifUnauthorized,
  };
  installFetch401Handler();
})(typeof window !== "undefined" ? window : this);
