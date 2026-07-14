import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev mode: `npm run dev` serves the SPA on :5173 and proxies /api to the
// FastAPI server started with `mtg gui --no-browser` (default port 8321).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8321",
    },
  },
});
