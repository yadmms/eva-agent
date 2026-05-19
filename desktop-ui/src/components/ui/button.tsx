import * as React from "react";
import { cn } from "@/lib/utils";

const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "ghost" | "outline" | "destructive"; size?: "sm" | "default" | "lg" }>(
  ({ className, variant = "default", size = "default", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
        {
          "bg-primary text-primary-foreground shadow hover:bg-primary/90": variant === "default",
          "bg-transparent hover:bg-accent/10 hover:text-accent": variant === "ghost",
          "border border-input bg-transparent hover:bg-accent/10 hover:text-accent": variant === "outline",
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90": variant === "destructive",
        },
        { "h-8 px-3 text-xs": size === "sm", "h-9 px-4 py-2": size === "default", "h-10 px-6": size === "lg" },
        className
      )}
      {...props}
    />
  )
);
Button.displayName = "Button";
export { Button };
