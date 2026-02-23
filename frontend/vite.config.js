import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    // Proxy das chamadas /autoauditor/api/* para o Django em :8000
    proxy: {
      "/autoauditor": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Gera os arquivos estáticos na pasta autoauditor/static/autoauditor/
    // para que o Django possa servi-los em produção via collectstatic
    outDir: "../static/autoauditor/dashboard",
    emptyOutDir: true,
  },
});
