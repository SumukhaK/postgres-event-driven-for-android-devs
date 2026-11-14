---
title: Install guide for Windows 10, and playgrounds that need no install
part: Appendix
summary: Step-by-step tools setup on Windows 10, plus free browser and cloud options if you want to skip installing anything.
---

**You need three things to follow this course: a Postgres database, Python, and a place to type commands. This appendix shows the fastest ways to get them on Windows 10, including ways that need no installation at all.**

In this appendix, we will learn:

- Which options let you skip installation completely
- How to install Python, Postgres and Git on Windows 10, step by step
- How to use WSL 2 if you prefer Linux commands
- When Docker is a good idea on Windows 10, and when it is not
- How to check that everything works

Let's get started.

## Read this first: Windows 10 is out of support

Microsoft's lifecycle page lists the end date of Windows 10 version 22H2 as **15 October 2025**. That has already passed. Two things follow for this course:

- Docker's installation page says it supports Docker Desktop only on Windows versions that are still within Microsoft's servicing timeline. So Docker Desktop on a plain Windows 10 is no longer a supported setup. That is why this guide does **not** make Docker the default (chapter 0 still shows it for people on Mac and Linux).
- Python, Postgres, Git and Ollama all publish Windows 10 installers or say they support it, with the notes below. These are the tools we use.

!!! warning "What was tested, and what was not"
    The course's SQL and Python were run on Linux with PostgreSQL 16. I do not have a Windows 10 machine, so the Windows steps below follow the official installation pages (linked in Sources) and were **not** run by me on Windows 10. If a screen looks different from the description, trust the screen and the official page. Tell me which step differs and I will fix this page.

## Option 0: skip the installation

You can start learning SQL in a few minutes with nothing installed. Here are the choices, with what each one is good for.

| Option | What it is | Good for | Limits (from the official pages) |
|---|---|---|---|
| **PGlite online** (pglite.dev) | A complete Postgres compiled to WebAssembly that runs in your browser tab. The site says it is "under 3MB Gzipped" and the home page has a live Postgres you can type into. | Chapters 1 to 8: the SQL chapters | Lives in the browser, so it is for practice. Not a server your Python code can connect to. I did not test the Part 3 queries in it. |
| **Neon** (free plan) | A hosted Postgres you connect to from your own computer | The whole course, including the FastAPI project | $0/month. 1 GB of storage per project, 100 compute-hours per project per month, and the database goes to sleep after 5 minutes without use, then wakes on the next connection. |
| **Supabase** (free plan) | A hosted Postgres with extras | SQL chapters and the FastAPI project | Two free projects, 500 MB database per project. |
| **GitHub Codespaces** | A Linux computer in the cloud, opened from GitHub in your browser | Following along on Linux without touching Windows | Free GitHub accounts get 120 compute-hours and 15 GB-month storage per month. You still install Postgres inside it, with the Linux steps. |

!!! tip "My suggestion"
    For chapters 1 to 8, open PGlite and start typing. When you reach chapter 9, create a free Neon project and put its connection string in `DATABASE_URL`, or install Postgres on your laptop with Option A below.

!!! android "Android parallel"
    PGlite is like running your Room tests with an in-memory database: a real database engine, living inside the process, perfect for trying things. Neon and Supabase are like Firebase: someone else runs the server.

Creating an account on these sites is something you do yourself in the browser. Never paste your database password into a chat, a public repository or a screenshot.

## Option A: install natively on Windows 10

We install three tools: Python, PostgreSQL and Git. Open **PowerShell** (Start menu, type "PowerShell") for the commands.

### Step 1: install Python

1. Go to python.org/downloads and download the **Python install manager**. The Python documentation says you can also get it from the Microsoft Store. It states that the current Python release supports Windows 10 and newer.
2. Run the installer. When it asks about adding a directory to your `PATH`, you can say yes. The documentation says this is optional if you prefer the `py` command, but it makes `python` work in every terminal.
3. Close and reopen PowerShell, then check:

```powershell
py --version
```

The documentation calls `py` the recommended command when you have more than one Python on the machine.

### Step 2: a virtual environment for the project

A virtual environment is Python's version of a per-project `build.gradle`: the libraries live inside the project folder, not in your whole computer.

```powershell
py -m venv .venv
.venv\Scripts\activate.bat
```

The Python documentation lists `<venv>\Scripts\activate.bat` as the activation command for `cmd.exe`, and `<venv>\Scripts\Activate.ps1` for PowerShell. It adds that on Windows you may need to enable the `Activate.ps1` script through the execution policy. Running the `.bat` file avoids that. Your prompt now starts with `(.venv)`.

Install what the course project needs:

```powershell
pip install -r project/requirements.txt
```

### Step 3: install PostgreSQL

1. Open postgresql.org/download/windows. It sends you to the **interactive installer by EDB**, which the page says is hosted by EDB and not on the PostgreSQL servers.
2. Choose version **16** (the version this course was tested on).
3. Run the installer and keep these components ticked. The EDB documentation lists them as **PostgreSQL Server**, **pgAdmin 4**, **Stack Builder** and **Command Line Tools**. You need the server and the command-line tools (they contain `psql` and `createdb`). pgAdmin is a point-and-click viewer you may like.
4. On the **Password** screen, choose a password. The documentation says it is used for both the database superuser and the service account called `postgres`. **Write it down in a password manager.** You will need it every time you connect.
5. On the **Port** screen, keep the default **5432**.
6. Finish the wizard. Postgres now runs as a Windows service in the background, so it starts with your computer.

!!! note "A note on compatibility"
    The download page's table for Postgres 16 lists the Windows platforms "2022, 2019". Those are server editions of Windows. It does not list Windows 10 by name. Many people run it on desktop Windows, but I could not confirm that from the page. If the installer refuses to run, use Option B (WSL) or Option 0 (Neon).

