export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    // NodeJS runtime instrumentation bootstrap (OpenTelemetry etc.)
    console.log("[Next.js Instrumentation] Registering NodeJS diagnostics...");
  }
}
