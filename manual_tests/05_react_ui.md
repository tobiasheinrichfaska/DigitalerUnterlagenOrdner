# 05 — Bedienoberfläche

Start, Öffnen und Speichern, Importieren per Ziehen, Bearbeiten des Baums, mehrere Fenster, Sicherheitsabfragen, Tastenkürzel, große Dokumente und Tags.

---

## MT-30: Starten, öffnen, speichern

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist installiert, aber noch nicht gestartet.

**Schritte:**
1. BelegTool starten (Startmenü → **BelegTool**) und auf das Fenster warten.
2. Auf **📂 Öffnen** klicken und `Beispielmappe.belegtool` wählen.
3. Eine Änderung vornehmen, z. B. Rechtsklick auf einen Eintrag → **Umbenennen**.
4. Auf **💾 Speichern** klicken (oder **Strg+S**).

**Erwartet:**
- Das Fenster erscheint zügig; das Öffnen geht nahezu sofort.
- *Nicht offensichtlich:* Die allererste Aktion direkt nach dem Start kann etwa eine Sekunde zögern – im Hintergrund werden die PDF-Bibliotheken vorgewärmt.
- Nach der Änderung steht ein **„•“** am **💾** und hinter dem Titel. Speichern entfernt es und zeigt die grüne Meldung **„✓ Gespeichert“**.

---

## MT-31: Importieren – Schaltfläche, Ziehen und Zielposition

**Beispieldateien:** `Beispielmappe.belegtool`, `Rechnung_5_Seiten.pdf`, `Foto_Kassenbon.jpg`, `Notiz.txt`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Auf **📥 Importieren** klicken und mehrere Dateien auf einmal auswählen.
2. Eine Datei aus dem Explorer **auf das Fenster** ziehen (nicht auf eine Zeile) und loslassen.
3. Eine Datei **auf eine Ordnerzeile** ziehen und loslassen. Die Anzeige beobachten.
4. Eine Datei **zwischen zwei Zeilen** ziehen; ganz unten in einem Ordner die Maus zusätzlich **nach links und rechts schieben**.

**Erwartet:**
- Importierte Dateien erscheinen als Einträge; mehrere behalten ihre Reihenfolge. Jeder Import ist **ein** Rückgängig-Schritt.
- Das Ablegen zeigt **dieselben Anzeigen wie das Verschieben**: Ein Ordner wird hervorgehoben („hinein“), eine Linie zeigt „davor/dahinter“, und am unteren Ende erscheint ein Geist **„📥 importieren“** mit Zielangabe, die beim seitlichen Schieben die Ebene wechselt.
- Ablegen **auf dem Fensterhintergrund** importiert in den markierten Ordner, sonst auf die oberste Ebene. Der gestrichelte Rahmen mit Hinweistext ist nur eine Orientierung.

---

## MT-32: Baum bearbeiten – verschieben, Ebene wählen, zusammenführen, gruppieren, splitten

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet, alle Ordner sind aufgeklappt.

**Schritte:**
1. Einen Eintrag auf einen Ordner ziehen (hinein), zwischen zwei Zeilen ziehen (davor/dahinter) und am unteren Ende eines Ordners **nach links schieben**, um ihn eine Ebene höher abzulegen.
2. Mit **Strg+Klick** `Telefon_2025-01.pdf` und `Strom_Abschlag_2025-01.pdf` markieren (gleicher Ordner) → Rechtsklick auf einen davon → **Zusammenführen → 1 PDF (2)**.
3. Mit **Strg+Klick** zwei Einträge aus **verschiedenen** Ordnern markieren → Rechtsklick auf einen davon → **In neuen Ordner (2)**. Im Dialog „Name des neuen Ordners“ die Vorgabe **Neue Gruppe** bestätigen.
4. Rechtsklick auf `Sammelrechnung_Wartung.pdf` (4 Seiten) → **Splitten ▸** → **pro Seite**.

**Erwartet:**
- Schritt 1: Der Baum wird ohne Flackern oder Doppelungen neu gezeichnet; der Geist nennt das Ziel („in <Ordner>“ / „oberste Ebene“).
- Schritt 2: **Zusammenführen** erscheint nur für mindestens zwei Dokumente **desselben Ordners** und ergibt ein PDF. Der Menüpunkt wird nur angeboten, wenn Sie auf **einen markierten** Eintrag rechtsklicken.
- Schritt 3: **In neuen Ordner** funktioniert über Ebenen hinweg. Der neue Ordner entsteht im gemeinsamen übergeordneten Ordner (sonst auf der obersten Ebene); die Einträge bleiben getrennte Dokumente.
- Schritt 4: **Splitten** ersetzt das Dokument durch einen Eintrag je Seite.