### Step 4: connect and check

Open a new PowerShell window and run (it will ask for the password you chose):

```powershell
psql -U postgres -h localhost
```

If PowerShell says `psql` is not recognised, the tools are installed but not on your `PATH`. Run it by its full path: the installer's *Installation Directory* screen shows the folder, and `psql.exe` is in its `bin` folder. Or open the psql shell the installer adds to the Start menu.

At the `postgres=#` prompt:

```sql-skip
SELECT version();
```

You should see a line that starts with `PostgreSQL 16`. Now create the course database and leave:

```sql-skip
CREATE DATABASE chaipoint;
\q
```

### Step 5: point the project at your database

The course project reads its database address from the `DATABASE_URL` setting (chapter 9). In PowerShell, for the current window only:

```powershell
$env:DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/chaipoint"
```

Replace `YOUR_PASSWORD` with your own. Do not put this line in a file that you commit to Git.

### Step 6: install Git

Download **Git for Windows** from git-scm.com (the page links the installer directly). If you use the `winget` tool, the same page gives `winget install --id Git.Git -e --source winget`, and notes that the winget package is not maintained by the Git for Windows project and can differ from the latest official version. Keep the installer's default options if you are unsure.

Then get the course code:

```powershell
git clone https://github.com/SumukhaK/postgres-event-driven-for-android-devs
cd postgres-event-driven-for-android-devs
```

## Option B: WSL 2, a real Linux inside Windows

If you like Linux commands, or the Postgres installer does not run on your machine, use the Windows Subsystem for Linux. Microsoft's page says you need Windows 10 version 2004 or higher (build 19041 and up) or Windows 11. Open PowerShell **as administrator** (right click, Run as administrator), run the command below, and restart the computer:

```powershell
wsl --install
```

After the restart, a Linux (Ubuntu by default) window finishes setting up and asks you to create a Linux username and password. Inside it, follow the Linux steps: install Postgres and Python with `sudo apt install postgresql python3-venv`, then start the server with `sudo service postgresql start`. That is the same way I started Postgres 16 while testing this course.

## Option C: Docker Desktop (only if your machine meets the rules)

Docker's page lists these requirements for Windows 10: 64-bit **Enterprise, Pro or Education** version 22H2 (build 19045), the WSL 2 feature turned on, SLAT support, 8 GB of RAM, and hardware virtualization enabled in the BIOS/UEFI. It also says the Windows Server service must be set to start automatically. Home edition is not listed on that page.

If you meet them, and you accept the support-timeline caveat above, the one-line setup from chapter 0 works:

```powershell
docker run --name chaipoint-db -e POSTGRES_PASSWORD=chai -e POSTGRES_DB=chaipoint -p 5432:5432 -d postgres:16
```

## Later: running AI models on your laptop

Part 3 does not need an AI model, but the portfolio appendix does. Ollama's Windows page says: Windows 10 22H2 or newer (Home or Pro), NVIDIA drivers 551.61 or newer if you have an NVIDIA card, and that it installs in your home directory without administrator rights. It needs at least 4 GB for the program, plus space for the models, which "can be tens to hundreds of GB in size". Its API listens on `http://localhost:11434`.

## When something goes wrong

- **"password authentication failed"**: you typed a different password than the one in the installer. Use the same one for `psql` and for `DATABASE_URL`.
- **"connection refused"**: the Postgres service is not running. Open Services (Start menu, type "Services"), find the PostgreSQL service and start it.
- **Port 5432 is already in use**: another Postgres is running. Pick another port in the installer and use it in `DATABASE_URL`.
- **Activate.ps1 is blocked**: use `.venv\Scripts\activate.bat` as in Step 2.

## Summary

- You can start with no install at all: PGlite in the browser for the SQL chapters, a free Neon project for the full course.
- Windows 10 is past its support date, so Docker Desktop is not the default here.
- Native path: Python install manager, `py -m venv`, the EDB Postgres installer (server and command-line tools, a password you keep, port 5432), Git for Windows.
- WSL 2 gives you Linux commands with one `wsl --install` and a restart.
- Windows steps follow the official pages and were not run on a Windows 10 machine.

!!! faq "Do I need pgAdmin?"
    No. `psql` plus this course is enough. pgAdmin is a visual tool, like Android Studio's Database Inspector, if you prefer clicking.

!!! faq "Is a free Neon database safe to use for learning?"
    Yes for learning data. Do not put real customer data on any free plan, and remember the free plan has hard limits: when you use up the monthly compute hours, the compute is suspended until the next billing period.

## Sources

- [Microsoft Lifecycle: Windows 10 Home and Pro](https://learn.microsoft.com/en-us/lifecycle/products/windows-10-home-and-pro)
- [Docker Docs: Install Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
- [PostgreSQL: Windows installers](https://www.postgresql.org/download/windows/)
- [EDB Docs: Installing PostgreSQL on Windows](https://www.enterprisedb.com/docs/supported-open-source/postgresql/installing/windows/)
- [Python docs: Using Python on Windows](https://docs.python.org/3/using/windows.html)
- [Python docs: venv](https://docs.python.org/3/library/venv.html)
- [Git for Windows download](https://git-scm.com/downloads/win)
- [Microsoft Learn: Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install)
- [PGlite](https://pglite.dev/)
- [Neon plans](https://neon.com/docs/introduction/plans)
- [Supabase: About billing](https://supabase.com/docs/guides/platform/billing-on-supabase)
- [GitHub Docs: Codespaces billing](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces)
- [Ollama docs: Windows](https://docs.ollama.com/windows)

That's it for now. In the next appendix, we will plan portfolio projects you can build for no money.
