export const money = (n: number | null | undefined) =>
  n === null || n === undefined ? "Not applicable" : new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(n);

export const dateTime = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

export const reasonLabel = (r: string) =>
  ({ defective: "Defective", wrong_item: "Wrong item", damaged: "Damaged", changed_mind: "Changed mind", other: "Other" } as Record<string, string>)[r] ?? r;

export const actionLabel = (a: string | null) =>
  a ? ({ refund: "Refund", replacement: "Replacement", reject: "Rejection", manual_review: "Manual review" } as Record<string, string>)[a] ?? a : "None";
