# 01 — Import

Dateien in den Dokumentbaum holen – mit **📥 Importieren** oder durch Ziehen aus dem Windows-Explorer – und die Sicherheitsprüfung beim Import.

---

## MT-01: Einzelnes PDF importieren

**Beispieldateien:** `Rechnung_5_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet – mit dem leeren „Dokument 1“ oder mit einem bereits geöffneten Dokument.

**Schritte:**
1. In der Symbolleiste auf **📥 Importieren** klicken.
2. Im Dateidialog `Rechnung_5_Seiten.pdf` auswählen und bestätigen. (Der Dialog erlaubt auch eine Mehrfachauswahl.)
3. Als Alternative dieselbe Datei aus dem Explorer **auf das Fenster ziehen** und loslassen:
   - auf den Hintergrund → sie landet im markierten Ordner, sonst auf der obersten Ebene;
   - auf eine Ordnerzeile → sie landet in diesem Ordner;
   - zwischen zwei Zeilen → sie landet genau an dieser Stelle.

**Erwartet:**
- Im **Baum** (links) erscheint ein neuer Eintrag, benannt nach der Datei (`Rechnung_5_Seiten`).
- Ein Klick darauf zeigt die fünf Seiten in der **Vorschau** (rechts).
- *Nicht offensichtlich:* Für einen Moment kann ein hell **gestreifter Platzhalter** in Seitengröße zu sehen sein, bevor die echte Seite erscheint. Die Vorschau füllt sich nach und nach.
- Das Dokument hat jetzt ungespeicherte Änderungen: Neben **💾** und hinter dem Dokumenttitel steht ein **„•“**.
- Jeder Import ist **ein** Rückgängig-Schritt: **↶ Rückgängig** entfernt ihn wieder.
- *Nicht offensichtlich:* Der Vorschau-Cache füllt sich von selbst (unten in der Statusleiste: „Cache füllt“), auch ohne dass Sie den Eintrag anklicken.

---

## MT-01b: BelegTool-Dokument in ein geöffnetes Dokument importieren

Ein `.belegtool` lässt sich nicht nur öffnen, sondern auch in ein anderes Dokument **hinein**holen.

**Beispieldateien:** `Beispielmappe.belegtool`, `Zweite_Mappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist mit **📂 Öffnen** geöffnet.

**Schritte:**
1. Den Ordner **02 Bank** anklicken.
2. **📥 Importieren** → `Zweite_Mappe.belegtool` auswählen.
3. **↶ Rückgängig** klicken.

**Erwartet:**
- Der **Inhalt** der zweiten Mappe erscheint im Ordner **02 Bank**: die Ordner **Beiträge** und **Veranstaltungen** mit ihren Dokumenten.
- *Nicht offensichtlich:* Es entsteht **kein** umschließender Ordner „Zweite_Mappe“ – die obersten Einträge der importierten Mappe werden direkt eingefügt.
- Der Dokumenttitel bleibt „Beispielmappe“; die Datei `Zweite_Mappe.belegtool` selbst wird nicht verändert.
- Schritt 3 nimmt den gesamten Import in **einem** Schritt zurück.

---

## MT-02: Bild importieren (JPG / PNG / WEBP / HEIC / BMP / TIFF)

**Beispieldateien:** `Foto_Kassenbon.jpg`, `Scan_Quittung.png`, `Grafik_Diagramm.webp`, `Handyfoto_Beleg.heic`, `Scan_Kontoblatt.bmp`, `Scan_Vertrag.tif`

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. **📥 Importieren** anklicken und alle sechs Bilddateien auf einmal auswählen.
2. Die sechs neuen Einträge nacheinander anklicken.

**Erwartet:**
- Jedes Bild wird in ein **einseitiges PDF** umgewandelt und erscheint als eigener Eintrag im Baum.
- Die Vorschau zeigt jedes Bild als genau eine Seite.
- *Nicht offensichtlich:* Die Einträge heißen wie die Bilddatei mit angehängtem `.pdf` (z. B. `Foto_Kassenbon.jpg.pdf`).

