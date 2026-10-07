export default {
  plugins: {
    // Explicit path: a stale tailwind.config.js would otherwise win over the .ts.
    tailwindcss: { config: './tailwind.config.ts' },
    autoprefixer: {},
  },
};
