# 🚀 Demo: DevSecOps Zero-Budget

## Censimento SBOM e Monitoraggio CVE con GitLab CE e Dependency-Track

Questo progetto dimostra come automatizzare il censimento delle librerie software e il rilevamento delle vulnerabilità (CVE) utilizzando solo strumenti Open Source.

**Documentazione:**
- [Setup e Configurazione](SETUP.md) — Docker, GitLab, variabili CI/CD, primo avvio
- [Pipeline DevSecOps](PIPELINE_GUIDE.md) — Guida completa alla pipeline, stage, troubleshooting
- [VEX Analysis Engine](VEX_ANALYSIS_ENGINE.md) — Motore 3 fasi Bedrock, strategia di analisi
- [Gestione Issue](ISSUES.md) — Come funziona, deduplicazione, workflow
- [Gestione Vulnerabilità](VULNERABILITY_HANDLING.md) — Casi d'uso, stati VEX, best practices

---

## 🏗️ 1. Requisiti di Sistema

* **Docker & Docker Compose** installati.
* **RAM:** Almeno 8GB dedicati a Docker (consigliati 10GB).
* **Network:** Le porte `80`, `8080` e `8081` devono essere libere.

---

## 🛠️ 2. Setup Rapido

### Passo 1: Avvio dei servizi

```bash
docker-compose up -d
```

### Passo 2: Recupero password GitLab

```bash
docker exec -it gitlab grep 'Password:' /etc/gitlab/initial_root_password
```

### Passo 3: Configurazione API Key Dependency-Track

1. Accedi a `http://localhost:8080` (User: `admin` / Pass: `admin`).
2. **Administration** > **Access Management** > **Teams** > **Automation**.
3. Copia la **API Key** generata.

### Passo 4: Variabili CI/CD

Configura nel gruppo GitLab (`demo-security`):

| Variabile | Valore |
|---|---|
| `DT_API_KEY` | API key DTrack |
| `AWS_ACCESS_KEY_ID` | IAM user |
| `AWS_SECRET_ACCESS_KEY` | IAM user |
| `AWS_DEFAULT_REGION` | `eu-west-1` |
| `GITLAB_PAT` | Personal Access Token (scope: `api`, `read_repository`, `write_repository`) |

---

## 🧪 3. I Progetti "Esca"

Crea due repository su GitLab:

### 🐍 Python (Django)

**File: `requirements.txt`**
```text
Django==2.2.12
PyYAML==3.12
Pillow==7.0.0
requests==2.25.0
```

### ☕ Java (Maven)

**File: `pom.xml`**
```xml
<dependency>
    <groupId>org.apache.logging.log4j</groupId>
    <artifactId>log4j-core</artifactId>
    <version>2.14.1</version>
</dependency>
```

---

## 🤖 4. Pipeline a 3 Stage

Il file `.gitlab-ci.yml` di ogni progetto applicativo include il template condiviso da `demo-security/vex-engine`:

```yaml
include:
  - project: 'demo-security/vex-engine'
    file: 'ci-template.yml'
    ref: main

stages:
  - scan
  - upload-bom
  - analyze
  - sync-vex
```

**Stage 1 — Scan**: Trivy genera `bom.json` (SBOM CycloneDX)  
**Stage 2 — Analyze**: Analisi AI con Bedrock, crea Issue, push `vex.json`  
**Stage 3 — Sync**: Upload SBOM + VEX su Dependency-Track

---

## 🧠 5. Bedrock VEX Analysis Engine

Il triage è completamente automatizzato tramite **AWS Bedrock (Claude)**:

- **Progetto condiviso `vex-engine`**: script di analisi centralizzati
- **Phase 1 — Strategist (Bedrock)**: estrae pattern di ricerca dalla descrizione CVE
- **Phase 2 — Scanner (locale)**: regex sul codice sorgente
- **Phase 3 — Auditor (Bedrock)**: analizza data flow e decide se è exploitabile
- **Delta Analysis**: CVE già analizzate vengono saltate
- **Issue GitLab**: automatiche per CVE `affected`, idempotenti

---

## 📊 6. Modalità di Analisi

| `VEX_MODE` | Analizza | Costo | Uso |
|---|---|---|---|
| `critical` (default) | HIGH + CRITICAL | ~$0.01 | Ogni push |
| `medium` | + MEDIUM | ~$0.03 | Pipeline schedulata |
| `full` | Tutte le CVE | ~$0.10 | Pipeline schedulata |

---

## 🎤 7. Demo Script

1. **Push del Codice**: fai un commit con una libreria vecchia
2. **Pipeline a 3 stage**: mostra i tre stage in GitLab CI
3. **Stage Analyze**: mostra le 3 fasi per una CVE
4. **Issue automatica**: mostra la Issue creata con reasoning AI
5. **Dependency-Track**: mostra come le CVE `not_affected` spariscono

---

## ⚙️ 8. Pipeline Schedulata

Per analizzare anche le CVE non critiche:

1. Vai su `http://localhost/demo-security/app-python/-/pipeline_schedules`
2. **New schedule**:
   - Description: `Weekly full VEX analysis`
   - Interval: `0 2 * * 0` (ogni domenica alle 2:00)
   - Target branch: `main`
3. Aggiungi variabile: `VEX_MODE = full`

---

## 📚 9. Documentazione Completa

| Documento | Contenuto |
|---|---|
| [SETUP.md](SETUP.md) | Setup Docker, GitLab, Runner, variabili CI/CD |
| [PIPELINE_GUIDE.md](PIPELINE_GUIDE.md) | Pipeline completa, modalità analisi, troubleshooting |
| [VEX_ANALYSIS_ENGINE.md](VEX_ANALYSIS_ENGINE.md) | Motore 3 fasi Bedrock, strategia di analisi |
| [ISSUES.md](ISSUES.md) | Gestione Issue GitLab, deduplicazione, workflow |
| [VULNERABILITY_HANDLING.md](VULNERABILITY_HANDLING.md) | Casi d'uso, stati VEX, best practices |

---

## ⚠️ 10. Troubleshooting

| Problema | Soluzione |
|---|---|
| Clone fallisce | Aggiungi `clone_url = "http://gitlab/"` nel `config.toml` |
| Runner stuck | Verifica "Run untagged jobs" su GitLab |
| DTrack non raggiungibile | Usa `host.docker.internal:8081` |
| Issue non creata | Verifica `GITLAB_PAT` con scope `api` |
| Bedrock access denied | Abilita i modelli in **Bedrock** → **Model access** |

---

## 📝 11. Note Tecniche

- **Formato SBOM/VEX**: CycloneDX 1.5
- **Modello Bedrock**: `eu.amazon.nova-2-lite-v1:0` (default)
- **Porte Docker**: `80` (GitLab), `8080` (DTrack UI), `8081` (DTrack API)
- **Network**: `talk-sbom-sbam_default` (subnet: `172.20.0.0/24`)