**Hinweis:** **Bekannte Einschränkung:** Von einer **mehrseitigen** TIFF-Datei (z. B. Fax oder Stapelscan) wird nur die **erste Seite** übernommen. Bitte nicht als neuen Fehler melden.

---

## MT-03: E-Mail mit Anhängen importieren (.eml / .msg)

**Beispieldateien:** `Mail_mit_Anhaengen.eml`

**Voraussetzungen:** BelegTool ist gestartet. Wer Outlook hat, kann zusätzlich eine eigene `.msg`-Datei testen (eine Mail aus Outlook auf den Desktop ziehen).

**Schritte:**
1. **📥 Importieren** → `Mail_mit_Anhaengen.eml` auswählen.
2. Den neuen Ordner aufklappen und die Einträge darin anklicken.

**Erwartet:**
- Für die E-Mail entsteht ein **Ordner**, benannt nach der Datei. Darin liegen der Mailtext und jeder Anhang als eigener Eintrag:
  - der Mailtext („Belege Januar 2025 …“),
  - `Rechnung_Januar.pdf` (2 Seiten),
  - `Foto_Kassenbon.jpg` (1 Seite).
- *Nicht offensichtlich:* Der vierte Anhang lässt sich nicht umwandeln. Er erscheint trotzdem – als Eintrag mit dem Namen `Messwerte.xyz – nicht importierbar (Nicht unterstützter Dateityp: .xyz)`. Der **Grund in Klammern** ist gewollt: Sie sehen, warum etwas fehlt, statt dass es stillschweigend verschwindet.

**Hinweis:** Das direkte Ziehen einer Mail **aus Outlook** in das Fenster funktioniert nicht (Outlook übergibt keine echte Datei). Speichern Sie die Mail zuerst als `.msg` oder `.eml` und importieren Sie diese Datei.

---

## MT-03b: Text- und HTML-Dateien importieren (.txt / .md / .html)

**Beispieldateien:** `Notiz.txt`, `Liesmich.md`, `Bestellbestaetigung.html`

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. **📥 Importieren** → alle drei Dateien auf einmal auswählen.
2. Die drei neuen Einträge nacheinander anklicken.

**Erwartet:**
- Jede Datei wird in ein PDF umgewandelt und erscheint als eigener Eintrag (`Notiz.pdf`, `Liesmich.pdf`, `Bestellbestaetigung.pdf`).
- Die Vorschau zeigt den Text lesbar, **Umlaute** eingeschlossen.
- Bei der HTML-Datei ist die Überschrift „Bestellbestätigung“ als Überschrift gesetzt.
- *Nicht offensichtlich:* Eine Markdown-Datei wird als **reiner Text** übernommen – die Zeichen `#`, `*` und `-` bleiben sichtbar und werden nicht als Formatierung umgesetzt.

---

## MT-03c: Office-Dateien importieren (Word / Excel / PowerPoint / OpenDocument)

**Beispieldateien:** `Brief.docx`, `Tabelle.xlsx`, `Praesentation.pptx`, `Text.odt`, `Tabelle.ods`, `Folien.odp`

**Voraussetzungen:** BelegTool ist gestartet. Notieren Sie im Testprotokoll, ob **Microsoft Office** (Word, Excel, PowerPoint) auf diesem PC installiert ist – das Ergebnis hängt davon ab.

**Schritte:**
1. **📥 Importieren** → `Brief.docx` auswählen.
2. Die übrigen fünf Dateien auf einmal importieren.
3. Die neuen Einträge nacheinander anklicken.

**Erwartet (mit installiertem Office):**
- Jede Datei wird über das passende Office-Programm in ein **einseitiges PDF** umgewandelt und erscheint als Eintrag.
- In der Vorschau steht jeweils der Kenntext der Datei, z. B. „BelegtoolGoldenWord2026“ beim Word-Dokument (die Kenntexte stehen oben in der Tabelle der Beispieldateien).
- *Nicht offensichtlich:* Der **erste** Office-Import einer Sitzung kann einige Sekunden dauern, weil die Office-Anbindung erst dann geladen wird. Danach bleibt kein unsichtbares Word, Excel oder PowerPoint im Hintergrund offen.

