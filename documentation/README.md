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
4. **IMPORTANTE**: Assicurati che al team siano assegnati i permessi:
   - `BOM_UPLOAD`
   - `PROJECT_CREATION_UPLOAD` (necessario per `autoCreate=true`)

### Passo 4: Configurazione Sorgenti Vulnerabilità (API Keys)

Per un'analisi efficace e senza blocchi, Dependency-Track ha bisogno di connettersi ai database esterni. È fortemente consigliato configurare le API Key:

1. **NVD (NIST)**:
   - Richiedi una chiave qui: [NVD API Key Request](https://nvd.nist.gov/developers/request-an-api-key).
   - Inseriscila in **Administration** > **Analyzers** > **Vulnerability Analyzers** > **NVD**.
2. **Sonatype OSS Index**:
   - Registrati su [OSS Index](https://ossindex.sonatype.org/).
   - Inserisci email e token in **Administration** > **Analyzers** > **Vulnerability Analyzers** > **OSS Index**.
3. **GitHub Advisories**:
   - Crea un personal token su GitHub (permessi base).
   - Abilita il mirror in **Administration** > **Vulnerability Sources** > **GitHub Advisories**.

---

## 🧬 3. Configurazione Progetti su GitLab

### A. Registrazione del Runner

Per far girare le scansioni, GitLab ha bisogno di un "braccio operativo".

1. Su GitLab (`http://localhost`), vai in **Admin Area** > **CI/CD** > **Runners**.
2. Crea un nuovo **Instance Runner**, spunta **"Run untagged jobs"** e copia l'**Authentication Token** (inizia con `glrt-`).
3. Registralo nel container usando questo comando (sostituisci `TOKEN` e l'IP di GitLab):

```bash
# Trova l'IP di GitLab nella rete docker
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gitlab

# Registra
docker exec -it gitlab-runner gitlab-runner register \
  --non-interactive \
  --url "http://gitlab/" \
  --token "IL_TUO_TOKEN_GLRT" \
  --executor "docker" \
  --docker-image "alpine:latest" \
  --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" \
  --docker-network-mode "talk-sbom-sbam_default" \
  --docker-extra-hosts "gitlab:IP_GITLAB" \
  --docker-extra-hosts "host.docker.internal:host-gateway"
```

4. **Configurazione finale**: Se il clone fallisce, aggiungi `clone_url = "http://gitlab"` nel file `config.toml` del runner e riavvia il container.

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

## 🤖 5. Il Motore di Automazione (Pipeline a 3 Stage)

Il file `.gitlab-ci.yml` di ogni progetto applicativo include il template condiviso
da `root/vex-engine` e definisce tre stage in sequenza:

1. **Scan Stage** — Trivy scansiona il repository e genera `bom.json` (SBOM CycloneDX).
2. **Analyze Stage** — Il cuore del sistema (eseguito dal motore `vex-engine`):
   - Scarica il VEX baseline da Dependency-Track.
   - Per ogni CVE CRITICAL/HIGH non ancora analizzata chiama **AWS Bedrock (Claude)**
     in 3 fasi: Strategist → Scanner locale → Auditor.
   - Aggiorna `vex.json` con verdetti, confidence score e reasoning in linguaggio naturale.
   - Apre una **Issue GitLab** automatica per ogni CVE confermata `affected` (idempotente).
   - Committa e pusha il `vex.json` arricchito con `[skip ci]`.
3. **Sync Stage** — Carica SBOM e VEX arricchito su Dependency-Track, riducendo il
   rumore della dashboard eliminando i `not_affected`.

Lo sviluppatore non deve eseguire nessuno script manualmente: fa solo `git push`.

## 🧠 6. Bedrock VEX Analysis Engine

Il triage delle vulnerabilità è completamente automatizzato tramite **AWS Bedrock (Claude)**,
senza dipendere da IDE o azioni manuali dello sviluppatore:

- **Progetto condiviso `vex-engine`**: gli script di analisi (`generate_vex.py`,
  `llm_analyzer.py`) risiedono in un unico progetto GitLab e vengono inclusi da
  tutti i progetti applicativi via `include:` nel CI. Un aggiornamento al motore
  si propaga automaticamente a tutti i progetti.
- **Phase 1 — Strategist (Bedrock)**: Claude interpreta la descrizione della CVE
  e genera i pattern di ricerca specifici — zero configurazione manuale per nuove CVE.
- **Phase 2 — Scanner (locale)**: regex sul codice sorgente, nessun costo API,
  produce code snippet con ±30 righe di contesto.
- **Phase 3 — Auditor (Bedrock)**: Claude analizza il data flow nei snippet e
  produce un verdetto (`affected` / `not_affected`) con confidence score (0-100%)
  e reasoning tecnico dettagliato.
- **Delta Analysis**: le CVE già analizzate vengono saltate — solo le nuove
  vengono mandate a Bedrock, con costo per pipeline inferiore a $0.01.
- **VEX-as-Code**: il `vex.json` con i verdetti AI è versionato nel repository,
  costituendo l'audit trail immutabile delle decisioni di sicurezza.

---

## 🎤 7. Demo Script (Cosa mostrare)

1. **Push del Codice**: fai un commit con una libreria vecchia (`PyYAML 3.12`, `log4j 2.14.1`).
2. **Pipeline a 3 stage**: mostra i tre stage in GitLab CI — scan → analyze → sync.
3. **Stage Analyze in dettaglio**: apri il log del job `vex_ai_analysis` e mostra
   le 3 fasi per una CVE (Strategist genera i pattern, Scanner trova il codice,
   Auditor decide se è exploitabile con reasoning).
4. **Issue automatica**: mostra la Issue di sicurezza creata automaticamente con
   il reasoning dell'AI, il file:riga come evidence e la label `cve:CVE-XXXX-XXXX`.
5. **Dependency-Track aggiornato**: mostra come le CVE `not_affected` spariscono
   dalla dashboard dopo l'upload del VEX arricchito.


---

### ⚠️ Note per il Debug (Lessons Learned)

*   **SSH GitLab**: Se usi SSH da locale, ricorda che la porta è la `2222`. Esempio: `ssh://git@localhost:2222/root/progetto.git`.
*   **Networking Job**: I container dei job sono isolati. Assicurati di usare `extra_hosts` nella config del runner per risolvere il nome `gitlab`.
*   **Accesso all'Host**: Per raggiungere Dependency-Track o altri servizi sul Mac dal pipeline, usa sempre `host.docker.internal`.
*   **Clone Loop**: Se il runner cerca di clonare da `localhost`, usa `clone_url = "http://gitlab"` nel `config.toml`.
*   **Untagged Jobs**: Se il job rimane "stuck", verifica che il runner abbia l'opzione "Run untagged jobs" attiva su GitLab.

---
