import js from "@eslint/js";
import ts from "typescript-eslint";
import reactPlugin from "eslint-plugin-react";
import reactHooksPlugin from "eslint-plugin-react-hooks";
import nextPlugin from "@next/eslint-plugin-next";
import jsxA11yPlugin from "eslint-plugin-jsx-a11y";
import simpleImportSortPlugin from "eslint-plugin-simple-import-sort";
import unusedImportsPlugin from "eslint-plugin-unused-imports";
import prettierConfig from "eslint-config-prettier";

export default ts.config(
  // Global ignore patterns
  {
    ignores: [
      "**/node_modules/**",
      "**/.next/**",
      "**/dist/**",
      "**/build/**",
      "**/coverage/**",
      "**/playwright-report/**",
      "**/test-results/**"
    ]
  },

  // Base ESLint recommended rules
  js.configs.recommended,

  // TypeScript ESLint recommended type-checked and strict rulesets
  ...ts.configs.recommendedTypeChecked,
  ...ts.configs.strictTypeChecked,

  // Feature Configuration
  {
    files: ["**/*.{js,jsx,ts,tsx}"],
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooksPlugin,
      "@next/next": nextPlugin,
      "jsx-a11y": jsxA11yPlugin,
      "simple-import-sort": simpleImportSortPlugin,
      "unused-imports": unusedImportsPlugin
    },
    languageOptions: {
      parserOptions: {
        // Automatically locates the closest tsconfig.json for each file in the monorepo
        project: true,
        tsconfigRootDir: import.meta.dirname
      }
    },
    settings: {
      react: {
        version: "detect"
      }
    },
    rules: {
      // React Rules overrides
      ...reactPlugin.configs.recommended.rules,
      ...reactHooksPlugin.configs.recommended.rules,
      "react/react-in-jsx-scope": "off", // Next.js 15 does not require React in scope
      "react/prop-types": "off", // TypeScript handles prop validation compile-time
      
      // Next.js Rules overrides
      ...nextPlugin.configs.recommended.rules,
      ...nextPlugin.configs["core-web-vitals"].rules,

      // Accessibility Rules
      ...jsxA11yPlugin.configs.recommended.rules,

      // Import Sorting & Unused Imports
      "simple-import-sort/imports": "error",
      "simple-import-sort/exports": "error",
      "no-unused-vars": "off", // Disabled in favor of typescript-eslint rule
      "@typescript-eslint/no-unused-vars": "off", // Disabled in favor of unused-imports plugin
      "unused-imports/no-unused-imports": "error",
      "unused-imports/no-unused-vars": [
        "warn",
        {
          "vars": "all",
          "varsIgnorePattern": "^_",
          "args": "after-used",
          "argsIgnorePattern": "^_"
        }
      ],

      // Type-Safety & Promise Safety Rules
      "@typescript-eslint/no-floating-promises": "error", // Promises must be awaited or handled
      "@typescript-eslint/no-misused-promises": [
        "error",
        {
          "checksVoidReturn": false // Permits passing async handlers to onClick and other void events
        }
      ],
      "@typescript-eslint/await-thenable": "error", // Only await thenable items
      "@typescript-eslint/no-explicit-any": "warn", // Discourage any-escape-hatches
      "@typescript-eslint/no-unnecessary-condition": "warn", // Flags checks that always evaluate to true/false

      // Security Rules
      "react/no-danger": "warn" // Alert developers to dangerous innerHTML bindings
    }
  },

  // Turn off stylistic/formatting ESLint rules to prevent conflicts with Prettier
  prettierConfig
);
