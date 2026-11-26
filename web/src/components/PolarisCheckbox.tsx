import React from "react";

export interface PolarisCheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  indeterminate?: boolean;
}

export function PolarisCheckbox({ indeterminate = false, ...props }: PolarisCheckboxProps) {
  const ref = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  return (
    <input
      type="checkbox"
      ref={ref}
      {...props}
      style={{
        width: 16,
        height: 16,
        accentColor: "var(--accent-cyan)",
        cursor: "pointer",
        borderRadius: "var(--radius-sm)",
        verticalAlign: "middle",
        ...props.style,
      }}
    />
  );
}
