"""Matching tests run offline. Set TRACKER_TEST_DB=1 with an empty test DB for CRUD."""
import os
import unittest

from app import app, match_jobs


class MatchTests(unittest.TestCase):
    def test_matching(self):
        jobs = [dict(job_id=i, job_title=name, requirements=req) for i, (name, req)
                in enumerate([("Full", '["PYTHON","Python","SQL"]'),
                              ("Partial", '["Python","SQL","Flask"]'),
                              ("Unscored", None), ("Zero", '["Go"]')])]
        ranked = match_jobs(jobs, " python, SQL, sql, ")
        self.assertEqual([j["percent"] for j in ranked], [100, 67, 0, None])
        self.assertEqual(ranked[1]["missing"], ["Flask"])
        self.assertEqual(ranked[0]["total"], 2)


@unittest.skipUnless(os.getenv("TRACKER_TEST_DB") == "1", "Set TRACKER_TEST_DB=1 with a fresh test database")
class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.get("/")
        with self.client.session_transaction() as session:
            self.token = session["token"]

    def submit(self, path, data=None):
        return self.client.post(path, data=dict(data or {}, token=self.token))

    def test_complete_lifecycle(self):
        # Refuse to create data unless all tables in the selected DB are empty.
        import database
        from records import FIELDS
        with app.app_context():
            for table in FIELDS:
                self.assertEqual(database.rows(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"], 0,
                                 "Use a separate, empty test database.")
        pages = {}
        ids = {}

        def create(kind, fields, marker):
            base = "/" + kind
            self.assertEqual(self.client.get(base + "/new").status_code, 200)
            r = self.submit(base + "/new", fields)
            self.assertEqual(r.status_code, 303, r.data)
            pages[kind] = r.location
            ids[kind] = r.location.rsplit("/", 1)[1]
            self.assertIn(marker, self.client.get(r.location).data)
            self.assertIn(marker, self.client.get(base + "/").data)

        def edit(kind, fields, marker):
            path = pages[kind] + "/edit"
            self.assertEqual(self.client.get(path).status_code, 200)
            self.assertEqual(self.submit(path, fields).status_code, 303)
            self.assertIn(marker, self.client.get(pages[kind]).data)

        self.assertEqual(self.client.get("/unknown/").status_code, 404)
        self.assertEqual(self.client.get("/jobs/999999").status_code, 404)
        self.assertEqual(self.client.post("/companies/new", data={}).status_code, 400)
        self.assertEqual(self.submit("/companies/new", {"company_name": " "}).status_code, 422)
        self.assertEqual(self.submit("/companies/new", {"company_name": "Test", "website": "bad"}).status_code, 422)
        create("companies", dict(company_name="Green Studio"), b"Green Studio")
        edit("companies", dict(company_name="Green Labs"), b"Green Labs")
        job = dict(job_title="Analyst", company_id=ids["companies"], requirements="SQL, Python, Tableau")
        self.assertEqual(self.submit("/jobs/new", dict(job, salary_min="2", salary_max="1")).status_code, 422)
        self.assertEqual(self.submit("/jobs/new", dict(job, company_id="999999")).status_code, 422)
        create("jobs", job, b"Analyst")
        edit("jobs", dict(job, salary_min="0", salary_max="85000"), b"85,000")
        application = dict(job_id=ids["jobs"], application_date="2026-11-18", status="Applied")
        self.assertEqual(self.submit("/applications/new", dict(application, interview_data="[]")).status_code, 422)
        self.assertEqual(self.submit("/applications/new", dict(application, status="Invalid")).status_code, 422)
        self.assertEqual(self.submit("/applications/new", dict(application, application_date="bad")).status_code, 422)
        create("applications", application, b"Analyst")
        edit("applications", dict(application, status="Interview", interview_data='{"round": 1}',
                                  cover_letter_sent="on"), b"Interview")
        contact = dict(company_id=ids["companies"], contact_name="Maya Reed")
        self.assertEqual(self.submit("/contacts/new", dict(contact, email="bad")).status_code, 422)
        create("contacts", contact, b"Maya Reed")
        edit("contacts", dict(contact, email="maya@example.org"), b"maya@example.org")
        self.assertIn(b"67%", self.client.get("/job-match?skills=sql,python").data)
        self.assertIn(b"Tableau", self.client.get("/job-match?skills=sql,python").data)
        self.assertIn(b"Enter at least one skill", self.client.get("/job-match?skills=,").data)
        self.assertIn(b"Analyst", self.client.get("/").data)
        for kind in ("companies", "jobs"):
            self.assertEqual(self.submit(pages[kind] + "/delete").status_code, 409)
        for kind in ("contacts", "applications", "jobs", "companies"):
            path = pages[kind] + "/delete"
            self.assertIn(b"Confirm deletion", self.client.get(path).data)
            self.assertEqual(self.client.get(pages[kind]).status_code, 200)
            self.assertEqual(self.submit(path).status_code, 303)
            self.assertEqual(self.client.get(pages[kind]).status_code, 404)


if __name__ == "__main__":
    unittest.main()
