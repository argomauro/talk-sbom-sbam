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
10. [Stage 3 — SYNC: Aggiornamento Dependency-Track](#10-stage-3--sync-aggiornamento-dependency-track)
11. [Il problema del loop infinito e come lo risolviamo](#11-il-problema-del-loop-infinito-e-come-lo-risolviamo)
12. [Struttura dei file nel repository](#12-struttura-dei-file-nel-repository)
13. [Le variabili CI/CD](#13-le-variabili-cicd)
14. [Il formato VEX — come si legge il file](#14-il-formato-vex--come-si-legge-il-file)
15. [Flusso di una GitLab Issue di sicurezza](#15-flusso-di-una-gitlab-issue-di-sicurezza)
16. [Modalità di analisi e pipeline schedulata](#16-modalità-di-analisi-e-pipeline-schedulata)
17. [Troubleshooting — errori comuni e soluzioni](#17-troubleshooting--errori-comuni-e-soluzioni)

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
contesto specifico.

**Questa pipeline risolve il problema** analizzando automaticamente il codice sorgente
con un LLM (Large Language Model) per distinguere le vulnerabilità reali da quelle
teoriche, senza richiedere nessuna azione manuale da parte dello sviluppatore.

---

## 2. I componenti del sistema

```text
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
│   Runner (esecutore dei job CI)                             │
└──────┬───────────────────────┬──────────────────────────────┘
       │                       │
       ▼                       ▼
┌──────────────┐    ┌──────────────────────┐
│  AWS BEDROCK │    │   DEPENDENCY-TRACK   │
│              │    │                      │
│  LLM Model  │    │  Database CVE        │
│  (analisi    │    │  Gestione SBOM       │
│   semantica) │    │  Gestione VEX        │
│              │    │  Dashboard           │
└──────────────┘    └──────────────────────┘
```

| Componente | Ruolo | Dove gira |
| --- | --- | --- |
| **GitLab CE** | Repository + CI/CD + Issue tracker | Container Docker locale |
| **GitLab Runner** | Esegue i job della pipeline | Container Docker locale |
| **Trivy** | Scansiona le dipendenze e genera lo SBOM | Container Docker (job CI) |
| **Dependency-Track** | Database centralizzato di SBOM e VEX | Container Docker locale |
| **AWS Bedrock** | Analisi semantica del codice vulnerabile | Cloud AWS |
| **vex-engine** | Progetto GitLab condiviso con script di analisi e CI template | GitLab CE (`demo-security/vex-engine`) |

---

## 3. Cos'è uno SBOM

**SBOM** = Software Bill of Materials = "Distinta Base del Software"

Elenca ogni libreria usata nel progetto, con versione e licenza.
Viene generato da **Trivy** leggendo i file di dipendenze del progetto
(`requirements.txt`, `pom.xml`, `package.json`) e inviato a Dependency-Track
che lo confronta con i database di vulnerabilità (NVD, GitHub Advisories).

**Formato usato**: CycloneDX 1.5 (standard OWASP).

---

## 4. Cos'è un VEX

**VEX** = Vulnerability Exploitability eXchange

Se lo SBOM dice "usi questa libreria", il VEX dice "e **questo è il nostro verdetto**
su ogni vulnerabilità trovata in quella libreria".

| Stato VEX | Significato |
| --- | --- |
| `exploitable` | La vulnerabilità è presente ed exploitabile nel nostro codice |
| `not_affected` | La libreria è presente ma la vulnerabilità non è raggiungibile |
| `in_triage` | Non ancora analizzata (fuori scope del VEX_MODE corrente) |
| `fixed` | La vulnerabilità era presente ma è stata corretta |

Quando Dependency-Track riceve il VEX, le CVE `not_affected` spariscono dalla
dashboard — il rumore scende drasticamente.

---

## 5. Cos'è Dependency-Track

Piattaforma open source OWASP di gestione del rischio delle dipendenze software.

**Endpoint API usati dalla pipeline:**

```text
POST /api/v1/bom                          → upload SBOM
GET  /api/v1/bom/token/{token}            → polling stato elaborazione
POST /api/v1/vex                          → upload VEX arricchito
```

---

## 6. Cos'è AWS Bedrock

Servizio AWS per accedere a modelli LLM tramite API, senza gestire infrastrutture.
Paghi per token consumati. I dati rimangono nella tua region AWS.

**Modello usato**: `eu.amazon.nova-2-lite-v1:0` (default, configurabile via `BEDROCK_MODEL_ID`).

**Costo indicativo**: ~$0.01 per pipeline run in mode `critical` (~35 CVE).

---

## 7. La pipeline completa — visione d'insieme

```text
git push
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 1: scan                                                │
│  Trivy genera bom.json (SBOM CycloneDX)                      │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 2: analyze (vex-engine)                                │
│  1. Carica vex.json dal repository (baseline)                │
│  2. Per ogni CVE in scope: Strategist → Scanner → Auditor    │
│  3. Aggiorna vex.json con verdetti                           │
│  4. Crea Issue GitLab per exploitable                        │
│  5. Push automatico [skip ci]                                │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 3: sync                                                │
│  Upload SBOM + VEX su Dependency-Track                       │
└──────────────────────────────────────────────────────────────┘
```

Lo sviluppatore fa solo `git push`. Il resto è completamente automatico.

---

## 8. Stage 1 — SCAN: Trivy genera lo SBOM

**File**: `.gitlab-ci.yml` → job `generate_sbom`

```yaml
generate_sbom:
  stage: scan
  image: aquasec/trivy:latest
  script:
    - trivy fs --format cyclonedx --output bom.json .
  artifacts:
    paths:
      - bom.json
```

Trivy legge i file di dipendenze e produce `bom.json`. Nessuna CVE viene cercata
qui — l'associazione CVE → libreria avviene in Dependency-Track.

---

## 9. Stage 2 — ANALYZE: Il cuore del sistema

**File**: `vex-engine/ci-template.yml` → job `vex_ai_analysis`

### Fase 2a — Baseline VEX

Il job usa il `vex.json` presente nel repository Git come baseline. Questo file
contiene i verdetti delle analisi precedenti e le issue URL nelle properties.

### Fase 2b — Analisi a 3 fasi (Bedrock)

Per ogni CVE in scope (determinato da `VEX_MODE`):

1. **Strategist (Bedrock)**: estrae i pattern di ricerca dalla descrizione CVE
2. **Scanner (locale)**: cerca i pattern nel codice con regex
3. **Auditor (Bedrock)**: analizza il data flow e decide se è exploitabile

**Tutte le CVE in scope vengono sempre rivalutate** — non esiste delta analysis.
Questo garantisce che dopo una fix del developer, il VEX si aggiorni automaticamente.

### Fase 2c — Issue GitLab

Se `exploitable`, crea una Issue con:

- Titolo: `[SECURITY] GHSA-xxxx — Vulnerability confirmed reachable (HIGH)`
- Body: tabella CVE + severity + evidence file:line + reasoning AI
- Labels: `security`, `cve:GHSA-xxxx`

**Deduplicazione**: cerca issue esistenti con la label `cve:GHSA-xxxx` — se esiste, salta.

### Fase 2d — Push automatico

```bash
git add vex.json
git commit -m "chore: AI VEX enrichment via Bedrock [skip ci]"
git push origin main
```

Il tag `[skip ci]` impedisce loop infiniti.

---

## 10. Stage 3 — SYNC: Aggiornamento Dependency-Track

1. Upload `bom.json` → Dependency-Track (con polling completamento)
2. Upload `vex.json` arricchito → Dependency-Track
3. Le CVE `not_affected` spariscono dalla dashboard

---

## 11. Il problema del loop infinito e come lo risolviamo

Senza gestione corretta:

```text
push → pipeline → vex.json modificato → push → pipeline → loop infinito
```

**Soluzione**: `[skip ci]` nella commit message. GitLab ignora il push e non avvia pipeline.

**Ulteriore protezione**: `git diff --staged --quiet` — se il vex.json non è cambiato,
il push non avviene.

---

## 12. Struttura dei file nel repository

```text
talk-sbom-sbam/
│
├── vex-engine/                      ← progetto GitLab: demo-security/vex-engine
│   ├── generate_vex.py              ← orchestratore analisi
│   ├── llm_analyzer.py              ← motore 3 fasi Bedrock
│   ├── requirements.txt             ← boto3, requests
│   └── ci-template.yml              ← job "vex_ai_analysis" condiviso
│
├── app-python/                      ← progetto GitLab: demo-security/app-python
│   ├── .gitlab-ci.yml               ← include: vex-engine/ci-template.yml
│   ├── requirements.txt             ← dipendenze Python (lette da Trivy)
│   └── vex.json                     ← stato sicurezza del progetto (versionato)
```

Il `.gitlab-ci.yml` di ogni progetto applicativo include il template condiviso:

```yaml
include:
  - project: 'demo-security/vex-engine'
    file: 'ci-template.yml'
    ref: main
```

Il job clona `vex-engine` in `/opt/vex-engine` (separato dal progetto) per non
interferire con la scansione del codice sorgente.

---

## 13. Le variabili CI/CD

Configurate a livello di **Gruppo** GitLab (`demo-security`) per condividerle tra tutti i progetti.

| Variabile | Scopo | Masked |
| --- | --- | --- |
| `GITLAB_PAT` | Clone vex-engine + push vex.json + creazione issue | YES |
| `DT_API_KEY` | Autenticazione API Dependency-Track | YES |
| `AWS_ACCESS_KEY_ID` | Credenziale AWS per Bedrock | YES |
| `AWS_SECRET_ACCESS_KEY` | Credenziale AWS per Bedrock | YES |
| `AWS_DEFAULT_REGION` | Region AWS (es. `eu-west-1`) | NO |
| `BEDROCK_MODEL_ID` | Override modello (opzionale) | NO |

**`GITLAB_PAT`** è un Personal Access Token con scope `api`, `read_repository`, `write_repository`.
Sostituisce i vecchi `CI_GIT_TOKEN` e `GITLAB_ACCESS_TOKEN` — un unico token per tutto.

---

## 14. Il formato VEX — come si legge il file

Esempio di entry nel `vex.json`:

```json
{
  "id": "GHSA-jgpv-4h4c-xhw3",
  "ratings": [{ "severity": "HIGH" }],
  "analysis": {
    "state": "exploitable",
    "detail": "Vulnerability GHSA-jgpv-4h4c-xhw3 analyzed by LLM Analyzer (python) on 2026-05-18. Affected: The Pillow library is used with user-uploaded images..."
  },
  "properties": [
    { "name": "gitlab:issue-url", "value": "http://localhost/demo-security/app-python/-/issues/1" }
  ]
}
```

---

## 15. Flusso di una GitLab Issue di sicurezza

```text
1. Pipeline rileva CVE exploitable
2. Cerca issue con label cve:GHSA-xxxx → non esiste
3. Crea Issue con titolo, body, labels
4. Salva URL in vex.json properties
5. Push successivo: CVE ancora exploitable → cerca label → issue esiste → skip
6. Developer patcha → push → CVE diventa not_affected → VEX aggiornato
7. Issue resta aperta per audit trail (il team la chiude manualmente)
```

---

## 16. Modalità di analisi e pipeline schedulata

| `VEX_MODE` | CVE analizzate | Costo | Uso |
| --- | --- | --- | --- |
| `critical` (default) | CRITICAL + HIGH + già exploitable/affected | ~$0.01 | Ogni push |
| `medium` | + MEDIUM | ~$0.03 | Pipeline schedulata |
| `full` | Tutte le CVE | ~$0.10 | Pipeline schedulata settimanale |

### Pipeline schedulata

Per analizzare anche le CVE non critiche:

1. GitLab → `demo-security/app-python` → **CI/CD → Schedules**
2. **New schedule**:
   - Description: `Weekly full VEX analysis`
   - Interval: `0 2 * * 0` (ogni domenica alle 2:00)
   - Target branch: `main`
3. Aggiungi variabile: `VEX_MODE = full`

---

## 17. Troubleshooting — errori comuni e soluzioni

| Errore | Causa | Soluzione |
| --- | --- | --- |
| Clone fallisce nel runner | Runner cerca `localhost` | Aggiungi `clone_url = "http://gitlab/"` nel `config.toml` |
| `Access denied` su push | Token insufficiente | Verifica `GITLAB_PAT` con scope `api`, `read_repository`, `write_repository` |
| `Bedrock AccessDeniedException` | Modello non abilitato | **Bedrock → Model access → Request access** |
| Issue non creata | `CI_API_V4_URL` punta a localhost | Il codice sostituisce automaticamente `localhost` con `gitlab` |
| DTrack HTTP 400 su VEX upload | Schema CycloneDX non valido | Verificare struttura `metadata.tools` (deve essere array) |
| DTrack non raggiungibile | Hostname errato | Usare `host.docker.internal:8081` nel job |
| Pipeline loop infinito | Manca `[skip ci]` nel commit | Verificare che il commit message contenga `[skip ci]` |
