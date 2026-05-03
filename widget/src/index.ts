import { Widget } from "./Widget";

// Auto-initialize when script loads
(function () {
  if (typeof window === "undefined") return;

  // Wait for DOM
  const init = () => {
    const config = (window as any).AgeAyurvedaConfig || {};
    const widget = new Widget(config);
    widget.mount();
    (window as any).AgeAyurvedaWidget = widget;
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
