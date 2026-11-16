import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// BatchlensCraft is served under /batchlens/ behind the suite's proxy (PlantCraft owns /).
export default defineConfig({
  base: "/batchlens/",
  plugins: [react()],
  build: {
    outDir: "dist",
    // Not "assets": <prefix>assets/<id> is the suite's uniform page for one asset.
    assetsDir: "static",
    sourcemap: false,
    rollupOptions: { output: { manualChunks: { icons: ["lucide-react"] } } },
  },
  server: {
    port: 5177,
    proxy: { "/batchlens/api": "http://127.0.0.1:9100", "/batchlens/healthz": "http://127.0.0.1:9100" },
  },
  // Vitest 5 no longer derives import.meta.env.BASE_URL from `base` in tests.
  test: { environment: "jsdom", env: { BASE_URL: "/batchlens/" } },
});
