# Deployment-Anleitung für Google Cloud Run

## 1. Google Cloud Projekt erstellen
- Gehe zu [console.cloud.google.com](https://console.cloud.google.com/)
- Erstelle ein neues Projekt (z. B. "gbp-mcp-readonly")

## 2. APIs aktivieren (NUR NACH GOOGLE-FREIGABE!)
- Business Profile Performance API
- My Business Account Management API
- My Business Business Information API

## 3. OAuth-Client erstellen
- In Google Cloud Console: APIs & Services → Credentials → "Create Credentials" → OAuth client ID
- Anwendungstyp: **Webanwendung**
- Name: gbp-mcp-readonly
- Autorisierte JavaScript-Ursprünge: `https://DEINE-CLOUD-RUN-URL.a.run.app`
- Autorisierte Redirect-URIs: `https://DEINE-CLOUD-RUN-URL.a.run.app/oauth/callback`
- Client-ID und Client-Secret in **Secret Manager** speichern

## 4. Container deployen
```bash
gcloud builds submit --tag gcr.io/DEIN-PROJEKT/gbp-mcp-readonly\:latest
gcloud run deploy gbp-mcp-readonly --image gcr.io/DEIN-PROJEKT/gbp-mcp-readonly\:latest --platform managed --region europe-west1 --allow-unauthenticated=false --port 8080 --set-secrets GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID\:latest,GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET\:latest,MCP_BEARER_TOKEN=MCP_BEARER_TOKEN\:latest
