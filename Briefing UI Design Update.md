# Briefing UI Design — Update Mai 2026

> **Status:** Ergänzt das ursprüngliche `Briefing UI Design.txt`.
> Wo dieses Dokument konkrete Entscheidungen trifft, **überschreibt es das alte Briefing**.
> Begleitmaterial: `BelegTool UI Redesign.html` (interaktiver Mockup mit Vorher / Variante A / Variante B).

---

## 0. Designentscheidung

Wir gehen mit **Variante A („faithful ttk")**. Bedeutet:

- Optik **bleibt ttk/Windows-nativ** — keine Theme-Bibliothek, keine Custom-Widgets.
- Keine Schrift-, Farb- oder Padding-Änderungen, die nicht aus ttk-Standardmitteln kommen.
- Das ursprüngliche Briefing-Verbot „Keine Theming-Änderungen" gilt weiterhin.

Variante B (modernisiert) ist verworfen und dient nur als Referenz im Mockup.

---

## 1. Toolbar — radikal entschlackt

Im Briefing-Original waren **8 Elemente in 4 Gruppen** vorgesehen. Wir gehen weiter:

> **Regel:** Jede Aktion, die im Kontextmenü erreichbar ist, hat in der Toolbar **nichts** zu suchen.
> Aktion = Toolbar **oder** Kontextmenü, nie beides.

Die neue Toolbar besteht **nur noch aus Datei-Aktionen, die nicht auf einer Knoten-Auswahl beruhen**:

```
[Importieren]  [Speichern]  [Speichern als]
```

Das war's. 3 Buttons.

**Entfernt aus der Toolbar (gegenüber Briefing-Original):**

| Button            | Stattdessen erreichbar in                       |
|-------------------|--------------------------------------------------|
| Exportieren       | Datei-Menü, Kontextmenü                          |
| Splitten          | Bearbeiten-Menü, Kontextmenü                     |
| Zusammenführen    | Bearbeiten-Menü, Kontextmenü                     |
| Ordner (Dropdown) | Bearbeiten-Menü, Kontextmenü                     |
| Status (Dropdown) | Bearbeiten-Menü → Status, Kontextmenü → Status   |
| Löschen           | Bearbeiten-Menü, Kontextmenü, `Entf`-Taste       |
| Umbenennen        | Bearbeiten-Menü, Kontextmenü, `F2`-Taste         |
| Schließen / Beenden | Datei-Menü, Window-X                           |

**Implementierungshinweis (`panel_controls.py`):**
Alle entsprechenden `ttk.Button`-Instanzen + `pack`-Aufrufe ersatzlos streichen.
Die zugehörigen `*-Selected`-Methoden bleiben — sie werden weiter aus dem Menü-/Kontextmenü-Pfad aufgerufen.

---

## 2. Menüleiste (unverändert gegenüber Original-Briefing)

```
Datei              Bearbeiten         Ansicht                  ?
─────────────────  ─────────────────  ───────────────────────  ─────
Importieren…      Splitten           Zoom +        Strg++     Info
Speichern  Strg+S Zusammenführen     Zoom −        Strg+−
Speichern als…   ─────────────────  Zoom zurücksetzen Strg+0
Exportieren…      Ordner innerhalb   ─────────────────
─────────────────  Ordner unterhalb   ☑ Original anzeigen
Schließen          ─────────────────
─────────────────  Umbenennen   F2
Beenden  Alt+F4    Löschen      Entf
                   ─────────────────
                   Status ▶  Vorjahreswert / Zu erfassen / Erfasst
```

**Implementierungshinweis (`belegtool_main.py`):**
- `tk.Menu(self)` als Toplevel-Menü, `self.config(menu=menubar)` direkt nach `super().__init__()`.
- Accelerator-Texte (`accelerator="Strg+S"`) sind reine **Anzeige**. Die echten Bindings:
  ```python
  self.bind_all("<Control-s>", lambda e: self.control_panel.save_automatic())
  self.bind_all("<Control-Shift-S>", lambda e: self.control_panel.save_as())
  self.bind_all("<Control-o>", lambda e: self.control_panel.import_pdf())
  ```
- F2/Entf-Bindings auf dem TreeView existieren bereits (`view_tree.py`) und bleiben.

---

## 3. Kontextmenü — neue Reihenfolge

In `view_tree.py`, `self.context_menu` komplett neu aufbauen (Reihenfolge **streng einhalten** — sie spiegelt Häufigkeit, gefolgt von destruktiven Aktionen unten):

```
Umbenennen                F2
──────────────────
Exportieren…
──────────────────
Splitten
Zusammenführen
──────────────────
Status ▶  Vorjahreswert
          Zu erfassen
          Erfasst
──────────────────
Ordner innerhalb
Ordner unterhalb
──────────────────
Löschen                   Entf
```

**Implementierungshinweis:** `Status ▶` als `tk.Menu(self.context_menu, tearoff=0)`, dann `self.context_menu.add_cascade(label="Status", menu=status_submenu)`. Drei `add_command` darin für die drei Status-Werte.

Accelerator-Anzeige im Kontextmenü via `accelerator="F2"` / `accelerator="Entf"`.

---

## 4. Vorschaufenster — restrukturierte Steuerleisten

Stapelung von unten nach oben (`pack(side="bottom")` in dieser Reihenfolge):

```
┌─────────────────────────────────────────────────────────┐
│ [CANVAS – Vorschau]                                     │
├─────────────────────────────────────────────────────────┤
│ Ansicht:  [100%] [━━━━━━━━━━━━━━] [⟳ Drehen ▾]         │  view_frame
├─────────────────────────────────────────────────────────┤
│ DPI:      [50]   [━━━━━━━━━━━━━━]  ∞                   │  compression_frame
│ Kompression: [✓ jpg · 120 KB · bestes Ergebnis ▾]      │  method_frame (conditional)
│ [Kompression wieder erlauben]                           │  (nur wenn no_compression)
├─────────────────────────────────────────────────────────┤
│              [✓ Lesbarkeit geprüft]                     │  commit_frame
└─────────────────────────────────────────────────────────┘
```

**Pack-Reihenfolge (`view_preview.py`, in `__init__`):**

```python
self.commit_frame.pack(side="bottom", pady=4)       # zuletzt → ganz unten
self.compression_frame.pack(side="bottom", pady=4)  # darüber
# method_frame wird nur conditional gepackt
self.view_frame.pack(side="bottom", pady=4)         # direkt unter Canvas
self.canvas_frame.pack(side="top", fill="both", expand=True)
```

**Labels (Strings exakt so):**
- View-Row: `Label(text="Ansicht:")` ganz links
- DPI-Row: `Label(text="DPI:")` ganz links
- Method-Row: `Label(text="Kompression:")` (vorher: „Methode:")

**Methodenwahl (`_update_method_selector`):**
- Format: `"✓ jpg · 120 KB · bestes Ergebnis"` für die kleinste, sonst `"png · 185 KB"`.
- Einheit immer **KB**, gerundet auf ganze Zahlen.
- Bestes Ergebnis = kleinstes `len(data)` aus `_compression_results`.

---

## 5. TreeView — keine Änderung an Logik, nur Validierung

Status-Tag-Farben in `view_tree.py` **bleiben exakt wie sie sind**:

```python
self.tree.tag_configure("status_erfasst_light",       foreground="green")
self.tree.tag_configure("status_erfasst_dark",        foreground="green")
self.tree.tag_configure("status_zu_erfassen_light",   foreground="blue", background="#ddeeff")
self.tree.tag_configure("status_zu_erfassen_dark",    foreground="blue", background="#99aacc")
self.tree.tag_configure("status_vorjahreswert_light", foreground="red",  background="#ffdada")
self.tree.tag_configure("status_vorjahreswert_dark",  foreground="red",  background="#dd8888")
```

Nichts ändern, nichts ergänzen. Insbesondere:
- Keine zusätzlichen Icons in der Treeview (ttk-Treeview-Default beibehalten).
- Keine Fett-Schreibung für `_dark`-Varianten.
- Keine zusätzlichen Status-Werte einführen.

---

## 6. Kontextsensitive States — Vollständigkeitsliste

Diese Buttons / Menüeinträge müssen je nach Auswahl `state="disabled"` / `state="normal"`:

| Element                | Aktiv wenn                                                        |
|------------------------|--------------------------------------------------------------------|
| Menü/Ctx: Splitten     | Genau **1** Knoten ausgewählt, **kein Ordner**                     |
| Menü/Ctx: Zusammenführen | **≥2** Knoten ausgewählt, **gleiche Ebene**                      |
| Menü/Ctx: Ordner innerhalb | Genau **1** **Ordner** ausgewählt                              |
| Menü/Ctx: Ordner unterhalb | Genau **1** Knoten ausgewählt, der ein **Geschwister** hat     |
| Menü/Ctx: Exportieren  | **≥1** Knoten ausgewählt                                           |
| Menü/Ctx: Umbenennen   | Genau **1** Knoten ausgewählt                                      |
| Menü/Ctx: Löschen      | **≥1** Knoten ausgewählt                                           |
| Menü/Ctx: Status →…    | **≥1** Knoten ausgewählt                                           |
| DPI-Slider, Methode, Commit | Genau **1** Knoten, **kein Ordner**, **kein Background-Task** |

Bereits implementiert in `_set_controls_enabled()` für Preview-Controls — analoge Funktion für Menüs / Kontextmenüs neu schreiben:

```python
def _update_menu_states(self):
    selection = self.tree_view.tree.selection()
    nodes = [self.tree_view.nodes_by_id.get(i) for i in selection]
    nodes = [n for n in nodes if n]

    n   = len(nodes)
    one = n == 1
    multi = n >= 2
    one_leaf   = one and not nodes[0].is_folder
    one_folder = one and nodes[0].is_folder
    same_level = multi and len({id(n.parent) for n in nodes}) == 1

    self.edit_menu.entryconfig("Splitten",         state="normal" if one_leaf else "disabled")
    self.edit_menu.entryconfig("Zusammenführen",   state="normal" if same_level else "disabled")
    self.edit_menu.entryconfig("Ordner innerhalb", state="normal" if one_folder else "disabled")
    # …etc
    # Kontextmenü analog mit self.context_menu.entryconfig(...)
```

Aufruf am Ende von `_on_tree_select` + nach Drag-Operationen + nach Löschen.

---

## 7. Was NICHT geändert wird

Unverändert ggü. Original-Briefing — hier nochmal als Erinnerung:

- Drag & Drop im TreeView (rechte Maustaste).
- Keyboard-Shortcuts im TreeView: F2, Entf, `Ctrl+Pfeile`.
- Polling-/Lockout-System im Vorschaufenster (`_schedule_poll`, `_set_controls_enabled` für Busy-State).
- Zoom-Logik: Auto-Zoom + `Ctrl+Mausrad`.
- Status-Tag-Farben (siehe §5).
- Speicher-/Lade-Logik (`PDFStorage`).
- Import-Logik (`UniversalImporter`).

---

## 8. Prioritätsreihenfolge

1. **HOCH** — Menüleiste + Toolbar-Bereinigung (§1, §2).
2. **HOCH** — Kontextmenü neu aufbauen (§3).
3. **HOCH** — Vorschaufenster-Stapelung + Label-Strings (§4).
4. **MITTEL** — `_update_menu_states` für kontextsensitive Aktivierung (§6).
5. **NIEDRIG** — Methodenwahl-Label-Format mit ✓-Markierung (§4 unten).

---

## 9. Abgrenzung zu anderen Briefings

| Briefing                                  | Berührt diese Datei? |
|-------------------------------------------|----------------------|
| `Briefing Erweiterungen Zammad.txt`       | Nein — separater Knotenbaum, separate Toolbar/Menü möglicherweise später |
| `Briefing Ergänzung Funktionalität.txt`   | Ja — eml/msg-Import: betrifft nur `universal_importer.py`. „Exportieren als .belegtool / .pdf" ist bereits in §6 unterstützt (siehe `export_selected` + Filetypes-Liste in `panel_controls.py`). |
| `Briefing Performance und Kompression.txt` | Ja — die Methodenwahl-UI in §4 (jetzt mit ✓-Markierung) ist die UI-Anbindung dafür. Backend separat. |

---

## 10. Begleitdatei / Visueller Referenz

`BelegTool UI Redesign.html` — interaktiver Mockup mit drei Frames:
1. **Vorher** (heutiger Zustand) — zur Validierung der Diagnose.
2. **Nachher A — faithful ttk** — **das, was gebaut werden soll**.
3. **Nachher B — modernisiert** — nicht bauen, nur Referenz.

Im Mockup lassen sich pro Frame folgende Zustände durchschalten:
- Leerlauf
- Mehrfachauswahl (für Merge / Methodenwahl)
- Geöffnete Menüs (Datei, Bearbeiten, Ansicht)
- Geöffnetes Kontextmenü

Window-Größe im Mockup: **900 × 600&nbsp;px** (Mindestgröße laut Original-Briefing).
