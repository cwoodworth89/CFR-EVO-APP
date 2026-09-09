/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  // `hover:` only where a pointer can hover. Without this a tap on the touch TV or a phone
  // sets a button's hover state and nothing clears it (verified in the installed 3.4:
  // corePlugins.js wraps hover in `@media (hover: hover) and (pointer: fine)` under this
  // flag, and emits a bare `&:hover` otherwise).
  future: {
    hoverOnlyWhenSupported: true,
  },
  theme: {
    extend: {},
  },
  plugins: [
    // `touch:` -- a coarse pointer: a finger on the hall's touch TV, a phone, a tablet.
    // Used for target sizes and 16 px inputs, so the workstation's mouse layout is
    // untouched. The breakpoint for *layout* is `lg:`; this is only about what is pointing.
    function touchVariant({ addVariant }) {
      addVariant('touch', '@media (pointer: coarse)');
    },
  ],
}
