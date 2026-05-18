# Istruzioni Operative — Demo Talk

> ⚠️ Questo file contiene credenziali e token validi solo per l'ambiente locale
> della demo. Non committare mai questo file in un repository pubblico.

---

## 1. Credenziali ambiente locale

| Servizio | URL | Credenziale |
|---|---|---|
| Dependency-Track | `http://localhost:8080` | admin / uPTwNh0jsNXtYYhRTHPnO8pH6k7hSJX/iXlyNpRklG4= , key / odt_ShGTbXGy_3xSAnw967518TKmHyjn5vFNBEbsGCSoh|
| Dependency-Track API Key | — | `odt_8UBlLIh8_aobI0T5deRik9YgqOC2khj6rAFxdWnwx` |
| GitLab CE | `http://localhost` | root / uPTwNh0jsNXtYYhRTHPnO8pH6k7hSJX/iXlyNpRklG4= |

**Recupero password GitLab root**:
```bash
docker exec -it gitlab grep 'Password:' /etc/gitlab/initial_root_password
# oppure usa quella salvata: FQ9NiPkeGwyPJmuz1qPDzVUrjUDItvsrgN/RD053rGE=
```

---

## 2. Avvio dei servizi

```bash
docker-compose up -d
```

Attendi ~2 minuti per GitLab. Verifica con:
```bash
docker-compose ps
```

---

## 3. Registrazione Runner (Docker Executor)

```bash
docker exec -it gitlab-runner gitlab-runner register \
  --non-interactive \
  --url "http://gitlab/" \
  --token "{GITLAB_RUNNER_TOKEN}" \
  --executor "docker" \
  --docker-image "alpine:latest" \
  --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" \
  --docker-network-mode "talk-sbom-sbam_default" \
  --docker-extra-hosts "gitlab:172.20.0.10" \
  --docker-extra-hosts "host.docker.internal:host-gateway"
```

---

## 4. Setup progetto `vex-engine` su GitLab CE

Prima di poter usare la pipeline automatizzata, il motore di analisi deve essere
disponibile come progetto GitLab separato.

**Crea il progetto su GitLab CE**:
1. Vai su `http://localhost` → **New project** → **Create blank project**
2. Project name: `vex-engine` — Namespace: `root` — Visibility: Private
3. **Non** inizializzare con README

**Push del codice**:
```bash
cd vex-engine/
git init
git remote add origin http://root@localhost/demo-security/vex-engine.git
git add .
git commit -m "feat: initial vex-engine — Bedrock Edition"
git push -u origin main
```

---

## 5. Variabili CI/CD da configurare

Per ogni progetto applicativo (`app-python`, `app-java`), vai in
**Settings → CI/CD → Variables** e aggiungi:

| Variabile | Valore | Masked |
|---|---|---|
| `DT_API_KEY` | `odt_8UBlLIh8_...` | YES |
| `AWS_ACCESS_KEY_ID` | (dalla console AWS IAM) | YES |
| `AWS_SECRET_ACCESS_KEY` | (dalla console AWS IAM) | YES |
| `AWS_DEFAULT_REGION` | `us-east-1` | NO |
| `GITLAB_ACCESS_TOKEN` | (token con scope `api`) | YES |
| `CI_GIT_TOKEN` | (token con scope `read_repository` + `write_repository`) | YES |
| `BEDROCK_MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` | NO |

> **Suggerimento**: configura le variabili a livello di **Gruppo** in GitLab
> (Admin Area → Groups) per condividerle automaticamente tra tutti i progetti,
> evitando di inserirle progetto per progetto.

---

## 6. Come si scatena il triage (workflow normale)

Il triage è **completamente automatico**. Lo sviluppatore fa solo:

```bash
git add .
git commit -m "feat: aggiornamento dipendenze"
git push
```

La pipeline CI farà il resto:
1. Trivy genera lo SBOM (`bom.json`)
2. Il job `vex_ai_analysis` scarica il VEX baseline da Dependency-Track,
   chiama Bedrock per le CVE nuove, apre Issue per quelle `affected`,
   e pusha il `vex.json` arricchito con `[skip ci]`
3. Il job `dtrack_sync` carica SBOM e VEX su Dependency-Track

---

## 7. Esecuzione manuale degli script (debug / sviluppo del motore)

Se hai bisogno di eseguire il motore localmente per testare modifiche a
`vex-engine/`, puoi farlo direttamente dalla directory `vex-engine/`:

```bash
# Prerequisiti
pip install boto3 requests

# Analisi completa (tutte le CVE)
cd /path/to/progetto-applicativo
python3 /path/to/vex-engine/generate_vex.py vex.json vex.json --mode full

# Analisi rapida (solo CRITICAL/HIGH)
python3 /path/to/vex-engine/generate_vex.py vex.json vex.json --mode critical

# Analisi con apertura Issue GitLab (richiede GITLAB_ACCESS_TOKEN e CI_PROJECT_ID)
export GITLAB_ACCESS_TOKEN=xxx
export CI_PROJECT_ID=1
python3 /path/to/vex-engine/generate_vex.py vex.json vex.json --mode critical --create-issues
```

Le variabili AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`)
devono essere impostate nell'ambiente locale prima di eseguire.

---

## 8. Note di debug (Lessons Learned)

- **SSH GitLab**: porta `2222`. Esempio: `ssh://git@localhost:2222/root/progetto.git`
- **Clone loop**: se il runner clona da `localhost` invece di `gitlab`, aggiungi
  `clone_url = "http://gitlab"` nel `config.toml` del runner e riavvia il container.
- **Untagged Jobs**: se il job rimane "stuck", verifica che il runner abbia
  l'opzione "Run untagged jobs" attiva su GitLab (Admin Area → Runners).
- **Primo push**: Dependency-Track non conosce ancora il progetto — lo stage
  `analyze` stamperà un WARN e procederà comunque. Dal secondo push tutto funziona.
- **Modelli Bedrock**: ricordati di abilitare i modelli Anthropic su
  AWS Console → Bedrock → Model access prima del primo run.
