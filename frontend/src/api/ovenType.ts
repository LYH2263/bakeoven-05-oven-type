export type OvenType = "tray" | "stone";

export const OVEN_TYPE_LABELS: Record<OvenType, string> = {
  tray: "盘炉",
  stone: "石板",
};

export function ovenTypeLabel(t: string | null | undefined): string {
  return OVEN_TYPE_LABELS[(t ?? "tray") as OvenType] ?? t ?? "盘炉";
}
