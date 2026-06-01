import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 4
  }).format(value);
}

export function formatLatency(ms: number) {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(2)}s`;
  }

  return `${Math.round(ms)}ms`;
}
