DT_API_KEY=odt_8UBlLIh8_aobI0T5deRik9YgqOC2khj6rAFxdWnwx
gitlab-runner register  --url http://localhost  --token glrt-epZ_SiRX32tpojlE9M4_-W86MQp0OjEKdToxCw.01.121pu8tt4

GITLAB ROOT
root/FQ9NiPkeGwyPJmuz1qPDzVUrjUDItvsrgN/RD053rGE=

docker exec -it gitlab-runner gitlab-runner register \
  --non-interactive \
  --url "http://gitlab/" \
  --registration-token "glrt-epZ_SiRX32tpojlE9M4_-W86MQp0OjEKdToxCw.01.121pu8tt4" \
  --executor "docker" \
  --docker-image "aquasec/trivy:latest" \
  --docker-network-mode "host"


  docker exec -it gitlab-runner gitlab-runner register \
  --non-interactive \
  --url "http://gitlab" \
  --token "glrt-epZ_SiRX32tpojlE9M4_-W86MQp0OjEKdToxCw.01.121pu8tt4" \
  --executor "docker" \
  --docker-image "alpine:latest" \
  --docker-volumes "/var/run/docker.sock:/var/run/docker.sock" \
  --docker-network-mode "talk-sbom-sbam_default" \
  --docker-extra-hosts "gitlab:172.20.0.2" \
  --docker-extra-hosts "host.docker.internal:host-gateway"