import React, { createContext, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'
import { createApiClient } from '../service/apiClient.js'

const BrandSeasonContext = createContext({
  brand: '',
  season: '',
  setBrand: () => {},
  setSeason: () => {},
  brands: [],
  seasons: [],
  loading: true,
})

export function BrandSeasonProvider({ children }) {
  const { user } = useAuth()
  const [brands, setBrands] = useState([])
  const [seasons, setSeasons] = useState([])
  const [brand, setBrand] = useState('')
  const [season, setSeason] = useState('')
  const [loading, setLoading] = useState(true)

  // 1) 마운트 시 본인 권한 brands 로드 + 첫 brand 자동 선택
  useEffect(() => {
    if (!user?.email) return
    let canceled = false
    ;(async () => {
      try {
        const api = createApiClient(user.email, '', '', user.role)
        const res = await api.get('/api/brands')
        const data = res.ok ? await res.json() : null
        if (canceled) return
        const list = data?.brands || []
        setBrands(list)
        if (list.length > 0) setBrand(list[0])
      } catch (e) {
        console.error('[BrandSeasonContext] /brands 실패:', e)
      } finally {
        if (!canceled) setLoading(false)
      }
    })()
    return () => { canceled = true }
  }, [user?.email])

  // 2) brand 변경 시 seasons 로드 + 첫 season 자동 선택
  useEffect(() => {
    if (!user?.email || !brand) return
    let canceled = false
    ;(async () => {
      try {
        const api = createApiClient(user.email, brand, '', user.role)
        const res = await api.get('/api/seasons')
        const data = res.ok ? await res.json() : null
        if (canceled) return
        const list = data?.seasons || []
        setSeasons(list)
        if (list.length > 0) setSeason(list[0].season_code)
      } catch (e) {
        console.error('[BrandSeasonContext] /seasons 실패:', e)
      }
    })()
    return () => { canceled = true }
  }, [user?.email, brand])

  return (
    <BrandSeasonContext.Provider
      value={{ brand, season, setBrand, setSeason, brands, seasons, loading }}
    >
      {children}
    </BrandSeasonContext.Provider>
  )
}

export function useBrandSeason() {
  return useContext(BrandSeasonContext)
}
