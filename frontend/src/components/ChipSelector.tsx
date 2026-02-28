import { useState } from 'react';

interface ChipSelectorProps {
  label: string;
  options: string[];           // full list fetched from API
  selected: string[];          // currently selected values (controlled)
  onChange: (values: string[]) => void;
  placeholder?: string;
}

export function ChipSelector({ label, options, selected, onChange, placeholder }: ChipSelectorProps) {
  const [inputValue, setInputValue] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  const filtered = options.filter(
    o => o.toLowerCase().includes(inputValue.toLowerCase()) && !selected.includes(o)
  );

  const addItem = (item: string) => {
    onChange([...selected, item]);
    setInputValue('');
    setIsOpen(false);
  };

  const removeItem = (item: string) => {
    onChange(selected.filter(s => s !== item));
  };

  return (
    <div className="relative min-w-[160px]">
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {selected.map(item => (
            <span
              key={item}
              className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded"
            >
              {item}
              <button
                type="button"
                onClick={() => removeItem(item)}
                className="hover:text-blue-600 leading-none"
                aria-label={`Remove ${item}`}
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}
      {/* Autocomplete input */}
      <input
        type="text"
        value={inputValue}
        onChange={e => { setInputValue(e.target.value); setIsOpen(true); }}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setTimeout(() => setIsOpen(false), 150)}
        placeholder={placeholder ?? `Add ${label.toLowerCase()}...`}
        className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
      />
      {/* Dropdown */}
      {isOpen && filtered.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded shadow-lg max-h-48 overflow-auto">
          {filtered.map(item => (
            <li
              key={item}
              onMouseDown={() => addItem(item)}
              className="px-3 py-1.5 text-sm hover:bg-blue-50 cursor-pointer"
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
