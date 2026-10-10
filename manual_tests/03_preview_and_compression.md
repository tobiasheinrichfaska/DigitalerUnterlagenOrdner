# 03 — Vorschau, Komprimierung, Drehen, Status

Die Vorschau (rechts) mit Zoom, die Regler für DPI und Komprimierung darüber, das Drehen und die Status-Punkte. Die Status-Punkte werden im Bereich 08 ausführlich geprüft; hier stehen die Grundlagen.

---

## MT-10: Vorschau und Zoom

**Ab Version:** 3.10.0

**Beispieldateien:** `Kontoauszug_8_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; `Kontoauszug_8_Seiten.pdf` ist importiert und angeklickt.

**Schritte:**
1. In der Vorschau durch die Seiten scrollen.
2. Mit **Strg + Mausrad** über der Vorschau zoomen; außerdem die Zoom-Leiste der Vorschau benutzen (**−**, **＋**, **100%**).
3. Bis etwa Seite 5 scrollen und sich die Zeilennummer merken, die **ganz oben** im sichtbaren Bereich steht (z. B. „Zeile 141“). Dann einige Stufen **hinein-** und wieder **herauszoomen**.

**Erwartet:**
- Die Seiten erscheinen in der Vorschau; nur die sichtbaren werden gezeichnet, Platzhalter füllen sich beim Scrollen.
- Strg + Mausrad und die Zoom-Leiste ändern die Seitengröße.
- *Nicht offensichtlich:* Beim Zoomen bleibt die **Stelle im Dokument** stehen – die gemerkte Zeile ist nach dem Zoomen immer noch oben im sichtbaren Bereich. Die Seite rutscht nicht nach oben oder unten weg.
- Die Zoom-Leiste zeigt die aktuelle Position als **„Seite n / m“**.
- *Nicht offensichtlich:* Es gibt keinen eigenen Schalter „Original anzeigen“. Die Vorschau zeigt immer den aktuellen Stand des Dokuments; verglichen wird in der Komprimierungs-Vorschau (MT-11).

---

## MT-11: Komprimierung mit DPI-Regler und Verfahren ausprobieren

**Beispieldateien:** `Farbscan_Rechnung_6_Seiten.pdf`, `Farbscan_Rechnung_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; beide Dateien sind importiert.

**Schritte:**
1. Den Eintrag `Farbscan_Rechnung_6_Seiten` anklicken. Auf **↶ Rückgängig** und auf die Auswahlliste neben dem DPI-Regler achten.
2. Die Auswahlliste (Verfahren) öffnen.
3. Ein Verfahren wählen; den **DPI**-Regler verschieben (Bereich 50–300); danach wieder **unkomprimierte Fassung** wählen.
4. Den Eintrag `Farbscan_Rechnung_3_Seiten` anklicken und einen Moment warten.

**Erwartet:**
- Schritt 1: Das Anklicken verändert das Dokument nicht. Weil der Eintrag **mehr als 5 Seiten** hat, wird auch noch nichts berechnet; die Liste steht auf „unkomprimierte Fassung“.
- Schritt 2: Die Liste zeigt zunächst **„Kompression läuft …“**, dann die Verfahren mit ihrer Größe.
- Es erscheinen **nur** Verfahren, deren Ergebnis **kleiner als das Original** ist. Möglich sind **JPEG (Graustufen)**, **JPEG (Farbe)**, **PNG (Graustufen)** und **Struktur (Farbe erhalten)**; bei der Beispieldatei sind es die beiden JPEG-Verfahren. Das kleinste trägt den Zusatz **„· beste“**.
- Die Größe des Originals steht am Eintrag **„unkomprimierte Fassung — … KB“**.
- Schritt 3: Verfahren und DPI zu wechseln zeigt nur eine **Vorschau** – das Dokument ist noch nicht verändert (**↶** kommt dadurch nicht hinzu). Ein bereits angesehenes Verfahren erscheint beim Zurückwechseln sofort.
- Schritt 4: Bei Dokumenten mit **höchstens 5 Seiten** wird automatisch berechnet und die kleinste Fassung vorausgewählt (Einzelheiten: Bereich 06, MT-43).

---

