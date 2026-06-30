"use client";

import React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { LazyMotion, domAnimation } from "framer-motion";
import { queryClient } from "@/lib/query-client";
import { Toaster } from "sonner";

export function GlobalProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>
        <LazyMotion features={domAnimation}>
          {children}
          <Toaster richColors position="top-right" />
        </LazyMotion>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