---

## MT-33: Komprimierungs-Vorschau

**Beispieldateien:** `Farbscan_Rechnung_6_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; die Datei ist importiert und angeklickt.

**Schritte:**
1. Die Auswahlliste der Verfahren über der Vorschau öffnen.
2. Ein Verfahren wählen; den **DPI**-Regler verschieben; **unkomprimierte Fassung** wählen.
3. Wieder ein Verfahren wählen und auf **❓ Lesbarkeit geprüft** klicken. Einen anderen Eintrag anklicken und zurückkehren.

**Erwartet:**
- *Nicht offensichtlich:* Das Anklicken des Eintrags startet **keine** Komprimierung. Erst das Öffnen der Liste zeigt **„Kompression läuft …“** und danach die Verfahren.
- Verfahren und DPI zu wechseln zeigt nur eine Vorschau. Das Dokument ändert sich **erst** mit **Lesbarkeit geprüft** (ein Rückgängig-Schritt); die Schaltfläche zeigt dann **✓ übernommen**.
- Nach der Rückkehr zum Eintrag ist das übernommene Verfahren eingestellt.

---

## MT-34: Mehrere Fenster

**Beispieldateien:** `Beispielmappe.belegtool`, `Zweite_Mappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Auf **🗗 Neues Fenster** klicken (oder **Strg+N**).
2. Im neuen Fenster mit **📂 Öffnen** `Zweite_Mappe.belegtool` laden und etwas ändern.
3. In beiden Fenstern **📥 Importieren** und **💾 Speichern** benutzen.

**Erwartet:**
- Es öffnet sich ein zweites, unabhängiges Fenster; die beiden Dokumente haben nichts miteinander zu tun.
- *Nicht offensichtlich:* Dateidialoge und das Speicherziel gehören zu dem Fenster, in dem Sie geklickt haben – nicht immer zum ersten Fenster.

---

## MT-34b: Fenster merkt sich Größe, Position und Bildschirm

**Ab Version:** 3.10.0

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte:**
1. Die Fenstergröße **ändern** und das Fenster an eine andere Stelle **ziehen** – bei mehreren Bildschirmen auf den **zweiten**.
2. Das Fenster **schließen** (BelegTool beendet sich).
3. BelegTool erneut **starten**.

**Erwartet:**
- Das Fenster öffnet sich in **derselben Größe an derselben Stelle** – auch auf **demselben Bildschirm**.
- *Nicht offensichtlich:* Nur das **erste** Fenster merkt sich seine Lage; weitere Fenster aus **Neues Fenster** öffnen in Standardgröße.
- *Nicht offensichtlich:* Ist der zuletzt benutzte Bildschirm **abgesteckt**, öffnet BelegTool mittig in Standardgröße (1280 × 820) statt außerhalb des sichtbaren Bereichs.

---

## MT-35: Schutz vor Verlust ungespeicherter Änderungen

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Eine Änderung vornehmen (das **„•“** am **💾** erscheint).
2. Auf **📂 Öffnen** klicken und die Rückfrage mit **Abbrechen** beantworten.
3. Versuchen, das **Fenster zu schließen**, und die Rückfrage mit **Abbrechen** beantworten.
4. Speichern und das Fenster erneut schließen.

**Erwartet:**
- Schritt 2: BelegTool fragt „Eine andere Datei öffnen und die ungespeicherten Änderungen verwerfen?“. Abbrechen behält das Dokument.
- Schritt 3: BelegTool fragt „Das Fenster schließen und die ungespeicherten Änderungen verwerfen?“ (Titel „Ungespeicherte Änderungen“). Abbrechen lässt das Fenster offen.
- Schritt 4: Nach dem Speichern schließt das Fenster ohne Rückfrage.
- Bei mehreren Fenstern warnt jedes Fenster nur vor **seinen eigenen** Änderungen.

---

## MT-36: Export als PDF mit Inhaltsverzeichnis

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Auf **⬇ Export PDF** klicken, im Dialog **Exportieren** wählen und einen Speicherort angeben.
2. Einige Einträge mit Strg+Klick markieren und erneut exportieren.
3. Die exportierten PDFs öffnen.

