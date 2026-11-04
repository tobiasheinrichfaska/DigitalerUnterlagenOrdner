# 02 — Baum bearbeiten

Splitten, Zusammenführen, Ordner, Umbenennen, Löschen und Verschieben mit der Maus. Die meisten Aktionen liegen im **Kontextmenü (Rechtsklick)**; in der Symbolleiste stehen **＋ Ordner**, **↶ Rückgängig** und **↷ Wiederholen**.

---

## MT-06: Mehrseitiges Dokument splitten

**Beispieldateien:** `Dokument_3_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; `Dokument_3_Seiten.pdf` ist importiert (**📥 Importieren**).

**Schritte:**
1. Rechtsklick auf den Eintrag und mit der Maus auf **Splitten ▸** zeigen, bis das Untermenü aufklappt.
2. **pro Seite** wählen.
3. **↶ Rückgängig** klicken und die anderen Varianten ausprobieren: **N Seiten pro Knoten…**, **pro Seite → neuer Ordner**, **N Seiten → neuer Ordner…**. Die „N Seiten“-Einträge fragen nach der Seitenzahl („Seiten pro Knoten:“) – z. B. `2` eingeben.

**Erwartet:**
- **pro Seite** ersetzt den Eintrag durch **einen Eintrag je Seite** (hier 3). Jeder zeigt in der Vorschau genau **eine** Seite.
- **N Seiten pro Knoten…** mit `2` ergibt zwei Einträge: einen mit 2 Seiten und einen mit 1 Seite.
- Die Varianten **→ neuer Ordner** legen die Teile in einen neuen Ordner.
- *Nicht offensichtlich:* **Splitten** wird nur bei einem **Dokument mit mehr als einer Seite** angeboten. Bei Ordnern und einseitigen Dokumenten fehlt der Eintrag im Menü.
- *Nicht offensichtlich:* Die Teile bleiben komprimierbar – sie tragen die unkomprimierten Quellseiten.
- *Ab Version 3.11.4:* Trug das Dokument **Tags** oder einen **Veranlagungszeitraum**, erben die Teile sie (vorher gingen sie still verloren). Bei den Varianten **→ neuer Ordner** sitzen die Tags auf dem **neuen Ordner** (die Teile erben sie dort), damit das Stichwortverzeichnis nicht jeden Teil einzeln listet.

---

## MT-07: Zwei benachbarte Dokumente zusammenführen

**Beispieldateien:** `Teil_A_1_Seite.pdf`, `Teil_B_2_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; beide Dateien sind importiert und liegen auf **derselben Ebene** (im selben Ordner bzw. beide auf der obersten Ebene).

**Schritte:**
1. Den ersten Eintrag anklicken, dann mit **Strg+Klick** den zweiten dazu markieren.
2. Rechtsklick auf **einen der beiden markierten** Einträge → **Zusammenführen → 1 PDF (2)**.

**Erwartet:**
- Aus den beiden Einträgen wird **einer**, dessen Vorschau **alle 3 Seiten** in der ursprünglichen Reihenfolge zeigt.
- *Nicht offensichtlich:* **Zusammenführen** erscheint nur, wenn **mindestens zwei Dokumente desselben Ordners** markiert sind **und** Sie auf einen Eintrag **innerhalb der Markierung** rechtsklicken. Ein Rechtsklick auf einen Eintrag außerhalb der Markierung blendet den Eintrag aus (dieselbe Regel gilt für Export, Status und Löschen).
- *Nicht offensichtlich:* Waren die Teile mit **unterschiedlichen DPI** komprimiert, verwirft das zusammengeführte Dokument die komprimierte Fassung und fällt auf die Originale zurück.
- Status: Hatten alle Teile denselben Status, bleibt er erhalten; bei unterschiedlichen Status hat das Ergebnis keinen Status.
- *Ab Version 3.11.4:* **Tags** werden **vereinigt** (jedes Tag der Teile erscheint einmal am Ergebnis) und der **Veranlagungszeitraum** wird **aufgespannt** (frühester Beginn bis spätestes Ende der Teile). Vorher gingen beide beim Zusammenführen still verloren.

---

## MT-08: Ordner anlegen, umbenennen, löschen

**Ab Version:** 3.10.0

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist frisch geöffnet (noch nichts markiert).

