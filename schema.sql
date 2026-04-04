DROP TABLE IF EXISTS groups;
DROP TABLE IF EXISTS divisions;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS members;

CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    leader_name TEXT,
    leader_position TEXT,
    leader_email TEXT
);

CREATE TABLE divisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    leader_name TEXT,
    leader_position TEXT,
    leader_email TEXT,
    FOREIGN KEY (group_id) REFERENCES groups (id)
);

CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    leader_name TEXT,
    leader_position TEXT,
    leader_email TEXT,
    FOREIGN KEY (division_id) REFERENCES divisions (id)
);

CREATE TABLE members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    position TEXT NOT NULL, /* 사원, 선임, 책임, 상무, 전문위원 */
    email TEXT,
    FOREIGN KEY (team_id) REFERENCES teams (id)
);

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
