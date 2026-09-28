"""
Database Schema Initializer & Data Access Layer for B2B Agentic Enterprise.

Manages SQLite pipeline.db connection, table creation, migrations, and seed data.
"""

import sqlite3
import os
import json
from datetime import datetime, timedelta

DEFAULT_DB_PATH = os.getenv("DB_PATH", "pipeline.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Returns a thread-safe SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes SQLite database tables if they do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Leads Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            decision_maker TEXT,
            target_keyword TEXT,
            service_lane TEXT,
            email_body TEXT,
            subject TEXT,
            status TEXT NOT NULL DEFAULT 'scouted',
            compliance_notes TEXT,
            last_contacted_date TIMESTAMP,
            follow_up_count INTEGER DEFAULT 0,
            source_platform TEXT DEFAULT 'web_search',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Safe migration for existing databases — add new columns if missing
    _migrate_leads_table(cursor)

    # 2. Campaign Directives Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaign_directives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            directive_text TEXT NOT NULL,
            target_sectors TEXT,
            focus_service_lane TEXT,
            search_keywords TEXT,
            allocation_percentage REAL DEFAULT 100.0,
            reasoning TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 3. Replies Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            sender_email TEXT NOT NULL,
            subject TEXT,
            body TEXT NOT NULL,
            sentiment TEXT NOT NULL,
            service_lane TEXT,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE SET NULL
        );
    """)

    # 4. Analytics Logs Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analytics_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()


def _migrate_leads_table(cursor: sqlite3.Cursor) -> None:
    """Safely adds new columns to the leads table if they don't already exist."""
    cursor.execute("PRAGMA table_info(leads);")
    existing_cols = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("email", "TEXT"),
        ("last_contacted_date", "TIMESTAMP"),
        ("follow_up_count", "INTEGER DEFAULT 0"),
        ("source_platform", "TEXT DEFAULT 'web_search'"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_def};")
            except sqlite3.OperationalError:
                pass  # Column already exists or other benign error


