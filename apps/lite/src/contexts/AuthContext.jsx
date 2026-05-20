import React, { createContext, useContext } from 'react'
import { useDcsAuth } from '../hooks/useDcsAuth'

// order-ai-share: 항상 인증된 단일 운영자.
// hasRole/hasAnyRole 은 호출처 호환을 위해 유지 — 항상 true 반환.

const AuthContext = createContext({
  user: null,
  isLoading: true,
  hasRole: () => true,
  hasAnyRole: () => true,
})

export function AuthProvider({ children }) {
  const { user, isLoading } = useDcsAuth()

  const hasRole = () => true
  const hasAnyRole = () => true

  return (
    <AuthContext.Provider value={{ user, isLoading, hasRole, hasAnyRole }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
