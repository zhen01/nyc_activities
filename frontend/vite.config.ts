import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev-server proxy so the Vite app (localhost:5173) can call the FastAPI
// backend (localhost:8000) with relative paths ("/recommendations", ...)
// exactly as it will in production once the built app is served from the
// same origin as the API (see backend/app/static/).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/recommendations": "http://localhost:8000",
      "/organizations": "http://localhost:8000",
      "/favorites": "http://localhost:8000",
    },
  },
});
