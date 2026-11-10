"""English/Italian presentation catalog. SDK commands, program files and logs stay canonical."""

import re
from string import Formatter

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QPushButton

LANGUAGES = {"en": "English", "it": "Italiano"}
_language = "en"

ITALIAN = {
    "Tello Flight · Local flight console": "Tello Flight · Console di volo locale",
    "Session settings": "Impostazioni sessione",
    "Connect": "Connetti",
    "Disconnect": "Disconnetti",
    "SIMULATOR": "SIMULATORE",
    "LIVE TELLO": "TELLO REALE",
    "Fly": "Volo",
    "Program with cards": "Programma con le schede",
    "Take off": "Decolla",
    "Land": "Atterra",
    "Hover · Space": "Staziona · Spazio",
    "Camera on": "Attiva video",
    "Camera off": "Disattiva video",
    "Grid": "Griglia",
    "Snapshot": "Fotogramma",
    "Motor cut": "Arresto motori",
    "Flight log": "Registro di volo",
    "Save diagnostics": "Salva diagnostica",
    "Starting simulator…": "Avvio del simulatore…",
    "LOCAL FLIGHT CONSOLE": "CONSOLE DI VOLO LOCALE",
    "SIMULATOR CONNECTED": "SIMULATORE CONNESSO",
    "TELLO CONNECTED": "TELLO CONNESSO",
    "TELEMETRY STALE": "TELEMETRIA NON AGGIORNATA",
    "DISCONNECTED": "DISCONNESSO",
    "CONNECTING": "CONNESSIONE IN CORSO",
    "READY": "PRONTO",
    "UNCERTAIN": "STATO INCERTO",
    "GROUNDED": "A TERRA",
    "TAKING OFF": "DECOLLO",
    "AIRBORNE": "IN VOLO",
    "LANDING": "ATTERRAGGIO",
    "UNKNOWN": "SCONOSCIUTO",
    "BAT": "BAT",
    "TEMP": "TEMP",
    "DATA": "DATI",
    "SIMULATED CAMERA  /  NO DRONE CONNECTED": "VIDEO SIMULATO  /  NESSUN DRONE CONNESSO",
    "TELLO CAMERA": "VIDEO TELLO",
    "SIMULATION": "SIMULAZIONE",
    "LIVE": "DIRETTA",
    "NO VIDEO": "NESSUN VIDEO",
    "Camera unavailable": "Video non disponibile",
    "Camera is off": "Video disattivato",
    "Enable video while grounded to start the preview": "Attiva il video a terra per avviare l’anteprima",
    "HEIGHT": "QUOTA",
    "SPEED": "VELOCITÀ",
    "THROTTLE / YAW": "QUOTA / ROTAZIONE",
    "PITCH / ROLL": "AVANZAMENTO / SPOSTAMENTO",
    "MODE 2     •     HOLD TO MOVE     •     RELEASE TO HOVER": "MODO 2     •     TIENI PREMUTO PER MUOVERTI     •     RILASCIA PER STAZIONARE",
    "Hold and drag to move. Release to center.": "Tieni premuto e trascina per muoverti. Rilascia per centrare.",
    "Flight session": "Sessione di volo",
    "Choose your flight session": "Scegli la sessione di volo",
    "Simulator — no drone required": "Simulatore — non serve un drone",
    "Live Tello — connected over Wi-Fi": "Tello reale — connesso tramite Wi-Fi",
    "Session": "Sessione",
    "Drone IPv4 address": "Indirizzo IPv4 del drone",
    "Local bind IPv4": "IPv4 dell’interfaccia locale",
    "Connect your computer to TELLO Wi-Fi before choosing live mode.\nLeave local bind as 0.0.0.0 unless selecting a specific adapter.\nLive hardware behavior has not yet been validated.": "Collega il computer al Wi-Fi TELLO prima di scegliere il drone reale.\nLascia 0.0.0.0 come indirizzo locale, salvo la scelta di un’interfaccia specifica.\nIl funzionamento con un drone reale non è ancora stato verificato.",
    "Invalid address": "Indirizzo non valido",
    "Enter valid IPv4 addresses.": "Inserisci indirizzi IPv4 validi.",
    "Flight status is not grounded": "Il drone non risulta a terra",
    "Land first. If the link is lost, inspect the drone.\n\nDisconnect only after physically confirming the motors are stopped.": "Atterra prima. Se il collegamento è perso, controlla il drone.\n\nDisconnetti solo dopo aver verificato di persona che i motori siano fermi.",
    "Land first": "Atterra prima",
    "Session settings are available while grounded.": "Le impostazioni della sessione sono disponibili a terra.",
    "Clear area, propeller guards fitted, and drone in sight?": "Area libera, protezioni delle eliche montate e drone a vista?",
    "Run flight program": "Esegui il programma di volo",
    "Run {count} cards on the real Tello?\nCheck the whole route is clear and keep the drone in sight.\nStop & land discards remaining cards. Flip cards need extra clearance.": "Eseguire {count} schede sul Tello reale?\nVerifica che tutto il percorso sia libero e mantieni il drone a vista.\nFerma e atterra elimina le schede rimanenti. Le capriole richiedono più spazio libero.",
    "Program cannot run": "Impossibile eseguire il programma",
    "Immediate motor cut": "Arresto immediato dei motori",
    "This stops the motors immediately. An airborne drone will fall.\nSend motor cut?": "I motori si fermeranno immediatamente. Se il drone è in volo, cadrà.\nInviare il comando di arresto motori?",
    "Simulated camera": "Video simulato",
    "The simulator uses a generated indoor scene.": "Il simulatore utilizza una scena interna generata.",
    "No live frame": "Nessun fotogramma disponibile",
    "Start the live camera before saving a snapshot.": "Attiva il video prima di salvare un fotogramma.",
    "Save camera snapshot": "Salva fotogramma",
    "Save failed": "Salvataggio non riuscito",
    "Could not save the image.": "Impossibile salvare l’immagine.",
    "Flight log & diagnostics": "Registro di volo e diagnostica",
    "Persistent logs: {path}": "Registri salvati: {path}",
    "Simulate signal loss": "Simula perdita del segnale",
    "Save diagnostic bundle": "Salva pacchetto diagnostico",
    "Land before exporting diagnostics. Logs continue automatically.": "Atterra prima di esportare la diagnostica. I registri continuano a essere salvati automaticamente.",
    "Diagnostics saved": "Diagnostica salvata",
    "Bundle includes logs, command timing, telemetry, connection IPs and system versions.\nNo camera images are included. Review it before sharing.": "Il pacchetto contiene registri, tempi dei comandi, telemetria, indirizzi IP e versioni del sistema.\nNon contiene immagini della videocamera. Controllalo prima di condividerlo.",
    "Export failed": "Esportazione non riuscita",
    "Video error: {error}": "Errore video: {error}",
    "COMMAND CARDS": "SCHEDE COMANDO",
    "Click a command to add a card.": "Clicca un comando per aggiungere una scheda.",
    "Your flight": "Il tuo volo",
    "{count} cards": "{count} schede",
    "Read from top to bottom. Drag cards to change the order.": "Leggi dall’alto verso il basso. Trascina le schede per riordinarle.",
    "Move": "Sposta",
    "Duplicate": "Duplica",
    "Remove": "Rimuovi",
    "Run from top": "Esegui dall’inizio",
    "Stop & land": "Ferma e atterra",
    "CARD SETTINGS": "IMPOSTAZIONI SCHEDA",
    "Select a card": "Seleziona una scheda",
    "Select a card to adjust its parameter.": "Seleziona una scheda per modificarne il parametro.",
    "Choose a card to adjust its parameter.": "Scegli una scheda per modificarne il parametro.",
    "Relative distance, not an absolute altitude.\n": "Spostamento relativo, non quota assoluta.\n",
    "Allowed: {minimum}–{maximum} {unit}": "Valori ammessi: {minimum}–{maximum} {unit}",
    "No adjustable parameter.": "Nessun parametro modificabile.",
    " Flips need at least 50% battery.": " Per le capriole serve almeno il 50% di batteria.",
    "SIMULATOR POSITION\nX {x} m   Y {y} m\nHeading {yaw}°": "POSIZIONE NEL SIMULATORE\nX {x} m   Y {y} m\nOrientamento {yaw}°",
    "Simulator position\nX 0.0 m   Y 0.0 m\nHeading 0°": "Posizione nel simulatore\nX 0,0 m   Y 0,0 m\nOrientamento 0°",
    "Load example": "Carica esempio",
    "Open program…": "Apri programma…",
    "Save program…": "Salva programma…",
    "Clear all": "Svuota tutto",
    "Program full": "Programma completo",
    "A program can contain at most 100 cards.": "Un programma può contenere al massimo 100 schede.",
    "Running…": "In esecuzione…",
    "Finished": "Completata",
    "{parameter} · editable": "{parameter} · modificabile",
    "Flight command": "Comando di volo",
    "Fly up": "Sali",
    "Fly down": "Scendi",
    "Fly forward": "Avanti",
    "Fly backward": "Indietro",
    "Fly left": "A sinistra",
    "Fly right": "A destra",
    "Turn clockwise": "Ruota in senso orario",
    "Turn counterclockwise": "Ruota in senso antiorario",
    "Flip forward": "Capriola in avanti",
    "Flip backward": "Capriola indietro",
    "Flip left": "Capriola a sinistra",
    "Flip right": "Capriola a destra",
    "Set speed": "Imposta velocità",
    "Wait / hover": "Attendi / staziona",
    "Height change": "Variazione di quota",
    "Distance": "Distanza",
    "Angle": "Angolo",
    "Speed": "Velocità",
    "Duration": "Durata",
    "Ready to run. Each card finishes before the next starts.": "Pronto. Ogni scheda termina prima dell’inizio della successiva.",
    "Card {index}/{total} · {detail}": "Scheda {index}/{total} · {detail}",
    "Connect to the simulator or drone to run.": "Connetti il simulatore o il drone per eseguire.",
    "Open program": "Apri programma",
    "Save program": "Salva programma",
    "Tello program (*.json)": "Programma Tello (*.json)",
    "Could not open program": "Impossibile aprire il programma",
    "Could not save program": "Impossibile salvare il programma",
    "Unknown command card": "Scheda comando sconosciuta",
    "{title} has no parameter": "{title} non ha parametri",
    "{title}: enter {minimum}–{maximum} {unit}": "{title}: inserisci {minimum}–{maximum} {unit}",
    "A program can contain at most 100 cards": "Un programma può contenere al massimo 100 schede",
    "Programs must contain command cards": "Il programma deve contenere schede comando",
    "Start with Take off and finish with Land": "Inizia con Decolla e termina con Atterra",
    "Take off belongs first and Land belongs last": "Decolla deve essere la prima scheda e Atterra l’ultima",
    "Program file is too large": "Il file del programma è troppo grande",
    "Unsupported program file": "Formato del programma non supportato",
    "Invalid program file": "File del programma non valido",
    "Choose simulator or connect to your Tello.": "Scegli il simulatore o connetti il tuo Tello.",
    "Command queue full; request rejected": "Coda dei comandi piena; richiesta rifiutata",
    "Command queue full; try again": "Coda dei comandi piena; riprova",
    "A program is already running": "Un programma è già in esecuzione",
    "Manual command rejected while a program is running": "Comando manuale rifiutato durante l’esecuzione del programma",
    "Connect and land before running a program": "Connetti il drone e atterra prima di eseguire un programma",
    "Need fresh telemetry and at least 25% battery": "Servono telemetria aggiornata e almeno il 25% di batteria",
    "Keep the application in focus before running": "Mantieni attiva la finestra prima di eseguire",
    "Flip cards require at least 50% battery": "Le schede capriola richiedono almeno il 50% di batteria",
    "Program started — {count} cards": "Programma avviato — {count} schede",
    "Card {index}/{total}: {label}": "Scheda {index}/{total}: {label}",
    "Program complete — all cards finished": "Programma completato — tutte le schede sono terminate",
    "Low battery: program aborted; landing requested": "Batteria scarica: programma interrotto; atterraggio richiesto",
    "Low battery: program aborted; landing requested once": "Batteria scarica: programma interrotto; atterraggio richiesto una volta",
    "Landing not confirmed by telemetry; program aborted": "Atterraggio non confermato dalla telemetria; programma interrotto",
    "Battery below 50%: flip cancelled; program aborted": "Batteria sotto il 50%: capriola annullata; programma interrotto",
    "Drone is not airborne: program aborted": "Il drone non è in volo: programma interrotto",
    "Program stopped — landing requested": "Programma fermato — atterraggio richiesto",
    "Program cancelled by motor cut": "Programma annullato dall’arresto motori",
    "Program cancelled: session closed": "Programma annullato: sessione chiusa",
    "Card rejected ({command}: {response}); program aborted": "Scheda rifiutata ({command}: {response}); programma interrotto",
    "SDK handshake rejected; reconnect": "Inizializzazione SDK rifiutata; riconnetti",
    "Flight command rejected; verify drone before reconnecting": "Comando di volo rifiutato; controlla il drone prima di riconnettere",
    "Simulator: signal loss injected. Reconnect to restore.": "Simulatore: perdita del segnale simulata. Riconnetti per ripristinare.",
    "EMERGENCY motor cut sent; inspect drone and reconnect": "Arresto motori di EMERGENZA inviato; controlla il drone e riconnetti",
    "Control/telemetry lost: landing requested once; verify drone physically": "Controllo/telemetria persi: atterraggio richiesto una volta; controlla il drone di persona",
    "Priority landing sent; acknowledgement cannot be correlated. Verify drone.": "Atterraggio prioritario inviato; conferma non associabile al comando. Controlla il drone.",
    "Landing requested; waiting for grounded telemetry": "Atterraggio richiesto; attendo il ritorno a terra",
    "Landing observed; restoring command connection": "Ritorno a terra rilevato; ripristino la connessione dei comandi",
    "Landing not confirmed; inspect drone and reconnect": "Atterraggio non confermato; controlla il drone e riconnetti",
    "Battery query skipped during flight; use telemetry": "Richiesta batteria saltata durante il volo; usa la telemetria",
    "Takeoff rejected: need grounded state, fresh telemetry, and battery >= 25%": "Decollo rifiutato: il drone deve essere a terra, con telemetria aggiornata e batteria almeno al 25%",
    "Change video streaming while grounded": "Modifica il video quando il drone è a terra",
    "{command} timed out; outcome unknown. Reconnect before further flight.": "Tempo scaduto per {command}; esito sconosciuto. Riconnetti prima di proseguire il volo.",
    "Connection error: {error}": "Errore di connessione: {error}",
    "Sent: {command}": "Inviato: {command}",
    "OK": "OK",
    "Cancel": "Annulla",
    "Yes": "Sì",
    "No": "No",
    "Close": "Chiudi",
    "&Yes": "&Sì",
    "&No": "&No",
    "&Cancel": "&Annulla",
    "Open": "Apri",
    "Save": "Salva",
    "&Open": "&Apri",
    "&Save": "&Salva",
    "File name:": "Nome file:",
    "Files of type:": "Tipo di file:",
    "Look in:": "Cerca in:",
    "Save in:": "Salva in:",
    "All Files (*)": "Tutti i file (*)",
}


