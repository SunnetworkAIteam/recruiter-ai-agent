/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config) => {
    // face-api.js has both Node and browser code paths; we only ever
    // use the browser one (loadFromUri), but webpack still tries to
    // resolve the Node-only 'fs' import along the way. This tells
    // webpack that's fine to skip in the browser bundle — silences a
    // harmless warning, doesn't change runtime behavior.
    config.resolve.fallback = { ...config.resolve.fallback, fs: false };
    return config;
  },
};

export default nextConfig;
