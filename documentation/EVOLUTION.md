# Evoluzione del Sistema: da Triage Manuale a Pipeline Completamente Automatizzata

Questo documento traccia il percorso evolutivo dell'architettura, spiegando le
decisioni prese e il perché di ogni cambiamento.

---

## Versione 1.0 — Scanner euristico locale (IDE-driven)

Il primo approccio richiedeva che lo sviluppatore avviasse manualmente l'analisi
dall'IDE (Cursor o Claude Code), eseguendo uno script Python che simulava
l'intelligenza artificiale tramite regex e keyword hardcoded.

**Flusso operativo**:
1. Lo sviluppatore faceva `git pull` per ottenere il `vex.json` baseline.
2. Lanciava manualmente `generate_vex.py` dall'IDE.
3. Revisionava i risultati nella dashboard HTML locale.
4. Committava e pushava il `vex.json` arricchito.
5. La pipeline CI caricava il VEX su Dependency-Track.

**Limiti principali**:
- **Dipendenza dal gesto umano**: il triage avveniva solo se lo sviluppatore
  ricordava di eseguirlo. Nessuna garanzia di copertura sistematica.
- **Nessun LLM reale**: il "motore AI" era in realtà un insieme di regex con
  keyword hardcoded (`load`, `open`, `parse`...). Funzionava per CVE comuni,
  falliva su librerie di nicchia o funzioni con nomi non predicibili.
- **Falsi positivi strutturali**: il sistema confondeva contesti diversi (es.
  `img.verify()` di Pillow interpretato come `verify` di Requests — vedi `ERROR.md`
  per i casi documentati).
- **Script duplicati**: ogni progetto aveva la propria copia degli script in
  `.agent/skills/vex-triage/scripts/`, accoppiata alla struttura dell'IDE.
  Un fix richiedeva aggiornamenti manuali in ogni repository.

---

## Versione 2.0 — Integrazione Bedrock reale (ancora IDE-driven)

Il secondo passo ha sostituito la simulazione regex con vere chiamate API a
**AWS Bedrock (Claude)**, mantenendo però il trigger manuale dall'IDE.

**Miglioramenti**:
- **Phase 1 (Strategist)**: Bedrock interpreta la descrizione della CVE e genera
  i pattern di ricerca specifici — nessuna keyword hardcoded.
- **Phase 3 (Auditor)**: Bedrock analizza il data flow nei code snippet e produce
  un verdetto con confidence score e reasoning in linguaggio naturale.
- **Delta Analysis**: le CVE già analizzate vengono saltate, riducendo i costi
  Bedrock e i tempi di esecuzione.
- **Issue GitLab automatiche**: per ogni CVE `affected` viene aperta una Issue
  idempotente con evidence e reasoning dell'AI.

**Limiti residui**:
- Il flusso richiedeva ancora un'azione manuale dello sviluppatore.
- Gli script erano ancora accoppiati all'IDE (struttura `.agent/`) e duplicati
  in ogni progetto.

---

## Versione 3.0 — Pipeline CI completamente automatizzata + `vex-engine` condiviso

L'architettura attuale elimina entrambi i limiti residui.

### Automazione completa

Lo sviluppatore fa solo `git push`. La pipeline CI gestisce automaticamente:

```
git push
  → [scan]    Trivy genera bom.json (SBOM)
  → [analyze] Runner clona vex-engine → download VEX baseline da DTrack
               → 3 fasi Bedrock per ogni CVE nuova
               → Issue GitLab se affected
               → push vex.json arricchito [skip ci]
  → [sync]    Upload SBOM + VEX arricchito → Dependency-Track
```

Non esistono più script da eseguire localmente, dashboard da aprire, o commit
manuali da fare per il triage. Il ciclo è completamente chiuso dalla CI.

### Progetto `vex-engine` — infrastruttura condivisa

Gli script di analisi non appartengono più ai singoli progetti applicativi.
Vivono in un progetto GitLab dedicato (`root/vex-engine`) come infrastruttura:

```
vex-engine/
├── generate_vex.py    ← orchestratore (unica copia per tutti i progetti)
├── llm_analyzer.py    ← motore 3 fasi Bedrock (unica copia)
├── requirements.txt   ← boto3, requests
└── ci-template.yml    ← job "vex_ai_analysis" condiviso via include:
```

Ogni progetto applicativo include il template con tre righe:

```yaml
include:
  - project: 'root/vex-engine'
    file: 'ci-template.yml'
    ref: main
```

**Conseguenza pratica**: se domani si aggiorna il modello Bedrock, si migliora
il prompt dell'Auditor, o si aggiunge supporto a un nuovo linguaggio, si modifica
**un solo file** in `vex-engine`. Tutti i progetti ricevono il miglioramento
automaticamente al push successivo — senza toccare nessun repository applicativo.

### Eliminazione delle strutture IDE-specifiche

Le directory `.agent/` (Claude Code / Antigravity) e `.cursor/` (Cursor IDE)
sono state rimosse dai progetti applicativi. Queste strutture avevano senso
quando il triage era un gesto dell'IDE; con la pipeline automatizzata sono
rumore inutile che causava confusione su dove risiedesse la logica reale.

---

## Tabella comparativa delle versioni

| Aspetto | v1.0 | v2.0 | v3.0 |
|---|---|---|---|
| Trigger analisi | Manuale (IDE) | Manuale (IDE) | **Automatico (git push)** |
| LLM reale | No (regex) | Sì (Bedrock) | Sì (Bedrock) |
| Confidence score | No | Sì | Sì |
| Issue GitLab | No | Sì | Sì |
| Delta analysis | No | Sì | Sì |
| Script centralizzati | No (.agent/ duplicato) | No (.agent/ duplicato) | **Sì (vex-engine)** |
| Dipendenza da IDE | Sì | Sì | **No** |
| Falsi positivi di contesto | Alto | Basso | Basso |

---

## Principio architetturale: VEX-as-Code

In tutte le versioni, il file `vex.json` rimane versionato nel repository
applicativo come documento di compliance. Questo garantisce:

- **Audit trail immutabile**: ogni verdetto AI è tracciato in `git log` con
  data, modello usato e reasoning completo.
- **Single Source of Truth**: il repository è l'unica fonte autorevole sullo
  stato di sicurezza del progetto — non una dashboard esterna.
- **Branching**: branch diversi possono avere stati di sicurezza diversi,
  utile per gestire hotfix su versioni legacy.
- **Code review**: le modifiche al VEX (incluse quelle automatiche della CI)
  sono visibili nella history e possono essere oggetto di review.
