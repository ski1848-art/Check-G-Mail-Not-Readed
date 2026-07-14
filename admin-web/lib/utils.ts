/**
 * utils.ts - Tailwind CSS 클래스 병합 유틸리티
 * 
 * cn() 함수: clsx로 조건부 클래스를 결합하고, tailwind-merge로 충돌 해결
 * 예: cn("px-4 py-2", isActive && "bg-blue-500", "px-6") → "px-6 py-2 bg-blue-500"
 */
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

