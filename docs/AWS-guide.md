# **Deployment Guide on AWS EC2 using Ubuntu**

This guide provides step-by-step instructions to deploy a full-stack application (Flask backend + React frontend) on an AWS EC2 instance running **Ubuntu 24.04 LTS**.

The production environment uses **Nginx** as a reverse proxy and static file server, **Gunicorn** as the WSGI server for Flask, and **PostgreSQL** as the database.

## **Technology Stack**

  * **Backend**: Flask (Python)
  * **Frontend**: React (JSX)
  * **Database**: PostgreSQL
  * **WSGI Server**: Gunicorn 
  * **Web/Proxy Server**: Nginx 
  * **OS**: Ubuntu 24.04 LTS
  * **Process Manager**: systemd

-----

## **Step 1: Initial EC2 & System Setup**

First, prepare the server instance and install all required software.

1.  **Launch & Connect to EC2**:

      * In the AWS console, launch a new EC2 instance (e.g., `t2.micro` or larger) using the **Ubuntu Server 24.04 LTS** AMI.
      * Configure the **Security Group** with inbound rules to allow traffic for:
          * **SSH** (Port 22) - From your IP for access.
          * **HTTP** (Port 80) - From `Anywhere` (0.0.0.0/0, ::/0).
          * **HTTPS** (Port 443) - From `Anywhere` (0.0.0.0/0, ::/0).
      * Connect to your instance via SSH using your key pair:
        ```bash
        ssh -i "your-key-pair.pem" ubuntu@ec2-54-235-238-98.compute-1.amazonaws.com
        ```
      * _Replace all reference to `ec2-54-235-238-98.compute-1.amazonaws.com` with your AWS EC2 Public DNS._ 
        

2.  **Update System & Install Packages**:

      * Update the package lists and upgrade existing packages:
        ```bash
        sudo apt update && sudo apt upgrade -y
        ```
      * Install all necessary dependencies including Python, Node.js, PostgreSQL, and Nginx:
        ```bash
        sudo apt install -y python3 python3-venv python3-pip nodejs npm postgresql nginx git
        ```

3.  **Configure the Firewall (UFW)**:

      * Allow SSH and Nginx traffic through the local firewall.
        ```bash
        sudo ufw allow OpenSSH
        sudo ufw allow 'Nginx Full'
        ```
      * Enable the firewall. **Confirm "y"** when prompted.
        ```bash
        sudo ufw enable
        ```
      * Verify that the firewall is active and the rules are applied:
        ```bash
        sudo ufw status verbose
        ```

-----

## **Step 2: Deploy Code and Configure Environment**

Clone the application code onto the server and set up the necessary environment variables.

1.  **Clone the Repository**:

      * Clone the project into the `ubuntu` user's home directory. (The troubleshooting shows `/home/ubuntu/eternal_fusion_pavilion` as the final working directory).
        ```bash
        git clone https://github.com/stephen-cpe/eternal_fusion_pavilion.git eternal_fusion_pavilion
        ```

2.  **Create Environment File**:

      * Create and edit a `.env` file in the project's root directory:
        ```bash
        nano ~/eternal_fusion_pavilion/.env
        ```
      * Add the following variables, replacing placeholder values. **Use the password you created in Step 2**.
        ```
        DB_HOST=localhost
        DB_PORT=5432
        DB_NAME=eternal_fusion_pavilion_database
        DB_USER=efp_user
        DB_PASSWORD=strongpassword
        SECRET_KEY=generate_a_very_secret_key
        API_PREFIX=/api
        ```
      * **Note**: Ensure the Flask `config.py` is updated to load these variables using `os.getenv()`.

-----

## **Step 3: Set Up PostgreSQL Database**

Create the database, a dedicated user, and initialize the table schema.


1.  **Start and Enable PostgreSQL Service**

    ```bash
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    ```

2.  **Create Database and User**

      * Add postgres User to ubuntu Group:
        ```bash
        sudo usermod -aG ubuntu postgres
        ```

      * Access the PostgreSQL prompt:
        ```bash
        sudo -u postgres psql
        ```
      * Run the following SQL commands to create the user and database. Replace `'strongpassword'` with a secure password:
        ```sql
        CREATE USER efp_user WITH PASSWORD 'strongpassword';
        CREATE DATABASE eternal_fusion_pavilion_database;
        GRANT ALL PRIVILEGES ON DATABASE eternal_fusion_pavilion_database TO efp_user;
        \q
        ```

	
