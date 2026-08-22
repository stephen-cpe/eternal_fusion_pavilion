# Deployment Guide using Amazon Linux 2023

This guide provides step-by-step instructions to deploy the full Eternal
Fusion Pavilion application (Flask backend + FastAPI AI agent + React
frontend) on an AWS EC2 instance running Amazon Linux 2023.

The production environment uses Nginx as a reverse proxy, Gunicorn for
the Flask backend, uvicorn for the FastAPI AI agent, PostgreSQL 18 with
pgvector for the database, and local Ollama for embeddings. SSL is
provided by Certbot / Let's Encrypt via a free DuckDNS domain.

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
- OS: Amazon Linux 2023 (64-bit x86)
- Process Manager: systemd
- SSL: Certbot / Let's Encrypt via DuckDNS

## Instance Configuration

- AMI: Amazon Linux 2023 AMI 6.18 (64-bit x86)
- Instance type: t3.xlarge (4 vCPU, 16 GB RAM)
- Storage: 30 GB GP3 SSD

---

## Step 1: Launch EC2 Instance with Initialization Script

1. Navigate to EC2 Dashboard, then Launch instance.

2. Configure the instance:
   - **Name**: `efp-app`
   - **AMI**: Amazon Linux 2023 AMI 6.18 (64-bit x86)
   - **Instance type**: `t3.xlarge`
   - **Key pair**: Create new key pair (`efp-app.pem`) or use existing

3. Network settings - ensure these inbound rules are selected:
   - **Allow SSH traffic from** your IP
   - **Allow HTTP traffic from the internet** (port 80)
   - **Allow HTTPS traffic from the internet** (port 443)
   - Ensure **Auto-assign public IP** is enabled

4. Configure storage: 30 GB GP3 SSD

5. Advanced details:
   - User data: Paste the initialization script below

### Initialization Script (User Data)

Copy this script to the User data field during launch. It installs all
system packages (Python, Node.js, PostgreSQL, Nginx, Certbot), installs
the PostgreSQL server development headers (required for pgvector),
compiles and installs pgvector, initializes the database with the
pgvector extension enabled, configures firewall rules, installs Ollama,
and reboots.

```bash
#!/bin/bash
# Update system and install core dependencies
sudo dnf update -y
sudo dnf install -y python3.14 python3.14-pip python3.14-devel \
    nginx git postgresql18 postgresql18-server postgresql18-contrib \
    postgresql18-devel postgresql18-server-devel \
    firewalld certbot python3-certbot-nginx \
    gcc make

# Install Node.js 22 LTS
curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash -
sudo dnf install -y nodejs
sudo npm install -g npm@latest

# Set Python 3.14 as default
sudo alternatives --install /usr/bin/python python /usr/bin/python3.14 1
sudo alternatives --set python /usr/bin/python3.14

# Initialize PostgreSQL database
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create application database and user
sudo -u postgres psql << 'EOF'
CREATE USER efp_user WITH PASSWORD 'strongpassword';
CREATE DATABASE eternal_fusion_pavilion_database;
ALTER DATABASE eternal_fusion_pavilion_database OWNER TO efp_user;
GRANT ALL PRIVILEGES ON DATABASE eternal_fusion_pavilion_database TO efp_user;
\c eternal_fusion_pavilion_database
GRANT USAGE ON SCHEMA public TO efp_user;
GRANT CREATE ON SCHEMA public TO efp_user;
EOF

# Configure PostgreSQL to accept local password connections
sudo sed -i "s/^host\s*all\s*all\s*127\.0\.0\.1\/32\s*\w*/host    all             all             127.0.0.1\/32            md5/" /var/lib/pgsql/data/pg_hba.conf
sudo sed -i "s/^host\s*all\s*all\s*::1\/128\s*\w*/host    all             all             ::1\/128                 md5/" /var/lib/pgsql/data/pg_hba.conf
sudo sed -i "s/^local\s*all\s*all\s*peer/local   all             all                                     md5/" /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql

# Build and install pgvector
cd /tmp
git clone --branch v0.8.6 https://github.com/pgvector/pgvector.git
cd pgvector
sudo make PG_CONFIG=/usr/bin/pg_config
sudo make install PG_CONFIG=/usr/bin/pg_config

# Enable pgvector extension in the database
sudo -u postgres psql -d eternal_fusion_pavilion_database -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo systemctl restart postgresql

# Create application directory
sudo mkdir -p /var/www/efp
sudo chown ec2-user:ec2-user /var/www/efp

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama

# Set firewall rules
sudo systemctl start firewalld
sudo systemctl enable firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload

# Reboot to apply all updates
sudo reboot
```

Note: Change `'strongpassword'` to a more secure password in production.
The script reboots at the end. Wait 2-3 minutes after launch before
connecting via SSH to allow the initialization and reboot to complete.

