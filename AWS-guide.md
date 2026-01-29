# **Deployment Guide using Amazon Linux 2023**

## Disclaimer

* This project is intended for **educational, testing, and experimentation purposes only**.
* **Not suitable for production use**.
* This guide and project will not be updated regularly.
* Use at your own risk. No warranties, guarantees, or support are provided.

---

## **Step 1: Launch EC2 Instance (Amazon Linux)**

Deploy the application server with PostgreSQL on cost-effective ARM architecture.

### **1.1 Create Security Group**

1. Navigate to **EC2 Dashboard** → **Security Groups** → **Create security group**
2. Configure:
   - **Security group name**: `efp-app-sg`
   - **Description**: Security group for Eternal Fusion Pavilion app
3. **Inbound Rules**:
   - SSH (22) - Your IP only (for initial setup)
   - HTTP (80) - 0.0.0.0/0
   - HTTPS (443) - 0.0.0.0/0
4. **Outbound Rules**: All traffic
5. Click **Create security group**

### **1.2 Launch EC2 Instance**

1. Navigate to **EC2 Dashboard** → **Launch instance**
2. Configure instance:
   - **Name**: `efp-app`
   - **AMI**: Amazon Linux 2023 AMI 6.12 (64-bit ARM)
   - **Instance type**: t4g.micro (Free Tier eligible)
   - **Key pair**: Create new key pair (`efp-app.pem`) or use existing
3. **Network settings**:
   - VPC: Use default VPC (simplifies setup)
   - Subnet: Any availability zone
   - Auto-assign public IP: Enable
   - Security group: Select `efp-app-sg` created above
4. **Configure storage**: 8 GB GP3 (Free Tier includes 30 GB-month)
5. **Advanced details**: 
   - User data: Paste the initialization script below
6. Click **Launch instance**
7. **After launch**: Note the **Public IPv4 address** (e.g., `3.123.45.67`) from EC2 instance details. Use this for DuckDNS.

### **1.3 Initialization Script (User Data)**

Copy this script to the **User data** field during launch. It installs PostgreSQL, Node.js, Python, Nginx, and configures the database:

```bash
#!/bin/bash
# Update system and install core dependencies
sudo dnf update -y
sudo dnf install -y python3.13 python3.13-pip nginx git postgresql17 postgresql17-server postgresql17-contrib firewalld certbot python3-certbot-nginx

curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash -
sudo dnf install -y nsolid
sudo npm install -g npm@11.8.0

# Install Python 3.13 as default
sudo alternatives --install /usr/bin/python python /usr/bin/python3.13 1
sudo alternatives --set python /usr/bin/python3.13

# Initialize PostgreSQL database
sudo postgresql-setup --initdb

sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create application database and user
sudo -u postgres psql << EOF
CREATE DATABASE eternal_fusion_pavilion_database;
CREATE USER efp_user WITH PASSWORD 'strongpassword';
ALTER USER efp_user WITH SUPERUSER;
GRANT ALL PRIVILEGES ON DATABASE eternal_fusion_pavilion_database TO efp_user;
\c eternal_fusion_pavilion_database;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF

# Configure PostgreSQL to accept local connections
sudo sed -i "s/^#listen_addresses = 'localhost'/listen_addresses = '*'/" /var/lib/pgsql/data/postgresql.conf
sudo sed -i "s/^host\s*all\s*all\s*127\.0\.0\.1\/32\s*\w*/host    all             all             127.0.0.1\/32            md5/" /var/lib/pgsql/data/pg_hba.conf
sudo sed -i "s/^host\s*all\s*all\s*::1\/128\s*\w*/host    all             all             ::1\/128                 md5/" /var/lib/pgsql/data/pg_hba.conf
sudo sed -i "s/^local\s*all\s*all\s*peer/local   all             all                                     md5/" /var/lib/pgsql/data/pg_hba.conf
echo "host    all             all             0.0.0.0/0               scram-sha-256" | sudo tee -a /var/lib/pgsql/data/pg_hba.conf

# Restart PostgreSQL to apply authentication changes
sudo systemctl restart postgresql

# Create application directory
sudo mkdir -p /var/www/efp
sudo chown ec2-user:ec2-user /var/www/efp

# Install PM2 for process management (optional)
sudo npm install -g pm2

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

**Note**: Change `'strongpassword'` to a more secure password in production.

---

## **Step 2: Configure Application Environment**

Connect to your EC2 instance and set up the application with local PostgreSQL.

### **2.1 Connect to EC2 Instance**

```bash
# SSH to your instance (replace with your Public DNS)
ssh -i "efp-app.pem" ec2-user@ec2-xx-xx-xx-xx.compute-1.amazonaws.com
```

### **2.2 Deploy Application Code**

```bash
# Clone the repository
cd /var/www/efp
git clone https://github.com/stephen-cpe/eternal_fusion_pavilion.git .

# Set proper permissions
sudo chown -R ec2-user:ec2-user /var/www/efp
```

### **2.3 Configure Environment Variables**

Create `.env` file
```bash
sudo nano /var/www/efp/backend/.env
```

Add the following content:
```ini
DB_HOST=localhost
DB_PORT=5432
DB_NAME=eternal_fusion_pavilion_database
DB_USER=efp_user
DB_PASSWORD=strongpassword
SECRET_KEY=your_generated_secret_key_here
API_PREFIX=/api
FLASK_ENV=production
FLASK_DEBUG=False
CORS_ORIGINS=https://eternalfusionpavilion.duckdns.org
```

### **2.4 Initialize Database Schema**

```bash
# Install Python dependencies
cd /var/www/efp/backend
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database schema
PGPASSWORD=strongpassword psql -h localhost -U efp_user -d eternal_fusion_pavilion_database -f ../init_db.sql