3.  **Initialize the Database Schema**

      * With the database and user created, run the `init_db.sql` script to create all necessary tables and seed initial data (like the admin account).
      * Execute the script as the `postgres` superuser to ensure all permissions are handled correctly:
        ```bash
        sudo -u postgres psql -d eternal_fusion_pavilion_database -f ~/eternal_fusion_pavilion/init_db.sql
        ```

4.  **(Optional) Verify Initialization**

      * You can verify that the tables were created successfully by connecting to the database and listing the tables.
        ```bash
        # Connect to the database
        sudo -u postgres psql -d eternal_fusion_pavilion_database

        # List tables (at the psql prompt)
        \dt

        # Exit
        \q
        ```
-----


## **Step 4: Configure Backend (Flask & Gunicorn)**

Set up the Python environment, install dependencies, and create a systemd service to manage the Gunicorn process.

1.  **Create Virtual Environment & Install Dependencies**:

      * Navigate to the backend directory and create a virtual environment:
        ```bash
        cd ~/eternal_fusion_pavilion/backend
        python3 -m venv venv
        ```
      * Activate the environment and install the required packages:
        ```bash
        source venv/bin/activate
        pip install -r requirements.txt gunicorn
        ```

2.  **Create Gunicorn Systemd Service**:

      * Create a service file to manage the backend process
        ```bash
        sudo nano /etc/systemd/system/efp-backend.service
      * Paste in the following configuration. This is the **final corrected version** that ensures Nginx can communicate with the Gunicorn socket:
        ```
        [Unit]
        Description=Eternal Fusion Pavilion Backend
        After=network.target

        [Service]
        User=ubuntu
        Group=www-data
        WorkingDirectory=/home/ubuntu/eternal_fusion_pavilion/backend
        EnvironmentFile=/home/ubuntu/eternal_fusion_pavilion/.env
        ExecStart=/home/ubuntu/eternal_fusion_pavilion/backend/venv/bin/gunicorn --workers 3 --bind unix:/home/ubuntu/eternal_fusion_pavilion/efp.sock -m 007 "app:create_app()"
        Restart=always

        [Install]
        WantedBy=multi-user.target
        ```
          * **`User=ubuntu`**: Runs the process as the user.
          * **`Group=www-data`**: Allows the Nginx process group to access the socket.
          * **`-m 007`**: Sets the socket file permissions so the `www-data` group can read and write to it.

-----

## **Step 5: Configure Frontend (React & Nginx)**

Build the static React files and configure Nginx to serve them and proxy API calls to the backend.

1.  **Build the React App**:

      * Navigate to the frontend directory, install dependencies, and create the production build:
        ```bash
        cd ~/eternal_fusion_pavilion/frontend
        sudo npm install -g n
        sudo n lts
        npm install
        npm run build
        ```

2.  **Set Build File Permissions**:

      * **First, ensure the home directory itself is accessible** by setting execute permissions:
        ```bash
        chmod 755 /home/ubuntu
        ```
      * Change the group ownership of the build directory to `www-data`:
        ```bash
        sudo chown -R ubuntu:www-data ~/eternal_fusion_pavilion/frontend/dist
        ```
      * Set the correct permissions for directories (755) and files (644):
        ```bash
        sudo find ~/eternal_fusion_pavilion/frontend/dist -type d -exec chmod 755 {} \;
        sudo find ~/eternal_fusion_pavilion/frontend/dist -type f -exec chmod 644 {} \;
        ```

3.  **Configure Nginx**:

      * Create a new Nginx configuration file:
        ```bash
        sudo nano /etc/nginx/sites-available/efp
        ```

      * _Replace all reference to `ec2-54-235-238-98.compute-1.amazonaws.com` and `54.235.238.98` with your AWS EC2 Public DNS and Public IP._

      * Paste the following configuration. This serves the React app, proxies API requests to the Gunicorn socket, and includes a self-signed SSL certificate for HTTPS testing.
        ```nginx
        server {
            listen 80;
            listen 443 ssl;
            server_name ec2-54-235-238-98.compute-1.amazonaws.com 54.235.238.98;

            # Self-signed SSL certificate paths
            ssl_certificate /etc/ssl/certs/selfsigned.crt;
            ssl_certificate_key /etc/ssl/private/selfsigned.key;

            location / {
                root /home/ubuntu/eternal_fusion_pavilion/frontend/dist;
                index index.html;
                try_files $uri /index.html;
            }

            location /api/ {
                proxy_pass http://unix:/home/ubuntu/eternal_fusion_pavilion/efp.sock;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
            }
        }
        ```
      * Enable the site by creating a symbolic link:
        ```bash
        sudo ln -s /etc/nginx/sites-available/efp /etc/nginx/sites-enabled/
        ```
      * Generate a self-signed SSL certificate for testing:
        ```bash
        sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/private/selfsigned.key -out /etc/ssl/certs/selfsigned.crt -subj "/CN=ec2-54-235-238-98.compute-1.amazonaws.com"
        ```

-----

## **Step 6: Launch and Test**

Start all services and verify that the application is running correctly.

1.  **Start and Enable Services**:

      * Reload the systemd daemon to recognize the new `efp-backend.service`.
        ```bash
        sudo systemctl daemon-reload
        ```
      * Start and enable the backend service:
        ```bash
        sudo systemctl start efp-backend
        sudo systemctl enable efp-backend
        ```
      * Test the Nginx configuration and restart the service:
        ```bash
        sudo nginx -t
        sudo systemctl restart nginx
        ```
      * If this part returns an error, modify `/etc/nginx/nginx.conf`
        ```bash
        sudo nano /etc/nginx/nginx.conf
        ```
        Uncomment and set `server_names_hash_bucket_size 128;`

2.  **Verify Application**:

      * Check that the Gunicorn socket file was created successfully:
        ```bash
        ls -l ~/eternal_fusion_pavilion/efp.sock
        ```
        You should see output like: `srw-rw---- 1 ubuntu www-data 0 Sep 01 12:55 efp.sock`
      * Visit the application in the browser. You will need to bypass the browser warning for the self-signed SSL certificate.
          * **HTTP**: `http://ec2-54-235-238-98.compute-1.amazonaws.com`
          * **HTTPS**: `https://ec2-54-235-238-98.compute-1.amazonaws.com`

