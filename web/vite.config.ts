import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API is same-origin in production (FastAPI serves web/dist); in dev it is proxied.
const backend = process.env.API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: { "/api": { target: backend, changeOrigin: false } },
  },
  preview: {
    port: 4173,
    proxy: { "/api": { target: backend, changeOrigin: false } },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2020",
    chunkSizeWarningLimit: 1200, // maplibre-gl is a lazy chunk and is intentionally large
  },
});
