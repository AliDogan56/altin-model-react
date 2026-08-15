/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_BACKEND_PROXY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
