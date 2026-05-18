# Guida Completa alla Pipeline DevSecOps
## Dal commit del codice alla segnalazione automatica delle vulnerabilità reali

> **A chi serve questa guida**
> A chiunque voglia capire *come funziona tutto*, senza dare nulla per scontato:
> dal significato di SBOM fino al momento in cui appare una Issue su GitLab.

---

## Indice

1. [Il problema che stiamo risolvendo](#1-il-problema-che-stiamo-risolvendo)
2. [I componenti del sistema](#2-i-componenti-del-sistema)
3. [Cos'è uno SBOM](#3-cosè-uno-sbom)
4. [Cos'è un VEX](#4-cosè-un-vex)
5. [Cos'è Dependency-Track](#5-cosè-dependency-track)
6. [Cos'è AWS Bedrock](#6-cosè-aws-bedrock)
7. [La pipeline completa — visione d'insieme](#7-la-pipeline-completa--visione-dinsieme)
8. [Stage 1 — SCAN: Trivy genera lo SBOM](#8-stage-1--scan-trivy-genera-lo-sbom)
9. [Stage 2 — ANALYZE: Il cuore del sistema](#9-stage-2--analyze-il-cuore-del-sistema)
   - [Fase 2a — Download baseline VEX](#fase-2a--download-baseline-vex)
   - [Fase 2b — Il motore di analisi a 3 fasi (Bedrock)](#fase-2b--il-motore-di-analisi-a-3-fasi-bedrock)
   - [Fase 2c — Apertura Issue GitLab](#fase-2c--apertura-issue-gitlab)
   - [Fase 2d — Push automatico del VEX arricchito](#fase-2d--push-automatico-del-vex-arricchito)
10. [Stage 3 — SYNC: Aggiornamento Dependency-Track](#10-stage-3--sync-aggiornamento-dependency-track)
11. [Il problema del loop infinito e come lo risolviamo](#11-il-problema-del-loop-infinito-e-come-lo-risolviamo)
12. [La Delta Analysis — perché non ri-analizziamo sempre tutto](#12-la-delta-analysis--perché-non-ri-analizziamo-sempre-tutto)
13. [Struttura dei file nel repository](#13-struttura-dei-file-nel-repository)
14. [Le variabili CI/CD — configurazione passo per passo](#14-le-variabili-cicd--configurazione-passo-per-passo)
15. [Il formato VEX — come si legge il file](#15-il-formato-vex--come-si-legge-il-file)
16. [Flusso di una GitLab Issue di sicurezza](#16-flusso-di-una-gitlab-issue-di-sicurezza)
17. [Scelta del modello Bedrock](#17-scelta-del-modello-bedrock)
18. [Troubleshooting — errori comuni e soluzioni](#18-troubleshooting--errori-comuni-e-soluzioni)

---

## 1. Il problema che stiamo risolvendo

Ogni software moderno usa librerie esterne (dipendenze): Django per le web app Python,
log4j per il logging Java, lodash per JavaScript. Queste librerie vengono aggiornate
costantemente e a volte vengono scoperte **vulnerabilità** (CVE) nelle versioni vecchie.

Il problema non è scoprire le CVE — ci sono strumenti automatici per questo.
Il problema è capire **se quella CVE ti riguarda davvero**.

Esempio reale:
> La tua applicazione usa `PyYAML 3.12`, che ha la CVE-2017-18342.
> Questa CVE è pericolosa **solo se usi `yaml.load()` con input utente non sanitizzato**.
> Se il tuo codice usa solo `yaml.safe_load()`, o carica file statici locali,
> **non sei vulnerabile** — ma lo scanner dice lo stesso "CRITICAL".

Il risultato è che i team di sicurezza si trovano sommersi da **falsi positivi**:
centinaia di CVE "critiche" di cui il 70-80% non è realmente exploitabile nel loro
contesto specifico. Ogni falsa allerta spreca ore di lavoro.

**Questa pipeline risolve il problema** analizzando automaticamente il codice sorgente
con un LLM (Large Language Model) per distinguere le vulnerabilità reali da quelle
teoriche, senza richiedere nessuna azione manuale da parte dello sviluppatore.

---

## 2. I componenti del sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     DEVELOPER MACHINE                       │
│  git push  ──────────────────────────────────────────────►  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                        GITLAB CE                            │
│                                                             │
│   Repository (codice + vex.json)                            │
│   CI/CD Pipeline (3 stage)                                  │
│   Issues (bug tracker)                                      │
│   Runner (eseguore dei job CI)                              │
└──────┬───────────────────────┬──────────────────────────────┘
       │                       │
       ▼                       ▼
┌──────────────┐    ┌──────────────────────┐
│  AWS BEDROCK │    │   DEPENDENCY-TRACK   │
│              │    │                      │
│  Claude LLM  │    │  Database CVE        │
│  (analisi    │    │  Gestione SBOM       │
│   semantica) │    │  Gestione VEX        │
│              │    │  Dashboard           │
└──────────────┘    └──────────────────────┘
```

| Componente | Ruolo | Dove gira |
|---|---|---|
| **GitLab CE** | Repository + CI/CD + Issue tracker | Container Docker locale |
| **GitLab Runner** | Esegue i job della pipeline | Container Docker locale |
| **Trivy** | Scansiona le dipendenze e genera lo SBOM | Container Docker (job CI) |
| **Dependency-Track** | Database centralizzato di SBOM e VEX | Container Docker locale |
| **AWS Bedrock (Claude)** | Analisi semantica del codice vulnerabile | Cloud AWS |
| **vex-engine** | Progetto GitLab condiviso: contiene gli script di analisi e il CI template | GitLab CE (project `root/vex-engine`) |
| **generate_vex.py** | Orchestratore dell'analisi (parte di `vex-engine`) | Python nel job CI, clonato da `vex-engine` |
| **llm_analyzer.py** | Motore di analisi a 3 fasi (parte di `vex-engine`) | Python nel job CI, clonato da `vex-engine` |

---

## 3. Cos'è uno SBOM

**SBOM** = Software Bill of Materials = "Distinta Base del Software"

Pensa a uno SBOM come alla **lista degli ingredienti** su un pacco di biscotti.
Elenca ogni libreria usata nel tuo progetto, con versione e licenza.

Esempio di SBOM (formato CycloneDX, semplificato):
```json
{
  "bomFormat": "CycloneDX",
  "components": [
    {
      "name": "PyYAML",
      "version": "3.12",
      "purl": "pkg:pypi/pyyaml@3.12"
    },
    {
      "name": "Django",
      "version": "2.2.12",
      "purl": "pkg:pypi/django@2.2.12"
    }
  ]
}
```

Lo SBOM viene generato da **Trivy** leggendo i file di dipendenze del progetto
(`requirements.txt`, `pom.xml`, `package.json`, ecc.) e viene inviato a
Dependency-Track che lo confronta con i database di vulnerabilità (NVD, GitHub Advisories).

**Formato usato**: CycloneDX (standard OWASP, il più diffuso in ambito enterprise).

---

## 4. Cos'è un VEX

**VEX** = Vulnerability Exploitability eXchange

Se lo SBOM dice "usi questa libreria", il VEX dice "e **questo è il nostro verdetto**
su ogni vulnerabilità trovata in quella libreria".

Il VEX è un documento JSON che affianca lo SBOM e assegna uno stato a ogni CVE:

| Stato VEX | Significato |
|---|---|
| `affected` | La vulnerabilità è presente ed exploitabile nel nostro codice |
| `not_affected` | La libreria è presente ma la vulnerabilità non è raggiungibile |
| `fixed` | La vulnerabilità era presente ma è stata corretta |
| `under_investigation` | Stiamo ancora analizzando |
| `in_triage` | In analisi, da rivedere |

Esempio di entry VEX:
```json
{
  "id": "CVE-2017-18342",
  "analysis": {
    "state": "not_affected",
    "justification": "code_not_reachable",
    "detail": "Analyzed by Antigravity AI on 2026-05-08. Not Affected (confidence: 94%): The yaml.load() function is only invoked with static config files, not user-supplied input. No untrusted data flow detected.",
    "response": ["will_not_fix"]
  }
}
```

Quando Dependency-Track riceve questo VEX, smette di mostrare quella CVE come
"aperta" nella dashboard — il rumore scende drasticamente.

---

## 5. Cos'è Dependency-Track

Dependency-Track (DTrack) è una **piattaforma open source** di gestione del rischio
delle dipendenze software, sviluppata da OWASP.

**Cosa fa nella nostra pipeline:**
1. Riceve lo SBOM dalla CI (upload via API REST).
2. Confronta le librerie con i database di vulnerabilità (NVD, GitHub Advisories,
   Sonatype OSS Index).
3. Assegna alle vulnerabilità trovate lo stato di default `in_triage`.
4. Fornisce una dashboard web per vedere le CVE aperte.
5. Riceve il VEX arricchito dalla CI e aggiorna gli stati delle CVE.
6. Espone un'API per scaricare il VEX baseline (usata nella pipeline).

**Endpoint API usati dalla pipeline:**

```
POST /api/v1/bom                          → upload SBOM
GET  /api/v1/project?name=X&version=Y     → ricerca progetto per UUID
GET  /api/v1/vex/cyclonedx/project/{uuid} → download VEX baseline
POST /api/v1/vex                          → upload VEX arricchito
GET  /api/v1/bom/token/{token}            → polling stato elaborazione SBOM
```

---

## 6. Cos'è AWS Bedrock

AWS Bedrock è il servizio di Amazon per accedere a modelli LLM (Large Language Model)
tramite API, senza gestire infrastrutture.

**Analogia**: è come Spotify, ma invece di musica fornisce intelligenza artificiale.
Tu chiami un'API, paghi per quello che usi (token), e non hai server da gestire.

Nel nostro caso usiamo **Claude di Anthropic** tramite Bedrock. Claude è lo stesso
modello che alimenta Claude Code (questo strumento).

**Perché Bedrock e non l'API diretta di Anthropic?**
- Hai crediti AWS disponibili
- I dati rimangono nella tua region AWS (compliance)
- Si integra con IAM per la gestione degli accessi
- SLA enterprise di AWS

**Come comunica la pipeline con Bedrock:**
```
Runner CI  →  boto3 (SDK Python AWS)  →  bedrock-runtime.us-east-1.amazonaws.com
                                              │
                                              ▼
                                    Claude analizza il codice
                                              │
                                              ▼
Runner CI  ←  JSON con verdetto  ←  Risposta API
```

**Costo indicativo** (maggio 2026):
- Claude Haiku: ~$0.00025 per 1.000 token di input
- Una singola analisi CVE completa: ~500-800 token
- Con delta analysis su 10-15 CVE nuove per push: **< $0.01 per pipeline**

---

## 7. La pipeline completa — visione d'insieme

```
git push
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 1: scan                                                │
│                                                              │
│  [generate_sbom]                                             │
│  Trivy legge requirements.txt / pom.xml                      │
│  → genera bom.json (SBOM CycloneDX)                          │
│  → artifact disponibile per gli stage successivi             │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 2: analyze                                             │
│                                                              │
│  [vex_ai_analysis]                                           │
│  1. Scarica vex.json baseline da Dependency-Track            │
│  2. Per ogni CVE CRITICAL/HIGH non ancora analizzata:        │
│     a. Phase 1/Strategist → Bedrock                          │
│        "Quali funzioni cercare per questa CVE?"              │
│     b. Phase 2/Scanner   → locale (regex)                    │
│        "Esistono chiamate a quella funzione nel codice?"     │
│     c. Phase 3/Auditor   → Bedrock                          │
│        "Quel codice è davvero exploitabile?"                 │
│  3. Aggiorna vex.json con verdetti e reasoning               │
│  4. Se affected → crea Issue GitLab (idempotente)            │
│  5. git commit + push vex.json [skip ci]                     │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 3: sync                                                │
│                                                              │
│  [dtrack_sync]                                               │
│  1. Upload bom.json → Dependency-Track (polling completamento)│
│  2. Recupera UUID progetto                                   │
│  3. Upload vex.json arricchito → Dependency-Track            │
│     → le CVE not_affected spariscono dalla dashboard         │
└──────────────────────────────────────────────────────────────┘
```

**Caratteristica chiave**: lo sviluppatore fa solo `git push`. Il resto è completamente
automatico. Non deve aprire dashboard, non deve eseguire script manualmente.

---

## 8. Stage 1 — SCAN: Trivy genera lo SBOM

**File**: `.gitlab-ci.yml` → job `generate_sbom`

**Cosa accade**:
1. Il runner avvia un container Docker con l'immagine `aquasec/trivy:latest`.
2. Trivy esegue `trivy fs --format cyclonedx --output bom.json .` — scansiona
   l'intera directory del repository.
3. Legge i file di dipendenze:
   - Python: `requirements.txt`, `Pipfile`, `pyproject.toml`
   - Java: `pom.xml`, `build.gradle`
   - Node: `package.json`, `package-lock.json`
4. Produce `bom.json` — un file JSON con tutte le librerie trovate.
5. `bom.json` viene salvato come **artifact** GitLab: gli stage successivi
   possono scaricarlo e usarlo.

**Nessuna CVE viene cercata qui** — Trivy in questa modalità si limita a
censire le librerie. L'associazione CVE → libreria avviene in Dependency-Track.

---

## 9. Stage 2 — ANALYZE: Il cuore del sistema

**File**: `vex-engine/ci-template.yml` → job `vex_ai_analysis` (incluso via `include:` in ogni progetto)

Questo è lo stage centrale, il cuore dell'innovazione. Il job è definito una volta sola in
`vex-engine` e incluso da tutti i progetti applicativi. All'avvio clona il progetto
`root/vex-engine` su `/opt/vex-engine` e installa le dipendenze (`boto3`, `requests`).

### Fase 2a — Download baseline VEX

Prima di analizzare, lo script scarica l'**ultimo VEX conosciuto** da Dependency-Track.
Questo serve a:
- Avere la lista aggiornata delle CVE (Dependency-Track aggiorna i propri DB in autonomia).
- Preservare i verdetti precedenti (se una CVE era già `not_affected`, non la ri-analizziamo).
- Partire da una base condivisa tra tutti gli sviluppatori del team.

```bash
curl -s GET "http://dependency-track/api/v1/vex/cyclonedx/project/{UUID}" \
     -H "X-Api-Key: $DT_API_KEY" \
     -o vex.json
```

Se è il **primo push** del progetto (non esiste ancora un UUID su DTrack), il passaggio
viene saltato e si usa il `vex.json` locale del repository (se presente) oppure si
parte da zero.

---

### Fase 2b — Il motore di analisi a 3 fasi (Bedrock)

**File principale**: `llm_analyzer.py` — classe `LLMCVEAnalyzer`

Per ogni CVE candidata all'analisi, vengono eseguite 3 fasi in sequenza.

---

#### Phase 1 — Strategist (Bedrock)

**Domanda**: "Per questa CVE, cosa devo cercare nel codice?"

Lo script invia a Bedrock la **descrizione testuale della CVE** (es. "PyYAML's
yaml.load() function deserializes Python objects from arbitrary input,
enabling arbitrary code execution") e chiede al modello di estrarre:

```json
{
  "search_patterns": ["load", "from_string"],
  "import_aliases": ["yaml"],
  "attack_vector": "Untrusted input passed to yaml.load() triggers arbitrary Python object deserialization"
}
```

**Perché è meglio del vecchio approccio?**
Il vecchio codice aveva una lista hardcoded di keyword (`load`, `open`, `parse`...).
Funzionava solo per CVE "standard". Se arrivava una CVE su una libreria oscura
con una funzione chiamata `_internal_deserialize_v2()`, l'engine non la trovava.
Bedrock capisce il **significato** della descrizione e adatta i pattern al caso specifico.

Il risultato viene **cachato in memoria** (`self.cache`) per evitare di chiamare
Bedrock due volte per la stessa CVE nella stessa pipeline run.

---

#### Phase 2 — Scanner (locale, nessuna chiamata di rete)

**Domanda**: "Esiste nel codice una chiamata a quelle funzioni?"

Lo scanner è interamente **locale e basato su regex**. Non fa chiamate di rete.
È il componente più veloce e il più economico (costo zero).

**Algoritmo** (file: `vex-engine/llm_analyzer.py` → `_scan_agnostic()`):

1. Percorre ricorsivamente tutti i file del progetto con `os.walk(".")`.
2. **Prima gate**: salta i file che non importano il pacchetto vulnerabile.
   - Per Python: cerca `import yaml` o `from yaml` nel file.
   - Questo evita falsi positivi dove una funzione si chiama `load` ma appartiene
     a una libreria diversa.
3. **Seconda gate**: cerca le `search_patterns` (da Phase 1) con regex word-boundary
   (`\b pattern \b`), saltando righe commentate o vuote.
4. Quando trova un match, estrae una **finestra di contesto** di ±30 righe attorno
   alla riga trovata.
5. Restituisce una lista di "findings" con: file, numero riga, snippet di codice,
   pattern trovato, riga che ha triggerato il match.

```python
# Esempio di finding:
{
  "file": "./cvedemo/unsafe_processor.py",
  "line": 23,
  "snippet": "...20 righe prima... yaml.load(user_input) ...20 righe dopo...",
  "pattern": "load",
  "trigger_line": "data = yaml.load(user_input, Loader=yaml.FullLoader)"
}
```

**Directory ignorate**: `.git`, `venv`, `node_modules`, `__pycache__`, `target`.
Questo evita di analizzare librerie installate (che contengono codice vulnerabile
per definizione ma non è il nostro codice a chiamarlo). Il motore è clonato in
`/opt/vex-engine` (fuori dalla directory di progetto) quindi non si auto-analizza.

---

#### Phase 3 — Auditor (Bedrock)

**Domanda**: "Quel codice trovato dallo scanner è davvero exploitabile?"

Questa è la fase più importante per eliminare i falsi positivi.
Lo script invia a Bedrock:
- La descrizione della CVE
- Il vettore di attacco (da Phase 1)
- I code snippet trovati dallo scanner (max 5, ~30 righe ciascuno)

Bedrock analizza il **data flow**: da dove viene l'input che entra nella funzione
vulnerabile? È input utente (HTTP request, form, upload)? È un file statico locale?
È una costante hardcoded? È codice commentato?

Risposta attesa:
```json
{
  "verdict": "not_affected",
  "confidence": 0.91,
  "reasoning": "The yaml.load() call at line 23 receives input from a hardcoded config file path, not from user-supplied data. The variable 'user_input' despite its name is populated from os.path.join(BASE_DIR, 'config.yaml') which is a static path. No network or user input reaches this call.",
  "evidence_file": "./cvedemo/unsafe_processor.py",
  "evidence_line": 23
}
```

**Cosa analizza Bedrock:**
- La funzione è commentata? → `not_affected`
- L'input viene da `request.POST` / `request.body` / `form.data` / `argv`? → `affected`
- Viene usato `safe_load` invece di `load`? → `not_affected`
- La funzione è definita ma mai chiamata? → `not_affected`
- Il valore è hardcoded (`"config.yaml"`) non dinamico? → `not_affected`

---

### Fase 2c — Apertura Issue GitLab

Se il verdetto è `affected`, lo script chiama le **API GitLab** per aprire una Issue.

**Deduplicazione** (idempotente): prima di creare la Issue, lo script cerca
issues esistenti con la label `cve:CVE-XXXX-XXXX`. Se ne esiste già una aperta,
salta la creazione. Questo significa che puoi fare 100 push e aprirai **al massimo
1 issue per CVE** — non 100.

```python
# Query issues esistenti
GET /api/v4/projects/{id}/issues?labels=cve:CVE-2017-18342&state=opened
```

La Issue creata contiene:
- **Titolo**: `[SECURITY] CVE-2017-18342 — Vulnerability confirmed reachable (CRITICAL)`
- **Body**: tabella con CVE, severity, evidence file:line
- **Reasoning dell'AI**: spiegazione tecnica in linguaggio naturale
- **Labels**: `security`, `cve:CVE-XXXX-XXXX`

Questo porta la vulnerabilità direttamente nel **workflow di sviluppo ordinario**
del team: la Issue viene assegnata, messa in sprint, risolta come qualsiasi altro bug.

---

### Fase 2d — Push automatico del VEX arricchito

Dopo l'analisi, il file `vex.json` contiene i nuovi verdetti. Va pushato nel
repository in modo che:
1. Lo stage successivo (`sync`) possa caricarlo su Dependency-Track.
2. Il repository rimanga la **Single Source of Truth** per lo stato di sicurezza.
3. Il team possa vedere con `git log` la storia delle analisi.

```bash
git add vex.json
git diff --staged --quiet || \
  git commit -m "chore: AI VEX enrichment via Bedrock [skip ci]" && \
  git push origin HEAD:$CI_COMMIT_BRANCH
```

Il tag `[skip ci]` nella commit message è **fondamentale** — impedisce che questo
push automatico scateni una nuova pipeline, evitando il loop infinito.

---

## 10. Stage 3 — SYNC: Aggiornamento Dependency-Track

**File**: `.gitlab-ci.yml` → job `dtrack_sync`

Questo stage comunica con Dependency-Track tramite la sua API REST:

**Step 1 — Upload SBOM**:
```bash
POST /api/v1/bom
  -F projectName=app-python
  -F projectVersion=main
  -F autoCreate=true
  -F bom=@bom.json
```
Il parametro `autoCreate=true` fa sì che se il progetto non esiste ancora
su Dependency-Track, venga creato automaticamente. Non serve configurazione manuale.

La risposta contiene un **token** di elaborazione: l'SBOM viene processato
in modo asincrono da Dependency-Track, quindi la pipeline fa **polling**
ogni 5 secondi fino a che l'elaborazione è completata (max 30 tentativi = 2.5 minuti).

**Step 2 — Recupero UUID**:
Dependency-Track assegna un UUID univoco a ogni `(nome progetto, versione)`.
Questo UUID è necessario per le operazioni successive.

**Step 3 — Upload VEX**:
```bash
POST /api/v1/vex
  -F projectName=app-python
  -F projectVersion=main
  -F vex=@vex.json
```
Dependency-Track aggiorna gli stati di ogni CVE nel suo database.
Le CVE marcate `not_affected` scompaiono dalla lista dei "rischi aperti".
Le CVE `affected` rimangono visibili come rischi da gestire.

---

## 11. Il problema del loop infinito e come lo risolviamo

Questo è uno degli aspetti più sottili dell'intera pipeline. Senza la gestione
corretta, si creerebbe un loop:

```
dev push
  → pipeline si avvia
    → stage analyze: vex.json viene modificato e pushato
      → nuovo push scatena una nuova pipeline
        → stage analyze: vex.json viene modificato e pushato
          → loop infinito → GitLab va in crash per job accodati
```

**Soluzione**: il tag `[skip ci]` nella commit message di ogni auto-commit.

GitLab legge i commit message di ogni push. Se la stringa `[skip ci]` è presente,
**ignora** quel push e non avvia nessuna pipeline.

```bash
git commit -m "chore: AI VEX enrichment via Bedrock [skip ci]"
#                                                    ^^^^^^^^^
#                                          GitLab vede questo e non avvia pipeline
```

**Ulteriore protezione**: prima del commit, controlliamo se ci sono davvero
modifiche con `git diff --staged --quiet`. Se il vex.json non è cambiato (tutte
le CVE erano già analizzate grazie alla delta analysis), il push non avviene
proprio — zero traffico Git inutile.

---

## 12. La Delta Analysis — perché non ri-analizziamo sempre tutto

Il `vex.json` di un progetto reale ha centinaia di CVE. Chiamare Bedrock per
tutte ad ogni push significherebbe:
- Costo elevato (centinaia di chiamate API)
- Pipeline lenta (minuti di attesa)
- Spreco: le CVE analizzate ieri non sono cambiate

**La Delta Analysis** salta le CVE già analizzate:

```python
def _already_ai_analysed(vuln: dict) -> bool:
    analysis = vuln.get("analysis", {})
    state = analysis.get("state", "")
    detail = analysis.get("detail", "")
    is_ai = "analyzed by Antigravity AI" in detail
    is_definitive = state in ("not_affected", "exploitable", "affected")
    return is_ai and is_definitive
```

Una CVE viene **ri-analizzata** solo se:
- Non ha ancora un'analisi AI (è nuova o è in `in_triage`)
- Ha uno stato non definitivo (es. `under_investigation`)
- Lo sviluppatore ha cancellato manualmente il detail per forzare la ri-analisi

Una CVE viene **preservata senza ri-analisi** se:
- Ha già un verdetto AI definitivo (`not_affected`, `exploitable`, `affected`)
- Ha un commento manuale dello sviluppatore (testo senza la firma "analyzed by Antigravity AI")

In un progetto maturo, dopo le prime pipeline, la grande maggioranza delle CVE ha
già un verdetto. Le pipeline successive analizzeranno solo le **CVE nuove**
introdotte dagli aggiornamenti delle librerie — tipicamente 5-15 per push.

---

## 13. Struttura dei file nel repository

```
talk-sbom-sbam/                      ← monorepo della demo
│
├── vex-engine/                      ← progetto GitLab: root/vex-engine
│   ├── generate_vex.py              ← orchestratore analisi (unica copia)
│   ├── llm_analyzer.py              ← motore 3 fasi Bedrock (unica copia)
│   ├── requirements.txt             ← boto3, requests
│   └── ci-template.yml             ← job "vex_ai_analysis" condiviso
│
├── app-python/                      ← progetto GitLab: root/app-python
│   ├── .gitlab-ci.yml               ← include: vex-engine/ci-template.yml + scan + sync
│   ├── requirements.txt             ← dipendenze Python (lette da Trivy)
│   └── vex.json                     ← stato sicurezza del progetto (versionato)
│
└── app-java/                        ← progetto GitLab: root/app-java
    ├── .gitlab-ci.yml               ← identico strutturalmente ad app-python
    ├── pom.xml
    └── vex.json
```

**Come funziona l'`include:`**

Il `.gitlab-ci.yml` di ogni progetto applicativo contiene solo tre righe per ottenere
lo stage `analyze`:

```yaml
include:
  - project: 'root/vex-engine'
    file: 'ci-template.yml'
    ref: main
```

GitLab risolve questo include al momento del lancio della pipeline: scarica
`ci-template.yml` da `vex-engine` e lo fonde con il CI locale. Il runner non
deve fare nulla di speciale — è GitLab CI stesso a gestire la composizione.

**Come il job ottiene gli script Python**

Il job `vex_ai_analysis` (definito in `ci-template.yml`) clona il progetto
`vex-engine` nella propria directory di lavoro come primo passo:

```bash
git clone --depth 1 \
  "http://oauth2:${CI_GIT_TOKEN}@host.docker.internal/root/vex-engine.git" \
  /opt/vex-engine
```

Gli script vengono clonati in `/opt/vex-engine` (separato dalla directory del
progetto applicativo) per non interferire con la scansione del codice sorgente.

**Perché `vex.json` è versionato nel repository applicativo?**

Il VEX è un documento di **compliance** — registra le decisioni prese riguardo
alla sicurezza del software. Metterlo nel repository significa:
- Audit trail: `git log vex.json` mostra ogni decisione con data e reasoning AI
- Code review: le modifiche al VEX possono essere revisionate come qualsiasi PR
- Branching: branch diversi possono avere stati di sicurezza diversi
- Ripristino: `git revert` per tornare a un verdetto precedente se sbagliato

**Perché `vex.json` è versionato nel repository?**

Il VEX è un documento di **compliance** — registra le decisioni prese riguardo
alla sicurezza del software. Metterlo nel repository significa:
- Storia audit-trail: `git log vex.json` mostra ogni decisione nel tempo
- Code review: le modifiche al VEX possono essere revisionate come qualsiasi PR
- Branching: branch diversi possono avere stati di sicurezza diversi
- Ripristino: `git revert` per tornare a un verdetto precedente se sbagliato

---

## 14. Le variabili CI/CD — configurazione passo per passo

Le variabili vanno configurate in GitLab alla voce:
**Settings → CI/CD → Variables** (per ogni progetto, o a livello di gruppo per
condividerle tra tutti i progetti).

Le variabili "masked" vengono offuscate nei log della pipeline (`[MASKED]`).

---

### DT_API_KEY

**Cos'è**: La chiave di autenticazione per le API di Dependency-Track.

**Come ottenerla**:
1. Vai su `http://localhost:8080` (Dependency-Track)
2. **Administration → Access Management → Teams → Automation**
3. Copia la API Key mostrata
4. Assicurati che il team abbia i permessi: `BOM_UPLOAD`, `PROJECT_CREATION_UPLOAD`, `VEX_UPLOAD`

**In GitLab**: masked = YES, protected = NO (serve anche su branch feature)

---

### AWS_ACCESS_KEY_ID e AWS_SECRET_ACCESS_KEY

**Cos'è**: Credenziali AWS per autenticare le chiamate a Bedrock.

**Come ottenerle**:
1. Vai su `https://console.aws.amazon.com`
2. **IAM → Users → (il tuo utente) → Security credentials**
3. **Create access key** → seleziona "Application running outside AWS"
4. Salva subito: la `SECRET_ACCESS_KEY` viene mostrata solo una volta

**Permessi IAM minimi necessari** (policy da allegare all'utente):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
    }
  ]
}
```

**IMPORTANTE**: Prima di usare il modello, devi abilitarlo nella console AWS:
**Bedrock → Model access → Request access** → seleziona i modelli Anthropic.
Senza questo passaggio, le chiamate API daranno errore `AccessDeniedException`.

**In GitLab**: masked = YES per entrambe.

---

### AWS_DEFAULT_REGION

**Cos'è**: La region AWS dove sono disponibili i modelli Bedrock.

**Valore**: `us-east-1` (Nord Virginia) — ha la disponibilità più ampia.
Alternativa: `us-west-2` (Oregon).

**NOTA**: La region deve corrispondere a dove hai abilitato i modelli nel passo precedente.

**In GitLab**: masked = NO (non è un segreto), valore: `us-east-1`

---

### GITLAB_ACCESS_TOKEN

**Cos'è**: Token di autenticazione per le API GitLab (apertura Issue).

**Come ottenerlo**:
1. GitLab → **User Settings → Access Tokens** (angolo in alto a destra, avatar)
2. **Add new token**
3. Nome: `vex-pipeline-bot`
4. Scopes: seleziona **`api`** (necessario per creare Issue)
5. Expiration: metti una data futura
6. **Create** e copia il token (mostrato solo una volta)

**In GitLab**: masked = YES

---

### CI_GIT_TOKEN

**Cos'è**: Token con doppio utilizzo nel job CI:
1. **Clonare `vex-engine`**: il job scarica gli script di analisi dal progetto condiviso.
2. **Push del `vex.json` arricchito**: dopo l'analisi, il VEX aggiornato viene committato nel repository applicativo.

**Come ottenerlo**:
1. GitLab → **Progetto → Settings → Access Tokens**
2. **Add new token**
3. Nome: `vex-ci-push`
4. Role: **Developer** (o Maintainer se il branch è protetto)
5. Scopes: **`read_repository`** e **`write_repository`**
6. **Create** e copia

**In GitLab**: masked = YES — va configurata in ogni progetto applicativo
(o a livello di gruppo per condividerla).

**Perché non usare CI_JOB_TOKEN?**
`CI_JOB_TOKEN` è iniettato automaticamente da GitLab in ogni job ma ha
permessi limitati: può fare clone/fetch del proprio progetto ma **non push**
e non può clonare altri progetti dello stesso gruppo senza configurazioni aggiuntive.
Un token dedicato è più esplicito e controllabile.

---

### BEDROCK_MODEL_ID (opzionale)

**Cos'è**: Permette di scegliere il modello Claude da usare.

**Valori possibili**:
```
anthropic.claude-3-haiku-20240307-v1:0       ← default, più veloce e economico
anthropic.claude-3-5-sonnet-20241022-v2:0    ← più accurato per codice complesso
anthropic.claude-3-opus-20240229-v1:0        ← massima qualità, molto costoso
```

Se non configurata, viene usato Haiku (buon compromesso velocità/costo/qualità).

---

## 15. Il formato VEX — come si legge il file

Il `vex.json` segue lo standard **CycloneDX VEX**. Ecco come interpretare le parti principali:

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.4",
  "version": 1,
  "metadata": {
    "timestamp": "2026-05-08T09:00:00Z",
    "tools": [
      {"vendor": "OWASP", "name": "Dependency-Track"},
      {
        "name": "Antigravity VEX Analyst — Bedrock Edition",
        "version": "3.0.0",
        "model": "anthropic.claude-3-haiku-20240307-v1:0"
      }
    ]
  },
  "vulnerabilities": [
    {
      "bom-ref": "uuid-della-componente",
      "id": "CVE-2017-18342",                    ← ID della vulnerabilità
      "source": {"name": "NVD"},                 ← database sorgente
      "ratings": [
        {
          "severity": "CRITICAL",                ← gravità secondo CVSS
          "score": 9.8,
          "method": "CVSSv3"
        }
      ],
      "description": "PyYAML...",                ← testo descrittivo della CVE
      "analysis": {
        "state": "not_affected",                 ← verdetto finale
        "justification": "code_not_reachable",   ← motivo standardizzato
        "detail": "Analyzed by Antigravity AI... Not Affected (94%): ...",
        "response": ["will_not_fix"]             ← azione pianificata
      },
      "affects": [
        {
          "ref": "pkg:pypi/pyyaml@3.12"         ← quale componente è affetta
        }
      ]
    }
  ]
}
```

**Stati `justification` standardizzati (CycloneDX)**:
- `code_not_reachable`: il codice vulnerabile non è raggiungibile nel flusso di esecuzione
- `protected_by_mitigating_control`: esiste una misura di protezione (firewall, sanitizzazione)
- `requires_configuration`: la vulnerabilità richiede una configurazione specifica non presente
- `requires_dependency`: richiede un'altra dipendenza non installata

---

## 16. Flusso di una GitLab Issue di sicurezza

Quando Bedrock determina che una CVE è `affected`, il sistema crea automaticamente una Issue:

```
Titolo: [SECURITY] CVE-2021-44228 — Vulnerability confirmed reachable (CRITICAL)

Labels: security, cve:CVE-2021-44228

Body:
┌─────────────────────────────────────────────────────┐
│ ## Vulnerability Confirmed Reachable by AI Analysis │
│                                                     │
│ | Campo    | Valore                               | │
│ |----------|--------------------------------------| │
│ | CVE ID   | CVE-2021-44228                       | │
│ | Severity | CRITICAL                             | │
│ | Evidence | ./src/main/java/App.java:47           | │
│                                                     │
│ ### AI Reasoning                                    │
│ Reachable (confidence: 96%): The Logger.info() call │
│ at line 47 receives the 'userAgent' parameter which │
│ is populated from the HTTP request header           │
│ 'User-Agent'. This value is attacker-controlled     │
│ and flows directly into the log4j logging call,     │
│ enabling JNDI lookup injection (Log4Shell).         │
│                                                     │
│ ### CVE Description                                 │
│ Apache Log4j2 2.0-beta9 through 2.15.0...          │
└─────────────────────────────────────────────────────┘
```

**Il team di sviluppo**:
1. Riceve la notifica GitLab della nuova Issue
2. Legge il reasoning dell'AI per capire dove e perché
3. Va direttamente al file:riga indicato come evidence
4. Applica il fix (aggiornare la libreria, sanitizzare l'input, usare safe API)
5. Chiude la Issue con il link al commit di fix

**Idempotenza**: se la stessa CVE è ancora aperta alla pipeline successiva,
non viene creata una seconda Issue — il controllo prelimitare cerca issues
esistenti con la label `cve:CVE-XXXX-XXXX` nello stato `opened`.

---

## 17. Scelta del modello Bedrock

| Modello | Velocità | Costo | Qualità analisi codice | Quando usarlo |
|---|---|---|---|---|
| `claude-3-haiku` | ~2s | ~$0.0003/analisi | Buona | Default per la maggior parte dei progetti |
| `claude-3-5-sonnet` | ~5s | ~$0.003/analisi | Ottima | Progetti critici, codice complesso |
| `claude-3-opus` | ~15s | ~$0.015/analisi | Eccellente | Solo per CVE ad altissimo impatto |

**Raccomandazione pratica**:
- Inizia con **Haiku** (default): copre bene il 90% dei casi
- Configura `BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0` solo per
  progetti con codice particolarmente complesso (molti livelli di indirezione,
  heavy metaprogramming, codice generato)

---

## 18. Troubleshooting — errori comuni e soluzioni

---

### ❌ `AccessDeniedException` nelle chiamate Bedrock

**Causa**: Il modello non è stato abilitato nella console AWS Bedrock.

**Soluzione**:
1. Vai su AWS Console → **Amazon Bedrock → Model access**
2. Clicca **Manage model access**
3. Seleziona i modelli Anthropic (Claude Haiku, Sonnet)
4. Clicca **Request model access**
5. Attendi l'approvazione (di solito immediata per modelli di base)

---

### ❌ Clone di `vex-engine` fallisce nel job CI

**Causa**: `CI_GIT_TOKEN` non ha il permesso `read_repository` oppure il progetto
`root/vex-engine` non esiste ancora su GitLab CE.

**Soluzione**:
1. Verifica che il progetto `vex-engine` sia stato creato su GitLab CE e che
   `ci-template.yml`, `generate_vex.py` e `llm_analyzer.py` siano presenti nel branch `main`.
2. Assicurati che `CI_GIT_TOKEN` abbia almeno lo scope `read_repository`.
3. Controlla che l'IP di GitLab sia raggiungibile dall'interno del container del runner
   (`host.docker.internal` o IP diretto).

---

### ❌ `NoCredentialsError` o `InvalidClientTokenId`

**Causa**: Le variabili `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` non sono
configurate in GitLab, o sono configurate con il valore sbagliato.

**Soluzione**:
1. Verifica le variabili in **Settings → CI/CD → Variables**
2. Controlla che non ci siano spazi o caratteri extra
3. Verifica che le chiavi IAM siano ancora attive su AWS Console → IAM → Users

---

### ❌ Stage `analyze` non trova il progetto su Dependency-Track

**Causa**: È il primo push del progetto e Dependency-Track non lo conosce ancora.

**Comportamento atteso**: Il warning `WARN: progetto non ancora su DTrack` viene
stampato, lo stage continua comunque. Lo stage `sync` successivo creerà il progetto
grazie a `autoCreate=true` nel caricamento dello SBOM. Dal secondo push in poi,
tutto funzionerà normalmente.

---

### ❌ Push del vex.json fallisce con `Permission denied`

**Causa**: `CI_GIT_TOKEN` non ha il permesso `write_repository`, o il branch è
protetto e il token non ha il ruolo adeguato.

**Soluzione**:
1. Vai in GitLab → **Progetto → Settings → Access Tokens**
2. Crea un nuovo token con scope `write_repository`
3. Se il branch è protetto, assegna il ruolo **Maintainer** al token
4. Aggiorna la variabile `CI_GIT_TOKEN` in CI/CD Variables

---

### ❌ Vengono create Issue duplicate

**Causa**: La label `cve:CVE-XXXX-XXXX` non viene trovata perché le Issue
precedenti sono state chiuse manualmente.

**Comportamento**: Le Issue chiuse non vengono rilevate dalla query
`state=opened`. Se una Issue viene chiusa prima che il fix sia deployato
e la CVE rimane nel vex.json come `affected`, la prossima pipeline creerà
una nuova Issue.

**Soluzione intenzionale**: Chiudi la Issue solo dopo aver fatto il deploy del fix.

---

### ❌ Vex.json diventa troppo grande e il push è lento

**Causa**: Il file accumula centinaia di CVE con i rispettivi dettagli AI.

**Soluzione**: Puoi impostare `--mode critical` nel job CI per limitare l'analisi
alle CVE CRITICAL/HIGH. Le CVE LOW/MEDIUM vengono mantenute nello stato precedente
senza essere ri-analizzate.

---

### ❌ La pipeline dura troppo (>15 minuti)

**Causa**: Troppe CVE nuove da analizzare in un unico push (es. aggiornamento massiccio
di dipendenze).

**Soluzioni**:
1. Passa da Haiku a Haiku (già il default) — non cambia
2. Aumenta `--mode critical` (analizza solo CRITICAL/HIGH)
3. Esegui una singola pipeline "bootstrap" con `--mode full` per analizzare tutto,
   poi le pipeline ordinarie gestiranno solo le nuove CVE (delta analysis)

---

*Documento generato il 2026-05-08 — versione pipeline 3.1.0 (Bedrock Edition + vex-engine shared project)*