6. Click Launch instance.

7. After launch: Note the **Public IPv4 address** from EC2 instance
   details. You will need this for DuckDNS and SSH.

---

## Step 2: Connect to EC2 and Deploy Application Code

Wait 2-3 minutes for the initialization script to finish and the instance
to reboot. Then connect via SSH:

```bash
ssh -i "efp-app.pem" ec2-user@ec2-xx-xx-xx-xx.compute-1.amazonaws.com
```

Replace with your actual EC2 Public DNS.

The initialization script changed PostgreSQL's authentication to require
passwords for all connections, including the local `postgres` superuser.
Before running database commands as `postgres`, temporarily switch to
peer authentication so the `postgres` user can connect without a
password:

```bash
sudo sed -i 's/^local   all             all                                     md5/local   all             all                                     peer/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql
```

Clone the repository:

```bash
cd /var/www/efp
git clone https://github.com/stephen-cpe/eternal_fusion_pavilion.git .
```

Initialize the database schema (the pgvector extension is already
enabled from the initialization script, so all tables including the
AI agent tables will be created successfully):

```bash
sudo -u postgres psql -d eternal_fusion_pavilion_database -f /var/www/efp/init_db.sql
```

Grant permissions to `efp_user` on all tables and sequences:

```bash
sudo -u postgres psql -d eternal_fusion_pavilion_database -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO efp_user; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO efp_user; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO efp_user; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO efp_user;"
```

Verify all 11 tables were created:

```bash
sudo -u postgres psql -d eternal_fusion_pavilion_database -c "\dt"
```

You should see all core tables (locations, rooms, reservations, etc.)
plus the AI agent tables (efp_knowledge_chunks, chat_threads,
guest_ai_memory).

Restore password authentication (important for security):

```bash
sudo sed -i 's/^local   all             all                                     peer/local   all             all                                     md5/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql
```

---

## Step 3: Configure Environment Variables

Create the `.env` file:

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

## Step 4: Configure Flask Backend

Create the Flask virtual environment and install dependencies:

```bash
cd /var/www/efp/backend
python3.14 -m venv venv
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
User=ec2-user
Group=nginx
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

## Step 5: Configure AI Agent

The initialization script already installed Ollama. Pull the embedding
model as the `ec2-user` (the User Data script runs as root, so the model
must be pulled again for the current user):

```bash
ollama pull qwen3-embedding:0.6b
ollama list
```

You should see `qwen3-embedding:0.6b` in the list.

Create a separate virtual environment for the AI agent:

```bash
cd /var/www/efp/backend/ai_agent
python3.14 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Ingest the knowledge base (embeds 35 documents into pgvector):

```bash
python -m rag.ingest_knowledge
```

This should report "Ingested 35 documents into efp_knowledge_chunks."

Verify:

```bash
PGPASSWORD=strongpassword psql -h localhost -U efp_user -d eternal_fusion_pavilion_database -c "SELECT COUNT(*) FROM efp_knowledge_chunks;"
```

Should return 35.

Deactivate the venv:

```bash
deactivate
```

Create the AI agent systemd service:

```bash
sudo nano /etc/systemd/system/efp-ai-agent.service
```

Add:

```ini
[Unit]
Description=Eternal Fusion Pavilion AI Agent (FastAPI)
After=network.target postgresql.service

[Service]
User=ec2-user
Group=nginx
WorkingDirectory=/var/www/efp/backend/ai_agent
EnvironmentFile=/var/www/efp/backend/.env
ExecStart=/var/www/efp/backend/ai_agent/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Step 6: Build Frontend

```bash
cd /var/www/efp/frontend
npm install
npm run build
```

Set permissions for Nginx:

```bash
sudo chown -R ec2-user:nginx /var/www/efp/frontend/dist
sudo find /var/www/efp/frontend/dist -type d -exec chmod 755 {} \;
sudo find /var/www/efp/frontend/dist -type f -exec chmod 644 {} \;
```

---

## Step 7: Configure DuckDNS (Free Domain)

1. Go to [DuckDNS.org](https://www.duckdns.org/) and log in (free, uses
   Google/GitHub).

2. In the subdomain field, enter `eternalfusionpavilion2` (creates
   `eternalfusionpavilion2.duckdns.org`).

3. Set **IP/URL** to your EC2 **Public IPv4 address** (from Step 1).

4. Click **Update IP**. It updates every 5 minutes.

5. Verify propagation (5-10 min):

```bash
dig eternalfusionpavilion2.duckdns.org
```

Should resolve to your EC2 IP.

Note: If you stop/start EC2, the IP changes unless using an Elastic IP
(recommended, free under AWS Free Tier).

---

## Step 8: Configure Nginx

Remove the default config and create the EFP config (HTTP only first;
Certbot will add HTTPS later):

```bash
sudo rm -f /etc/nginx/conf.d/default.conf
sudo nano /etc/nginx/conf.d/efp.conf
```

Add:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name eternalfusionpavilion2.duckdns.org;

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

Test and start Nginx:

```bash
sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx
```

If you get a `server_names_hash_bucket_size` error, edit
`/etc/nginx/nginx.conf`, uncomment `server_names_hash_bucket_size 64;`
inside the `http { }` block and change it to `128;`. Then re-run
`sudo nginx -t`.

---

## Step 9: Obtain SSL Certificate (Certbot / Let's Encrypt)

Run Certbot in two steps for reliability:

```bash
# Step 1: Obtain the certificate (without redirect)
sudo certbot --nginx -d eternalfusionpavilion2.duckdns.org --email youremail@address.com --agree-tos

