# 10 — DATEV-Modus

Der DATEV-Modus legt Dokumente in der lokalen **DATEV Dokumentenablage** ab und schreibt sie dorthin zurück. Er ist **standardmäßig aus**; ausgeschaltet verhält sich BelegTool genau wie ohne diese Funktion.

> ⚠️ **Umgebung:** Diese Tests brauchen einen PC mit laufendem **DATEVconnect** und eine Windows-Anmeldung als DATEV-Benutzer – in der Regel den Kanzlei-Arbeitsplatz. Ohne erreichbares DATEVconnect sind nur **MT-DATEV-01** und **MT-DATEV-07** durchführbar; alle anderen im Testprotokoll als „Nicht durchführbar“ ankreuzen.

> ⚠️ **Echte Daten:** Das Zurückschreiben **überschreibt** das Dokument in DATEV (die Dokumentenablage führt keine Versionen). Verwenden Sie ausschließlich einen **Testmandanten** und **Testdokumente** („ZZZ TEST“), niemals echte Mandantenunterlagen. Vor jedem Überschreiben legt BelegTool eine Sicherung des bisherigen Stands unter `%APPDATA%\DigitalerUnterlagenOrdner\datev_backups\` ab.

---

## MT-DATEV-01: DATEV-Modus ein- und ausschalten (ohne DATEV-Anbindung möglich)

**Ab Version:** 3.10.0

**Voraussetzungen:** BelegTool ist gestartet (beliebiges Dokument).

**Schritte:**
1. Die Schaltfläche **DATEV** ganz rechts in der Kopfzeile suchen.
2. Darauf klicken.
3. BelegTool schließen und neu starten.
4. Erneut auf **DATEV** klicken, um den Modus auszuschalten.

**Erwartet:**
- Eingeschaltet ist die Schaltfläche grün gefüllt und zeigt **DATEV ●**.
- Die Einstellung wird **je Benutzer gemerkt**: Nach dem Neustart ist der DATEV-Modus **weiterhin ein**. Auf einem Terminalserver hat jeder Benutzer seine eigene Einstellung.
- **Ohne erreichbares DATEVconnect** darf das Einschalten das Programm **weder einfrieren noch abstürzen** lassen. Neben der Schaltfläche steht dann zunächst **⏳ verbinde…** und danach **⚠️ keine Verbindung**; die DATEV-Aktionen sind ausgegraut.
- Ausschalten stellt die schlichte Kopfzeile wieder her.

---

## MT-DATEV-02: Kennzeichen „Mit DATEV verknüpft“ bei einem ausgecheckten Dokument

**Ab Version:** 3.10.0

**Voraussetzungen:** DATEV-Modus **ein**; DATEVconnect erreichbar. In DATEV ist ein **Testdokument ausgecheckt** – DATEV legt dessen Datei dabei in einem Ordner mit der Dokumentkennung ab.

**Schritte:**
1. Die ausgecheckte Datei in BelegTool **öffnen** (mit **📂 Öffnen** oder per Doppelklick).
2. Die Kopfzeile ansehen.

**Erwartet:**
- Es erscheint das Kennzeichen **🔗 Mit DATEV verknüpft** mit dem Namen der Quelldatei.
- War das Dokument beim Öffnen bereits **von jemand anderem ausgecheckt**, steht der Zusatz **· in DATEV ausgecheckt** **sofort** dabei – Sie erfahren die Einschränkung gleich und nicht erst beim Speichern.
- Neben dem Kennzeichen steht die Schaltfläche **Nach DATEV zurückschreiben**.

---

## MT-DATEV-03: Geschütztes Zurückschreiben (Normalfall)

**Ab Version:** 3.10.0

**Voraussetzungen:** MT-DATEV-02 ist durchgeführt: Ein verknüpftes Testdokument ist geöffnet und von niemand anderem ausgecheckt. Eine kleine Änderung ist vorgenommen (z. B. eine Textnotiz über das PDF-Tool).

**Schritte:**
1. Auf **Nach DATEV zurückschreiben** klicken.
2. Die Rückfrage „Nach DATEV zurückschreiben?“ mit **Ja** bestätigen.
3. Den Test wiederholen und die Rückfrage mit **Nein** beantworten.

**Erwartet:**
- Schritt 2: Es erscheint die Meldung **„✓ Nach DATEV zurückgeschrieben“**.
- In DATEV zeigt die Datei des Dokuments die Änderung; das **Änderungsdatum ist neuer**.
- Die zugehörige lokale Datei wird **im selben Schritt mitgespeichert** – es gibt keine Nachfrage „Speichern unter…“, und das **„•“** verschwindet.
- Unter `%APPDATA%\DigitalerUnterlagenOrdner\datev_backups\` liegt eine Sicherung des **vorherigen** DATEV-Stands, angelegt **vor** dem Überschreiben.
- Schritt 3: **Nein** schreibt **nichts** nach DATEV. Sie können stattdessen normal mit **💾** lokal speichern.

**Hinweis:** Sonderfall „DATEV gelingt, lokales Speichern scheitert“ (z. B. die lokale Datei liegt auf einem schreibgeschützten Laufwerk): Die Meldung „Nach DATEV zurückgeschrieben“ erscheint trotzdem, **zusätzlich** nennt eine Fehlermeldung das gescheiterte lokale Speichern. Die Änderung geht nicht stillschweigend verloren.

---

## MT-DATEV-04: Zurückschreiben wird bei Konflikten verweigert

**Ab Version:** 3.10.0

**Voraussetzungen:** Ein verknüpftes Testdokument ist geöffnet (wie in MT-DATEV-03).

**Schritte:**
1. Jeden der drei Fälle aus der Tabelle herbeiführen und danach auf **Nach DATEV zurückschreiben** klicken.

| Fall herbeiführen | Erwartete Meldung |
|---|---|
| In DATEV das Dokument durch einen **anderen Benutzer auschecken** lassen | „DATEV: Das Dokument ist ausgecheckt — nur lokal speichern möglich.“ |
| In DATEV das Dokument **ändern** (neue Datei), nachdem es in BelegTool geöffnet wurde | „DATEV: Das Dokument wurde zwischenzeitlich geändert — bitte lokal speichern.“ |
| Eine **gespeicherte `.belegtool`** öffnen, die ihre DATEV-Herkunft kennt, deren Inhalt aber nicht mehr zur Datei in DATEV passt | „DATEV: Der Serverstand weicht vom geöffneten Stand ab — bitte lokal speichern.“ |

**Erwartet:**
- In **jedem** Fall bleibt das Dokument in DATEV **unverändert** – es wird nie stillschweigend überschrieben.
- Die Meldung nennt den Grund.
- Ein normales lokales **💾 Speichern** bleibt möglich.

---

## MT-DATEV-05: Ein nicht verknüpftes Dokument nach DATEV ablegen

**Ab Version:** 3.11.0

**Beispieldateien:** `ZZZ_TEST_Dokument.pdf`

**Voraussetzungen:** DATEV-Modus **ein**; DATEVconnect erreichbar. In BelegTool ist ein **neues** Dokument offen, in das `ZZZ_TEST_Dokument.pdf` importiert wurde – es stammt nicht aus DATEV und ist daher **nicht verknüpft**.

**Schritte:**
1. In der Kopfzeile auf **Nach DATEV ablegen** klicken. Es öffnet sich ein Ablagedialog, der die Mandantenliste lädt.
2. Im Suchfeld **Mandant** eine Nummer **oder** einen Namen eintippen und den **Testmandanten** in der Liste wählen.
3. Das Feld **Bezeichnung** prüfen und auf einen erkennbaren Testnamen ändern (z. B. „ZZZ TEST BelegTool“). Probeweise leeren und wieder füllen.
4. Nach Wunsch **Ordner** und **Register**, ein **Belegdatum** sowie **Veranlagungsjahr** und **-monat** wählen. Probeweise einen Monat **ohne** Jahr wählen.
5. Auf **Ablegen** klicken.

**Erwartet:**
- Das Feld **Bezeichnung** ist mit dem Dokumentnamen **vorbelegt**; es wird der **Name des Dokuments in DATEV**.
- **Ablegen ist ausgegraut, bis ein Mandant gewählt UND eine Bezeichnung vorhanden ist.** Wird die Bezeichnung geleert, wird die Schaltfläche wieder ausgegraut – ein abgelegtes Dokument ist nie namenlos.
- Ein Monat ohne Jahr zeigt den Hinweis „Monat ohne Jahr ist nicht möglich — bitte ein Jahr wählen.“ und hält **Ablegen** ausgegraut.
- Nach Schritt 5 erscheint die Meldung **„✓ In DATEV abgelegt“**.
- In der Dokumentenablage des Testmandanten liegt ein **neues** Dokument mit der Datei, dem eingegebenen Namen, im gewählten Ordner und Register, mit Belegdatum und Veranlagungszeitraum. **Bitte diese Felder in DATEV ausdrücklich nachsehen** und im Protokoll bestätigen.
- Das Kennzeichen in der Kopfzeile wechselt auf **🔗 Mit DATEV verknüpft** – eine spätere Änderung bietet das Zurückschreiben an.
- **Lässt sich die Mandantenliste nicht laden**, nennt der Dialog den Grund und **Ablegen bleibt ausgegraut** – es wird nichts auf Verdacht abgelegt.

---

## MT-DATEV-06: Export nach DATEV (gleicher Mandant), auch aufgeteilt

**Ab Version:** 3.10.0

**Voraussetzungen:** DATEV-Modus **ein**; ein **verknüpftes** Testdokument mit mehreren Seiten ist geöffnet (damit ist der Mandant bekannt).

**Schritte:**
1. Auf **⬇ Export PDF** klicken.
2. Im Dialog **Nach DATEV ablegen (gleicher Mandant)** anhaken.
3. Bei einem zweiten Durchlauf zusätzlich **In mehrere Dateien aufteilen** mit einer kleinen Seitenzahl anhaken.
4. Auf **Exportieren** klicken.

**Erwartet:**
- Es erscheint **kein Dialog zum Speichern** – der Export geht nach DATEV statt auf die Festplatte.
- Die Meldung lautet **„✓ In DATEV abgelegt (N Dokumente)“**.
- In DATEV entstehen **N neue Dokumente** beim **selben Mandanten** wie die Quelle. Mit Aufteilung ist **jede Teildatei ein eigenes Dokument** (N = Zahl der Teile), ohne Aufteilung genau eines.

---

## MT-DATEV-07: Ausgeschalteter Modus ist wirklich unsichtbar

**Ab Version:** 3.10.0

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** DATEV-Modus **aus**.

**Schritte:**
1. `Beispielmappe.belegtool` öffnen, etwas ändern, speichern und den Exportdialog (**⬇ Export PDF**) öffnen.
2. Ein Dokument per Rechtsklick → **Im PDF-Tool öffnen** öffnen und die Schaltflächen dort ansehen.

**Erwartet:**
- Kein DATEV-Kennzeichen, keine DATEV-Aktionen, keine DATEV-Option im Exportdialog, keine DATEV-Schaltfläche im PDF-Tool.
- In der Kopfzeile steht nur die unauffällige Schaltfläche **DATEV** zum Einschalten.
- Öffnen, Bearbeiten, Speichern und Exportieren verhalten sich wie gewohnt.

---

## MT-DATEV-08: Ausgechecktes PDF im PDF-Tool bearbeiten und einchecken

**Ab Version:** 3.11.1

**Beispieldateien:** `ZZZ_TEST_Dokument.pdf`

**Voraussetzungen:** DATEV-Modus **ein**; DATEVconnect erreichbar. In DATEV ist ein **Testdokument (PDF) ausgecheckt**. Wichtig zu wissen: DATEV lehnt das direkte Zurückschreiben in ein **ausgechecktes** Dokument ab. Ein ausgechecktes Dokument wird deshalb auf dem üblichen Weg gesichert – Arbeitskopie bearbeiten, speichern, **in DATEV einchecken**.

**Schritte (A – ausgechecktes Dokument, der Normalfall):**
1. Die ausgecheckte **`.pdf`** direkt öffnen (Doppelklick bzw. „Öffnen mit → BelegTool“).
2. Die Leiste oben im Fenster ansehen.
3. Über **✎ Text** eine kleine Notiz einfügen und auf **💾 Speichern** klicken.
4. Das Dokument in DATEV wieder **einchecken**.

**Erwartet (A):**
- Schritt 1: Die Datei öffnet im **PDF-Tool** (Einzel-PDF-Ansicht), **nicht** im Hauptfenster mit dem Baum.
- ⚠️ Das Fenster erscheint **sofort** und zeigt das PDF – es hängt **nicht** 10–20 Sekunden, bis die DATEV-Verbindung steht.
- ⚠️ Der **Seiteninhalt ist sichtbar** – keine leere weiße Seite. DATEV-Dokumente sind meist Scans; eine leere Seite bei richtiger Seitenzahl wäre ein Fehler.
- Schritt 2: Es steht dort **🔗 Mit DATEV verknüpft · <Datei> · ausgecheckt (💾 Speichern → in DATEV einchecken)**. Eine Schaltfläche **🔗 Nach DATEV zurückschreiben** gibt es **nicht** (sie ist bei ausgecheckten Dokumenten ausgeblendet).
- Schritt 3: Der Statustext zeigt **„Gespeichert ✓“**; die Änderung steht in der lokalen **Arbeitskopie**. Ist die Arbeitskopie gesperrt oder schreibgeschützt, meldet Speichern den Fehler und nichts wurde gespeichert.
- Schritt 4: Nach dem Einchecken zeigt der neue Stand in DATEV die Notiz.

**Schritte (B – verknüpftes, aber nicht ausgechecktes Dokument):**
5. Ein verknüpftes `.pdf` öffnen, das **nicht** ausgecheckt ist.
6. Eine Notiz einfügen, auf **🔗 Nach DATEV zurückschreiben** klicken und mit **Ja** bestätigen.

**Erwartet (B):**
- Die Schaltfläche **🔗 Nach DATEV zurückschreiben** **ist** vorhanden.
- Der Statustext zeigt **„Nach DATEV zurückgeschrieben ✓ · <Datei>.pdf“**; die Datei in DATEV enthält die Notiz; unter `%APPDATA%\DigitalerUnterlagenOrdner\datev_backups\` liegt eine Sicherung des vorherigen Stands.

**Schritte (C – weitere Zustände):**
7. `ZZZ_TEST_Dokument.pdf` (nicht aus DATEV) per Doppelklick bzw. „Öffnen mit → BelegTool“ öffnen.
8. Den DATEV-Modus ausschalten und die Datei erneut öffnen.

**Erwartet (C):**
- Schritt 7: Ein **nicht verknüpftes** PDF zeigt **📤 Nach DATEV ablegen**; ein Klick öffnet den Ablagedialog aus MT-DATEV-05.
- Solange die Verbindung noch aufgebaut wird, ist die DATEV-Schaltfläche **ausgegraut** und trägt einen Hinweis.
- Schritt 8: Bei **ausgeschaltetem** DATEV-Modus zeigt das PDF-Tool **gar keine** DATEV-Schaltfläche.

---

## MT-DATEV-09: Ein im PDF-Tool geöffnetes Dokument nach DATEV ablegen

**Ab Version:** 3.11.0

**Beispieldateien:** `Beispielmappe.belegtool`

**Voraussetzungen:** DATEV-Modus **ein**; DATEVconnect erreichbar; `Beispielmappe.belegtool` ist im Hauptfenster geöffnet (nicht aus DATEV ausgecheckt).

**Schritte:**
1. Rechtsklick auf ein Dokument → **Im PDF-Tool öffnen**.
2. Die Schaltflächen im PDF-Tool ansehen.
3. Über **✎ Text** eine kleine Notiz einfügen. Auf **📤 Nach DATEV ablegen** klicken, im Ablagedialog den **Testmandanten** wählen, die **Bezeichnung** auf einen Testnamen setzen und auf **Ablegen** klicken.

**Erwartet:**
- Schritt 2: Es gibt die Schaltfläche **📤 Nach DATEV ablegen**.
- Schritt 3: Es öffnet sich **derselbe Ablagedialog** wie in MT-DATEV-05. Danach erscheint **„In DATEV abgelegt ✓“**.
- In DATEV liegt beim gewählten Mandanten ein **neues** Dokument mit dem bearbeiteten PDF, benannt nach der Bezeichnung.
- Im **Hauptfenster** enthält der Eintrag jetzt Ihre Notiz. Es erscheint **kein** Fehler „lokal nicht gespeichert“.
- *Nicht offensichtlich:* Ein aus dem Baum geöffnetes Dokument bietet immer nur **Ablegen** (📤) an, nie **Zurückschreiben** (🔗). Das Zurückschreiben einer verknüpften Mappe geschieht im Hauptfenster (MT-DATEV-03).
