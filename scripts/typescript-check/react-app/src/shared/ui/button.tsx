// A copy of the shadcn/ui button component (Q41).
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";
import { cn } from "@/shared/lib";

const buttonVariants = cva(
  "inline-flex items-center rounded-md text-sm font-medium",
  {
    variants: {
      variant: {
        default: "bg-blue-600 text-white",
        outline: "border border-gray-300",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export function Button({
  className,
  variant,
  asChild = false,
  ...props
}: ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp className={cn(buttonVariants({ variant, className }))} {...props} />
  );
}
