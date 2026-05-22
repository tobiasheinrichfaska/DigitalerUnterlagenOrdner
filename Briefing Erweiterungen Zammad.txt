# Technical Briefing: Modulerweiterung für Dokumenten-Tool (Zammad-Schnittstelle)

## 1. Core-Konzept & UI-Struktur
Das bestehende hauseigene Dokumenten-Tool verwaltet PDF-Inhalte über eine **dynamische Baumstruktur (linke Seitenleiste)**. Diese Struktur wird auf oberster Ebene in zwei isolierte Hauptbereiche aufgeteilt:

*   **[Knoten: "PDF"]**
    *   Beinhaltet die gewohnte, flexible PDF- und Ordnerstruktur des Tools.
    *   Erlaubt das Umsortieren, Splitten (z. B. Seite 1–4, Seite 5) und Zusammenfügen von Dokumenten.
*   **[Knoten: "Zammad"]**
    *   Visualisiert angebundene Support-Tickets und deren Kommunikationshistorie (Artikel) über die Zammad REST-API.
    *   Dieser Bereich operiert rein lesend (Read-Only).

---

## 2. Technische & Funktionale Anforderungen

### 2.1 Artikel-Transformation und Anhang-Handling (Zammad-Baum)
*   **HTML-to-PDF Transformation:** Jeder Zammad-Artikel (E-Mails, Telefonnotizen, Interne Chats) muss für die Anzeige im Tool in ein standardisiertes, lesbares PDF-Format transformiert werden. 
*   **Anhang-Extraktion & Konvertierung:** Im Artikel enthaltene Dateianhänge werden isoliert extrahiert und als untergeordnete Elemente gelistet. Nicht-PDF-Anhänge (z. B. Bilder, Office-Dokumente) werden im Hintergrund automatisch parallel in PDF-Dateien konvertiert.
*   **Kopieren statt Verschieben (Revisionssicherheit):** Da originale Zammad-Artikel unveränderlich sind, können Elemente aus dem Zammad-Baum **niemals verschoben**, sondern **ausschließlich kopiert** werden. 
*   **Verhalten im PDF-Zweig:** Beim Kopieren in den Hauptknoten "PDF" entsteht ein eigenständiges PDF-Element, das sich im Baukastensystem frei splitten, bewegen und mergen lässt. Das Element behält im Hintergrund eine permanente Referenz-ID (`zammad_ticket_id` / `zammad_article_id`).

### 2.2 Synchronisation & Lifecycle-Management (Live-Check)
*   **Echtzeit-Update beim Öffnen:** Sobald ein Benutzer ein referenziertes Dokument im PDF- oder Zammad-Baum öffnet, erfolgt ein asynchroner API-Call im Hintergrund. Das System prüft auf neue Artikel im Ticket (Delta-Prüfung) und fügt diese bei Bedarf sofort live als transformierte PDFs im Baum hinzu.
*   **Lösch-Workflow bei Ticket-Schließung ("Permdelete"):** Erkennt das Tool beim Live-Check, dass das verknüpfte Zammad-Ticket geschlossen wurde (`status: closed`), wird dem Nutzer ein Prompt (Dialogfenster) angezeigt: 
    *   *Frage:* "Das verknüpfte Ticket wurde geschlossen. Möchten Sie dieses Ticket in Zammad zum Löschen vormerken?"
    *   *Aktion:* Bei Bestätigung setzt das Tool über die API das Tag `Permdelete` am Ticket. Die endgültige Bereinigung erfolgt über den Zammad-Scheduler.

### 2.3 Outbound-Kommunikation (E-Mail-Versand aus dem Tool)
*   **Artikel-Erstellung:** Benutzer können direkt innerhalb des Tools einen neuen Artikel zu einem bestehenden Ticket verfassen.
*   **API-Trigger:** Dieser Artikel wird über die API an das Ticketsystem übergeben. Er muss so deklariert werden (Sichtbarkeit: `public`), dass Zammad getriggert wird, den nativen E-Mail-Versand automatisch an den Kunden auszulösen.

---

## 3. Technische Prüfaufträge für die Entwicklung
1.  **Asynchrones API-Polling:** Die Live-Aktualisierung beim Öffnen einer Datei muss performant im Hintergrund laufen, damit das UI-Rendering nicht blockiert wird.
2.  **Konverter-Bibliotheken:** Evaluierung performanter Server-Bibliotheken zur On-the-fly-Konvertierung von HTML/Office-Formaten in saubere PDFs.
3.  **Zammad API-Berechtigungen:** Sicherstellen, dass das verwendete Service-Token über ausreichende Schreibrechte verfügt, um neue Artikel zu erstellen und Tags zu setzen (`tags.add`).
