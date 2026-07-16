/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_AUTH_MODE?: string;
  readonly VITE_PRODUCT_NAME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
