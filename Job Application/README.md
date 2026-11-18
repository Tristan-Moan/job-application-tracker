# Shortlist | Job Application Tracker

A Flask and MySQL application for tracking companies, jobs, applications and professional contacts. The dashboard summarizes the search. Job Match ranks openings against the skills you enter.

## Run locally on Windows

You need Python 3.10 or newer, MySQL Community Server 8.0.16 or newer (8.4 recommended), and a running MySQL service. MySQL Workbench or the MySQL command line can run the SQL scripts. Start in the folder containing `app.py` and `schema.sql`.

1. Open `schema.sql` in MySQL Workbench using your local administrator connection. Execute the entire script with the lightning bolt. It creates the `job_tracker` database and all four tables. For the command line, open `mysql -u root -p` and enter `SOURCE C:/path/to/job_tracker/schema.sql` using your actual path. Use forward slashes in the MySQL console.
2. In Workbench or the MySQL console, create a local application account. Replace the example password with your own in both the SQL and the environment file.

   ```sql
   CREATE USER 'tracker_app'@'127.0.0.1' IDENTIFIED BY 'replace_with_your_password';
   GRANT SELECT, INSERT, UPDATE, DELETE ON job_tracker.* TO 'tracker_app'@'127.0.0.1';
   ```

3. Optionally execute `demo/sample.sql` once in a new, empty database to load the fictional records from the video. The application also works with empty tables.
4. In PowerShell, create a virtual environment, install the dependencies and copy the configuration template.

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   Copy-Item .env.example .env
   notepad .env
   ```

5. Set `DB_PASSWORD` in `.env` to the account password. Keep `DB_HOST=127.0.0.1`. Adjust `DB_PORT` if your server uses another port. Save the file, then run the app.

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app app run
   ```

6. Open [the local dashboard](http://127.0.0.1:5000). Press Ctrl+C in the terminal to stop the server.

On macOS or Linux use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, and `cp .env.example .env`. After editing the configuration, start it with `.venv/bin/python -m flask --app app run`. The database setup is the same.

## Use the tracker

1. Add a company. Add a job at that company and list its required skills, separated by commas or new lines.
2. Add an application for the job. Track its date, status, resume version, cover letter and optional interview details. Interview details accept a JSON object such as `{"round": 2, "location": "Zoom"}`.
3. Add contacts under their company. Select a record name in any list to see its details, edit it or open its deletion confirmation. MySQL prevents deleting a company or job while other records still reference it.
4. Open Job Match and enter your skills. Matching ignores capitalization, repeated skills and surrounding spaces. Each distinct required skill has equal weight. Two matches out of three display as 67%. Ranking uses the unrounded percentage, then job title and ID. Jobs without requirements appear last as unscored.
5. Return to Dashboard to see record totals, counts by application status and the five most recent applications.

## Recorded demo

Open [the recorded walkthrough](demo/walkthrough.mp4). It shows the browser, a Flask request log, and queries against the same MySQL database. The walkthrough uses fictional data and has no narration.

## Files

| File or folder | Purpose |
| --- | --- |
| app.py | Routes, form validation, dashboard and matching |
| database.py | MySQL connection, parameterized queries and transactions |
| records.py | Field definitions, allowed types and joined queries |
| schema.sql | Tables, relationships, constraints and JSON columns |
| templates/ and static/ | HTML views and responsive CSS |
| demo/ | Optional sample data and the required recording |
| tests/ | Matching and end to end database integration tests |
| AI_USAGE.md | Development assistance and verification notes |

## Test a fresh copy

Run the setup above in a fresh folder. Before loading sample data, the dashboard should show four zero totals. Run the offline matching test with `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`. The database test is opt in.

For full integration testing, create an empty `job_tracker_test` database by changing both occurrences of `job_tracker` in a copy of `schema.sql` to `job_tracker_test` and executing that copy. Grant the application account the same four privileges on `job_tracker_test.*`. Set these variables in a separate PowerShell window in the project folder.

```powershell
$env:DB_NAME = 'job_tracker_test'
$env:TRACKER_TEST_DB = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The integration test requires empty tables. It exercises create, list, detail, edit and confirmed delete for each table, invalid inputs, missing records, linked deletion, dashboard data and match results. Close that PowerShell window after testing.

## Troubleshooting

* **Access denied**. Confirm the MySQL account, host and password match the values in `.env`. The app account needs permissions on the database chosen by `DB_NAME`.
* **Connection refused**. Start the MySQL service and verify the configured port.
* **Unknown database or missing tables**. Execute the whole schema script on the same MySQL instance used by Flask.
* **Expired form**. Reload the page and submit again. The local server generates a new session key at startup unless you supply a persistent `SECRET_KEY` in the environment.
