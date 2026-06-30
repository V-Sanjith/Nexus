import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // Cache stale TTL set to 5 minutes
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
