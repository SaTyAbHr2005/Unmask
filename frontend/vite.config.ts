import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Pages are lazy-loaded (see main.tsx), so the 3D libraries only download on the pages that use them.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: { chunkSizeWarningLimit: 1600 },
});
