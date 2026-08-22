# Deployment Guide on AWS EC2 using Ubuntu

This guide provides step-by-step instructions to deploy the full Eternal
Fusion Pavilion application (Flask backend + FastAPI AI agent + React
frontend) on an AWS EC2 instance running Ubuntu 26.04 LTS.

The production environment uses Nginx as a reverse proxy, Gunicorn for
the Flask backend, uvicorn for the FastAPI AI agent, PostgreSQL 18 with
pgvector for the database, and local Ollama for embeddings.

## Technology Stack

- Backend: Flask (Python 3.14+) on port 5000
- AI Agent: FastAPI + LangGraph on port 8000
- Frontend: React (Vite build) served by Nginx
- Database: PostgreSQL 18 with pgvector extension
- Embeddings: Local Ollama (qwen3-embedding:0.6b)
- Chat LLM: Ollama Cloud (deepseek-v4-flash:cloud)
- WSGI Server: Gunicorn (Flask)
- ASGI Server: uvicorn (FastAPI agent)
- Web/Proxy Server: Nginx
- OS: Ubuntu 26.04 LTS
- Process Manager: systemd
- SSL: Certbot / Let's Encrypt via DuckDNS

## Storage Requirements

30 GB SSD is sufficient for this project. The breakdown:
- OS + system packages: ~5 GB
- PostgreSQL database: ~1 GB
- Ollama embedding model: ~0.6 GB
- Node.js + npm + React build: ~1 GB
- Python venvs (2x): ~2 GB
- Application code + logs: ~1 GB
- Remaining free space: ~19 GB

---

## Step 1: Launch EC2 Instance

1. In the AWS console, launch a new EC2 instance:
   - **Name**: `efp-app`
   - **AMI**: Ubuntu Server 26.04 LTS (64-bit x86)
   - **Instance type**: `t3.xlarge` (4 vCPU, 16 GB RAM)
   - **Key pair**: Create new key pair (`efp-app.pem`) or use existing
   - **Storage**: 30 GB GP3 SSD

2. **Network settings** - configure the Security Group with inbound rules:
   - **SSH** (Port 22) - From your IP
   - **HTTP** (Port 80) - From Anywhere (0.0.0.0/0, ::/0)
   - **HTTPS** (Port 443) - From Anywhere (0.0.0.0/0, ::/0)

3. Ensure **Auto-assign public IP** is enabled.

4. Click **Launch instance**.

5. After launch, note the **Public IPv4 address** (e.g., `3.123.45.67`).

---

## Step 2: Connect and Install System Packages

Connect to your EC2 instance via SSH:

```bash
ssh -i "efp-app.pem" ubuntu@ec2-xx-xx-xx-xx.compute-1.amazonaws.com
```

Replace with your actual EC2 Public DNS.

Update the system and install all required packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip nodejs npm postgresql nginx git certbot python3-certbot-nginx build-essential
```

Configure the firewall:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
sudo ufw status verbose
```

---

## Step 3: Install pgvector Extension

pgvector must be compiled from source on Ubuntu.

```bash
# Install build dependencies
sudo apt install -y postgresql-server-dev-all make g++

# Clone and build pgvector
cd /tmp
git clone --branch v0.8.6 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

Verify the files were installed:

```bash
ls /usr/share/postgresql/18/extension/vector*
ls /usr/lib/postgresql/18/lib/vector.so
```

Restart PostgreSQL to load the new shared library:

```bash
sudo systemctl restart postgresql
```

---

## Step 4: Set Up PostgreSQL Database

Start and enable PostgreSQL:

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

Create the database and user:

```bash
sudo -u postgres psql
```

Run the following SQL commands:

```sql
CREATE USER efp_user WITH PASSWORD 'strongpassword';
CREATE DATABASE eternal_fusion_pavilion_database;
ALTER DATABASE eternal_fusion_pavilion_database OWNER TO efp_user;
GRANT ALL PRIVILEGES ON DATABASE eternal_fusion_pavilion_database TO efp_user;