def language():
    return _language


def set_language(code):
    global _language
    if code not in LANGUAGES:
        raise ValueError("Unsupported language")
    _language = code


def preferred_language(settings, system_name=None):
    saved = settings.value("language", "")
    if isinstance(saved, str) and saved in LANGUAGES:
        return saved
    return "it" if (system_name or QLocale.system().name()).lower().startswith("it") else "en"


def number(value, decimals=1):
    return QLocale("it_IT" if _language == "it" else "en_US").toString(float(value), "f", decimals)


def tr(source, **values):
    translated = ITALIAN.get(source, source) if _language == "it" else source
    return translated.format(**values) if values else translated


def _pattern(template):
    parts = []
    for literal, field, _, _ in Formatter().parse(template):
        parts.append(re.escape(literal))
        if field:
            value_pattern = (
                r"\d+"
                if field in ("index", "total", "count", "minimum", "maximum")
                else r"-?\d+(?:[.,]\d+)?"
                if field in ("x", "y", "yaw")
                else r".+?"
            )
            parts.append(f"(?P<{field}>{value_pattern})")
    return re.compile("".join(parts), re.DOTALL)


_TEMPLATES = sorted(
    [(source, _pattern(source)) for source in ITALIAN if "{" in source],
    key=lambda entry: sum(len(literal) for literal, _, _, _ in Formatter().parse(entry[0])),
    reverse=True,
)