**Erwartet:**
- Es entsteht ein einzelnes PDF mit einer **Inhaltsverzeichnis-Seite**, anklickbaren Einträgen und **Lesezeichen** in der Seitenleiste.
- Schritt 2: Solange Einträge markiert sind, zeigt **⬇** deren Anzahl am Symbol; der Export enthält nur die markierten Einträge samt Inhalt.
- Bei Erfolg erscheint die grüne Meldung **„✓ PDF exportiert (N Einträge)“**.

---

## MT-37: Tastenkürzel und Zoom

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte:**
1. Nacheinander ausprobieren: **Strg+Z** / **Strg+Y** (Rückgängig / Wiederholen), **Strg+S** (Speichern), **Strg+O** (Öffnen), **Strg+E** (Export), **Strg+N** (Neues Fenster), **Entf** (markierten Eintrag löschen).
2. Einen Eintrag mit **F2** umbenennen und **während der Eingabe** `Strg+S` und `Entf` drücken.
3. In der Vorschau mit **Strg + Mausrad** zoomen; die Zoom-Leiste **− / ＋ / 100%** benutzen.

**Erwartet:**
- Schritt 1: Alle Kürzel lösen die genannte Aktion aus. **Entf** löscht den markierten Eintrag (rückgängig machbar).
- Schritt 2: Solange in einem Textfeld oder Dialog getippt wird, werden die Kürzel **ignoriert** – `Entf` löscht dann ein Zeichen und nicht den Eintrag.
- Schritt 3: Strg + Mausrad zoomt nur die Vorschau, nicht das ganze Fenster.

---

## MT-39: Großes PDF – Vorschau ohne lange Wartezeit

Ein großes PDF soll seine Vorschau **sofort** zeigen (nur die ersten Seiten) und beim Scrollen nachladen, statt einzufrieren, bis alle Seiten gezeichnet sind.

**Beispieldateien:** `Grosses_Dokument_120_Seiten.pdf`, `Rechnung_5_Seiten.pdf`

**Voraussetzungen:** BelegTool ist gestartet; beide Dateien sind importiert.

**Schritte:**
1. Den Eintrag `Grosses_Dokument_120_Seiten` anklicken und die Vorschau beobachten.
2. Langsam durch das Dokument nach unten scrollen.
3. Schnell weit nach unten und wieder nach oben scrollen.
4. Den anderen Eintrag anklicken und danach wieder das große Dokument.

**Erwartet:**
- Die Vorschau erscheint **sofort**: Die ersten Seiten sind nach etwa 1–2 Sekunden da. Noch nicht gezeichnete Seiten zeigen einen hell **gestreiften Platzhalter** in der richtigen Größe – das Layout springt nicht, wenn die echte Seite eintrifft.
- Scrollen im Lesetempo bleibt flüssig; die Seiten füllen sich knapp vor dem sichtbaren Bereich.
- Schnelles Scrollen zeigt kurz Platzhalter, die sich gleich füllen; die Position der Bildlaufleiste bleibt stabil.
- *Nicht offensichtlich:* Bei der Rückkehr zum großen Dokument steht die Vorschau an **derselben Stelle** wie zuvor; bereits gesehene Seiten sind sofort wieder da.
- *Nicht offensichtlich:* Auch die Komprimierungs-Vorschau lädt nur die sichtbaren Seiten. Das erste Ansehen bei einem neuen DPI-Wert dauert dennoch, weil die komprimierte Fassung erst berechnet wird.

---

## MT-40: Baum mit der Tastatur umbauen und Ordner zuklappen

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** BelegTool ist gestartet; `Beispielmappe.belegtool` ist geöffnet.

**Schritte (A – Ordner zuklappen):**
1. Auf den Pfeil **▾** vor einem Ordner klicken.
2. Rechtsklick auf einen Ordner → **Zuklappen** bzw. **Aufklappen**; Rechtsklick auf einen beliebigen Eintrag → **Alle zuklappen** / **Alle aufklappen**.
3. **💾 Speichern**, das Fenster schließen und die Datei erneut öffnen.

**Erwartet (A):**
- Der Pfeil wechselt auf **▸** und die Inhalte des Ordners werden ausgeblendet.
- *Nicht offensichtlich:* Zuklappen markiert das Dokument als **geändert („•“)**. Es wird mitgespeichert – nach dem Öffnen sind dieselben Ordner wieder zugeklappt. **Strg+Z** macht ein Zuklappen rückgängig.