**Erwartet (ohne Office):**
- Es wird nichts importiert. Eine rote Meldung mit **⚠** nennt den Grund je Datei: „…: Office-Programm zum Konvertieren nicht verfügbar (Word/Excel/PowerPoint erforderlich)“.
- PDF-, Bild-, Archiv- und E-Mail-Import funktionieren unabhängig davon weiter.

---

## MT-04: Archiv importieren (.zip / .tar)

**Ab Version:** 3.10.0

**Beispieldateien:** `Belege_mit_Unterordnern.zip`, `Belege_Archiv.tar`

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. **📥 Importieren** → `Belege_mit_Unterordnern.zip` auswählen.
2. Den neuen Ordner vollständig aufklappen.
3. Den Import mit `Belege_Archiv.tar` wiederholen.

**Erwartet:**
- Die **Ordnerstruktur des Archivs bleibt erhalten**. Für das ZIP entsteht:
  - Ordner `rechnungen` › Ordner `2024` › `beleg.pdf` und `kassenbon.jpg`
  - Ordner `rechnungen` › Ordner `2023` › `beleg.pdf`
  - Ordner `vertraege` › `mietvertrag.pdf`
- *Nicht offensichtlich:* Ein Unterordner wird ein echter **Ordner** im Baum – es entsteht **kein** Dokument, das wörtlich `rechnungen/2024/beleg.pdf` heißt.
- *Nicht offensichtlich:* Die beiden gleichnamigen Dateien `beleg.pdf` (2023 und 2024) bleiben **beide** erhalten; keine geht verloren.
- Das TAR-Archiv ergibt `bank` › `2025` › `kontoauszug.pdf` und `bank` › `2024` › `kontoauszug.pdf`.

**Hinweis:** Sehr große oder böswillig gepackte Archive (zu viele Einträge oder entpackt zu groß) werden abgelehnt, statt den Arbeitsspeicher zu füllen. Das lässt sich mit den Beispieldateien nicht auslösen.

---

## MT-05: Import-Sicherheit – getarnte Programmdatei wird abgelehnt

Geprüft wird der **Inhalt** einer Datei, nicht nur ihre Endung.

**Beispieldateien:** `getarnte_EXE_rechnung.pdf`, `Mail_mit_getarnter_EXE.eml`

**Voraussetzungen:** BelegTool ist gestartet. Die Beispieldatei `getarnte_EXE_rechnung.pdf` ist eine **harmlose Attrappe**: Sie beginnt mit den zwei Buchstaben, an denen Windows-Programme erkannt werden, enthält sonst nur Text und lässt sich nicht ausführen.

**Schritte:**
1. **📥 Importieren** → `getarnte_EXE_rechnung.pdf` auswählen.
2. **📥 Importieren** → `Mail_mit_getarnter_EXE.eml` auswählen und den neuen Ordner aufklappen.

**Erwartet:**
- Schritt 1: Die getarnte Datei wird **nicht** als PDF übernommen. Es erscheint eine rote Meldung mit **⚠**, die den Grund nennt („… sieht aus wie Windows-Programm (EXE/DLL), nicht wie .pdf – abgelehnt.“).
- Schritt 2: Im Mail-Ordner steht der Anhang als `rechnung.pdf – nicht importierbar ('rechnung.pdf' sieht aus wie Windows-Programm (EXE/DLL), nicht wie .pdf – abgelehnt.)`. Der zweite Anhang `echte_Rechnung.pdf` wird normal importiert.
- *Nicht offensichtlich:* Das ist das gewollte Sicherheitsverhalten. Eine umbenannte EXE oder ein Skript wird sichtbar abgelehnt und nicht stillschweigend „irgendwie“ übernommen. Dieselbe Prüfung lehnt Word-/Excel-/PowerPoint-Dateien ab, die auf eine externe Vorlage im Netz verweisen.

