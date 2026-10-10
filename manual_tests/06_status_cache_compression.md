# 06 — Statusleiste, Vorschau-Cache und Komprimierungsablauf

Die **Statusleiste** am unteren Fensterrand, das Verhalten des **Vorschau-Caches** und der Ablauf der Komprimierung: kleinste Fassung als Vorgabe, gemerkte Auswahl, Übernahme beim Splitten, Abbruch beim Entfernen.

---

## MT-40: Statusleiste – Hintergrundarbeit und Cache-Anzeige

**Beispieldateien:** `Grosses_Dokument_120_Seiten.pdf`, `Farbscan_Rechnung_6_Seiten.pdf`, `Kontoauszug_8_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die drei Dateien sind importiert.

**Schritte:**
1. Die **Leiste am unteren Rand** ansehen. Rechts steht die Anzeige `📦 Cache x/y MB · n/m Seiten`.
2. Schnell zwischen den Einträgen hin- und herklicken und die linke Seite der Leiste beobachten.
3. Beim Farbscan die Auswahlliste der Verfahren öffnen und die linke Seite beobachten.
4. Mit der Maus auf der Cache-Anzeige verweilen.

**Erwartet:**
- Links steht, was im Hintergrund läuft: **⚙ Komprimiere N**, **Vorschau lädt N**, **Cache füllt** – oder **Bereit**, wenn nichts zu tun ist.
- *Nicht offensichtlich:* **Komprimiere N** zählt **Dokumente**, nicht einzelne Rechenschritte.
- Die Cache-Anzeige steigt, während Seiten gezeichnet werden: **belegt / Budget in MB** und **zwischengespeicherte / gesamte Seiten**.
- *Nicht offensichtlich:* Die Zahl der zwischengespeicherten Seiten kann die Seitenzahl des Dokuments **übersteigen** – die normale und die komprimierte Darstellung eines Dokuments werden getrennt gespeichert.
- Schritt 4: Der Hinweistext nennt den freien Speicher („Vorschau-Cache · … MB frei“).

---

## MT-41: Cache vergrößern und verkleinern (＋ / −)

**Beispieldateien:** `Grosses_Dokument_120_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist importiert.

**Schritte:**
1. Im großen Dokument scrollen, bis die MB-Anzeige des Caches gestiegen ist.
2. Einige Male auf **＋** neben der Cache-Anzeige klicken.
3. Mehrmals auf **−** klicken – bis unter die aktuell belegte Menge.

**Erwartet:**
- **＋** erhöht das Budget je Klick um 50 MB; das Vorausladen beginnt sofort, den neuen Platz zu **füllen** („Cache füllt“, die MB steigen).
- **−** senkt das Budget je Klick um 50 MB (Untergrenze 50 MB). Lag die Belegung über dem neuen Budget, wird **sofort Speicher freigegeben** – die belegten MB fallen auf das Budget.

---

## MT-42: Vorausladen wärmt das ganze Dokument an

**Beispieldateien:** `Grosses_Dokument_120_Seiten.pdf`, `Kontoauszug_8_Seiten.pdf`

**Voraussetzungen:** BelegTool ist frisch gestartet.

**Schritte:**
1. Beide Dateien importieren und danach **nichts anklicken**.
2. Die Anzeige `n/m Seiten` etwa 10–30 Sekunden lang beobachten.
3. Einen Eintrag anklicken, zum anderen wechseln und dort scrollen.

**Erwartet:**
- Das Anwärmen **beginnt von selbst nach dem Öffnen oder Importieren** (ohne Klick) und läuft über das **ganze** Dokument weiter in Richtung des Budgets – die nächstliegenden Einträge zuerst.
- Seiten, zu denen Sie scrollen, sind meist **schon gezeichnet** (kaum Platzhalter).
- *Nicht offensichtlich:* Das Anwärmen **pausiert, während eine Komprimierung läuft**, und setzt danach von selbst wieder ein.

---

## MT-43: Die kleinste Fassung ist die Vorgabe (bis 5 Seiten)

**Beispieldateien:** `Farbscan_Rechnung_3_Seiten.pdf`, `Farbscan_Rechnung_6_Seiten.pdf`, `Rechnung_5_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die drei Dateien sind importiert.

**Schritte:**
1. Den Eintrag `Farbscan_Rechnung_3_Seiten` anklicken und einen Moment warten.
2. Die Auswahlliste der Verfahren über der Vorschau öffnen.
3. Ein anderes Verfahren wählen, einen anderen Eintrag anklicken und wieder zurückkehren.
4. `Farbscan_Rechnung_6_Seiten` anklicken und warten.
5. `Rechnung_5_Seiten` anklicken, warten und die Auswahlliste öffnen.

**Erwartet:**
- Schritt 1: Die Vorschau wechselt **von selbst auf die kleinste Fassung**; die Liste zeigt dieses Verfahren mit Größe und dem Zusatz **„· beste“**.
- Der Eintrag **„unkomprimierte Fassung“** nennt die Größe der Quelle.
- Schritt 3: Das zuletzt gewählte Verfahren ist für dieses Dokument **gemerkt**.
- Schritt 4: *Nicht offensichtlich:* Die automatische Vorgabe gilt nur bis **5 Seiten**. Größere Dokumente bleiben auf dem Original, bis Sie die Liste öffnen.
- Schritt 5: Bei einem reinen Text-PDF ist nichts kleiner als das Original – die Liste bietet nur **„unkomprimierte Fassung“** an. Das ist richtig so.

---

## MT-44: Komprimierung übernehmen – „Lesbarkeit geprüft“

**Beispieldateien:** `Farbscan_Rechnung_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist importiert und angeklickt.

