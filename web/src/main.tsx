import { createRoot } from "react-dom/client";
import "./fonts";
import "./styles.css";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(<App />);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Installability is a bonus; the app works without a service worker.
    });
  });
}
