# 🛠️ Istruzioni Operative (Talk Demo)

### 1. Database & Credenziali
* **Dependency-Track API Key:** `odt_8UBlLIh8_aobI0T5deRik9YgqOC2khj6rAFxdWnwx`
* **GitLab Root Password:** `FQ9NiPkeGwyPJmuz1qPDzVUrjUDItvsrgN/RD053rGE=`

### 2. Registrazione Runner (Docker Executor)
Assicurati che il runner sia registrato per eseguire i job della pipeline:

```bash
docker exec -it gitlab-runner gitlab-runner register \
  --non-interactive \
  --url "http://gitlab/" \
  --token "glrt-epZ_SiRX32tpojlE9M4_-W86MQp0OjEKdToxCw.01.121pu8tt4" \
  --executor "docker" \
  --docker-image "alpine:latest" \
  --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" \
  --docker-network-mode "talk-sbom-sbam_default" \
  --docker-extra-hosts "gitlab:172.20.0.10" \
  --docker-extra-hosts "host.docker.internal:host-gateway"
```

### 3. Workflow VEX Triage (Antigravity)
Dall'IDE Antigravity, esegui l'arricchimento offline:

```bash
python3 .agent/skills/vex-triage/scripts/generate_vex.py
```

### 4. Push & Sync
Dopo l'arricchimento, sincronizza tutto con un unico comando:

```bash
git add vex.json && git commit -m "docs: AI-enriched VEX analysis" && git push
```