**Schritte (B – mit den Pfeiltasten bewegen):**
4. Einen Eintrag anklicken und mit **↑ / ↓** die Markierung bewegen.
5. Auf einem Ordner **→** drücken (aufklappen bzw. hineingehen) und **←** (zuklappen bzw. herausgehen).

**Erwartet (B):**
- Die Markierung folgt den **sichtbaren** Zeilen; Inhalte zugeklappter Ordner werden übersprungen. **← / →** klappen Ordner zu und auf.

**Schritte (C – Eintrag „tragen“: Einfg → Pfeiltasten → Einfg):**
6. Einen Eintrag markieren und **Einfg** drücken.
7. Mit **↑ / ↓** die Reihenfolge ändern, mit **→** in den Ordner direkt darüber hineinschieben, mit **←** eine Ebene herausholen.
8. **Einfg** erneut drücken, um abzulegen.
9. Den Vorgang wiederholen, am Ende aber **Esc** statt Einfg drücken.

**Erwartet (C):**
- Nach dem ersten **Einfg** bekommt die Zeile einen **gestrichelten Rahmen** („gegriffen“).
- Während des Tragens ist der Baum vollständig aufgeklappt und der Eintrag wandert **nur optisch** – es ist noch nichts verändert.
- **Einfg** legt ab: **eine** rückgängig machbare Verschiebung (Strg+Z holt sie in einem Schritt zurück).
- **Esc** bricht ab; der Eintrag springt zurück und das Dokument bleibt unverändert.
- *Nicht offensichtlich:* Die Taste zum Verschieben ist **Einfg** und nicht Strg+Pfeil, weil Strg bereits für die Mehrfachauswahl belegt ist.

---

## MT-41: Tags – ein/aus, bearbeiten, gefilterte Ansicht

**Beispieldateien:** `Beispielmappe.belegtool`, `Beispielmappe_mit_Tags.belegtool`

**Voraussetzungen:** BelegTool ist gestartet.

**Schritte (A – Schalter und automatisches Einschalten):**
1. `Beispielmappe.belegtool` öffnen. Die Schaltfläche **🏷️ Tags** ist **aus** – es sind keine Tags und kein Tag-Editor zu sehen.
2. Auf **🏷️ Tags** klicken.
3. Ein Dokument anklicken, im Tag-Editor in das Feld **+ Tag** `Spende` eingeben und **Enter** drücken.
4. Über **▾ → Speichern unter…** an einem neuen Ort speichern, das Fenster schließen und die Datei erneut öffnen.

**Erwartet (A):**
- Schritt 2: Die Schaltfläche ist hervorgehoben; über der Vorschau erscheint der **Tag-Editor**, über dem Baum eine **Suchleiste** („Tags suchen…“).
- Schritt 3: Das Tag steht als Marke am Dokument und in dessen Zeile im Baum.
- *Nicht offensichtlich:* Eine Datei, die **bereits Tags enthält**, öffnet mit **eingeschalteten** Tags (Schritt 4) – der Schalter muss nicht erst betätigt werden.
- Ausschalten blendet alle Marken und Tag-Funktionen aus; die Tags **bleiben gespeichert** und erscheinen nach dem Einschalten wieder.

**Schritte (B – Suche und Vererbung):**
5. `Beispielmappe_mit_Tags.belegtool` öffnen (der Ordner **02 Bank** trägt das Tag `Bank`, einzelne Dokumente tragen eigene Tags).
6. In die Suchleiste `bank` eingeben.
7. Die Suche leeren und `miete` eingeben.
8. Die Suche leeren und einen **Dateinamen** eingeben, z. B. `Deckblatt`.

**Erwartet (B):**
- `bank` → Der Ordner **02 Bank** erscheint mit seinem **gesamten Inhalt** (ein Ordner-Tag gilt für alles darin).
- `miete` → Es erscheint nur der **Pfad** zum Treffer: der Ordner **03 Vorjahr 2024** als Rahmen und darin `Miete_2024-12.pdf`. Das Nachbardokument ohne dieses Tag ist **ausgeblendet**.
- Die Suche findet **nur Tags** (Groß-/Kleinschreibung egal). Ein Datei- oder Eintragsname findet **nichts** – Namen werden absichtlich nicht durchsucht.

**Schritte (B2 – nach Tag gruppieren):**
9. Die Suche leeren und **Nach Tag gruppieren** anhaken.

