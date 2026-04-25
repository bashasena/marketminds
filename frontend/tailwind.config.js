/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ink: { 950: "#0b1220", 900: "#111827", 800: "#1f2937" },
        mist: "#e5e7eb",
      },
    },
  },
  plugins: [],
};
