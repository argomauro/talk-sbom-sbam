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

## 🤖 5. Il Motore di Automazione (CI/CD Consolidato)

In ogni repository, il file `.gitlab-ci.yml` gestisce l'intero ciclo di vita della sicurezza in due stage atomici:

1. **Scan Stage**: Genera lo SBOM (CycloneDX) usando Trivy.
2. **Sync Stage**: 
   - Carica lo SBOM su Dependency-Track.
   - Carica il VEX arricchito (se modificato dallo sviluppatore/IA).
   - Scarica e sincronizza la baseline VEX dal server se non ci sono modifiche locali.

Questo garantisce che il repository git sia sempre la "Single Source of Truth" per lo stato di sicurezza del progetto.

## 🧠 6. AI-Native VEX Triage (Antigravity Analyst)

L'integrazione con **Antigravity** è ora **AI-Native**, eliminando la necessità di configurazioni manuali o pattern hardcoded:

1. **Dynamic CVE Interpretation**: L'IA legge la descrizione della vulnerabilità (CVE/GHSA) direttamente dal VEX e "capisce" quali funzioni o pattern pericolosi cercare.
2. **Analisi Semantica Context-Aware**: Oltre a cercare pattern (es. `yaml.load()`), l'IA analizza il contesto per distinguere se il codice è in una funzione mai chiamata, se è commentato o se è effettivamente raggiungibile.
3. **Evidence-Based Justification**: Genera automaticamente lo stato `not_affected` con giustificazioni tecniche dettagliate e riferimenti precisi a `file:linea` nel file `vex.json`.
4. **Zero-Configuration Scalability**: Funziona su qualsiasi nuovo CVE senza dover aggiornare gli script di analisi, rendendo il triage scalabile all'infinito.

---

## 🎤 7. Demo Script (Cosa mostrare)

1. **Push del Codice:** Fai un commit con una libreria vecchia.
2. **Pipeline Consolidata:** Mostra lo stage `sync` che carica SBOM e gestisce il VEX.
3. **AI-Native Triage**: Apri l'IDE, lancia lo script di arricchimento e mostra come l'IA "legge" la CVE di PyYAML, scansiona il codice, rileva che `unsafe_processor()` è commentato e aggiorna il `vex.json` con precisione millimetrica.
4. **Final Sync:** Pusha il VEX arricchito e mostra su Dependency-Track come le vulnerabilità passano a "Not Affected".


---

### ⚠️ Note per il Debug (Lessons Learned)

*   **SSH GitLab**: Se usi SSH da locale, ricorda che la porta è la `2222`. Esempio: `ssh://git@localhost:2222/root/progetto.git`.
*   **Networking Job**: I container dei job sono isolati. Assicurati di usare `extra_hosts` nella config del runner per risolvere il nome `gitlab`.
*   **Accesso all'Host**: Per raggiungere Dependency-Track o altri servizi sul Mac dal pipeline, usa sempre `host.docker.internal`.
*   **Clone Loop**: Se il runner cerca di clonare da `localhost`, usa `clone_url = "http://gitlab"` nel `config.toml`.
*   **Untagged Jobs**: Se il job rimane "stuck", verifica che il runner abbia l'opzione "Run untagged jobs" attiva su GitLab.

---
