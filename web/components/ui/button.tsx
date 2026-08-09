import { type ButtonHTMLAttributes, forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium " +
    "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 " +
    "focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-blue-600 text-white hover:bg-blue-500 shadow-sm shadow-blue-950/50",
        outline: "border border-slate-700 bg-transparent text-slate-200 hover:bg-slate-800 hover:border-slate-600",
        ghost: "text-slate-300 hover:bg-slate-800 hover:text-slate-100",
        destructive: "bg-red-600/90 text-white hover:bg-red-600",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-7 px-2.5 text-xs",
        lg: "h-10 px-6",
        icon: "h-8 w-8 shrink-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
);
Button.displayName = "Button";
