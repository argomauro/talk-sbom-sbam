# Setup e Configurazione

## 1. Requisiti di Sistema

- **Docker & Docker Compose** installati
- **RAM:** Almeno 8GB dedicati a Docker (consigliati 10GB)
- **Porte libere:** `80`, `8080`, `8081`

---

## 2. Avvio dei Servizi

```bash
docker-compose up -d
```

Attendi ~2 minuti per GitLab. Verifica con:
```bash
docker-compose ps
```

---

## 3. Credenziali di Default

| Servizio | URL | User | Password |
|---|---|---|---|
| GitLab CE | `http://localhost` | `root` | Recupera con: `docker exec -it gitlab grep 'Password:' /etc/gitlab/initial_root_password` |
| Dependency-Track UI | `http://localhost:8080` | `admin` | `admin` |
| Dependency-Track API | `http://localhost:8081` | — | — |

---

## 4. Configurazione Dependency-Track

### 4.1 API Key

1. Accedi a `http://localhost:8080` (admin/admin)
2. **Administration** → **Access Management** → **Teams** → **Automation**
3. Copia la **API Key** generata
4. Assicurati che il team abbia i permessi:
   - `BOM_UPLOAD`
   - `PROJECT_CREATION_UPLOAD`
   - `VEX_UPLOAD`

### 4.2 Sorgenti Vulnerabilità

Configura le API Key esterne in **Administration** → **Analyzers**:

- **NVD (NIST)**: [richiedi chiave](https://nvd.nist.gov/developers/request-an-api-key)
- **Sonatype OSS Index**: [registrati](https://ossindex.sonatype.org/)
- **GitHub Advisories**: Personal token con permessi base

---

## 5. Configurazione GitLab

### 5.1 Runner

1. Su GitLab (`http://localhost`), vai in **Admin Area** → **CI/CD** → **Runners**
2. Crea un nuovo **Instance Runner**, spunta **"Run untagged jobs"**
3. Copia l'**Authentication Token** (inizia con `glrt-`)

Registra il runner:
```bash
docker exec -it gitlab-runner gitlab-runner register \
  --non-interactive \
  --url "http://gitlab/" \
  --token "IL_TUO_TOKEN_GLRT" \
  --executor "docker" \
  --docker-image "alpine:latest" \
  --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" \
  --docker-network-mode "talk-sbom-sbam_default" \
  --docker-extra-hosts "gitlab:172.20.0.10" \
  --docker-extra-hosts "host.docker.internal:172.20.0.1"
```

Se il clone fallisce, aggiungi nel file `config.toml` del runner:
```toml
clone_url = "http://gitlab/"
```

### 5.2 Variabili CI/CD (a livello di Gruppo)

Vai in **Settings** → **CI/CD** → **Variables** e aggiungi:

| Variabile | Valore | Masked | Note |
|---|---|---|---|
| `DT_API_KEY` | API key DTrack | YES | |
| `AWS_ACCESS_KEY_ID` | IAM user | YES | |
| `AWS_SECRET_ACCESS_KEY` | IAM user | YES | |
| `AWS_DEFAULT_REGION` | `eu-west-1` | NO | |
| `BEDROCK_MODEL_ID` | `eu.amazon.nova-2-lite-v1:0` | NO | Opzionale |
| `GITLAB_PAT` | Personal Access Token | YES | Scope: `api`, `read_repository`, `write_repository` |

**Importante**: Configura le variabili a livello di **Gruppo** per condividerle tra tutti i progetti.

---

## 6. Setup Progetti su GitLab

### 6.1 Progetto `vex-engine`

1. **New project** → **Create blank project**
2. Project name: `vex-engine` — Namespace: `demo-security` — Visibility: Private
3. Non inizializzare con README

Push del codice:
```bash
cd vex-engine/
git init
git remote add origin http://root@localhost/demo-security/vex-engine.git
git add .
git commit -m "feat: initial vex-engine"
git push -u origin main
```

### 6.2 Progetto Applicativo (es. `app-python`)

1. **New project** → **Create blank project**
2. Project name: `app-python` — Namespace: `demo-security` — Visibility: Private
3. Inizializza con README

Aggiungi il file `.gitlab-ci.yml`:
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

# ... (vedi template per stage completi)
```

---

## 7. Primo Avvio

1. Fai `git push` su `app-python`
2. La pipeline si avvia automaticamente:
   - `scan`: Trivy genera `bom.json`
   - `upload-bom`: carica SBOM su DTrack
   - `analyze`: analisi AI con Bedrock
   - `sync-vex`: carica VEX su DTrack
3. Dopo il primo run, le CVE `not_affected` spariscono dalla dashboard

---

## 8. Pipeline Schedulata (Analisi Completa)

Per analizzare anche le CVE non critiche:

1. Vai su `http://localhost/demo-security/app-python/-/pipeline_schedules`
2. **New schedule**:
   - Description: `Weekly full VEX analysis`
   - Interval: `0 2 * * 0` (ogni domenica alle 2:00)
   - Target branch: `main`
3. Aggiungi variabile:
   - Key: `VEX_MODE` — Value: `full`
4. Salva

---

## 9. Troubleshooting

| Problema | Soluzione |
|---|---|
| Clone fallisce | Aggiungi `clone_url = "http://gitlab/"` nel `config.toml` |
| Runner stuck | Verifica "Run untagged jobs" su GitLab |
| DTrack non raggiungibile | Usa `host.docker.internal:8081` nel job |
| Issue non creata | Verifica `GITLAB_PAT` con scope `api` |
| Bedrock access denied | Abilita i modelli in **Bedrock** → **Model access** |
