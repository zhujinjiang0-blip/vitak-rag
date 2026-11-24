import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiTarget = env.VITE_API_TARGET || "http://127.0.0.1:8000";
  const processEnv = (
    globalThis as {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process?.env;
  const publicBuild =
    mode === "public" ||
    processEnv?.VITE_STATIC_DEMO === "true" ||
    env.VITE_STATIC_DEMO === "true";
  return {
    base: "./",
    plugins: [
      react(),
      {
        name: "vitak-public-entry",
        transformIndexHtml: {
          order: "pre",
          handler(html) {
            if (!publicBuild) return html;
            return html.replace(
              "/src/main.tsx",
              "/src/main.public.tsx"
            );
          }
        }
      }
    ],
    resolve: {
      alias: [
        {
          find: "@api",
          replacement: decodeURIComponent(
            new URL(
              publicBuild ? "./src/lib/api.public.ts" : "./src/lib/api.ts",
              import.meta.url
            ).pathname
          )
        },
        {
          find: "@auth",
          replacement: decodeURIComponent(
            new URL(
              publicBuild ? "./src/lib/auth.public.tsx" : "./src/lib/auth.tsx",
              import.meta.url
            ).pathname
          )
        }
      ]
    },
    server: {
      host: "127.0.0.1",
      port: 5173,
      proxy: {
        "/api": apiTarget,
        "/internal": apiTarget
      }
    }
  };
});