**Schritte:**
1. Ohne etwas zu markieren auf **＋ Ordner** klicken. Im Dialog „Name des neuen Ordners“ die Vorgabe **Neuer Ordner** mit OK bestätigen.
2. Den Ordner **02 Bank** anklicken und erneut **＋ Ordner** → Namen bestätigen.
3. Das Dokument `Telefon_2025-01.pdf` anklicken und erneut **＋ Ordner** → Namen bestätigen.
4. Rechtsklick auf einen **Ordner** → **Ordner anlegen**.
5. Einen Eintrag markieren und **F2** drücken, einen neuen Namen tippen, mit Enter bestätigen. Alternativ: Rechtsklick → **Umbenennen** (Dialog „Neuer Name“).
6. Einen Eintrag markieren und **Entf** drücken (oder Rechtsklick → **Löschen**).
7. Mehrere Einträge mit Strg+Klick markieren → Rechtsklick auf einen davon → **Löschen (N)**.

**Erwartet:**
- *Nicht offensichtlich:* **＋ Ordner** richtet sich nach der Markierung:
  - nichts markiert (Schritt 1) → der Ordner entsteht auf der obersten Ebene;
  - Ordner markiert (Schritt 2) → er entsteht **in** diesem Ordner;
  - Dokument markiert (Schritt 3) → er entsteht **direkt hinter** diesem Dokument.
- Wird der Namensdialog abgebrochen (Esc oder leerer Name), entsteht nichts.
- **Ordner anlegen** im Kontextmenü legt ohne Rückfrage einen „Neuer Ordner“ **im** angeklickten Ordner an.
- Der umbenannte Eintrag zeigt den neuen Namen.
- Nach dem Löschen ist der Eintrag weg und die **Markierung springt** auf einen Nachbarn (den vorherigen Eintrag, sonst den übergeordneten Ordner), sodass Sie direkt weiterarbeiten können.
- **Löschen (N)** entfernt die ganze Markierung in **einem** Rückgängig-Schritt.
- *Nicht offensichtlich:* Enthält die Markierung einen Ordner **und** Einträge daraus, fragt BelegTool vorher nach (siehe Bereich 07, MT-52).

---

## MT-08b: Mehrfachauswahl und Status für mehrere Einträge

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet, alle Ordner sind aufgeklappt.

**Schritte:**
1. `Telefon_2025-01.pdf` anklicken, dann mit **Strg+Klick** `Miete_2024-12.pdf` dazu markieren.
2. Mit **Strg+Klick** auf `Telefon_2025-01.pdf` diesen Eintrag wieder aus der Markierung nehmen.
3. `Telefon_2025-01.pdf` anklicken, dann mit **Umschalt+Klick** auf `Sammelrechnung_Wartung.pdf` klicken (der letzte Eintrag im selben Ordner).
4. Rechtsklick auf einen der markierten Einträge → unter **Status (4)** den Eintrag **Erfasst** wählen.
5. **↶ Rückgängig** klicken.

**Erwartet:**
- Schritt 1: Beide Einträge sind markiert, obwohl sie in verschiedenen Ordnern liegen. Die Vorschau zeigt den zuletzt angeklickten.
- Schritt 2: Nur `Miete_2024-12.pdf` bleibt markiert.
- Schritt 3: **Alle vier Zeilen** vom ersten bis zum letzten angeklickten Eintrag sind markiert.
- Schritt 4: Die Überschrift im Menü nennt die Anzahl („Status (4)“). Alle vier Dokumente bekommen einen grünen Punkt am Zeilenende.
- Schritt 5: **Ein** Rückgängig-Schritt nimmt den Status bei allen vier wieder weg.

---

## MT-09: Verschieben mit der Maus und Ebene wählen

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Einen Eintrag **auf einen Ordner ziehen** und loslassen.
2. Einen Eintrag **zwischen zwei Zeilen** ziehen und loslassen.
3. Einen Eintrag an das **untere Ende** eines Ordners ziehen und vor dem Loslassen die Maus **nach links und rechts schieben**. Dabei den „Geist“ (die mitlaufende Vorschau der Zielposition) beobachten.

