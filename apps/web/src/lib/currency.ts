/**
 * Centralized Currency Formatting Utility for Nexus AI Shopping Advisor
 * Market: India (en-IN)
 * Format Examples: ₹35,000 | ₹1,00,000 | ₹1,49,999
 */
export function formatCurrency(amount: number | null | undefined, symbol: string = "₹"): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "Not available";
  }
  const formatted = new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 0,
  }).format(Math.round(amount));

  return `${symbol}${formatted}`;
}

export function formatPrice(amount: number | null | undefined, symbol: string = "₹"): string {
  return formatCurrency(amount, symbol);
}
