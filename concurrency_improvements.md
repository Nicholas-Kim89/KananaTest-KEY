# Concurrency Improvements and Testing Guide

This document details the recent updates made to address concurrent user access issues and the testing strategies employed to verify them.

## Issue Summary
When multiple users logged into the system and triggered database writes simultaneously (e.g., adding progress logs, querying AI summaries), the application encountered SQLite locking errors such as `"database is locked"`.

This occurred because the default SQLite configuration (`journal_mode=delete`) locks the entire database file during a write operation, preventing both other writers and readers from accessing it. In a production-like environment with multiple Gunicorn workers or threads processing requests concurrently, this frequently leads to failed requests.

## Key Changes Made

To resolve this, the SQLite database connections in the core configuration files were updated:

1.  **Write-Ahead Logging (WAL)**: Enabled WAL mode (`PRAGMA journal_mode=WAL;`). This mode allows multiple readers to exist simultaneously with a single writer, drastically improving read concurrency.
2.  **Increased Timeout**: Added a 10-second `timeout` to the SQLite connection (`timeout=10`). This tells SQLite to wait and retry for up to 10 seconds if the database is currently locked by another writer, rather than failing immediately.

These changes were applied to:
*   `db.py` (`init_db` and `get_db_connection`)
*   `rag.py` (`get_db`)

Additionally, `.gitignore` was updated to exclude `workprogress.db` and log files (`*.log`) from version control to prevent committing local database states.

## Concurrency Testing Performed

To verify the effectiveness of the fixes, several test scripts were created and placed in the `tests/` directory.

### 1. Concurrent Logins (`tests/test_concurrent_login.py`)
*   **Goal**: Simulate a scenario where dozens of users attempt to log in at the exact same moment.
*   **Action**: Spawns 100 concurrent threads, each sending a POST request to the `/login` endpoint with valid credentials.
*   **Result**: All requests successfully connect, query the database, and authenticate the users without errors.

### 2. Concurrent Writes (`tests/test_concurrent_writes.py`)
*   **Goal**: Simulate multiple users adding progress updates simultaneously.
*   **Action**: 20 threads concurrently log in and submit POST requests to `/api/add-progress`.
*   **Result**: All database writes (inserting into `progress_logs` and triggering RAG syncs) successfully complete without `database is locked` errors.

### 3. Heavy Mixed Workload (`tests/test_heavy_concurrent.py`)
*   **Goal**: Simulate a realistic heavy user flow involving mixed read/write operations.
*   **Action**: 50 threads each perform the following sequence: Login -> Request AI Summary (Read heavy) -> Add Progress (Write heavy).
*   **Result**: The system handles the load gracefully, completing all steps for all threads.

### 4. Direct DB Lock Simulation (`tests/test_db_timeout*.py`)
*   **Goal**: Explicitly test the `timeout` configuration.
*   **Action**: Uses Python's `sqlite3` module directly. One thread opens an `EXCLUSIVE` transaction and sleeps for 6 seconds (holding the lock). Another thread attempts to write.
*   **Result**: Thanks to the 10-second timeout, the second thread successfully waits for the lock to be released and then completes its write operation, instead of immediately crashing.

## Conclusion
The implementation of WAL mode and connection timeouts has successfully mitigated the concurrency bottlenecks associated with SQLite in this application. The system can now reliably support concurrent usage by multiple team members.
