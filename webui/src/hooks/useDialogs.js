import { useState } from 'react'

// Groups the four transient overlay states (right-click context menu, the Save and
// Export option dialogs, the Help modal). Pure UI state — no business logic — lifted
// out of App so the orchestrator's state block reads as named, cohesive units.
export function useDialogs() {
  const [menu, setMenu] = useState(null)            // context menu { x, y, node }
  const [saveAsk, setSaveAsk] = useState(null)      // save dialog { mode:'in'|'as', count }
  const [exportAsk, setExportAsk] = useState(null)  // export options dialog { ids }
  const [helpOpen, setHelpOpen] = useState(false)
  return { menu, setMenu, saveAsk, setSaveAsk, exportAsk, setExportAsk, helpOpen, setHelpOpen }
}
