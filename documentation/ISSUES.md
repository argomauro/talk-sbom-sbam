# Gestione delle Issue GitLab

## Come funziona

Quando il motore trova una CVE `exploitable`, crea automaticamente una Issue GitLab con:

- **Titolo**: `[SECURITY] GHSA-xxxx — Vulnerability confirmed reachable (HIGH)`
- **Body**:
  - Tabella CVE + severity + evidence file:line
  - Reasoning dell'AI in linguaggio naturale
  - CVE description completa
- **Labels**: `security`, `cve:GHSA-xxxx`
- **Confidential**: `false` (visibile a tutti)

## Deduplicazione

La creazione è **idempotente**:

1. Prima di creare, cerca issue aperte con la label `cve:GHSA-xxxx`
2. Se esiste già, salta la creazione
3. Se non esiste, crea la issue

**Risultato**: anche con 100 push, avrai al massimo 1 issue per CVE.

## Stato delle Issue

Le issue vengono create solo per CVE con stato `exploitable` o `affected`.

Se la CVE viene successivamente rivalutata come `not_affected`, l'issue **rimane aperta** — è compito del team chiuderla dopo aver patchato o valutato il rischio.

## Issue URL nel VEX

Dopo la creazione, l'URL della issue viene salvato nel `vex.json`:

```json
{
  "id": "GHSA-jgpv-4h4c-xhw3",
  "analysis": {
    "state": "exploitable",
    "detail": "..."
  },
  "properties": [
    {
      "name": "gitlab:issue-url",
      "value": "http://localhost/demo-security/app-python/-/issues/1"
    }
  ]
}
```

Ai run successivi, il motore vede l'URL già presente e **salta la chiamata API** — zero chiamate inutili.

## Workflow tipico

1. Pipeline rileva CVE `exploitable`
2. Crea Issue GitLab
3. Issue appare nel backlog del team
4. Developer patcha la vulnerabilità
5. Chiude l'issue
6. Pipeline successiva rivaluta la CVE come `not_affected`
7. Issue rimane chiusa (audit trail)

## Casi d'uso

### Caso 1: CVE falsa positiva

- Issue creata → Developer analizza → Determina `not_affected`
- Aggiorna `vex.json` manualmente con `justification: code_not_reachable`
- Issue rimane aperta per tracciamento

### Caso 2: CVE vera vulnerabilità

- Issue creata → Developer patcha → Chiude issue
- Pipeline successiva rivaluta come `not_affected`
- Issue rimane chiusa (storia audit)

### Caso 3: Issue già esistente

- Pipeline rileva CVE `exploitable`
- Cerca issue con label `cve:GHSA-xxxx`
- Trova issue esistente → Salta creazione
- Log: `Issue already tracked: http://.../issues/1. Skipping.`

## Best practices

1. **Non chiudere le issue prima di patchare** — mantieni l'audit trail
2. **Aggiorna `vex.json` manualmente** se il verdetto AI è errato
3. **Usa `VEX_MODE=full`** periodicamente per rivalutare tutte le CVE `in_triage`
4. **Controlla le issue** come parte del workflow di sviluppo normale
