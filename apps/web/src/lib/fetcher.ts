import { env } from "@/config/env";

export async function fetcher<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${env.NEXT_PUBLIC_API_URL}${path}`;
  
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  
  const config = {
    ...options,
    headers,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData?.message || `HTTP error! status: ${response.status}`);
  }

  return response.json() as Promise<T>;
}