**Schritte:**
1. Ein Verfahren wählen und prüfen, ob die Vorschau gut lesbar ist.
2. Auf **❓ Lesbarkeit geprüft** klicken.
3. Speichern, das Fenster schließen, die Datei erneut öffnen und den Eintrag anklicken.

**Erwartet:**
- Schritt 2: Die Vorschau zeigt **sofort** das übernommene Ergebnis (kein Scrollen nötig). Die Schaltfläche zeigt **✓ übernommen**.
- *Nicht offensichtlich:* Eine **nicht übernommene** Fassung wird nicht zum Dokument – erst „Lesbarkeit geprüft“ macht das komprimierte Ergebnis verbindlich.
- Schritt 3: Das übernommene Dokument zeigt **„bereits komprimiert (keine Quelle)“** und lässt sich weder erneut komprimieren noch zurücksetzen.

---

## MT-45: Splitten übernimmt die Komprimierung; Abbruch beim Entfernen

**Beispieldateien:** `Farbscan_Rechnung_3_Seiten.pdf`, `Grosses_Dokument_120_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; beide Dateien sind importiert. Beim Farbscan ist ein JPEG-Verfahren mit **❓ Lesbarkeit geprüft** übernommen, das Dokument aber noch **nicht** gespeichert und neu geöffnet.

**Schritte:**
1. Rechtsklick auf den Farbscan → **Splitten ▸** → **pro Seite**.
2. Einen der entstandenen Einseiter anklicken und die Auswahlliste öffnen.
3. `Grosses_Dokument_120_Seiten` anklicken, die Auswahlliste der Verfahren öffnen (links unten erscheint **⚙ Komprimiere 1**) und den Eintrag **sofort** mit **Entf** löschen.

**Erwartet:**
- Schritt 1–2: Die Teile kommen **bereits komprimiert** an (gleiche Qualität) und bleiben bearbeitbar; es muss nichts neu berechnet werden.
- *Nicht offensichtlich:* War das beste Verfahren **Struktur (Farbe erhalten)**, werden die Teile stattdessen aus der Quelle neu berechnet.
- Schritt 3: Das Löschen (oder Splitten) eines Dokuments, das **gerade komprimiert wird**, **stoppt** diese Berechnung – die Zahl hinter **Komprimiere** fällt, statt dass für ein nicht mehr vorhandenes Dokument weitergerechnet wird.

---

## MT-46: Berechnete Fassungen bleiben über das Speichern hinweg erhalten

**Beispieldateien:** `Farbscan_Rechnung_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist importiert. **Nicht** auf „Lesbarkeit geprüft“ klicken.

**Schritte:**
1. Den Eintrag anklicken und warten, bis die Verfahren mit ihren **Größen** in der Liste stehen.
2. Mit **💾** speichern und im Dialog **Wie geplant speichern** wählen. BelegTool schließen, neu starten und die Datei öffnen.
3. Den Eintrag anklicken und die Auswahlliste öffnen.

**Erwartet:**
- Die Verfahren und ihre Vorschauen sind **sofort** da – kein „Kompression läuft …“, keine sekundenlange Wartezeit. Die berechneten Fassungen wurden in der `.belegtool`-Datei mitgespeichert.
- *Nicht offensichtlich:* Die Datei lässt sich weiterhin in jedem PDF-Betrachter öffnen – die Fassungen sind unsichtbare Anhänge, keine Seiten. Ein bereits übernommenes Dokument hat keine Quelle mehr und speichert keine Fassungen.

---

## MT-47: Roter Punkt „noch nicht entschieden“ bleibt weg (Verschieben und erneutes Öffnen)

**Beispieldateien:** `Viele_kleine_Belege.belegtool`

**Voraussetzungen:** BelegTool ist gestartet. Die Beispieldatei enthält 24 einseitige Text-Belege, bei denen sich **nichts einsparen** lässt, und im Ordner **Scans** zwei Dokumente, die sich verkleinern lassen. Jedes Dokument zeigt zunächst einen **roten Punkt vorn in der Zeile**.

**Schritte:**
1. Die Datei öffnen, alle Ordner aufklappen und **einige Sekunden warten**, ohne etwas anzuklicken. Beobachten, wie die roten Punkte verschwinden.
2. Wenn die Punkte in **Eingang** und **Ausgang** weg sind: einen dieser Belege in den jeweils anderen Ordner **ziehen**.
3. Über **▾ → Speichern unter…** speichern, BelegTool schließen und die gespeicherte Datei **erneut öffnen**.

**Erwartet:**
- Schritt 1: Die 24 Text-Belege verlieren ihren roten Punkt vorn von selbst (es wurde nichts Kleineres gefunden – die Entscheidung ist damit getroffen).
- Schritt 2: Das **Verschieben** bringt den roten Punkt **nicht** zurück – auch nicht bei den **anderen**, bereits entschiedenen Belegen.
- Schritt 3: Nach dem erneuten Öffnen sind die 24 Belege **weiterhin ohne Punkt**, ohne neue Wartezeit. Das Ergebnis „nichts Kleineres gefunden“ steht in der Datei.
- *Gegenprobe:* Die beiden Dokumente im Ordner **Scans** **behalten** ihren roten Punkt – für sie gibt es eine kleinere Fassung, über die noch nicht entschieden wurde. Das ist richtig und kein Fehler.
