// Window-level guard against drag-and-drop NAVIGATION.
//
// WebView2 navigates the window to a file (or link) dropped on it. pywebview re-injects its JS
// bridge into whatever page loads there, so a hostile .html/.svg dropped onto a window would
// get `window.pywebview.api.*` (open / save arbitrary paths). The organizer already cancels
// file drops via useOsFileDrop; the PDF-Tool surface had no handler at all (security review
// 2026-11-25, H-3). This cancels the default action of EVERY dragover/drop that nobody else
// handled. It never blocks in-page drags that call preventDefault themselves — it only adds
// the cancel where the page left the default (navigation) in place.
export function installDropGuard(target = window) {
  const cancel = (e) => { if (!e.defaultPrevented) e.preventDefault() }
  target.addEventListener('dragover', cancel)
  target.addEventListener('drop', cancel)
  return () => {
    target.removeEventListener('dragover', cancel)
    target.removeEventListener('drop', cancel)
  }
}
