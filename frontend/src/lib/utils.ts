import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
export const number = (value: number, digits = 0) =>
  new Intl.NumberFormat('en-NP', { maximumFractionDigits: digits }).format(value)
export const currency = (value: number) => `NPR ${number(value)}`
export const dateTime = (value: string) =>
  new Date(
    value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`,
  ).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
