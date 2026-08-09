import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none",
  {
    variants: {
      variant: {
        neutral: "bg-slate-800 text-slate-300",
        blue: "bg-blue-500/15 text-blue-300",
        emerald: "bg-emerald-500/15 text-emerald-300",
        red: "bg-red-500/15 text-red-300",
        amber: "bg-amber-500/15 text-amber-300",
        sky: "bg-sky-500/15 text-sky-300",
      },
    },
    defaultVariants: { variant: "neutral" },
  }
);

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
