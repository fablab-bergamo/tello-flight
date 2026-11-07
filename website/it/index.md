# Tello Flight — guida in italiano

Tello Flight è un’applicazione locale per Windows e Linux per controllare un Ryze Tello e imparare
la programmazione sequenziale con le schede comando. Include un simulatore: non serve un drone per iniziare.

[Scarica la beta](https://github.com/fablab-bergamo/tello-flight/releases/tag/v0.1.0-beta.3) ·
[English documentation](../index.md)

## Installazione e lingua

Su Windows scarica il file ZIP, estrailo completamente e avvia `TelloFlight/TelloFlight.exe`.
Su Linux estrai l’archivio tar.gz e avvia `./TelloFlight/TelloFlight`. Il riferimento iniziale è Ubuntu 24.04 x86-64.
Mantieni l’eseguibile e la cartella `_internal` insieme. Non è necessario installare Python.

Seleziona **Italiano** nella barra superiore. La scelta viene ricordata. Al primo avvio, un sistema italiano
usa l’italiano; negli altri casi viene usato l’inglese. Puoi anche avviare l’applicazione con `--language it`.
Puoi tornare a **English** senza perdere le schede o modificarne i parametri.

## Primo programma con le schede

1. L’applicazione si avvia nel simulatore. Apri **Programma con le schede**.
2. Clicca un comando a sinistra per aggiungere una scheda.
3. Seleziona la scheda e modifica il valore in **Impostazioni scheda**, a destra.
4. Trascina le schede per cambiarne l’ordine, oppure usa **Sposta** con le frecce.
5. Inizia con **Decolla**, termina con **Atterra** e inserisci gli altri comandi tra queste due schede.
6. Premi **Esegui dall’inizio**. La scheda attiva viene evidenziata; quelle completate ricevono un segno di spunta.

Ogni scheda termina prima che inizi la successiva. La selezione di una scheda non cambia il punto di partenza:
l’esecuzione comincia sempre dalla prima. **Duplica** e **Rimuovi** permettono di modificare la sequenza.

### Comandi e parametri

| Scheda | Parametro |
| --- | --- |
| Decolla / Atterra | Nessuno; il decollo utilizza il comportamento automatico del drone |
| Sali / Scendi | Variazione relativa di quota, da 20 a 500 cm |
| Avanti / Indietro / A sinistra / A destra | Distanza relativa, da 20 a 500 cm |
| Ruota in senso orario / antiorario | Angolo, da 1 a 360 gradi |
| Capriola in avanti / indietro / a sinistra / a destra | Direzione scelta dalla scheda; serve almeno il 50% di batteria |
| Imposta velocità | Da 10 a 100 cm/s per i movimenti a distanza |
| Attendi / staziona | Durata, da 1 a 60 secondi |

**Sali 50 cm** significa salire di altri 50 cm, non raggiungere una quota assoluta di 50 cm.
Dopo una rotazione, Avanti segue il nuovo orientamento del drone.

Prova questo programma nel simulatore:

**Decolla → Sali 50 cm → Avanti 100 cm → Ruota in senso orario 90° → Attendi 2 s → Atterra**

Cambia la distanza da 100 a 200 cm e osserva la posizione finale nel simulatore. Il simulatore aggiorna
posizione, quota e orientamento, ma non riproduce la fisica del volo né gli ostacoli.

### Salvare e riaprire una lezione

Usa **Salva programma…** e **Apri programma…**. Puoi salvare anche una bozza incompleta.
I file JSON sono gli stessi in inglese e in italiano: cambiare lingua non cambia i comandi del drone.
Nel repository trovi gli [esempi](https://github.com/fablab-bergamo/tello-flight/tree/main/examples)
di primo volo e percorso quadrato.

## Fermare una sequenza

**Ferma e atterra**, il pulsante **Atterra** o la barra spaziatrice durante un programma eliminano le
schede rimanenti e richiedono l’atterraggio. Gli errori e i timeout interrompono la sequenza; i movimenti
con esito incerto non vengono ripetuti automaticamente.

La perdita del controllo o della telemetria e la batteria sotto il 15% durante un programma richiedono
l’atterraggio una volta. Una connessione Wi-Fi interrotta può impedire la consegna del comando.
**Arresto motori** è un’azione distinta, con conferma: ferma immediatamente i motori e un drone in volo cadrà.

## Controllo manuale

Nella scheda **Volo**, usa W/S per salire e scendere, A/D per ruotare, e le frecce per spostarti.
Puoi anche trascinare i joystick. Rilascia per stazionare. Durante un programma i controlli manuali sono disabilitati.

## Diagnostica e segnalazioni

Apri **Registro di volo** per leggere gli eventi. **Salva diagnostica** esporta un archivio ZIP con registri,
parametri delle schede, stato del programma, versioni del sistema e dati di connessione. Non include immagini
o video. Controlla il contenuto prima di condividerlo. I registri tecnici mantengono identificatori stabili
per facilitare il confronto e l’analisi degli errori in entrambe le lingue.

Per segnalare un problema, indica cosa ti aspettavi, cosa è successo, la versione, il sistema operativo e
se stavi usando il simulatore o un drone reale. Allega il pacchetto diagnostico dopo averlo controllato.

**La verifica su un drone reale è ancora da completare.** Prima di un volo reale verifica la diagnostica
in sola lettura e il video a terra. Collega il computer al Wi-Fi TELLO e scegli il drone reale nelle
**Impostazioni sessione**. Mantieni il drone a vista e verifica che tutto il percorso sia libero.
