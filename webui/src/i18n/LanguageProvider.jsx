/* eslint-disable react-refresh/only-export-components --
   Deliberately co-locates the LanguageProvider component with its useT() hook
   (a context+hook pair imported by 6 components). Splitting the hook into its
   own file just to satisfy fast-refresh adds indirection for no runtime gain. */
// React binding for the i18n core: a context holding { lang, setLang, t } and a
// useT() hook. The context DEFAULT is a working German `t`, so components rendered
// without a provider (e.g. in unit tests) still translate (to the default language)
// instead of crashing — that keeps the existing German-string tests green.
import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { DEFAULT_LANG, resolveInitialLang, translate } from './index'

const STORAGE_KEY = 'beleg.lang'

const I18nContext = createContext({
  lang: DEFAULT_LANG,
  setLang: () => {},
  t: (key, vars) => translate(DEFAULT_LANG, key, vars),
})

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    let stored = null
    try { stored = localStorage.getItem(STORAGE_KEY) } catch { /* ignore */ }
    const nav = typeof navigator !== 'undefined' ? navigator.language : ''
    return resolveInitialLang(stored, nav)
  })

  const setLang = useCallback((next) => {
    setLangState(next)
    try { localStorage.setItem(STORAGE_KEY, next) } catch { /* ignore */ }
  }, [])

  const t = useCallback((key, vars) => translate(lang, key, vars), [lang])
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useT() {
  return useContext(I18nContext)
}
