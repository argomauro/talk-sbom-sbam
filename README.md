# 🚀 Demo: DevSecOps Zero-Budget

## Censimento SBOM e Monitoraggio CVE con GitLab CE e Dependency-Track

Questo progetto dimostra come automatizzare il censimento delle librerie software e il rilevamento delle vulnerabilità (CVE) utilizzando solo strumenti Open Source.
https://dependencytrack.org/

Beyond the SBOM: VEX & AI Analysis" Non tutte le vulnerabilità sono reali. Vedremo come utilizzare modelli linguistici (LLM) per analizzare la 'reachability' del codice vulnerabile e generare automaticamente documenti VEX, riducendo i falsi positivi dell'80% senza intervento manuale.
---

## 🏗️ 1. Requisiti di Sistema

* **Docker & Docker Compose** installati.
* **RAM:** Almeno 8GB dedicati a Docker (consigliati 10GB).
* **Network:** Le porte `80`, `8080` e `8081` devono essere libere.

---

## 🛠️ 2. Setup dell'Ambiente

### Passo 1: Avvio dei servizi

Crea un file `docker-compose.yml` (usa quello fornito nella conversazione precedente) e lancia:

```bash
docker-compose up -d

```

### Passo 2: Recupero password GitLab

GitLab impiega qualche minuto per avviarsi. Una volta pronto, recupera la password per l'utente `root`:

```bash
docker exec -it gitlab grep 'Password:' /etc/gitlab/initial_root_password

```

### Passo 3: Configurazione API Key Dependency-Track

1. Accedi a `http://localhost:8080` (User: `admin` / Pass: `admin`).
2. Vai in **Administration** > **Access Management** > **Teams** > **Automation**.
3. Copia la **API Key** generata.

---

## 🧬 3. Configurazione Progetti su GitLab

### A. Registrazione del Runner

Per far girare le scansioni, GitLab ha bisogno di un "braccio operativo".

1. Su GitLab (`http://localhost`), vai in **Admin Area** > **CI/CD** > **Runners**.
2. Crea un nuovo **Project Runner** e copia il **Registration Token**.
3. Registralo nel container:

```bash
docker exec -it gitlab-runner gitlab-runner register \
  --non-interactive \
  --url "http://gitlab/" \
  --registration-token "IL_TUO_TOKEN" \
  --executor "docker" \
  --docker-image "aquasec/trivy:latest" \
  --docker-network-mode "host"

```

### B. Variabili CI/CD

In ogni progetto (o nel gruppo), vai in **Settings** > **CI/CD** > **Variables** e aggiungi:

* `DT_API_KEY`: La chiave copiata da Dependency-Track.

---

## 🧪 4. I Progetti "Esca" (Esempi Vulnerabili)

Crea tre repository e aggiungi questi file per scatenare le CVE:

### 🐍 Python (Django)

*File: `requirements.txt*`

```text
Django==2.2.12
PyYAML==3.12

```

### ☕ Java (Maven)

*File: `pom.xml*`

```xml
<dependency>
    <groupId>org.apache.logging.log4j</groupId>
    <artifactId>log4j-core</artifactId>
    <version>2.14.1</version> </dependency>

```

### 📦 Node.js

*File: `package.json*`

```json
{
  "dependencies": {
    "lodash": "4.17.4"
  }
}

```

---

## 🤖 5. Il Motore di Automazione

In ogni repository, crea il file `.gitlab-ci.yml`:

```yaml
stages:
  - scan

scan_and_upload:
  stage: scan
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  script:
    # 1. Genera SBOM
    - trivy fs --format cyclonedx --output bom.json .
    # 2. Invia a Dependency-Track
    - |
      curl -X "POST" "http://localhost:8081/api/v1/bom" \
           -H 'Content-Type: multipart/form-data' \
           -H "X-Api-Key: $DT_API_KEY" \
           -F "projectName=$CI_PROJECT_NAME" \
           -F "projectVersion=$CI_COMMIT_BRANCH" \
           -F "autoCreate=true" \
           -F "bom=@bom.json"

```

---

## 🎤 6. Demo Script (Cosa mostrare)

1. **Push del Codice:** Fai un commit su GitLab con una libreria vecchia.
2. **Pipeline in corso:** Mostra il log del Runner che usa `Trivy`.
3. **Analisi:** Apri Dependency-Track. Mostra il progetto appena creato.
4. **Esplosione CVE:** Mostra la tab "Vulnerabilities" e spiega che il sistema ha trovato le falle incrociando i dati con il database NVD.
5. **Ricerca Globale:** Cerca "Log4j" nella barra globale di Dependency-Track per far vedere come trovi istantaneamente tutti i progetti aziendali a rischio.

---

### ⚠️ Note per il Debug

* Se il Runner non raggiunge GitLab, controlla che nel file `config.toml` del runner l'URL sia corretto (usa l'IP locale se `localhost` fallisce).
* Se Dependency-Track non riceve il file, verifica che la porta `8081` sia raggiungibile dal Runner.

---
