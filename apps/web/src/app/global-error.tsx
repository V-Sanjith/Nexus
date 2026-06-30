"use client";

import React from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="flex flex-col items-center justify-center min-h-screen bg-background text-foreground p-4">
        <div className="max-w-md w-full text-center space-y-6">
          <h2 className="text-2xl font-semibold tracking-tight">Something went wrong</h2>
          <p className="text-sm text-muted-foreground">
            A critical system error has occurred. Our engineers have been alerted. Reference ID:{" "}
            <code className="bg-muted px-1 py-0.5 rounded text-xs">{error.digest || "N/A"}</code>
          </p>
          <button
            onClick={() => reset()}
            className="w-full py-2 px-4 bg-primary text-primary-foreground font-medium rounded-md hover:bg-opacity-90 transition-all"
          >
            Try Again
          </button>
        </div>
      </body>
    </html>
  );
}
