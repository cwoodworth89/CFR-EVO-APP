// Crash-class lint config for the pre-commit guard.
//
// Deliberately narrow. These are the mistakes that compile cleanly through Vite
// and then throw a ReferenceError in the browser on the kiosk:
//   - no-undef                   : referencing a variable that does not exist
//   - react-hooks/immutability   : using a binding before it is declared (TDZ)
//
// Style and hygiene rules live in eslint.config.js and run via `npm run lint`.
// They are advisory and must not block a commit.
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      'no-undef': 'error',
      'react-hooks/immutability': 'error',
    },
  },
])