def seed_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Populates pipeline.db with initial historic data across service lanes
    so Analytics & Strategy agents have rich data to analyze immediately.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Check if data already seeded
    cursor.execute("SELECT COUNT(*) as cnt FROM leads;")
    if cursor.fetchone()["cnt"] > 0:
        conn.close()
        return

    # Initial Active Directive
    cursor.execute("""
        INSERT INTO campaign_directives (directive_text, target_sectors, focus_service_lane, search_keywords, allocation_percentage, reasoning, status)
        VALUES (
            'Target hardware startups & robotics companies requiring mechatronics design optimization.',
            'Robotics, Industrial Automation, Embedded IoT, Medical Hardware',
            'SolidWorks DFM',
            '["robotics startup mechanical engineer", "SolidWorks DFM hardware", "ROS 2 Gazebo simulation", "TinyML ESP32 STM32"]',
            50.0,
            'Initial baseline directive focused on core mechatronics capabilities.',
            'active'
        );
    """)

    # Historic Sent Leads & Replies
    sample_leads = [
        # SolidWorks DFM (High positive reply rate)
        ("AeroMech Dynamics", "https://aeromech-example.com", "VP of Engineering", "SolidWorks DFM", "SolidWorks DFM", "sent", "Hi Mark,\n\nNoticed AeroMech's new actuator module. At UET Faisalabad, I specialize in SolidWorks DFM—optimizing complex assemblies for CNC machining and sheet metal to cut unit cost by 20%.\n\nWorth a 5-min chat?", "SolidWorks DFM for AeroMech"),
        ("Kinetix Robotics", "https://kinetix-robotics-demo.com", "Head of Hardware", "robotics startup mechanical", "SolidWorks DFM", "sent", "Hi Sarah,\n\nSaw Kinetix's quadcopter arm redesign. As a final-year Mechatronics engineer, I focus on SolidWorks DFM and stress analysis to trim weight without structural loss.\n\nOpen to discussing?", "DFM Optimization for Kinetix"),
        ("NovaFab Tech", "https://novafab-tech-sample.com", "CTO", "SolidWorks DFM", "SolidWorks DFM", "sent", "Hi Alex,\n\nYour rapid prototyping pipeline looks impressive. My SolidWorks DFM workflow streamlines tolerance stack-ups for fast low-volume injection molding.\n\nCan I send a 1-page case study?", "Injection Molding DFM"),
        ("Veloce Motion", "https://veloce-motion-demo.com", "Chief Engineer", "SolidWorks DFM", "SolidWorks DFM", "sent", "Hi Dave,\n\nVeloce's linear stage looks solid. I leverage SolidWorks DFM and FEA simulation to optimize component geometry before production tooling.\n\nLet's connect this week.", "Mechanical DFM Engineering"),

        # ROS 2 / Gazebo Simulation
        ("RoboNav Systems", "https://robonav-systems-demo.com", "Director of Robotics", "ROS 2 Gazebo simulation", "ROS 2 / Gazebo", "sent", "Hi Elena,\n\nSaw RoboNav's AMR navigation platform. I build ROS 2 / Gazebo simulation environments with custom URDFs and Nav2 pipelines for virtual fleet testing.\n\nWould a demo video be helpful?", "ROS 2 / Gazebo Simulation for RoboNav"),
        ("OmniBot Dynamics", "https://omnibot-dynamics-demo.com", "Robotics Lead", "ROS 2 Gazebo simulation", "ROS 2 / Gazebo", "sent", "Hi Ryan,\n\nOmniBot's manipulator looks promising. My Gazebo physics simulations validate ROS 2 control algorithms before physical hardware integration.\n\nAvailable for a quick call?", "ROS 2 Control & Gazebo Sim"),

        # TinyML / INT8 Quantization
        ("EdgeSense Micro", "https://edgesense-micro-demo.com", "Firmware Architect", "TinyML ESP32 STM32", "TinyML / INT8 Quantization", "sent", "Hi Chen,\n\nLoved EdgeSense's low-power vibration node. I optimize TinyML models using INT8 quantization for ESP32 and STM32 MCUs, maximizing battery life.\n\nOpen to reviewing benchmarks?", "INT8 TinyML Quantization on ESP32/STM32"),
        ("NeuralNode IoT", "https://neuralnode-iot-demo.com", "VP Product", "TinyML ESP32 STM32", "TinyML / INT8 Quantization", "sent", "Hi Lisa,\n\nNeuralNode's acoustic sensor setup is sleek. I deploy INT8 quantized neural networks on STM32 microcontrollers for real-time edge anomaly detection.\n\nCare to connect?", "Edge AI / INT8 Quantization"),

        # Cascade Pneumatics
        ("Fluidic Automation", "https://fluidic-auto-demo.com", "Operations Mgr", "pneumatic sequence control", "Cascade Pneumatics", "sent", "Hi James,\n\nNoticed Fluidic's multi-axis packing cell. I design cascade pneumatic circuits and PLC valve manifolds for reliable high-speed sequence automation.\n\nFree for a quick introduction?", "Cascade Pneumatic Sequence Design")
    ]

    lead_ids = []
    for company, url, dm, kw, lane, status, body, subj in sample_leads:
        cursor.execute("""
            INSERT INTO leads (company_name, url, decision_maker, target_keyword, service_lane, status, email_body, subject)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (company, url, dm, kw, lane, status, body, subj))
        lead_ids.append((cursor.lastrowid, company, lane))

    # Sample Historic Replies to reflect different sentiments per service lane
    # Note: SolidWorks DFM has high positive replies, ROS 2 has negative/pricing, TinyML has positive.
    sample_replies = [
        (lead_ids[0][0], "mark@aeromech-example.com", "Re: SolidWorks DFM for AeroMech", "Hey! Thanks for reaching out. We actually have an arm assembly that needs DFM optimization. Are you free Thursday at 2 PM?", "Positive", "SolidWorks DFM"),
        (lead_ids[1][0], "sarah@kinetix-robotics-demo.com", "Re: DFM Optimization for Kinetix", "Hi, this sounds interesting. What are your hourly rates or project quotes?", "Pricing", "SolidWorks DFM"),
        (lead_ids[2][0], "alex@novafab-tech-sample.com", "Re: Injection Molding DFM", "Yes, please send over the case study! We are launching a new casing next month.", "Positive", "SolidWorks DFM"),
        (lead_ids[4][0], "elena@robonav-systems-demo.com", "Re: ROS 2 / Gazebo Simulation for RoboNav", "Thanks, but we currently handle all ROS 2 simulation in-house. Please unsubscribe us.", "Negative", "ROS 2 / Gazebo"),
        (lead_ids[6][0], "chen@edgesense-micro-demo.com", "Re: INT8 TinyML Quantization on ESP32/STM32", "Great timing. We are trying to squeeze a keyword spotting model into an STM32F4. Let's setup a call.", "Positive", "TinyML / INT8 Quantization")
    ]

    for lead_id, email, subj, body, sent, lane in sample_replies:
        cursor.execute("""
            INSERT INTO replies (lead_id, sender_email, subject, body, sentiment, service_lane)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (lead_id, email, subj, body, sent, lane))
        # Update lead status to replied
        cursor.execute("UPDATE leads SET status = 'replied' WHERE id = ?;", (lead_id,))

    conn.commit()
    conn.close()
    print(f"[Database] Successfully initialized & seeded pipeline.db at {db_path}")


if __name__ == "__main__":
    init_db()
    seed_database()
