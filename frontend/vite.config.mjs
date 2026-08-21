import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    open: true,
    proxy: {
      // AI agent proxy MUST come before the Flask proxy — Vite matches in
      // declaration order, and a bare "/api" would swallow "/api/ai".
      "/api/ai": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: "dist",
  },
  envPrefix: ["VITE_", "REACT_APP_"], // Support both VITE_ and REACT_APP_ prefixes
  test: {
    environment: "jsdom",
    globals: true,
    pool: "threads",
    setupFiles: ["./src/test-setup.js"],
    css: false,
  },
})
