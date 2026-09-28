// VerifyMeasure frontend runtime configuration.
//
// This is the single place where the deployed API address lives. No page may
// hardcode a host. Resolution order (first match wins):
//
//   1. <meta name="api-base-url" content="https://api.example.com"> in <head>
//      -- lets a deployment inject the value without touching this file.
//   2. window.APP_CONFIG.API_BASE_URL, set by an injected config script.
//   3. API_BASE_URL_DEFAULT below.
//
// Replace API_BASE_URL_DEFAULT at deploy time, or inject a meta tag, per
// DEPLOY.md. Keep it https:// in production; it must match an entry in the
// backend's CORS_ALLOWED_ORIGINS allowlist.

(function (global) {
    "use strict";

    var API_BASE_URL_DEFAULT = "https://api.verifymeasure.example";

    function readMeta(name) {
        var tag = document.querySelector('meta[name="' + name + '"]');
        return tag ? tag.getAttribute("content") : null;
    }

    function normalise(value) {
        if (!value) {
            return "";
        }
        return String(value).trim().replace(/\/+$/, "");
    }

    var injected = (global.APP_CONFIG && global.APP_CONFIG.API_BASE_URL) || null;
    var apiBaseUrl =
        normalise(readMeta("api-base-url")) ||
        normalise(injected) ||
        normalise(API_BASE_URL_DEFAULT);

    // The public verification page always lives on the same origin that served
    // this script, so derive it instead of hardcoding a domain.
    var frontendBaseUrl =
        normalise(readMeta("frontend-base-url")) || global.location.origin;

    global.APP_CONFIG = Object.assign({}, global.APP_CONFIG, {
        API_BASE_URL: apiBaseUrl,
        FRONTEND_URL: frontendBaseUrl
    });

    // Convenience accessor for pages that prefer a function.
    global.apiUrl = function (path) {
        var suffix = String(path || "");
        if (suffix && suffix.charAt(0) !== "/") {
            suffix = "/" + suffix;
        }
        return global.APP_CONFIG.API_BASE_URL + suffix;
    };
})(window);