# Step 2: Add the HTTP -> HTTPS redirect
sudo certbot --nginx -d eternalfusionpavilion2.duckdns.org --email youremail@address.com --agree-tos --redirect
```

Test auto-renewal:

```bash
sudo certbot renew --dry-run
```

Enable the auto-renewal timer. On Amazon Linux 2023, the timer is named
`certbot-renew.timer` (not `certbot.timer` as on Ubuntu):

```bash
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer
```

Verify the timer is active:

```bash
sudo systemctl status certbot-renew.timer
```

Should show `active (waiting)`.

---

## Step 10: Start All Services

Reload systemd and start all services:

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

## Step 11: Verify the Deployment

### 11.1 Check Service Status

```bash
sudo systemctl status efp-backend efp-ai-agent nginx postgresql
```

All should show `active (running)`.

### 11.2 Check Health Endpoints

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

### 11.3 Test the Full Application

Wait 5-10 minutes for DNS/SSL propagation, then visit:

- **Main site**: https://eternalfusionpavilion2.duckdns.org
- **Flask health**: https://eternalfusionpavilion2.duckdns.org/api/health
- **AI agent health**: https://eternalfusionpavilion2.duckdns.org/api/ai/health
- **AI agent chat** (test query):

```bash
curl -X POST https://eternalfusionpavilion2.duckdns.org/api/ai/graph \
  -H "Content-Type: application/json" \
  -d '{"question":"How much is the A5 Wagyu Ribeye?"}'
```

The AI agent should respond with the correct price ($165.00).

### 11.4 Test the Concierge Chat Widget

Open https://eternalfusionpavilion2.duckdns.org in a browser. The floating
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
sudo sed -i 's/^local   all             all                                     md5/local   all             all                                     peer/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql
sudo -u postgres psql -d eternal_fusion_pavilion_database -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo sed -i 's/^local   all             all                                     peer/local   all             all                                     md5/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql
sudo systemctl restart efp-ai-agent
```

**4. AI Agent health shows "knowledge_chunks: 0"**

The knowledge base was not ingested. Run:

```bash
cd /var/www/efp/backend/ai_agent
source venv/bin/activate
python -m rag.ingest_knowledge
```

**5. Ollama model not found**

The initialization script installs Ollama as root. Pull the model as
`ec2-user`:

```bash
ollama pull qwen3-embedding:0.6b
ollama list
```

**6. Permission Denied Errors (Nginx 5xx)**

```bash
sudo chown -R ec2-user:nginx /var/www/efp/frontend/dist
sudo find /var/www/efp/frontend/dist -type d -exec chmod 755 {} \;
sudo find /var/www/efp/frontend/dist -type f -exec chmod 644 {} \;
```

**7. Ollama not running**

```bash
systemctl status ollama
sudo systemctl start ollama
sudo systemctl enable ollama
ollama list
```

**8. DuckDNS IP changed after EC2 restart**

1. Go to DuckDNS.org and update the IP to the new public IPv4 address.
2. Re-run Certbot:
   ```bash
   sudo certbot --nginx -d eternalfusionpavilion2.duckdns.org --email youremail@address.com --agree-tos --redirect
   ```

For a stable IP, use an Elastic IP (free under AWS Free Tier).

**9. PostgreSQL password authentication failed for user "postgres"**

The initialization script changed pg_hba.conf to require passwords for
all connections. To run commands as the `postgres` superuser without a
password, temporarily switch to peer authentication:

```bash
sudo sed -i 's/^local   all             all                                     md5/local   all             all                                     peer/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql
```

Run your `sudo -u postgres psql` commands, then restore:

```bash
sudo sed -i 's/^local   all             all                                     peer/local   all             all                                     md5/' /var/lib/pgsql/data/pg_hba.conf
sudo systemctl restart postgresql
```

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
    +-- /api/ai/ --> 127.0.0.1:8000 (FastAPI AI Agent, uvicorn)
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