"use client";

import { useState, useRef, useEffect } from "react";
import { Search, X } from "lucide-react";
import { clsx } from "clsx";

interface SearchBarProps {
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  debounceMs?: number;
}

export function SearchBar({
  value = "",
  onChange,
  placeholder = "Buscar normativos...",
  className,
  debounceMs = 400,
}: SearchBarProps) {
  const [localValue, setLocalValue] = useState(value);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setLocalValue(newValue);

    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      onChange(newValue);
    }, debounceMs);
  };

  const handleClear = () => {
    setLocalValue("");
    onChange("");
  };

  return (
    <div className={clsx("relative", className)}>
      <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
        <Search className="h-4 w-4 text-gray-400" />
      </div>
      <input
        type="search"
        value={localValue}
        onChange={handleChange}
        placeholder={placeholder}
        className={clsx(
          "block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-10",
          "text-sm text-gray-900 placeholder-gray-400",
          "focus:border-navy-700 focus:outline-none focus:ring-2 focus:ring-navy-700/20",
          "transition-colors duration-200"
        )}
      />
      {localValue && (
        <button
          type="button"
          onClick={handleClear}
          className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400 hover:text-gray-600"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
