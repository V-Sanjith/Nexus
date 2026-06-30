import { z } from "zod";

const envSchema = z.object({
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  NEXT_PUBLIC_API_URL: z.string().url().default("http://127.0.0.1:8002"),
  
  // Feature Flags
  NEXT_PUBLIC_FF_ENABLE_COPILOT: z.preprocess((val) => val === "true", z.boolean()).default(true),
  NEXT_PUBLIC_FF_ENABLE_SANDBOX: z.preprocess((val) => val === "true", z.boolean()).default(true),
  NEXT_PUBLIC_FF_ENABLE_GRAPH: z.preprocess((val) => val === "true", z.boolean()).default(true),
  NEXT_PUBLIC_FF_ENABLE_RESEARCH: z.preprocess((val) => val === "true", z.boolean()).default(true),
  NEXT_PUBLIC_FF_ENABLE_DNA: z.preprocess((val) => val === "true", z.boolean()).default(true),
  NEXT_PUBLIC_FF_ENABLE_MEMORY: z.preprocess((val) => val === "true", z.boolean()).default(true),
  NEXT_PUBLIC_FF_ENABLE_INSIGHTS: z.preprocess((val) => val === "true", z.boolean()).default(true),
});

export const env = envSchema.parse({
  NODE_ENV: process.env.NODE_ENV,
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  NEXT_PUBLIC_FF_ENABLE_COPILOT: process.env.NEXT_PUBLIC_FF_ENABLE_COPILOT,
  NEXT_PUBLIC_FF_ENABLE_SANDBOX: process.env.NEXT_PUBLIC_FF_ENABLE_SANDBOX,
  NEXT_PUBLIC_FF_ENABLE_GRAPH: process.env.NEXT_PUBLIC_FF_ENABLE_GRAPH,
  NEXT_PUBLIC_FF_ENABLE_RESEARCH: process.env.NEXT_PUBLIC_FF_ENABLE_RESEARCH,
  NEXT_PUBLIC_FF_ENABLE_DNA: process.env.NEXT_PUBLIC_FF_ENABLE_DNA,
  NEXT_PUBLIC_FF_ENABLE_MEMORY: process.env.NEXT_PUBLIC_FF_ENABLE_MEMORY,
  NEXT_PUBLIC_FF_ENABLE_INSIGHTS: process.env.NEXT_PUBLIC_FF_ENABLE_INSIGHTS,
});
