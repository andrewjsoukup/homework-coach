// Homework Coach ships its UI as a native Desktop panel (desktop/plugin.js).
// This hidden web-dashboard entry only exists so the shared backend mount is discovered;
// it registers a placeholder so the dashboard does not report NO_REGISTER.
(function () {
  var reg = window.__HERMES_PLUGINS__;
  if (reg && typeof reg.register === "function") {
    reg.register("homework-coach", function () { return null; });
  }
})();