## MT-12: Übernehmen („Lesbarkeit geprüft“) und zurücksetzen

**Beispieldateien:** `Farbscan_Rechnung_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist importiert und angeklickt; in der Auswahlliste ist ein Verfahren gewählt (z. B. **JPEG (Graustufen)**).

**Schritte:**
1. Die Vorschau auf Lesbarkeit prüfen und auf **❓ Lesbarkeit geprüft** klicken.
2. Einen anderen Eintrag anklicken und wieder zurückkehren.
3. Zurücksetzen: in der Auswahlliste **unkomprimierte Fassung** wählen und erneut auf **❓ Lesbarkeit geprüft** klicken.

**Erwartet:**
- Schritt 1: Die komprimierte Fassung wird zum aktuellen Stand des Dokuments (ein Rückgängig-Schritt). Die Schaltfläche zeigt **✓ übernommen**; der rote Punkt **vorn** in der Zeile („Komprimierung noch nicht entschieden“) verschwindet.
- Schritt 2: Das gewählte Verfahren ist weiterhin eingestellt.
- Schritt 3: Das Dokument steht wieder auf der unkomprimierten Fassung.
- *Nicht offensichtlich:* Es gibt **keine eigene Zurücksetzen-Schaltfläche** – zurückgesetzt wird, indem man die unkomprimierte Fassung wählt und sie übernimmt.
- *Wichtig:* Sobald ein übernommenes Dokument **gespeichert** wurde, ist seine Quelle verworfen. Nach dem erneuten Öffnen zeigt die Liste **„bereits komprimiert (keine Quelle)“** und ist gesperrt. Das ist gewollt und nicht umkehrbar (siehe Bereich 04, MT-17).

---

## MT-12b: Seiten drehen (↺ / ↻)

**Beispieldateien:** `Rechnung_5_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist importiert und angeklickt.

**Schritte:**
1. Über der Vorschau auf **↻** klicken (Hinweistext „rechts drehen“).
2. Auf **↺** klicken (Hinweistext „links drehen“).
3. Viermal hintereinander **↻** klicken.
4. Einmal **↶ Rückgängig** klicken.

**Erwartet:**
- Schritt 1: **Alle Seiten** des Dokuments sind um 90° im Uhrzeigersinn gedreht (Querformat).
- Schritt 2: Die Seiten stehen wieder aufrecht.
- Schritt 3: Nach vier Drehungen ist die Ausgangslage wieder erreicht.
- Schritt 4: Jede Drehung ist ein eigener Rückgängig-Schritt; **↶** nimmt nur die letzte zurück.
- *Nicht offensichtlich:* Gedreht wird immer das **ganze Dokument**, nicht eine einzelne Seite. Um nur eine Seite zu drehen, das Dokument erst splitten (Bereich 02, MT-06), die Seite drehen und wieder zusammenführen.
- *Nicht offensichtlich:* Nach dem Drehen wird die Komprimierung neu bewertet; der rote Punkt vorn in der Zeile kann deshalb kurz wieder erscheinen.

---

## MT-13: Status-Punkte

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Rechtsklick auf ein Dokument → unter **Status** nacheinander **Zu erfassen**, **Erfasst**, **Vorjahr** und **Kein Status** wählen (jeweils erneut rechtsklicken).
2. Rechtsklick auf einen **Ordner** → unter **Status (gesamter Inhalt)** einen Wert wählen.

**Erwartet:**
- Ein Dokument zeigt **einen Punkt am Zeilenende**: **Zu erfassen → gelb**, **Erfasst → grün**, **Vorjahr → rot**, **Kein Status → kein Punkt**.
- Ein **Ordner** zeigt je enthaltenem Status einen Punkt (Reihenfolge rot → gelb → grün) und zusätzlich einen **schwarzen Punkt**, wenn manche Inhalte einen Status haben und andere nicht. Ein leerer Ordner oder einer ganz ohne Status zeigt keine Punkte.
- Ein Status am Ordner wird auf **alle Dokumente darin** übertragen (auch in Unterordnern).
- *Nicht offensichtlich:* Der Status wird als Punkt gezeigt, nicht durch Einfärben der Zeile. Die genauen Regeln prüft Bereich 08.