def message(source):
    """Localize canonical UI/status text without modifying core events or SDK payloads."""
    if source == "1 cards":
        return "1 scheda" if _language == "it" else "1 card"
    if _language == "en" or not source:
        return source
    if source in ITALIAN:
        return ITALIAN[source]
    # Painter labels, command palettes and timestamped log lines retain their prefixes.
    prefix = re.fullmatch(r"(\d{2}:\d{2}:\d{2}  |[^\w\s]+\s+)(.+)", source, re.DOTALL)
    if prefix:
        return prefix[1] + message(prefix[2])
    for template, pattern in _TEMPLATES:
        match = pattern.fullmatch(source)
        if match:
            values = {
                key: value if key in ("command", "response", "error", "path") else message(value)
                for key, value in match.groupdict().items()
            }
            return tr(template, **values)
    if " · " in source:
        return " · ".join(message(part) for part in source.split(" · "))
    # Parameter hints are composed from independently translated sentences.
    for lead in ("Relative distance, not an absolute altitude.\n", "No adjustable parameter."):
        if source.startswith(lead):
            return tr(lead) + message(source[len(lead) :])
    if source.startswith("LOCAL FLIGHT CONSOLE   /   "):
        return tr("LOCAL FLIGHT CONSOLE") + source[len("LOCAL FLIGHT CONSOLE") :]
    status = re.fullmatch(r"(BAT|TEMP|DATA)(  .+)", source)
    if status:
        return tr(status[1]) + status[2]
    return source


class TextLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setText(text)

    def setText(self, text):
        self.source_text = text
        super().setText(message(text))

    def retranslate(self):
        super().setText(message(self.source_text))


class TextButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setText(text)

    def setText(self, text):
        self.source_text = text
        super().setText(message(text))

    def retranslate(self):
        super().setText(message(self.source_text))


def retranslate_widgets(root):
    for kind in (TextLabel, TextButton):
        for widget in root.findChildren(kind):
            widget.retranslate()


class MessageBox(QMessageBox):
    @staticmethod
    def information(parent, title, text, *args, **kwargs):
        return QMessageBox.information(parent, message(title), message(text), *args, **kwargs)

    @staticmethod
    def warning(parent, title, text, *args, **kwargs):
        return QMessageBox.warning(parent, message(title), message(text), *args, **kwargs)

    @staticmethod
    def question(parent, title, text, *args, **kwargs):
        return QMessageBox.question(parent, message(title), message(text), *args, **kwargs)


class FileDialog(QFileDialog):
    @staticmethod
    def getOpenFileName(parent, caption="", directory="", file_filter="", *args, **kwargs):
        return QFileDialog.getOpenFileName(
            parent, message(caption), directory, message(file_filter), *args, **kwargs
        )

    @staticmethod
    def getSaveFileName(parent, caption="", directory="", file_filter="", *args, **kwargs):
        return QFileDialog.getSaveFileName(
            parent, message(caption), directory, message(file_filter), *args, **kwargs
        )


class ButtonTranslator(QTranslator):
    def isEmpty(self):
        return False

    def translate(self, context, sourceText, disambiguation=None, n=-1):
        return ITALIAN.get(sourceText, "") if _language == "it" else ""
