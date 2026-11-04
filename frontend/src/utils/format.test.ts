import { describe, expect, it } from 'vitest'

import { formatDate, formatDateTime, formatMoney, formatNumber, getInitials, relativeTime } from './format'

describe('formatMoney', () => {
  it('formats a decimal string as currency', () => {
    const value = formatMoney('3500.50', 'USD')
    expect(value).toContain('3')
    expect(value).toContain('500')
    expect(value).toContain('50')
  })

  it('returns an em dash for missing values', () => {
    expect(formatMoney(null)).toBe('—')
    expect(formatMoney(undefined)).toBe('—')
    expect(formatMoney('')).toBe('—')
  })

  it('never returns NaN for invalid input', () => {
    expect(formatMoney('abc')).toBe('—')
  })
})

describe('formatNumber', () => {
  it('formats with two decimals', () => {
    expect(formatNumber('1234.5')).toContain('234')
  })
})

describe('dates', () => {
  it('formats a date', () => {
    expect(formatDate('2026-11-01')).toMatch(/2026/)
  })

  it('handles invalid date', () => {
    expect(formatDate('nope')).toBe('—')
    expect(formatDateTime(null)).toBe('—')
  })

  it('describes relative time', () => {
    expect(relativeTime(null)).toBe('jamais')
    expect(relativeTime(new Date().toISOString())).toBeTruthy()
  })
})

describe('getInitials', () => {
  it('builds initials from a name', () => {
    expect(getInitials('Emanuel Kabeya')).toBe('EK')
  })

  it('falls back to a placeholder', () => {
    expect(getInitials('')).toBe('?')
  })
})
