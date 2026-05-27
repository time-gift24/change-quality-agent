import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