**Erwartet (B2):**
- Der Baum wird durch **einen Ordner je Tag** ersetzt (alphabetisch). Darin steht der Pfad zu jedem Eintrag mit diesem Tag: Ein getaggter **Ordner** bleibt **vollständig**, ein getaggtes **Dokument** behält seine übergeordneten Ordner als Zusammenhang.
- Ein Eintrag mit mehreren Tags erscheint unter **jedem** davon – Mehrfachnennungen sind gewollt. Alles ohne Tag landet in der Gruppe **„Ohne Tags“**.
- *Nicht offensichtlich:* Die Tag-Überschriften sind nur Anzeige – Klick und Rechtsklick darauf bewirken nichts. Die echten Ordner und Dokumente darin lassen sich weiterhin anklicken und ansehen. Haken entfernen oder **Ansicht zurücksetzen** führt zurück.

**Schritte (B3 – Ansicht in neuem Fenster öffnen):**
10. **Nach Tag gruppieren** abschalten, `miete` suchen und in der Leiste auf **In neuem Fenster öffnen** klicken.

**Erwartet (B3):**
- Ein **neues Fenster** enthält eine **echte, bearbeitbare Kopie** nur der **angezeigten** Einträge – in normaler Baumreihenfolge. Das ursprüngliche Fenster bleibt unverändert.
- Das neue Dokument trägt das gesuchte Tag vor dem bisherigen Namen (in der Art `Miete - Beispielmappe_mit_Tags`); so lautet auch der Vorschlag beim Speichern.
- *Nicht offensichtlich:* Die Schaltfläche erscheint **nur bei aktiver Tag-Suche**. **Nach Tag gruppieren** allein blendet sie weder ein noch aus. Änderungen an der Kopie berühren das Ausgangsdokument nicht.

**Schritte (C – Struktur ist gesperrt, solange gefiltert wird):**
11. Bei aktiver Suche den Hinweis **⚠ Ansicht gefiltert — Umsortieren aus** beachten und ausprobieren: eine Zeile ziehen, **Einfg** drücken, **Entf** drücken, auf **📥 Importieren** und **＋ Ordner** klicken, eine Datei aus dem Explorer auf den Baum ziehen, einen Eintrag rechtsklicken.

**Erwartet (C):**
- Die gefilterte Ansicht ist für die **Struktur schreibgeschützt**: Zeilen lassen sich nicht ziehen, Einfg und Entf bewirken nichts, **Importieren** und **＋ Ordner** sind ausgegraut, eine abgelegte Datei wird ignoriert, und im Kontextmenü fehlen **Löschen**, **Zusammenführen**, **In neuen Ordner**, **Splitten** und **Ordner anlegen**.
- *Warum:* Ein gefilterter Ordner kann nicht passende Inhalte verbergen. Löschen oder Verschieben würde unbemerkt Zeilen treffen, die gerade nicht zu sehen sind.
- **Inhaltliche Änderungen bleiben möglich**: Umbenennen, Status und Komprimierung funktionieren an den sichtbaren Zeilen.

**Schritte (D – mehrere Dokumente gleichzeitig taggen, ab Version 3.10.0):**
12. Die Ansicht zurücksetzen. `Telefon_2025-01.pdf` und `Strom_Abschlag_2025-01.pdf` tragen beide `Betriebsausgabe`, dazu je ein eigenes Tag. Beide mit **Strg+Klick** markieren.
13. Im Tag-Editor das Tag `Wichtig` **hinzufügen**, dann die gemeinsame Marke `Betriebsausgabe` über ihr **×** **entfernen**.
14. Das nur einseitig vorhandene Tag `Telefon` in das Feld **+ Tag** eingeben und bestätigen.

**Erwartet (D):**
- Der Editor zeigt **„2 markiert“** und die **Vereinigung** der Tags beider Dokumente. Ein Tag, das nur **eines** trägt (`Telefon`, `Energie`), ist als **hohle, gestrichelte** Marke gezeichnet; ein gemeinsames Tag als gefüllte Marke.
- `Wichtig` landet auf **beiden** Dokumenten, `Betriebsausgabe` verschwindet von **beiden** – jeweils **ein** Rückgängig-Schritt.
- Schritt 14 ergänzt `Telefon` auch beim zweiten Dokument (die Marke wird gefüllt). Ein Dokument, das das Tag schon hat, bleibt unverändert – keine Doppelungen.
- *Nicht offensichtlich:* Die **Rücktaste** im leeren Eingabefeld entfernt bei Mehrfachauswahl **nichts** (nur bei einem einzelnen Dokument das letzte Tag).
