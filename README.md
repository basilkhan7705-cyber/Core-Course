
# Student Portfolio

A responsive portfolio website built with Flask, HTML, CSS, JavaScript, and SQLAlchemy.

## Features

- Responsive portfolio landing page
- About and skills sections
- Project cards with category filtering
- Downloadable résumé
- Contact form with PostgreSQL storage
- Password-protected admin login
- Add and delete portfolio projects
- Admin inbox for submitted messages
- Vercel deployment configuration

## Requirements

- Python 3.11 or newer
- pip
- A PostgreSQL database for persistent deployment

## Run locally

1. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

2. Activate it:

   Windows:

   ```bash
   .venv\Scripts\activate
   ```

   macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Set environment variables before starting the application.

   Windows PowerShell:

   ```powershell
   $env:SECRET_KEY="your-long-random-secret"
   $env:ADMIN_USERNAME="admin"
   $env:ADMIN_PASSWORD="your-strong-password"
   $env:DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"
   ```

   macOS/Linux:

   ```bash
   export SECRET_KEY="your-long-random-secret"
   export ADMIN_USERNAME="admin"
   export ADMIN_PASSWORD="your-strong-password"
   export DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE"
   ```

5. Start Flask:

   ```bash
   python app.py
   ```

6. Visit http://127.0.0.1:5000

   Admin login: http://127.0.0.1:5000/admin/login

## Deploy to Vercel

1. Create a GitHub repository and upload this project.
2. Create a managed PostgreSQL database.
3. Import the GitHub repository into Vercel.
4. Add SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, and DATABASE_URL in Vercel's Environment Variables settings.
5. Deploy the project.
6. Test the home page and /health endpoint.
7. Visit /admin/login to add your real portfolio projects.

Use a strong, unique admin password and a randomly generated SECRET_KEY.
Do not commit .env or real credentials.

## Before public production use

- Add CSRF protection to all state-changing forms, including admin forms.
- Use a shared rate-limit backend such as Redis for serverless deployments.
- Set up database backups and connection pooling.
- Add monitoring and test error handling.
- Replace sample portfolio text with accurate personal details.
- Add your own résumé at static/files/resume.pdf.
- Verify Vercel's Python runtime and build configuration for your account.

## Database note

The application creates its tables on startup. A managed PostgreSQL database is
recommended for Vercel because local SQLite files are not persistent across
serverless instances. The schema.sql file is also provided for reference.
