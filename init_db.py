import sqlite3
import os

# Create database if it doesn't exist
db_path = 'state/videos.db'
os.makedirs(os.path.dirname(db_path), exist_ok=True)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create tables
cur.execute('''
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logline TEXT NOT NULL,
    prop TEXT NOT NULL,
    teaser TEXT NOT NULL,
    era TEXT NOT NULL,
    source_url TEXT,
    story_json TEXT,
    character_sheet TEXT,
    title_main TEXT,
    status TEXT DEFAULT 'pending',
    fact_checked BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    selected_at TIMESTAMP NULL
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    flow_id INTEGER,
    prompt_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS cycle_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_number INTEGER,
    cycle_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT,
    notes TEXT
)
''')

# Create indexes for performance
cur.execute('CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_cycle_date ON cycle_log(cycle_date)')  # Fixed: date -> cycle_date

# Commit changes
conn.commit()
conn.close()

print("Database initialized successfully")