-----

## **Service Management & Troubleshooting**

### **Managing Services**

Use the following `systemctl` commands to manage the core services.

```bash
# Check Status (nginx, efp-backend, postgresql)
sudo systemctl status efp-backend

# Stop/Start/Restart
sudo systemctl restart efp-backend
```

### **Common Issues**

If the application is not working as expected, check the following common issues first.

1.  **Permission Denied Errors (Nginx 5xx Errors)**
    If you see Nginx errors related to "permission denied," verify that the permissions set in **Step 5, Section 2** are correct.

      * **Verify home directory permissions**:
        ```bash
        ls -ld /home/ubuntu
        ```
        Should show: `drwxr-xr-x` (755 permissions)
      
      * **Verify build directory ownership**:
        ```bash
        ls -ld ~/eternal_fusion_pavilion/frontend/dist
        ```
        Should show: `ubuntu:www-data` as owner:group

2.  **Nginx Fails to Start (Hash Bucket Size Error)**
    If `sudo nginx -t` fails with a `server_names_hash_bucket_size` error, it means your EC2 DNS name is too long for Nginx's default settings.

      * **Solution**: Edit the main Nginx config file: `sudo nano /etc/nginx/nginx.conf`.
      * Inside the `http { ... }` block, find the line `# server_names_hash_bucket_size 64;` and uncomment it (remove the `#`). If it doesn't exist, add it. Save the file and run `sudo nginx -t` again.



> The steps in this guide are sequential and comprehensive. If you encounter issues not listed above, carefully review the previous steps for any missed commands, typos in configuration files, or incorrect values (e.g., hostnames, passwords). Checking service logs with `sudo journalctl -u efp-backend` and `sudo tail -f /var/log/nginx/error.log` will also provide valuable clues.

---

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
