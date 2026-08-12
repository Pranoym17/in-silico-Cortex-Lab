import { ButtonHTMLAttributes, ReactNode } from "react";

type PearlButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  icon?: ReactNode;
};

export function PearlButton({ children, className, icon, ...props }: PearlButtonProps) {
  return (
    <button className={["pearl-button", className].filter(Boolean).join(" ")} {...props}>
      <span className="pearl-button-content">
        {icon ? <span aria-hidden="true" className="pearl-button-icon">{icon}</span> : null}
        <span>{children}</span>
      </span>
    </button>
  );
}
