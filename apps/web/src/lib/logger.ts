type LogLevel = "info" | "warn" | "error" | "debug";

export const logger = {
  log(level: LogLevel, message: string, meta?: Record<string, any>) {
    const timestamp = new Date().toISOString();
    const payload = {
      timestamp,
      level,
      message,
      ...meta,
    };
    
    if (process.env.NODE_ENV === "development") {
      console[level](`[${timestamp}] [${level.toUpperCase()}] ${message}`, meta || "");
    } else {
      // Stream logs to console stdout for container aggregation
      console.log(JSON.stringify(payload));
    }
  },
  info(message: string, meta?: Record<string, any>) {
    this.log("info", message, meta);
  },
  warn(message: string, meta?: Record<string, any>) {
    this.log("warn", message, meta);
  },
  error(message: string, meta?: Record<string, any>) {
    this.log("error", message, meta);
  },
  debug(message: string, meta?: Record<string, any>) {
    this.log("debug", message, meta);
  }
};
