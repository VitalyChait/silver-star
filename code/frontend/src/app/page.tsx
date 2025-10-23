"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import './globals.css';

type Job = {
  id: number;
  title: string;
  company?: string | null;
  location?: string | null;
  description: string;
  job_type?: string | null;
  url?: string | null;
  created_at: string;
};

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = async (query?: string) => {
    try {
      setLoading(true);
      setError(null);
      const u = new URL("http://localhost:8000/api/jobs/", window.location.origin);
      if (query) u.searchParams.set("q", query);
      const res = await fetch(u);
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      const data = await res.json();
      setJobs(data);
    } catch (e: any) {
      setError(e.message || "Error fetching jobs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  return (
    <main>
      <header className="site-header">
        <h1>Silver Star Jobs</h1>
        <p>Find your next opportunity</p>
        <Link href="/chatbot" className="chatbot-link">
          Try our AI Job Assistant →
        </Link>
      </header>

      <section className="search-section">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            fetchJobs(q);
          }}
          className="search-form"
        >
          <input
            type="text"
            placeholder="Search jobs (title, company, location)"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="search-input"
          />
          <button type="submit" className="search-button">
            Search
          </button>
        </form>
      </section>

      {loading && <p>Loading…</p>}
      {error && <p className="error">{error}</p>}

      <section>
        {jobs.length === 0 && !loading ? (
          <p>No jobs yet. Add some via the API.</p>
        ) : (
          <ul className="job-list">
            {jobs.map((job) => (
              <li key={job.id} className="job-item">
                <div className="job-header">
                  <div>
                    <h3>{job.title}</h3>
                    <p className="job-meta">
                      {[job.company, job.location].filter(Boolean).join(" • ")}
                    </p>
                  </div>
                  <small className="job-date">{new Date(job.created_at).toLocaleDateString()}</small>
                </div>
                <p className="job-description">
                  {job.description.length > 220
                    ? job.description.slice(0, 220) + "…"
                    : job.description}
                </p>
                {job.url && (
                  <a href={job.url} target="_blank" rel="noreferrer" className="job-link">
                    Apply →
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <style jsx>{`
        .site-header {
          text-align: center;
          margin-bottom: 2rem;
          padding: 2rem 0;
          background-color: #f5f5f5;
          border-radius: 8px;
        }

        .site-header h1 {
          margin: 0 0 0.5rem 0;
          color: #333;
        }

        .site-header p {
          margin: 0 0 1rem 0;
          color: #666;
        }

        .chatbot-link {
          display: inline-block;
          background-color: #1976d2;
          color: white;
          padding: 0.75rem 1.5rem;
          border-radius: 24px;
          text-decoration: none;
          font-weight: 500;
          transition: background-color 0.2s;
        }

        .chatbot-link:hover {
          background-color: #1565c0;
        }
      `}</style>
    </main>
  );
}