# Verify database initialization
PGPASSWORD=strongpassword psql -h localhost -U efp_user -d eternal_fusion_pavilion_database -c "SELECT COUNT(*) FROM locations;"
```

---

## **Step 3: Configure Duck DNS (Free Domain)**

1. Go to [DuckDNS.org](https://www.duckdns.org/) and log in (free, uses Google/GitHub).
2. In the subdomain field, enter `eternalfusionpavilion` (creates `eternalfusionpavilion.duckdns.org`).
3. Set **IP/URL** to your EC2 **Public IPv4 address** (from Step 1.2).
4. Click **Update IP**. It updates every 5 minutes.
5. **Verify propagation** (5-10 min):
   ```bash
   dig eternalfusionpavilion.duckdns.org
   # Or use online tool: https://dnschecker.org
   ```
   Should resolve to your EC2 IP.

**Note**: If you stop/start EC2, IP changes unless using Elastic IP (recommended, free).

---

## **Step 4: Configure Backend Services**

Set up Gunicorn and systemd for the Flask application.

### **4.1 Create Gunicorn Service**

```bash
sudo nano /etc/systemd/system/efp-backend.service
```

Add:

```ini
[Unit]
Description=Eternal Fusion Pavilion Backend
After=network.target postgresql.service

[Service]
User=ec2-user
Group=nginx
WorkingDirectory=/var/www/efp/backend
EnvironmentFile=/var/www/efp/backend/.env
ExecStart=/var/www/efp/backend/venv/bin/gunicorn \
          --workers 2 \
          --bind 127.0.0.1:5000 \
          --timeout 120 \
          --access-logfile /var/log/efp/efp-backend-access.log \
          --error-logfile /var/log/efp/efp-backend-error.log \
          "app:create_app()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### **4.2 Build Frontend Application**

```bash
# Build React app
cd /var/www/efp/frontend
npm install
npm run build

# Set permissions for Nginx
sudo chown -R nginx:nginx /var/www/efp/frontend/dist
sudo chmod -R 755 /var/www/efp/frontend/dist
```

---

## **Step 5: Configure Nginx with SSL (Certbot/Let's Encrypt)**

### **5.1 Configure Nginx (HTTP only before SSL)**

```bash
# Stop and clean default Nginx
sudo systemctl stop nginx
sudo rm -f /etc/nginx/conf.d/*.conf

# Create main Nginx configuration
sudo nano /etc/nginx/conf.d/efp.conf
```

Add (HTTP-only; Certbot will add HTTPS later):

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

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    # Static cache
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security
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

> **Why HTTP-only first?**  
> This avoids the “cannot load certificate … no such file or directory” error. We don’t reference any `/etc/letsencrypt/live/...` files until Certbot has actually created them.

### **5.2 Obtain & Install Let's Encrypt SSL (two-step Certbot run)**

```bash
# 1) First run WITHOUT --redirect (more reliable)
sudo certbot --nginx -d eternalfusionpavilion.duckdns.org --email youremail@address.com --agree-tos

# 2) Then run again WITH --redirect to force HTTP -> HTTPS
sudo certbot --nginx -d eternalfusionpavilion.duckdns.org --email youremail@address.com --agree-tos --redirect

# Test renewal
sudo certbot renew --dry-run

# Enable auto-renewal
sudo systemctl enable certbot-renew.timer
sudo systemctl start certbot-renew.timer
```

- The **first** command obtains the certificate and lets Certbot update your Nginx config.
- The **second** command adds a permanent HTTP → HTTPS redirect.  
  You found that running the `--redirect` variant *first* sometimes failed (likely timeout), so this 2-step flow is safer.

> **Optional: Enable HTTP/2 (without deprecated syntax)**  
> After Certbot has created the HTTPS server block in `/etc/nginx/conf.d/efp.conf`, you can edit that block and, **inside the `server { ... }` that listens on 443**, add:
> ```nginx
> http2 on;
> ```
> Do **not** use `listen 443 ssl http2;` since that syntax is deprecated.

---

## **Step 6: Launch and Test Application**

### **6.1 Start All Services**

```bash
# Reload systemd & start backend
sudo systemctl daemon-reload
sudo systemctl enable efp-backend
sudo systemctl start efp-backend

# Test & start Nginx
sudo nginx -t
sudo systemctl start nginx
sudo systemctl enable nginx
```

### **6.2 Verify Services**

```bash
sudo systemctl status postgresql efp-backend nginx firewalld
PGPASSWORD=strongpassword psql -h localhost -U efp_user -d eternal_fusion_pavilion_database -c "SELECT version();"
curl http://127.0.0.1:5000/api/health  # Backend health
curl -k https://localhost  # Local HTTPS
```

### **6.3 Test Full App (Browser)**

1. Wait 5-10 min for DNS/SSL propagation.
2. Visit: **https://eternalfusionpavilion.duckdns.org**
3. Test API: **https://eternalfusionpavilion.duckdns.org/api/health**

### **6.4 Monitor Logs**

```bash
sudo journalctl -u efp-backend -f
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/efp/efp-backend-*.log
```

**Troubleshooting**:
- **DNS?** Check `dig eternalfusionpavilion.duckdns.org`
- **SSL?** `sudo certbot certificates`
- **IP Changed?** Update DuckDNS & re-run Certbot.
- **Logs show errors?** Check permissions, .env, DB connection.

Your app is live at https://eternalfusionpavilion.duckdns.org (Free Tier). Update DuckDNS IP if EC2 restarts. For production, secure DB (not 0.0.0.0/0), use Elastic IP, monitor Free Tier usage.

---
