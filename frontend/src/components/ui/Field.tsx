import {
  forwardRef,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'

import { cn } from '../../utils/cn'

interface BaseProps {
  label?: string
  error?: string
  hint?: string
  required?: boolean
}

const Wrapper = ({
  label,
  error,
  hint,
  required,
  htmlFor,
  children,
}: BaseProps & { htmlFor?: string; children: ReactNode }) => (
  <div>
    {label && (
      <label htmlFor={htmlFor} className="field-label">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
    )}
    {children}
    {error ? (
      <p className="field-error" role="alert">
        {error}
      </p>
    ) : hint ? (
      <p className="mt-1.5 text-xs text-slate-500">{hint}</p>
    ) : null}
  </div>
)

export interface InputProps
  extends InputHTMLAttributes<HTMLInputElement>,
    BaseProps {
  icon?: ReactNode
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, required, className, id, icon, ...props },
  ref,
) {
  const inputId = id || props.name
  return (
    <Wrapper label={label} error={error} hint={hint} required={required} htmlFor={inputId}>
      <div className="relative">
        {icon && (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
            {icon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={Boolean(error)}
          className={cn('field-input', icon && 'pl-10', error && 'border-red-400 focus:border-red-500 focus:ring-red-500/10', className)}
          {...props}
        />
      </div>
    </Wrapper>
  )
})

export interface SelectProps
  extends SelectHTMLAttributes<HTMLSelectElement>,
    BaseProps {
  options: { value: string; label: string }[]
  placeholder?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, hint, required, options, placeholder, className, id, ...props },
  ref,
) {
  const selectId = id || props.name
  return (
    <Wrapper label={label} error={error} hint={hint} required={required} htmlFor={selectId}>
      <select
        ref={ref}
        id={selectId}
        aria-invalid={Boolean(error)}
        className={cn('field-input appearance-none bg-[length:16px] pr-9', error && 'border-red-400', className)}
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20' fill='none' stroke='%236b7280' stroke-width='1.6'%3E%3Cpath d='M6 8l4 4 4-4'/%3E%3C/svg%3E\")",
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'right 0.75rem center',
        }}
        {...props}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Wrapper>
  )
})

export interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement>,
    BaseProps {}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, hint, required, className, id, ...props },
  ref,
) {
  const areaId = id || props.name
  return (
    <Wrapper label={label} error={error} hint={hint} required={required} htmlFor={areaId}>
      <textarea
        ref={ref}
        id={areaId}
        aria-invalid={Boolean(error)}
        className={cn('field-input min-h-[88px] resize-y', error && 'border-red-400', className)}
        {...props}
      />
    </Wrapper>
  )
})