-- Connect to the database and enable pgvector
\c eternal_fusion_pavilion_database
CREATE EXTENSION IF NOT EXISTS vector;

-- Grant schema permissions to efp_user
GRANT USAGE ON SCHEMA public TO efp_user;
GRANT CREATE ON SCHEMA public TO efp_user;

\q
```

---

## Step 5: Deploy Application Code

Clone the repository:

```bash
cd /var/www
sudo mkdir -p efp
sudo chown ubuntu:ubuntu efp
cd efp
git clone https://github.com/stephen-cpe/eternal_fusion_pavilion.git .
```

Initialize the database schema (run as postgres superuser):

```bash
sudo -u postgres psql -d eternal_fusion_pavilion_database -f /var/www/efp/init_db.sql
```

Verify the tables were created:

```bash
sudo -u postgres psql -d eternal_fusion_pavilion_database -c "\dt"
```

You should see all core tables (locations, rooms, reservations, etc.)
plus the AI agent tables (efp_knowledge_chunks, chat_threads,
guest_ai_memory).

---

## Step 6: Configure Environment Variables

Create the `.env` file in the backend directory:

```bash
nano /var/www/efp/backend/.env
```

Add the following content (replace placeholder values):

```ini
DB_HOST=localhost
DB_PORT=5432
DB_NAME=eternal_fusion_pavilion_database
DB_USER=efp_user
DB_PASSWORD=strongpassword
SECRET_KEY=generate_a_very_secret_key_here
API_PREFIX=/api
FLASK_ENV=production
FLASK_DEBUG=False

# AI Agent
AI_MOCK=false
OLLAMA_CLOUD_BASE_URL=https://ollama.com
OLLAMA_CLOUD_API_KEY=your_ollama_cloud_api_key_here
CHAT_MODEL=deepseek-v4-flash:cloud
```

---

## Step 7: Configure Flask Backend

Create the Flask virtual environment and install dependencies:

```bash
cd /var/www/efp/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

Create the Gunicorn systemd service:

```bash
sudo nano /etc/systemd/system/efp-backend.service
```

Add:

```ini
[Unit]
Description=Eternal Fusion Pavilion Flask Backend
After=network.target postgresql.service

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/efp/backend
EnvironmentFile=/var/www/efp/backend/.env
ExecStart=/var/www/efp/backend/venv/bin/gunicorn \
          --workers 3 \
          --bind 127.0.0.1:5000 \
          --timeout 120 \
          "app:create_app()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Step 8: Install Ollama and Configure AI Agent

### 8.1 Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Pull the embedding model:

```bash
ollama pull qwen3-embedding:0.6b
```

Verify it is available:

```bash
ollama list
```

You should see `qwen3-embedding:0.6b` in the list.

### 8.2 Configure AI Agent Virtual Environment

Create a separate virtual environment for the AI agent:

```bash
cd /var/www/efp/backend/ai_agent
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

### 8.3 Ingest the Knowledge Base

```bash
cd /var/www/efp/backend/ai_agent
source venv/bin/activate
python -m rag.ingest_knowledge
```

This should report "Ingested 35 documents into efp_knowledge_chunks."

Verify:

```bash
PGPASSWORD=strongpassword psql -h localhost -U efp_user -d eternal_fusion_pavilion_database -c "SELECT COUNT(*) FROM efp_knowledge_chunks;"
```

Should return 35.

### 8.4 Create AI Agent systemd Service

```bash
sudo nano /etc/systemd/system/efp-ai-agent.service
```

Add:

```ini
[Unit]
Description=Eternal Fusion Pavilion AI Agent (FastAPI)
After=network.target postgresql.service

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/efp/backend/ai_agent
EnvironmentFile=/var/www/efp/backend/.env
ExecStart=/var/www/efp/backend/ai_agent/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Step 9: Build Frontend

```bash
cd /var/www/efp/frontend
sudo npm install -g n
sudo n lts
hash -r
sudo npm install -g npm@latest
hash -r
npm install
npm run build
```

Set permissions for Nginx:

```bash
sudo chown -R ubuntu:www-data /var/www/efp/frontend/dist
sudo find /var/www/efp/frontend/dist -type d -exec chmod 755 {} \;
sudo find /var/www/efp/frontend/dist -type f -exec chmod 644 {} \;
```

---

## Step 10: Configure DuckDNS (Free Domain)

1. Go to [DuckDNS.org](https://www.duckdns.org/) and log in (free, uses
   Google/GitHub).

2. In the subdomain field, enter `eternalfusionpavilion` (creates
   `eternalfusionpavilion.duckdns.org`).

3. Set **IP/URL** to your EC2 **Public IPv4 address**.

4. Click **Update IP**. It updates every 5 minutes.

5. Verify propagation (5-10 min):

```bash
dig eternalfusionpavilion.duckdns.org
```

Should resolve to your EC2 IP.

Note: If you stop/start EC2, the IP changes unless using an Elastic IP
(recommended, free under AWS Free Tier).

---

## Step 11: Configure Nginx

Create the Nginx configuration (HTTP only first; Certbot will add HTTPS
later):

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo nano /etc/nginx/sites-available/efp
```

Add:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name eternalfusionpavilion.duckdns.org;

    # React app root
    root /var/www/efp/frontend/dist;
    index index.html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # AI Agent proxy (must come before /api/ to avoid being swallowed)
    location /api/ai/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support: disable buffering, increase timeout
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
    }

    # Flask API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static file cache
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/efp /etc/nginx/sites-enabled/
```

Test and start Nginx:

```bash
sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx
```

If you get a `server_names_hash_bucket_size` error:

```bash
sudo nano /etc/nginx/nginx.conf
```

Inside the `http { ... }` block, uncomment or add:

```
server_names_hash_bucket_size 128;
```

Then re-run `sudo nginx -t`.

---

## Step 12: Obtain SSL Certificate (Certbot / Let's Encrypt)

Run Certbot in two steps for reliability:

```bash
# Step 1: Obtain the certificate (without redirect)
sudo certbot --nginx -d eternalfusionpavilion.duckdns.org --email youremail@address.com --agree-tos

# Step 2: Add the HTTP -> HTTPS redirect
sudo certbot --nginx -d eternalfusionpavilion.duckdns.org --email youremail@address.com --agree-tos --redirect
```

Test auto-renewal:

```bash
sudo certbot renew --dry-run
```

Enable the renewal timer:

```bash
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer
```

---

## Step 13: Start All Services

Reload systemd and start all three services:

```bash
sudo systemctl daemon-reload

# Start Flask backend
sudo systemctl enable efp-backend
sudo systemctl start efp-backend

# Start AI agent
sudo systemctl enable efp-ai-agent
sudo systemctl start efp-ai-agent

# Restart Nginx to pick up SSL config
sudo nginx -t
sudo systemctl restart nginx
```

---

## Step 14: Verify the Deployment

### 14.1 Check Service Status

```bash
sudo systemctl status efp-backend efp-ai-agent nginx postgresql
```

All should show `active (running)`.

### 14.2 Check Health Endpoints

```bash
# Flask backend
curl http://127.0.0.1:5000/api/health

# AI agent
curl http://127.0.0.1:8000/api/ai/health
```

The AI agent health check should return:

```json
{
  "service": "ai_agent",
  "status": "healthy",
  "pgvector": "0.8.6",
  "knowledge_chunks": 35,
  "database": "connected"
}
```

### 14.3 Test the Full Application

Wait 5-10 minutes for DNS/SSL propagation, then visit:

- **Main site**: https://eternalfusionpavilion.duckdns.org
- **Flask health**: https://eternalfusionpavilion.duckdns.org/api/health
- **AI agent health**: https://eternalfusionpavilion.duckdns.org/api/ai/health
- **AI agent chat** (test query):
  ```bash
  curl -X POST https://eternalfusionpavilion.duckdns.org/api/ai/graph \
    -H "Content-Type: application/json" \
    -d '{"question":"How much is the A5 Wagyu Ribeye?"}'
  ```

The AI agent should respond with the correct price ($165.00).

### 14.4 Test the Concierge Chat Widget

Open https://eternalfusionpavilion.duckdns.org in a browser. The floating
concierge chat button should appear in the bottom-right corner. Click it
and type a question to verify the full stack is working.

---

## Service Management and Troubleshooting

### Managing Services

```bash
# Check status of all services
sudo systemctl status efp-backend efp-ai-agent nginx postgresql

