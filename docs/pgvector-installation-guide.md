# pgvector Installation Guide for Windows 11

This guide walks a developer through installing PostgreSQL 18 and the pgvector extension from scratch on a Windows 11 machine, within the context of the Eternal Fusion Pavilion (EFP) project. The EFP AI Concierge agent (`backend/ai_agent/`) uses pgvector to store and search the restaurant's knowledge base (menu, about, policies) as vector embeddings.

## Prerequisites

- A Windows 11 machine with administrator access.
- Git installed (to clone the pgvector source). Verify with:
  ```powershell
  git --version
  ```
  If Git is not installed, download it from https://git-scm.com/download/win and install it with default options.

---

## Part 1: Install PostgreSQL 18

### 1.1 Download the installer

Download the PostgreSQL 18 Windows installer from the official EnterpriseDB download page:

https://www.postgresql.org/download/windows/

Click "Download the installer" and choose the latest PostgreSQL 18.x version for Windows x86-64.

### 1.2 Run the installer

Run the downloaded `.exe` as administrator. Use these settings during setup:

- **Installation directory**: `C:\Program Files\PostgreSQL\18` (the default).
- **Components**: Check all (PostgreSQL Server, pgAdmin 4, Command Line Tools).
- **Data directory**: leave as default.
- **Superuser password**: choose a strong password for the `postgres` account and record it somewhere safe. You will need it later.
- **Port**: `5432` (the default).
- **Locale**: leave as default or choose your region.

Complete the installation and let it start the service at the end.

### 1.3 Verify the installation

Open a new PowerShell window and confirm the server is running:

```powershell
Get-Service | Where-Object { $_.Name -like "*postgres*" } | Select-Object Name, DisplayName, Status
```

You should see a service named `postgresql-x64-18` with status `Running`.

Verify the command-line tools are on your PATH:

```powershell
psql --version
```

If `psql` is not recognized, add the bin directory to your PATH:

```powershell
$env:PATH += ";C:\Program Files\PostgreSQL\18\bin"
```

To make this permanent, add it via System Environment Variables (right-click Start -> System -> Advanced system settings -> Environment Variables -> edit Path).

### 1.4 Create the EFP database and user

The EFP project expects a database named `eternal_fusion_pavilion_database` and a user named `efp_user`. These are created by the project's `init_db.sql` script, but the database itself must exist first.

Connect to PostgreSQL as the superuser:

```powershell
psql -U postgres
```

Enter the superuser password you chose during installation. Then run:

```sql
CREATE DATABASE eternal_fusion_pavilion_database;
CREATE USER efp_user WITH PASSWORD 'strongpassword';
GRANT ALL PRIVILEGES ON DATABASE eternal_fusion_pavilion_database TO efp_user;
\q
```

Then load the project schema into the new database. From the project root directory:

```powershell
psql -U postgres -d eternal_fusion_pavilion_database -f init_db.sql
```

This creates all the core EFP tables (locations, rooms, customers, reservations, etc.) and the AI agent tables (efp_knowledge_chunks, chat_threads, guest_ai_memory).

---

## Part 2: Install Visual Studio C++ Build Tools

pgvector does not ship prebuilt Windows binaries. It must be compiled from source using Microsoft's C++ compiler (`nmake`). This section installs the build tools without the full Visual Studio IDE.

### 2.1 Check if the build tools are already installed

Run this in PowerShell:

```powershell
Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio" -Directory -ErrorAction SilentlyContinue | Select-Object Name
```

If you see a folder named `2019`, `2022`, or similar, and it contains a `BuildTools` or `Community` or `Professional` subfolder, the tools may already be installed. Verify by searching for the build environment script:

```powershell
Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio" -Recurse -Filter "vcvars64.bat" -ErrorAction SilentlyContinue | Select-Object FullName
```

If you find a path like `C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat`, skip to Part 3.

### 2.2 Install the build tools (if not already installed)

Download the Build Tools for Visual Studio from:

https://visualstudio.microsoft.com/visual-cpp-build-tools/

Click "Download Build Tools" and run the installer. Under "Workloads", check **"Desktop development with C++"**. Click Install (default options are fine). This downloads approximately 2-3 GB and installs `nmake`, the MSVC compiler, and the Windows SDK without installing the full Visual Studio IDE.

### 2.3 Verify the installation

Search for the build environment script again:

```powershell
Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio" -Recurse -Filter "vcvars64.bat" -ErrorAction SilentlyContinue | Select-Object FullName
```

You should now see a path like:

```
C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat
```

Note this full path; you will use it in Part 3.

---

## Part 3: Build and Install pgvector

### 3.1 Open an Administrator command prompt

pgvector's install step copies files into `C:\Program Files\PostgreSQL\18\`, which requires administrator privileges.

Right-click the Start button and choose "Terminal (Admin)" or "Command Prompt (Admin)".

### 3.2 Initialize the build environment

In the administrator command prompt, run the `vcvars64.bat` script you located in Part 2.3. Replace the path below with the one you found:

```cmd
"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
```

You should see output ending with:

```
[vcvarsall.bat] Environment initialized for: 'x64'
```

### 3.3 Set the PostgreSQL root directory

Tell the build system where PostgreSQL is installed:

```cmd
set "PGROOT=C:\Program Files\PostgreSQL\18"
```

### 3.4 Clone the pgvector source

```cmd
cd %TEMP%
git clone --branch v0.8.6 https://github.com/pgvector/pgvector.git
cd pgvector
```

### 3.5 Build pgvector

```cmd
nmake /F Makefile.win
```

This compiles the C source files into `vector.dll`. You will see a series of `cl` compiler commands. If it completes without errors, proceed to the next step.

### 3.6 Install pgvector

```cmd
nmake /F Makefile.win install
```

This copies the following files:

- `vector.dll` to `C:\Program Files\PostgreSQL\18\lib\`
- `vector.control` to `C:\Program Files\PostgreSQL\18\share\extension\`
- `vector--*.sql` (41 SQL files) to `C:\Program Files\PostgreSQL\18\share\extension\`
- Header files to `C:\Program Files\PostgreSQL\18\include\server\extension\vector\`

You should see "41 file(s) copied." at the end.

### 3.7 Restart the PostgreSQL service

The server must be restarted to load the new shared library. Open a new PowerShell window (you can close the administrator command prompt now) and run:

```powershell
Restart-Service -Name "postgresql-x64-18" -Force
```

If you get an error about the service name not being found, list all PostgreSQL services first to find the exact name:

```powershell
Get-Service | Where-Object { $_.Name -like "*postgres*" } | Select-Object Name, DisplayName, Status
```

Then restart using the exact name shown.

---

## Part 4: Enable the pgvector Extension

### 4.1 Connect to the EFP database as superuser

```powershell
psql -U postgres -d eternal_fusion_pavilion_database
```

Enter the superuser password when prompted.

### 4.2 Create the extension

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

You should see:

```
CREATE EXTENSION
```

### 4.3 Verify the installation

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

You should see:

```
 extname | extversion
---------+------------
 vector  | 0.8.6
(1 row)
```

### 4.4 Exit psql

```sql
\q
```

---

## Part 5: Verify the EFP AI Agent Can Reach pgvector

The EFP AI agent service (`backend/ai_agent/`) has a health check endpoint that reports pgvector status and the knowledge chunk count.

### 5.1 Start the AI agent service

From the `backend/ai_agent/` directory, with its virtual environment activated:

```powershell
python main.py
```

### 5.2 Check the health endpoint

In a separate PowerShell window:

```powershell
curl http://localhost:8000/api/ai/health
```

You should see a response like:

```json
{
  "service": "ai_agent",
  "status": "healthy",
  "pgvector": "0.8.6",
  "knowledge_chunks": 35,
  "database": "connected"
}
```

The `pgvector` field shows the installed version, and `knowledge_chunks` shows how many documents have been ingested into the vector store. If `pgvector` shows `"not installed"` or `knowledge_chunks` is `0`, revisit Parts 3 and 4.

---

## Troubleshooting

### "extension vector is not available" when running CREATE EXTENSION

This means the pgvector files were not copied to the correct PostgreSQL directories, or the PostgreSQL service was not restarted after copying them. Recheck Part 3.6 (did `nmake install` copy all files?) and Part 3.7 (did you restart the service?).

### "Cannot open include file: postgres.h" during nmake

The `PGROOT` environment variable is wrong. Confirm PostgreSQL is installed at `C:\Program Files\PostgreSQL\18` and that the `include` and `lib` subdirectories exist. Re-run `set "PGROOT=C:\Program Files\PostgreSQL\18"` and try the build again.

### "Access is denied" during nmake install

You are not running the command prompt as administrator. Close it and reopen as administrator (right-click Start, choose "Command Prompt (Admin)" or "Terminal (Admin)").

### "error C2196: case value '4' already used" during nmake

You are not using the x64 build environment. Make sure you ran `vcvars64.bat` (not `vcvars32.bat`) before running `nmake`. Run `nmake /F Makefile.win clean` and then rebuild.

### Service name not found when restarting PostgreSQL

The service name depends on how PostgreSQL was installed. EnterpriseDB installs it as `postgresql-x64-18`. List all services with:

```powershell
Get-Service | Where-Object { $_.Name -like "*postgres*" } | Select-Object Name, DisplayName, Status
```

Use the exact `Name` value from that output.

### psql password authentication failed for user postgres

The superuser password was set during the PostgreSQL installation (Part 1.2). If you do not remember it, you can reset it by editing `pg_hba.conf` to temporarily trust local connections, restarting the service, changing the password with `ALTER USER postgres PASSWORD 'newpassword';`, reverting `pg_hba.conf`, and restarting again. The `pg_hba.conf` file is located at `C:\Program Files\PostgreSQL\18\data\pg_hba.conf`.