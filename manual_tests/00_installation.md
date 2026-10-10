# 00 — Installation aus dem Microsoft Store

Die ausführliche Anleitung mit allen Wegen und Hilfen steht in `00_Installation_Microsoft_Store.pdf`. Diese Tests prüfen, ob die Installation das gewünschte Ergebnis hat.

---

## MT-INST-01: BelegTool aus dem Microsoft Store installieren und starten

**Voraussetzungen:** Windows 11 oder Windows 10 (ab Version 1809), 64 Bit, mit Internetverbindung und nutzbarem Microsoft Store. BelegTool ist noch **nicht** installiert; eine frühere Testversion ist deinstalliert.

**Schritte:**
1. Den **Microsoft Store** öffnen (Startmenü → „Microsoft Store“) und nach `BelegTool` suchen – oder im Browser `https://apps.microsoft.com/detail/9PL4D25N00XD` aufrufen.
2. Den Eintrag **BelegTool** des Herausgebers **Tobias Heinrich** öffnen.
3. Auf die Schaltfläche zum Installieren klicken (je nach Store-Version „Herunterladen“, „Installieren“ oder „Abrufen“) und warten, bis die Installation abgeschlossen ist.
4. Im Store auf **Öffnen** klicken – oder BelegTool über das Startmenü starten.

**Erwartet:**
- Die Store-Seite nennt **BelegTool**, den Herausgeber **Tobias Heinrich** und den Preis **kostenlos**.
- Die Installation läuft **ohne Administratorkennwort** und **ohne Warnung** von Windows SmartScreen oder einem Virenschutz durch.
- **BelegTool** steht danach im Startmenü.
- Das Programm startet mit einem leeren Dokument („Dokument 1“): oben die Symbolleiste, links der Baum, rechts die Vorschau.
- *Nicht offensichtlich:* Erscheint stattdessen die Meldung „Microsoft Edge WebView2 Runtime fehlt“ (vor allem unter Windows 10 möglich), die angebotene Seite öffnen, die WebView2-Runtime installieren und BelegTool neu starten.

---

## MT-INST-02: Installierte Version feststellen

**Voraussetzungen:** BelegTool ist aus dem Microsoft Store installiert.

**Schritte:**
1. BelegTool starten und die **Titelleiste** des Fensters lesen.
2. Windows-**Einstellungen** → **Apps** → **Installierte Apps** öffnen, **BelegTool** suchen und über **⋯** die **Erweiterten Optionen** öffnen.
3. Im Microsoft Store unter **Downloads** bzw. **Bibliothek** auf **Updates abrufen** klicken.

**Erwartet:**
- Schritt 1: In der Titelleiste steht „DigitalerUnterlagenOrdner“ mit der Versionsnummer, z. B. `3.11.2`. **Bitte diese Nummer in jedes Testprotokoll eintragen.**
- Schritt 2: Die Einstellungen zeigen dieselbe Version mit einer zusätzlichen `.0` am Ende (z. B. `3.11.2.0`).
- Schritt 3: Gibt es eine neuere Version, wird sie installiert; nach einem Neustart zeigt die Titelleiste die höhere Nummer. Eigene `.belegtool`-Dateien bleiben dabei unverändert.

---

## MT-INST-03: BelegTool deinstallieren

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist aus dem Microsoft Store installiert und geschlossen. Die Beispieldatei liegt an einem eigenen Arbeitsort (z. B. auf dem Desktop).

**Schritte:**
1. Im Startmenü **BelegTool** rechtsklicken → **Deinstallieren** und bestätigen. (Alternativ: Einstellungen → Apps → Installierte Apps → BelegTool → Deinstallieren.)
2. Im Startmenü nach BelegTool suchen.
3. Die Beispieldatei rechtsklicken → **Öffnen mit** → einen PDF-Betrachter wählen (z. B. Microsoft Edge).
4. BelegTool über den Store wieder installieren (MT-INST-01).

**Erwartet:**
- Schritt 2: BelegTool ist aus dem Startmenü verschwunden.
- Schritt 3: Die `.belegtool`-Datei ist **noch vorhanden** und lässt sich als PDF ansehen – eine `.belegtool`-Datei ist ein gewöhnliches PDF, das zusätzlich die Ordnerstruktur enthält.
- Schritt 4: Die erneute Installation funktioniert ohne Besonderheiten.
