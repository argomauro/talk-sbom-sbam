# VEX Analysis Engine — Bedrock Edition

Il motore di analisi VEX è uno strumento language-agnostic che determina la
**reachability** reale delle vulnerabilità (CVE) nel codice sorgente, combinando
chiamate a **AWS Bedrock (Claude)** con uno scanner locale a regex.

Gli script che implementano il motore risiedono nel progetto GitLab condiviso
`root/vex-engine` e vengono eseguiti automaticamente dalla pipeline CI di ogni
progetto applicativo — senza nessuna azione manuale da parte dello sviluppatore.

---

## I 3 componenti del progetto `vex-engine`

| File | Ruolo |
|---|---|
| `generate_vex.py` | Entry point: carica il VEX, decide quali CVE analizzare, coordina le 3 fasi, crea le Issue GitLab |
| `llm_analyzer.py` | Motore delle 3 fasi: Strategist, Scanner, Auditor |
| `ci-template.yml` | Job CI condiviso: incluso via `include:` da tutti i progetti applicativi |
| `requirements.txt` | Dipendenze Python: `boto3`, `requests` |

---

## Il processo in 3 fasi

Il motore opera su una singola CVE alla volta, eseguendo tre fasi in sequenza.

### Fase 1 — Strategist (Bedrock)

**Input**: descrizione testuale della CVE + nome del pacchetto vulnerabile + linguaggio del progetto.

**Cosa fa**: invia un prompt strutturato a Claude su AWS Bedrock chiedendo di
estrarre dalla descrizione le informazioni necessarie alla scansione:

```json
{
  "search_patterns": ["load", "from_string"],
  "import_aliases": ["yaml"],
  "attack_vector": "Untrusted input passed to yaml.load() triggers arbitrary Python object deserialization"
}
```

**Perché serve un LLM reale**: le CVE descrivono vulnerabilità in linguaggio
naturale, spesso su librerie di nicchia con nomi di funzioni non predicibili.
Un approccio a keyword hardcoded (`load`, `open`, `parse`...) copre solo i casi
più comuni. Claude interpreta il significato della descrizione e genera pattern
specifici per quella CVE — senza richiedere nessuna configurazione manuale.

Il risultato viene **cachato in memoria** per evitare chiamate duplicate sulla
stessa CVE nella stessa run di pipeline.

---

### Fase 2 — Scanner (locale, nessuna chiamata di rete)

**Input**: `search_patterns` e `import_aliases` dalla Fase 1.

**Cosa fa**: scansiona l'intero codice sorgente del progetto applicativo
con regex e due gate di filtraggio:

1. **Gate import**: considera solo i file che importano il pacchetto vulnerabile
   (es. `import yaml` per PyYAML). Evita falsi positivi su funzioni omonime di
   altre librerie.
2. **Gate pattern**: cerca le `search_patterns` con regex word-boundary
   (`\b pattern \b`), ignorando righe commentate o vuote.
3. Per ogni match estrae una **finestra di ±30 righe** di contesto attorno alla riga trovata.

**Directory ignorate**: `.git`, `venv`, `node_modules`, `__pycache__`, `target`.
Il motore è installato in `/opt/vex-engine` (separato dal progetto) e non si auto-analizza.

---

### Fase 3 — Auditor (Bedrock)

**Input**: CVE description, attack vector (da Fase 1), code snippets (da Fase 2, max 5).

**Cosa fa**: invia i frammenti di codice a Claude chiedendo di determinare se la
vulnerabilità è effettivamente exploitabile analizzando il **data flow**:

- L'input nella funzione vulnerabile viene da una richiesta HTTP / form / upload? → `affected`
- Il valore è hardcoded o proviene da un file di configurazione statico? → `not_affected`
- La funzione è commentata o definita ma mai chiamata? → `not_affected`
- Esiste una safe alternative (es. `yaml.safe_load` invece di `yaml.load`)? → `not_affected`

**Output strutturato**:
```json
{
  "verdict": "not_affected",
  "confidence": 0.94,
  "reasoning": "The yaml.load() call at line 23 receives input from a hardcoded config file path. No user-controlled data flow detected.",
  "evidence_file": "./cvedemo/vuln_demo.py",
  "evidence_line": 23
}
```

---

## Delta Analysis — ottimizzazione dei costi

Il motore non ri-analizza le CVE che hanno già un verdetto AI definitivo nel
`vex.json`. Una CVE viene marcata come "già analizzata" quando il campo
`analysis.detail` contiene la firma `"analyzed by Antigravity AI"` e lo stato
è uno tra `not_affected`, `exploitable`, `affected`.

In un progetto maturo, la pipeline analizzerà solo le **CVE nuove** introdotte
dagli aggiornamenti delle librerie — tipicamente 5-15 per push, con un costo
Bedrock inferiore a $0.01 per pipeline run.

---

## Apertura Issue GitLab (automatica)

Se il verdetto è `affected`, `generate_vex.py` chiama le API GitLab per aprire
una Issue di sicurezza nel repository applicativo. La creazione è **idempotente**:
lo script cerca prima una Issue aperta con la label `cve:CVE-XXXX-XXXX` e la crea
solo se non ne esiste già una.

---

## Perché un progetto condiviso invece di script locali

Il motore è centralizzato in `root/vex-engine` per tre motivi:

1. **Single source of truth**: un fix al motore si propaga automaticamente a tutti
   i progetti al loro prossimo push — nessuna sincronizzazione manuale.
2. **Indipendenza dall'IDE**: gli script non appartengono a nessun IDE
   (non sono in `.agent/`, `.cursor/` o strutture analoghe) ma sono
   infrastruttura CI eseguita dal runner.
3. **Scalabilità**: aggiungere un nuovo progetto richiede solo tre righe di
   `include:` nel suo `.gitlab-ci.yml` — il resto è automatico.
