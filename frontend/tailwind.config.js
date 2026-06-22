/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#F6F7F9",
        surface: "#FFFFFF",
        line: "#ECECEF",
        "line-strong": "#E5E7EB",
        heading: "#1F2937",
        ink: "#374151",
        muted: "#6B7280",
        primary: { DEFAULT: "#C2410C", hover: "#9A3412", tint: "#FBEAE0" },
        warning: { DEFAULT: "#B45309", tint: "#FEF3C7" },
        danger: { DEFAULT: "#B91C1C", tint: "#FEE2E2" },
        success: { DEFAULT: "#15803D", tint: "#DCFCE7" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        lg: "0.625rem",
        xl: "0.75rem",
        "2xl": "0.875rem",
      },
    },
  },
  plugins: [],
};