# Restart individual services
sudo systemctl restart efp-backend
sudo systemctl restart efp-ai-agent
sudo systemctl restart nginx

# View logs
sudo journalctl -u efp-backend -f
sudo journalctl -u efp-ai-agent -f
sudo tail -f /var/log/nginx/error.log
```

### Common Issues

**1. Nginx 502 Bad Gateway**

The backend or AI agent is not running. Check:

```bash
sudo systemctl status efp-backend
sudo systemctl status efp-ai-agent
```

If a service failed, check its logs:

```bash
sudo journalctl -u efp-backend --no-pager -n 50
sudo journalctl -u efp-ai-agent --no-pager -n 50
```

**2. AI Agent returns 503 (LLM unavailable)**

The Ollama Cloud model may be temporarily overloaded. Wait a moment and
retry. Verify your `OLLAMA_CLOUD_API_KEY` in `/var/www/efp/backend/.env`
is correct.

**3. AI Agent health shows "pgvector: not installed"**

The pgvector extension was not created in the database. Run:

```bash
sudo -u postgres psql -d eternal_fusion_pavilion_database -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Then restart the AI agent:

```bash
sudo systemctl restart efp-ai-agent
```

**4. AI Agent health shows "knowledge_chunks: 0"**

The knowledge base was not ingested. Run:

```bash
cd /var/www/efp/backend/ai_agent
source venv/bin/activate
python -m rag.ingest_knowledge
```

**5. Permission Denied Errors (Nginx 5xx)**

```bash
# Verify home directory permissions
ls -ld /var/www/efp/frontend/dist

# Should show ubuntu:www-data as owner:group
sudo chown -R ubuntu:www-data /var/www/efp/frontend/dist
sudo find /var/www/efp/frontend/dist -type d -exec chmod 755 {} \;
sudo find /var/www/efp/frontend/dist -type f -exec chmod 644 {} \;
```

**6. Ollama not running**

```bash
# Check if Ollama is running
systemctl status ollama

# Start it if not
sudo systemctl start ollama
sudo systemctl enable ollama

# Verify the model is available
ollama list
```

**7. DuckDNS IP changed after EC2 restart**

If your EC2 instance restarts and gets a new public IP:

1. Go to DuckDNS.org and update the IP to the new public IPv4 address.
2. Re-run Certbot to update the SSL certificate:
   ```bash
   sudo certbot --nginx -d eternalfusionpavilion.duckdns.org --email youremail@address.com --agree-tos --redirect
   ```

For a stable IP, use an Elastic IP (free under AWS Free Tier).

---

## Architecture Summary

```
Internet
    |
    v
[Nginx :80/:443] -- SSL via Certbot/Let's Encrypt
    |
    +-- / (static files) --> /var/www/efp/frontend/dist (React build)
    |
    +-- /api/ai/ --> 127.0.0.1:8000 (FastAI AI Agent, uvicorn)
    |                   |
    |                   +-- Local Ollama :11434 (embeddings)
    |                   +-- Ollama Cloud (chat LLM)
    |                   +-- PostgreSQL (pgvector, guest_ai_memory)
    |
    +-- /api/ --> 127.0.0.1:5000 (Flask Backend, Gunicorn)
                     |
                     +-- PostgreSQL (reservations, customers, etc.)
```

Three systemd services:
- `efp-backend.service` - Flask + Gunicorn (port 5000)
- `efp-ai-agent.service` - FastAPI + uvicorn (port 8000)
- `ollama.service` - Local Ollama (port 11434, auto-installed)

---