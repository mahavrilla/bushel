/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cream: "#FBF7EF",
        surface: "#FFFDF8",
        primary: { DEFAULT: "#C2410C", hover: "#9A3412" },
        accent: "#D97706",
        success: "#4D7C0F",
        danger: "#B91C1C",
        ink: "#44403C",
        heading: "#7C2D12",
        muted: "#A8A29E",
        line: "#ECDFC9",
        "tint-amber": "#FEF3E2",
        "tint-green": "#ECFCCB",
      },
      fontFamily: {
        heading: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: { xl: "0.75rem" },
    },
  },
  plugins: [],
};
