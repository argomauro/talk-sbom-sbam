# VEX Analysis Engine — Bedrock Edition

Il motore di analisi VEX è uno strumento language-agnostic che determina la
**reachability** reale delle vulnerabilità (CVE) nel codice sorgente, combinando
chiamate a **AWS Bedrock** con uno scanner locale a regex.

Gli script che implementano il motore risiedono nel progetto GitLab condiviso
`demo-security/vex-engine` e vengono eseguiti automaticamente dalla pipeline CI di ogni
progetto applicativo — senza nessuna azione manuale da parte dello sviluppatore.

---

## I componenti del progetto `vex-engine`

| File | Ruolo |
| --- | --- |
| `generate_vex.py` | Entry point: carica il VEX, decide quali CVE analizzare, coordina le 3 fasi, crea le Issue GitLab |
| `llm_analyzer.py` | Motore delle 3 fasi: Strategist, Scanner, Auditor |
| `ci-template.yml` | Job CI condiviso: incluso via `include:` da tutti i progetti applicativi |
| `requirements.txt` | Dipendenze Python: `boto3`, `requests` |

---

## Il processo in 3 fasi

Il motore opera su una singola CVE alla volta, eseguendo tre fasi in sequenza.

### Fase 1 — Strategist (Bedrock)

**Input**: descrizione testuale della CVE + nome del pacchetto vulnerabile + linguaggio del progetto.

**Cosa fa**: invia un prompt strutturato al modello LLM su AWS Bedrock chiedendo di
estrarre dalla descrizione le informazioni necessarie alla scansione:

```json
{
  "search_patterns": ["load", "from_string"],
  "import_aliases": ["yaml"],
  "attack_vector": "Untrusted input passed to yaml.load() triggers arbitrary Python object deserialization"
}
```

**Perché serve un LLM**: le CVE descrivono vulnerabilità in linguaggio
naturale, spesso su librerie di nicchia con nomi di funzioni non predicibili.
Un approccio a keyword hardcoded copre solo i casi più comuni. Il modello interpreta
il significato della descrizione e genera pattern specifici per quella CVE.

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
   (`\bpattern\b`), ignorando righe commentate o vuote.
3. Per ogni match estrae una **finestra di ±30 righe** di contesto attorno alla riga trovata.

**Directory ignorate**: `.git`, `venv`, `node_modules`, `__pycache__`, `target`.
Il motore è installato in `/opt/vex-engine` (separato dal progetto) e non si auto-analizza.

---

### Fase 3 — Auditor (Bedrock)

**Input**: CVE description, attack vector (da Fase 1), code snippets (da Fase 2, max 5).

**Cosa fa**: invia i frammenti di codice al modello LLM chiedendo di determinare se la
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

## Strategia di analisi — sempre aggiornato

Il motore **rivaluta tutte le CVE in scope ad ogni push**. Non esiste delta analysis:
ogni CVE che rientra nel `VEX_MODE` corrente viene analizzata da Bedrock.

Questo garantisce che:

1. **Se il developer patcha una vulnerabilità**, la pipeline successiva la rivaluta
   e aggiorna lo stato da `exploitable` a `not_affected` automaticamente.
2. **Se il codice introduce un nuovo uso vulnerabile** di una libreria già presente,
   la pipeline lo rileva immediatamente.
3. **Il VEX è sempre allineato** allo stato reale del codice sorgente.

**Costo**: con il modello `eu.amazon.nova-2-lite-v1:0`, l'analisi di ~35 CVE
costa circa $0.01 per pipeline run in mode `critical`.

### Cosa viene preservato

- **Annotazioni manuali**: se uno sviluppatore ha inserito un commento con uno stato
  custom (diverso da `not_affected`, `exploitable`, `affected`, `in_triage`),
  il motore lo preserva senza sovrascriverlo.
- **Issue URL**: il riferimento alla issue GitLab viene mantenuto nelle `properties`
  del VEX per evitare chiamate API duplicate.

---

## Modalità di analisi (`VEX_MODE`)

| Modalità | CVE analizzate | Costo indicativo | Uso tipico |
| --- | --- | --- | --- |
| `critical` (default) | CRITICAL + HIGH + già exploitable/affected | ~$0.01 | Ogni push |
| `medium` | + MEDIUM | ~$0.03 | Pipeline schedulata |
| `full` | Tutte le CVE | ~$0.10 | Pipeline schedulata settimanale |

Le CVE fuori scope vengono lasciate in stato `in_triage` fino alla prossima
esecuzione con un mode più ampio.

---

## Apertura Issue GitLab (automatica)

Se il verdetto è `exploitable`, `generate_vex.py` chiama le API GitLab per aprire
una Issue di sicurezza nel repository applicativo.

La creazione è **idempotente**: lo script cerca prima una Issue aperta con la
label `cve:GHSA-xxxx` e la crea solo se non ne esiste già una.

Dopo la creazione, l'URL della issue viene salvato nel campo `properties` del VEX:

```json
{
  "properties": [
    { "name": "gitlab:issue-url", "value": "http://localhost/demo-security/app-python/-/issues/1" }
  ]
}
```

Ai run successivi, se la CVE è ancora `exploitable`, il motore verifica la label
via API — se la issue esiste già, salta la creazione (zero chiamate inutili).

---

## Ciclo di vita di una vulnerabilità

```
Push → Analisi Bedrock → exploitable → Issue creata
                                          ↓
                              Developer patcha il codice
                                          ↓
Push successivo → Analisi Bedrock → not_affected → VEX aggiornato
                                                    (Issue resta aperta per audit)
```

Il VEX si aggiorna **automaticamente** dopo ogni fix. Non serve intervento manuale
per cambiare lo stato da `exploitable` a `not_affected`.

---

## Perché un progetto condiviso invece di script locali

Il motore è centralizzato in `demo-security/vex-engine` per tre motivi:

1. **Single source of truth**: un fix al motore si propaga automaticamente a tutti
   i progetti al loro prossimo push — nessuna sincronizzazione manuale.
2. **Indipendenza dall'IDE**: gli script non appartengono a nessun IDE
   ma sono infrastruttura CI eseguita dal runner.
3. **Scalabilità**: aggiungere un nuovo progetto richiede solo tre righe di
   `include:` nel suo `.gitlab-ci.yml` — il resto è automatico.

---

## Configurazione

Il motore usa queste variabili CI/CD (configurate a livello di gruppo GitLab):

| Variabile | Scopo |
| --- | --- |
| `GITLAB_PAT` | Clone vex-engine + push vex.json + creazione issue (scope: `api`, `read_repository`, `write_repository`) |
| `DT_API_KEY` | Autenticazione API Dependency-Track |
| `AWS_ACCESS_KEY_ID` | Credenziale AWS per Bedrock |
| `AWS_SECRET_ACCESS_KEY` | Credenziale AWS per Bedrock |
| `AWS_DEFAULT_REGION` | Region AWS (es. `eu-west-1`) |
| `BEDROCK_MODEL_ID` | Override modello (opzionale, default: `eu.amazon.nova-2-lite-v1:0`) |
| `VEX_MODE` | Modalità analisi: `critical`, `medium`, `full` |