**Erwartet:**
- Schritt 1: Der Eintrag liegt danach **im** Ordner (der Ordner wird beim Ziehen hervorgehoben).
- Schritt 2: Der Eintrag liegt genau vor bzw. hinter der Zeile (eine Linie zeigt die Stelle).
- Schritt 3: Der Geist nennt das Ziel („in <Ordnername>“ / „oberste Ebene“) und wechselt beim seitlichen Schieben die Ebene.
- Es entstehen **keine doppelten oder „Geister“-Einträge**; jeder verschobene Eintrag zeigt weiterhin seine richtige Vorschau.
- Jedes Verschieben ist ein Rückgängig-Schritt.
- *Nicht offensichtlich:* Ziehen innerhalb eines Fensters **verschiebt immer** – es gibt kein „Strg = Kopieren“ und kein Ziehen in ein anderes BelegTool-Fenster.

---

## MT-09b: Mehrere Einträge gleichzeitig mit der Maus verschieben

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet, alle Ordner sind aufgeklappt.

**Schritte:**
1. `Telefon_2025-01.pdf` anklicken und mit **Strg+Klick** `Strom_Abschlag_2025-01.pdf` dazu markieren.
2. Einen der beiden markierten Einträge auf den Ordner **03 Vorjahr 2024** ziehen. Während des Ziehens den Geist beobachten.
3. **↶ Rückgängig** klicken.
4. Den Ordner **02 Bank** anklicken und mit **Strg+Klick** `Kontoauszug_2025-01.pdf` (liegt **in** diesem Ordner) dazu markieren. Einen der beiden auf **01 Eingangsrechnungen** ziehen.

**Erwartet:**
- Schritt 2: Der Geist zeigt **„2 Elemente“**. Nach dem Loslassen liegen **beide** Einträge im Zielordner – in ihrer bisherigen Reihenfolge.
- Schritt 3: **Ein** Rückgängig-Schritt holt beide zurück.
- Schritt 4: Weil ein Ordner **und** ein Eintrag daraus markiert sind, fragt BelegTool nach: „„02 Bank“: den ganzen Ordner einbeziehen? (Abbrechen = nur die ausgewählten Elemente, Ordner ausschließen)“. **OK** verschiebt den ganzen Ordner; **Abbrechen** führt zur zweiten Frage, ob nur die markierten Einträge verschoben werden sollen.

---

## MT-09c: Unzulässiges Verschieben – Ordner in den eigenen Unterordner

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet, der Ordner **02 Bank** ist aufgeklappt.

**Schritte:**
1. Den Ordner **02 Bank** auf seinen eigenen Unterordner **Darlehen** ziehen und loslassen.

**Erwartet:**
- Der Baum bleibt **unverändert**.
- Es erscheint die rote Meldung „⚠ Ein Knoten kann nicht in sich selbst oder seinen eigenen Teilbaum verschoben werden.“
- **↶ Rückgängig** bleibt so, wie es vorher war (es ist kein neuer Schritt entstanden).

---

## MT-09d: Rückgängig und Wiederholen über mehrere Schritte

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist frisch geöffnet.

**Schritte:**
1. Nacheinander vier Änderungen vornehmen: einen Eintrag **umbenennen** (F2), einen Eintrag in einen anderen Ordner **ziehen**, bei einem Dokument per Rechtsklick den Status **Erfasst** setzen, einen Eintrag mit **Entf löschen**.
2. Viermal **↶ Rückgängig** klicken (oder **Strg+Z**).
3. Zweimal **↷ Wiederholen** klicken (oder **Strg+Y**).
4. Jetzt eine **neue** Änderung vornehmen (z. B. noch einen Eintrag umbenennen).

**Erwartet:**
- Schritt 2: Die Änderungen verschwinden in **umgekehrter Reihenfolge**; nach dem vierten Mal sieht der Baum wieder aus wie nach dem Öffnen und **↶** ist ausgegraut.
- Schritt 3: Die ersten beiden Änderungen (Umbenennen, Verschieben) sind wieder da.
- Schritt 4: Nach der neuen Änderung ist **↷ Wiederholen** ausgegraut – die noch nicht wiederholten Schritte sind verworfen.
- *Nicht offensichtlich:* Auch das Zuklappen eines Ordners und das Setzen eines Status sind eigene Rückgängig-Schritte.
