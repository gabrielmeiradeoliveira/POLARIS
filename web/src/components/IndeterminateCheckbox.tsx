import React, { useEffect, useRef } from "react";

export interface IndeterminateCheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  indeterminate?: boolean;
}

export function IndeterminateCheckbox({ indeterminate = false, ...props }: IndeterminateCheckboxProps) {
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
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
        width: 15,
        height: 15,
        accentColor: "#4F6BED",
        cursor: "pointer",
        verticalAlign: "middle",
        ...props.style,
      }}
    />
  );
}
