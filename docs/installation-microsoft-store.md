# BelegTool aus dem Microsoft Store installieren

BelegTool (Projektname „Digitaler Unterlagen-Ordner“) sammelt PDFs, Scans, Fotos, Office-Dateien und E-Mails in einem Ordnerbaum und exportiert sie als ein PDF mit Inhaltsverzeichnis. Die Installation aus dem Microsoft Store ist der einfachste Weg: Sie braucht keine Administratorrechte, löst keine Sicherheitswarnungen aus und hält das Programm von selbst aktuell.

## Auf einen Blick

| Angabe | Wert |
|---|---|
| App | **BelegTool** |
| Herausgeber | **Tobias Heinrich** |
| Preis | kostenlos |
| Adresse im Store | https://apps.microsoft.com/detail/9PL4D25N00XD |
| Store-ID | `9PL4D25N00XD` |
| Größe | rund 70 MB zum Herunterladen, rund 150 MB installiert |

## Voraussetzungen

- **Windows 11** oder **Windows 10** ab Version 1809, in der 64-Bit-Ausführung.
- Eine Internetverbindung und ein nutzbarer **Microsoft Store**.
- **Kein** Administratorkonto: Die App wird nur für Ihr Benutzerkonto installiert.
- Für kostenlose Apps verlangt der Store in der Regel keine Anmeldung mit einem Microsoft-Konto. Erscheint dennoch ein Anmeldefenster, können Sie sich anmelden oder das Fenster schließen und es erneut versuchen.
- Nur für den Import von Word-, Excel- und PowerPoint-Dateien: ein installiertes **Microsoft Office**. Alles andere funktioniert ohne.

## Weg 1 – über den Link (empfohlen)

1. Öffnen Sie im Browser die Adresse https://apps.microsoft.com/detail/9PL4D25N00XD.
2. Prüfen Sie, dass die Seite **BelegTool** vom Herausgeber **Tobias Heinrich** zeigt.
3. Klicken Sie auf die Schaltfläche zum Installieren. Je nach Browser und Windows-Version heißt sie **Herunterladen**, **Installieren** oder **Im Store anzeigen**. Danach geschieht eines von beidem:
   - Der **Microsoft Store** öffnet sich mit der Seite von BelegTool. Klicken Sie dort noch einmal auf **Herunterladen** bzw. **Installieren**.
   - Oder der Browser lädt eine kleine Installationsdatei herunter. Öffnen Sie diese Datei; sie holt BelegTool aus dem Store und installiert es.
4. Warten Sie, bis die Installation abgeschlossen ist, und klicken Sie auf **Öffnen**.

## Weg 2 – im Microsoft Store suchen

1. Öffnen Sie das Startmenü und starten Sie **Microsoft Store**.
2. Geben Sie oben im Suchfeld `BelegTool` ein und drücken Sie die Eingabetaste.
3. Wählen Sie den Eintrag **BelegTool**. Achten Sie auf den Herausgeber **Tobias Heinrich**.
4. Klicken Sie auf **Herunterladen** bzw. **Installieren**.
5. Klicken Sie nach Abschluss auf **Öffnen**.

## Weg 3 – für Administratoren: Kommandozeile

Mit dem Windows-Paketmanager lässt sich BelegTool ohne Store-Oberfläche installieren:

```
winget install --id 9PL4D25N00XD --source msstore
```

Beim ersten Aufruf fragt `winget` nach der Zustimmung zu den Bedingungen des Stores.

## Der erste Start

- Starten Sie BelegTool über das **Startmenü**. Es erscheint ein leeres „Dokument 1“ mit der Symbolleiste oben, dem Baum links und der Vorschau rechts.
- Ihre **Version** steht in der Titelleiste des Fensters, zum Beispiel „DigitalerUnterlagenOrdner 3.11.4“.
- Dateien mit der Endung **.belegtool** sind jetzt mit BelegTool verknüpft: Ein Doppelklick im Explorer öffnet sie direkt.
- Die Sprache der Oberfläche stellen Sie über **🌐** in der Symbolleiste um; **❓ Hilfe** öffnet eine Kurzanleitung.
- Mit **📥 Importieren** holen Sie die ersten Dateien in das Dokument, mit **💾 Speichern** legen Sie es als `.belegtool` ab.

## Wenn etwas nicht klappt

| Beobachtung | Was Sie tun können |
|---|---|
| Die Store-Seite öffnet sich nicht oder meldet, die App sei nicht verfügbar | Auf Firmen-PCs ist der Store oft gesperrt. Fragen Sie Ihre Administration – sie kann Weg 3 nutzen oder die ZIP-Ausgabe von der Projektseite bereitstellen. |
| Statt „Installieren“ steht dort **Öffnen** | BelegTool ist bereits installiert. |
| Die Installation bricht ab, früher war eine Testversion installiert | Deinstallieren Sie die alte Version zuerst (Einstellungen → Apps → Installierte Apps) und installieren Sie erneut. |
| Meldung „Microsoft Edge WebView2 Runtime fehlt“ oder ein leeres Fenster | BelegTool braucht die WebView2-Runtime von Microsoft. Windows 11 bringt sie mit; unter Windows 10 kann sie fehlen. Installieren Sie sie von https://developer.microsoft.com/microsoft-edge/webview2/ und starten Sie BelegTool neu. |
| Word-, Excel- oder PowerPoint-Dateien lassen sich nicht importieren | Dafür muss Microsoft Office auf dem PC installiert sein. |
| Terminalserver oder Windows Server | Dort ist der Store meist nicht nutzbar. Die Administration installiert BelegTool maschinenweit auf ein lokales Laufwerk; die Beschreibung steht auf der Projektseite unter `packaging/README.md`. |

## Aktualisieren

Der Store aktualisiert BelegTool von selbst. Wenn Sie nicht warten möchten: Microsoft Store öffnen → **Downloads** (in älteren Store-Versionen **Bibliothek**) → **Updates abrufen**.

## Deinstallieren

Startmenü → Rechtsklick auf **BelegTool** → **Deinstallieren**. Ihre `.belegtool`-Dateien bleiben erhalten. Jede davon ist ein gewöhnliches PDF mit zusätzlicher Ordnerstruktur und lässt sich über „Öffnen mit“ auch in jedem PDF-Betrachter ansehen.

## Datenschutz

BelegTool arbeitet vollständig auf Ihrem PC: keine Cloud, kein Benutzerkonto, keine Übermittlung von Nutzungsdaten. Die Datenschutzerklärung steht unter https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner/blob/master/PRIVACY.md.

## Projektseite und Rückmeldungen

Quelltext, weitere Ausgaben und die Möglichkeit, Fehler zu melden: https://github.com/tobiasheinrichfaska/DigitalerUnterlagenOrdner