**Hinweis:** **Bekannte Abweichung in Version 3.11.2 – bitte nicht erneut melden.** Schritt 1 schlägt derzeit fehl: Statt der Ablehnung entsteht ein leerer Eintrag `getarnte_EXE_rechnung` mit 0 Seiten und ohne Meldung. Schritt 2 (Anhang in der E-Mail) verhält sich wie beschrieben. Ausgeführt wird die Datei in keinem Fall.

---

## MT-05b: Nicht unterstützte Datei und Teilimport

**Beispieldateien:** `Unbekanntes_Format.xyz`, `Rechnung_5_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet. Im Dateidialog von **📥 Importieren** ist die Datei `.xyz` nur sichtbar, wenn der Dateityp-Filter unten rechts auf **„Alle Dateien“** steht – oder Sie ziehen die Dateien aus dem Explorer auf das Fenster.

**Schritte:**
1. Nur `Unbekanntes_Format.xyz` importieren.
2. `Rechnung_5_Seiten.pdf` und `Unbekanntes_Format.xyz` **zusammen** importieren (im Dialog beide markieren).

**Erwartet:**
- Schritt 1: Es entsteht **kein** Eintrag. Eine rote Meldung mit **⚠** lautet „Unbekanntes_Format.xyz: Dateityp .xyz wird nicht unterstützt“.
- Schritt 2: Das PDF wird importiert. Zusätzlich erscheint die Meldung „⚠ Teilweise importiert — Unbekanntes_Format.xyz: Dateityp .xyz wird nicht unterstützt“.
- *Nicht offensichtlich:* Eine nicht lesbare Datei bricht den Import der übrigen Dateien **nicht** ab; Sie erfahren genau, welche Datei fehlt und warum.

---

## MT-06: Verschachtelte Container importieren (Archiv/E-Mail in einem anderen)

Ein Archiv oder eine E-Mail **innerhalb** eines anderen Containers wird geöffnet und nicht als „nicht importierbar“ abgelegt.

**Ab Version:** 3.10.0

**Beispieldateien:** `Verschachtelt_ZIP_in_ZIP.zip`, `Mail_mit_ZIP_Anhang.eml`, `Zu_tief_verschachtelt.zip`

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. **📥 Importieren** → `Verschachtelt_ZIP_in_ZIP.zip`. Den neuen Ordner vollständig aufklappen.
2. **📥 Importieren** → `Mail_mit_ZIP_Anhang.eml`. Den neuen Ordner vollständig aufklappen.
3. **📥 Importieren** → `Zu_tief_verschachtelt.zip`. Alle Ebenen aufklappen.

**Erwartet:**
- Schritt 1: Das innere Archiv erscheint als **eigener Ordner** `ebene_2.zip`; darin liegt `beleg_ganz_innen.pdf`. Daneben liegt `beleg_ebene_1.pdf`.
- Schritt 2: Im Mail-Ordner liegen der Mailtext und ein Ordner `unterlagen.zip` mit `beleg_im_zip.pdf`.
- Schritt 3: Der Baum folgt der Verschachtelung `ebene_2.zip` › `ebene_3.zip` › `ebene_4.zip`. In jeder Ebene liegt ein Beleg.
- *Nicht offensichtlich:* Die Verschachtelung ist auf **3 Ebenen** begrenzt. Das noch tiefer liegende Archiv wird nicht geöffnet, sondern erscheint als `ebene_5.zip – nicht importierbar (zu tief verschachtelt)`. Das ist ein Schutz vor Endlos-Archiven und kein Fehler.

**Hinweis:** Die Größen- und Mengenbegrenzung gilt **gemeinsam für alle Ebenen**. Ist sie mitten im Import ausgeschöpft, erscheint der nächste innere Container als „… – nicht importierbar“; der Rest des Imports bleibt unberührt.
