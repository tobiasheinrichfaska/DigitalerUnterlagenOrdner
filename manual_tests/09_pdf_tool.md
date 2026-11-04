# 09 — PDF-Tool (Text hinzufügen, Formulare ausfüllen)

Das PDF-Tool ist die zweite Arbeitsfläche: Es öffnet **ein einzelnes PDF** in einem eigenen Fenster – mit markierbarem Text und ausfüllbaren Formularfeldern –, lässt **Text hinzufügen** und speichert das Ergebnis in den Eintrag zurück.

---

## MT-50: Dokument im PDF-Tool öffnen – ein Ordner geht nicht

**Ab Version:** 3.10.0

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Rechtsklick auf ein **Dokument**, z. B. `Telefon_2025-01.pdf`.
2. Auf **Im PDF-Tool öffnen** klicken.
3. Im Hauptfenster versuchen, dasselbe Dokument zu drehen (**↻**) oder zu löschen (**Entf**).
4. Das PDF-Tool-Fenster schließen. Rechtsklick auf einen **Ordner**.

**Erwartet:**
- Schritt 2: Ein **neues Fenster** zeigt das PDF; oben stehen die Schaltflächen **✎ Text** und **💾 Speichern**. Der Text lässt sich mit der Maus markieren.
- Schritt 3: Solange das Dokument im PDF-Tool offen ist, ist es im Hauptfenster **gesperrt** – Drehen, Splitten, Zusammenführen, Komprimieren und Löschen werden abgelehnt, bis das PDF-Tool-Fenster geschlossen ist.
- Schritt 4: Im Kontextmenü eines Ordners **fehlt** der Eintrag **Im PDF-Tool öffnen** – ein Ordner hat kein eigenes PDF. Der Eintrag ist nicht ausgegraut, sondern nicht vorhanden.

---

## MT-51: Text hinzufügen und zurückspeichern

**Ab Version:** 3.10.0

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet; ein Dokument ist im PDF-Tool geöffnet (wie in MT-50).

**Schritte:**
1. Auf **✎ Text** klicken.
2. Auf die Seite klicken und eine Notiz eintippen, z. B. „Geprüft 27.06.“.
3. Auf **💾 Speichern** klicken und den Statustext rechts in der Leiste beobachten.
4. Das PDF-Tool-Fenster schließen und im Hauptfenster das Dokument ansehen.

**Erwartet:**
- Schritt 1: **✎ Text** ist hervorgehoben (aktiv).
- Schritt 2: Der Klick setzt ein Textfeld, das sich beschreiben und verschieben lässt.
- Schritt 3: Der Statustext wechselt von **„Speichern…“** zu **„Gespeichert ✓“**. Erscheint stattdessen eine Fehlermeldung, bitte ihren Wortlaut notieren.
- Schritt 4: Das Hauptfenster zeigt **ungespeicherte Änderungen („•“)** – der Eintrag hat das bearbeitete PDF als neuen Inhalt übernommen. **↶ Rückgängig** nimmt das zurück; erst **💾** im Hauptfenster schreibt die Änderung in die `.belegtool`-Datei.

---

## MT-52: Hinzugefügten Text später weiterbearbeiten

**Ab Version:** 3.10.0

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** MT-51 ist durchgeführt: Text wurde hinzugefügt und gespeichert.

**Schritte:**
1. **Dasselbe** Dokument erneut per Rechtsklick → **Im PDF-Tool öffnen** öffnen.
2. Auf **✎ Text** klicken und die frühere Notiz anklicken.

**Erwartet:**
- Der früher hinzugefügte Text steht **weiterhin auf der Seite** und ist **weiter bearbeitbar** – Wortlaut ändern, verschieben oder löschen. Er wurde als echte Textanmerkung gespeichert und nicht ins Seitenbild eingebrannt.

**Hinweis:** Wird das Dokument anschließend im Hauptfenster **komprimiert**, wird die Seite neu als Bild erzeugt – der hinzugefügte Text ist dann Teil des Bildes und nicht mehr bearbeitbar. Text deshalb vor dem Komprimieren fertigstellen.

---

## MT-53: Formularfeld ausfüllen und speichern

**Ab Version:** 3.10.0

**Beispieldateien:** `Formular_Antrag.pdf`

**Voraussetzungen:** BelegTool ist gestartet; `Formular_Antrag.pdf` ist importiert (ausfüllbares Formular mit fünf Textfeldern und einem Kontrollkästchen).

**Schritte:**
1. Rechtsklick auf den Eintrag → **Im PDF-Tool öffnen**.
2. In das Feld **Name** klicken und einen Wert eintippen; das Kästchen **Belege liegen bei** anhaken.
3. Auf **💾 Speichern** klicken, das Fenster schließen und den Eintrag erneut im PDF-Tool öffnen.

**Erwartet:**
- Die Felder nehmen Eingaben an.
- Nach Speichern und erneutem Öffnen stehen die Werte **weiterhin in den Feldern** und lassen sich weiter ändern. Der Statustext zeigte **„Gespeichert ✓“**.

## MT-54: Link in einem PDF öffnet den Browser – nie das Programmfenster

Ein Klick auf einen Link im PDF-Tool darf das BelegTool-Fenster nicht verlassen; die Seite öffnet im normalen Browser.

**Ab Version:** 3.11.4

**Beispieldateien:** `Rechnung_mit_Link.pdf`

**Voraussetzungen:** BelegTool ist gestartet; `Rechnung_mit_Link.pdf` ist importiert.

**Schritte:**
1. Rechtsklick auf den Eintrag → **Im PDF-Tool öffnen**.
2. Auf den blauen Link **„Mehr dazu: https://example.com/“** klicken.

**Erwartet:**
- Die Seite öffnet im **Standard-Browser** (neues Browserfenster oder neuer Tab).
- Das PDF-Tool-Fenster zeigt **weiterhin das PDF** – es navigiert nicht zur Internetseite und verliert keine ungespeicherten Eingaben.
- *Nicht offensichtlich:* Das ist eine Sicherheitsmaßnahme. Würde die Internetseite im Programmfenster laden, bekäme sie Zugriff auf die interne Programmschnittstelle. Vor Version 3.11.4 navigierte der Klick das Fenster – bitte als Fehler melden, falls das wieder passiert.
