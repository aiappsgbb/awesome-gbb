---
name: zava-workspace-deploy
description: >
  Deploy custom React/Vite SPAs to Azure Container Apps as static-serve
  containers. Builds the SPA, packages with nginx, generates Bicep + azure.yaml
  service entry. Handles API proxy to the Foundry-hosted control plane.
  Reusable for any custom web UI beyond threadlight-workspace-ui's generated
  reference UIs.
  USE FOR: deploy React app, deploy Vite SPA, static site on ACA, custom
  workspace deploy, Zava control plane UI, candidate portal, blueprint
  microsite, custom dashboard, nginx container, SPA hosting Azure.
  DO NOT USE FOR: generated threadlight workspace UIs (use threadlight-workspace-ui),
  full-stack app deployment (use threadlight-deploy), static marketing sites
  (use Azure Static Web Apps directly).
metadata:
  version: "1.0.0"
---

# Zava Workspace Deploy — Custom SPA → ACA

Deploy one or more React/Vite single-page applications to Azure Container
Apps as lightweight nginx-served containers with API proxy to the
Foundry-hosted backend.

> **When to use this vs `threadlight-workspace-ui`.** The workspace-ui skill
> generates a *reference* UI from a SPEC (case-list, inbox, dashboard shapes).
> This skill deploys *existing* custom-built SPAs — like Zava's control plane
> dashboard, candidate portal, or blueprint microsite — that are already
> written and need Azure hosting.

---

## What this skill does

1. **Build** — runs `npm run build` for each SPA, producing `dist/` bundles
2. **Package** — generates a Dockerfile with nginx serving the static bundle
3. **Proxy** — configures nginx to reverse-proxy `/api/*` requests to the
   Foundry-hosted backend (or any ACA service URL)
4. **Bicep** — generates an ACA app resource for the SPA container
5. **azure.yaml** — adds a service entry so `azd deploy` builds + pushes

---

## Prerequisites

| Need | Why |
|------|-----|
| A built React/Vite SPA with `npm run build` producing `dist/` | The app to deploy |
| An ACA environment (from `threadlight-deploy` or standalone Bicep) | Where the container runs |
| A backend API URL (Foundry endpoint or ACA service) | For the nginx proxy |

---

## Step 1: Generate the Dockerfile

```dockerfile
# Dockerfile.workspace
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --production=false
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

## Step 2: Generate nginx.conf with API proxy

```nginx
# nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback — all non-file routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API proxy — forward to the backend ACA service
    location /api/ {
        proxy_pass ${BACKEND_URL};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE — keep connections alive
    location /api/stream/ {
        proxy_pass ${BACKEND_URL};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
    }
}
```

> `${BACKEND_URL}` is injected via the ACA container env var at deploy
> time. Use `envsubst` in the Dockerfile entrypoint to template it.

## Step 3: Bicep for the SPA container

Uses the standard ACA app pattern from `azd-patterns`:

```bicep
// infra/modules/aca-workspace.bicep
param containerAppName string
param location string = resourceGroup().location
param acaEnvironmentId string
param containerImage string
param backendUrl string

resource workspace 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: acaEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          name: 'workspace'
          image: containerImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'BACKEND_URL', value: backendUrl }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
}

output fqdn string = workspace.properties.configuration.ingress.fqdn
```

## Step 4: azure.yaml service entry

```yaml
# In azure.yaml
services:
  workspace:
    host: containerapp
    project: ./web/client   # or ./web/portal, ./web/blueprint
    docker:
      path: Dockerfile.workspace
```

---

## Multi-SPA deployment (Zava pattern)

Zava has 3 SPAs. Deploy each as a separate service:

```yaml
services:
  control-plane-ui:
    host: containerapp
    project: ./web/client
    docker:
      path: Dockerfile.workspace
  candidate-portal:
    host: containerapp
    project: ./web/portal
    docker:
      path: Dockerfile.workspace
  blueprint:
    host: containerapp
    project: ./web/blueprint
    docker:
      path: Dockerfile.workspace
```

Each gets its own ACA app, its own ingress URL, and its own API proxy
configuration pointing to the shared backend.

---

## See Also

| Skill | Relationship |
|-------|-------------|
| [`threadlight-workspace-ui`](../threadlight-workspace-ui/) | Generates reference UIs from SPEC; this skill deploys custom-built ones |
| [`azd-patterns`](../azd-patterns/) | Bicep module library (ACA environment, volume mounts) |
| [`threadlight-deploy`](../threadlight-deploy/) | Phase 5-6 scaffolds the azd project this skill adds services to |
| [`foundry-observability`](../foundry-observability/) | App Insights for the backend (UIs don't need their own telemetry) |
