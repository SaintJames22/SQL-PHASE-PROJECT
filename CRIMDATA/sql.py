import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

DB_NAME = str(Path(__file__).resolve().parent / "system.db")


def create_schema(cursor):
    cursor.execute("PRAGMA foreign_keys = ON;")

    tables = [
        "Warrants",
        "Charges",
        "BiometricProfiles",
        "Evidence",
        "IncidentSuspects",
        "Suspects",
        "Incidents",
        "Officers",
        "Precincts",
        "Users",
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table};")

    # 1. Users (Superclass)
    cursor.execute("""
    CREATE TABLE Users (
        UserID INTEGER PRIMARY KEY AUTOINCREMENT,
        Username TEXT NOT NULL UNIQUE,
        PasswordHash TEXT NOT NULL,
        Role TEXT NOT NULL CHECK (Role IN ('Officer', 'Dispatcher', 'Admin')),
        CreatedAt TEXT NOT NULL
    );
    """)

    # 2. Precincts
    cursor.execute("""
    CREATE TABLE Precincts (
        PrecinctID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL UNIQUE,
        Address TEXT NOT NULL,
        City TEXT NOT NULL,
        Phone TEXT NOT NULL UNIQUE
    );
    """)

    # 3. Officers (Subclass of Users via ISA hierarchy: OfficerID is both PK and FK -> Users.UserID)
    cursor.execute("""
    CREATE TABLE Officers (
        OfficerID INTEGER PRIMARY KEY,
        BadgeNumber TEXT NOT NULL UNIQUE,
        Rank TEXT NOT NULL,
        PrecinctID INTEGER NOT NULL,
        Specialization TEXT NOT NULL,
        FOREIGN KEY (OfficerID) REFERENCES Users(UserID) ON DELETE CASCADE,
        FOREIGN KEY (PrecinctID) REFERENCES Precincts(PrecinctID) ON DELETE RESTRICT
    );
    """)

    # 4. Incidents (1:N with Officers)
    cursor.execute("""
    CREATE TABLE Incidents (
        IncidentID INTEGER PRIMARY KEY AUTOINCREMENT,
        IncidentDate TEXT NOT NULL,
        IncidentTime TEXT NOT NULL,
        Location TEXT NOT NULL,
        IncidentType TEXT NOT NULL,
        Status TEXT NOT NULL CHECK (Status IN ('Open', 'Under Investigation', 'Closed', 'Cold Case')),
        Description TEXT NOT NULL,
        HandlingOfficerID INTEGER NOT NULL,
        FOREIGN KEY (HandlingOfficerID) REFERENCES Officers(OfficerID) ON DELETE RESTRICT
    );
    """)

    # 5. Suspects
    cursor.execute("""
    CREATE TABLE Suspects (
        SuspectID INTEGER PRIMARY KEY AUTOINCREMENT,
        FirstName TEXT NOT NULL,
        LastName TEXT NOT NULL,
        DateOfBirth TEXT NOT NULL,
        Gender TEXT NOT NULL,
        Address TEXT NOT NULL,
        Status TEXT NOT NULL CHECK (Status IN ('At Large', 'In Custody', 'Released on Bail', 'Cleared')),
        Alias TEXT,
        CriminalRecord TEXT NOT NULL
    );
    """)

    # 6. IncidentSuspects (Junction table resolving M:N between Incidents and Suspects)
    cursor.execute("""
    CREATE TABLE IncidentSuspects (
        IncidentID INTEGER NOT NULL,
        SuspectID INTEGER NOT NULL,
        Role TEXT NOT NULL CHECK (Role IN ('Primary Suspect', 'Accomplice', 'Person of Interest')),
        Statement TEXT,
        DateLinked TEXT NOT NULL,
        PRIMARY KEY (IncidentID, SuspectID),
        FOREIGN KEY (IncidentID) REFERENCES Incidents(IncidentID) ON DELETE CASCADE,
        FOREIGN KEY (SuspectID) REFERENCES Suspects(SuspectID) ON DELETE CASCADE
    );
    """)

    # 7. Evidence (1:N with Incidents)
    cursor.execute("""
    CREATE TABLE Evidence (
        EvidenceID INTEGER PRIMARY KEY AUTOINCREMENT,
        IncidentID INTEGER NOT NULL,
        Type TEXT NOT NULL,
        Description TEXT NOT NULL,
        DateCollected TEXT NOT NULL,
        ChainOfCustody TEXT NOT NULL,
        Location TEXT NOT NULL,
        FOREIGN KEY (IncidentID) REFERENCES Incidents(IncidentID) ON DELETE CASCADE
    );
    """)

    # 8. BiometricProfiles (1:1 with Suspects enforced via UNIQUE on SuspectID)
    cursor.execute("""
    CREATE TABLE BiometricProfiles (
        ProfileID INTEGER PRIMARY KEY AUTOINCREMENT,
        SuspectID INTEGER NOT NULL UNIQUE,
        FingerprintHash TEXT NOT NULL UNIQUE,
        IrisScanHash TEXT NOT NULL UNIQUE,
        DNAMarker TEXT NOT NULL UNIQUE,
        FacialFeatureHash TEXT NOT NULL UNIQUE,
        FOREIGN KEY (SuspectID) REFERENCES Suspects(SuspectID) ON DELETE CASCADE
    );
    """)

    # 9. Charges (1:N with Suspects and 1:N with Incidents)
    cursor.execute("""
    CREATE TABLE Charges (
        ChargeID INTEGER PRIMARY KEY AUTOINCREMENT,
        SuspectID INTEGER NOT NULL,
        IncidentID INTEGER NOT NULL,
        LawSection TEXT NOT NULL,
        OffenseType TEXT NOT NULL,
        Degree TEXT NOT NULL CHECK (
            Degree IN (
                'Misdemeanor',
                'Class E Felony',
                'Class D Felony',
                'Class C Felony',
                'Class B Felony',
                'Class A Felony'
            )
        ),
        FilingDate TEXT NOT NULL,
        FOREIGN KEY (SuspectID) REFERENCES Suspects(SuspectID) ON DELETE CASCADE,
        FOREIGN KEY (IncidentID) REFERENCES Incidents(IncidentID) ON DELETE CASCADE
    );
    """)

    # 10. Warrants (1:N with Suspects, Officers, and Incidents)
    cursor.execute("""
    CREATE TABLE Warrants (
        WarrantID INTEGER PRIMARY KEY AUTOINCREMENT,
        Type TEXT NOT NULL CHECK (Type IN ('Arrest', 'Search', 'Bench', 'Extradition')),
        IssueDate TEXT NOT NULL,
        ExpirationDate TEXT NOT NULL,
        JudgeName TEXT NOT NULL,
        SuspectID INTEGER NOT NULL,
        OfficerID INTEGER NOT NULL,
        IncidentID INTEGER NOT NULL,
        Status TEXT NOT NULL CHECK (Status IN ('Active', 'Executed', 'Expired', 'Recalled')),
        FOREIGN KEY (SuspectID) REFERENCES Suspects(SuspectID) ON DELETE CASCADE,
        FOREIGN KEY (OfficerID) REFERENCES Officers(OfficerID) ON DELETE RESTRICT,
        FOREIGN KEY (IncidentID) REFERENCES Incidents(IncidentID) ON DELETE CASCADE
    );
    """)


def seed_data(cursor):
    random.seed(42)

    # 1. Users (20 rows)
    users_data = []
    for i in range(1, 21):
        if i <= 15:
            role = "Officer"
            uname = f"ofc_badge{100 + i}"
        elif i <= 18:
            role = "Dispatcher"
            uname = f"disp_unit{i}"
        else:
            role = "Admin"
            uname = f"sys_admin{i}"
        pw_hash = f"sha256$9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a{i:02d}"
        created_at = (datetime(2025, 1, 10) + timedelta(days=i * 12)).strftime("%Y-%m-%d")
        users_data.append((uname, pw_hash, role, created_at))
    cursor.executemany(
        "INSERT INTO Users (Username, PasswordHash, Role, CreatedAt) VALUES (?, ?, ?, ?);",
        users_data,
    )

    # 2. Precincts (12 rows)
    precincts_data = [
        ("1st Precinct", "16 Ericsson Pl", "New York", "212-334-0611"),
        ("5th Precinct", "19 Elizabeth St", "New York", "212-334-0711"),
        ("9th Precinct", "321 E 5th St", "New York", "212-477-7811"),
        ("13th Precinct", "230 E 21st St", "New York", "212-477-7411"),
        ("Midtown South Precinct", "357 W 35th St", "New York", "212-239-9811"),
        ("19th Precinct", "153 E 67th St", "New York", "212-452-0600"),
        ("24th Precinct", "151 W 100th St", "New York", "212-678-1811"),
        ("40th Precinct", "257 Alexander Ave", "Bronx", "718-402-2270"),
        ("67th Precinct", "2820 Snyder Ave", "Brooklyn", "718-287-3211"),
        ("84th Precinct", "301 Gold St", "Brooklyn", "718-875-6811"),
        ("109th Precinct", "37-05 Union St", "Queens", "718-321-2250"),
        ("114th Precinct", "34-16 Astoria Blvd", "Queens", "718-626-9311"),
    ]
    cursor.executemany(
        "INSERT INTO Precincts (Name, Address, City, Phone) VALUES (?, ?, ?, ?);",
        precincts_data,
    )

    # 3. Officers (15 rows)
    ranks = ["Police Officer", "Detective 3rd Grade", "Detective 2nd Grade", "Sergeant", "Lieutenant"]
    specs = ["Homicide", "Cybercrime", "Narcotics", "Financial Crimes", "Special Victims", "Robbery Squad"]
    officers_data = []
    for user_id in range(1, 16):
        badge = f"NYPD-{4000 + user_id}"
        rank = ranks[user_id % len(ranks)]
        precinct_id = ((user_id - 1) % 12) + 1
        spec = specs[user_id % len(specs)]
        officers_data.append((user_id, badge, rank, precinct_id, spec))
    cursor.executemany(
        "INSERT INTO Officers (OfficerID, BadgeNumber, Rank, PrecinctID, Specialization) VALUES (?, ?, ?, ?, ?);",
        officers_data,
    )

    # 4. Incidents (15 rows)
    incident_types = ["Grand Larceny", "Armed Robbery", "Cyber Intrusion", "Aggravated Assault", "Burglary", "Wire Fraud"]
    statuses = ["Open", "Under Investigation", "Closed", "Cold Case"]
    locations = [
        "120 Broadway, Manhattan",
        "450 Lexington Ave, Manhattan",
        "88 Queens Blvd, Queens",
        "210 Atlantic Ave, Brooklyn",
        "315 Grand Concourse, Bronx",
        "742 Evergreen Terrace, Queens",
        "1900 3rd Ave, Manhattan",
        "55 Water St, Manhattan",
        "102-10 Metropolitan Ave, Queens",
        "610 Flatbush Ave, Brooklyn",
        "14 Wall St, Manhattan",
        "35-11 Northern Blvd, Queens",
        "225 W 34th St, Manhattan",
        "89-02 Sutphin Blvd, Queens",
        "500 Fulton St, Brooklyn",
    ]
    incidents_data = []
    for i in range(1, 16):
        inc_date = (datetime(2026, 2, 1) + timedelta(days=i * 11)).strftime("%Y-%m-%d")
        inc_time = f"{(8 + i) % 24:02d}:{(i * 13) % 60:02d}:00"
        loc = locations[i - 1]
        i_type = incident_types[i % len(incident_types)]
        status = statuses[i % len(statuses)]
        desc = f"Reported {i_type.lower()} incident at {loc}; patrol unit secured scene and logged initial statements."
        officer_id = ((i - 1) % 15) + 1
        incidents_data.append((inc_date, inc_time, loc, i_type, status, desc, officer_id))
    cursor.executemany(
        """INSERT INTO Incidents
           (IncidentDate, IncidentTime, Location, IncidentType, Status, Description, HandlingOfficerID)
           VALUES (?, ?, ?, ?, ?, ?, ?);""",
        incidents_data,
    )

    # 5. Suspects (15 rows)
    suspect_names = [
        ("Marcus", "Vance", "1991-04-12", "Male", "412 E 14th St, New York, NY", "In Custody", "Ghost", "2 prior felony arrests for burglary"),
        ("Elena", "Rostova", "1988-09-23", "Female", "77-15 Queens Blvd, Elmhurst, NY", "At Large", "Viper", "Wanted for international wire fraud"),
        ("Devon", "Brooks", "1995-11-03", "Male", "1180 Fulton St, Brooklyn, NY", "Released on Bail", "D-Block", "Prior misdemeanor larceny conviction"),
        ("Tariq", "Al-Mansoor", "1984-02-17", "Male", "2900 Broadway, New York, NY", "In Custody", None, "No prior criminal record"),
        ("Sofia", "Castillo", "1993-07-30", "Female", "91-30 Corona Ave, Queens, NY", "At Large", "Sombra", "Prior arrest for identity theft"),
        ("Victor", "Kowalski", "1979-12-08", "Male", "642 Manhattan Ave, Brooklyn, NY", "In Custody", "Vic", "3 prior felony convictions (robbery)"),
        ("Darius", "Sterling", "1997-05-19", "Male", "310 E 138th St, Bronx, NY", "Cleared", None, "No prior convictions"),
        ("Mei", "Lin", "1990-01-25", "Female", "41-25 Kissena Blvd, Flushing, NY", "Released on Bail", "Cipher", "Prior cyber trespass charge"),
        ("Carlos", "Mendoza", "1986-08-14", "Male", "1450 St Nicholas Ave, New York, NY", "At Large", "Chino", "2 prior narcotics and weapons charges"),
        ("Nadia", "Okafor", "1994-03-11", "Female", "520 Nostrand Ave, Brooklyn, NY", "In Custody", None, "1 prior grand larceny arrest"),
        ("Julian", "Mercer", "1982-10-29", "Male", "215 W 84th St, New York, NY", "Released on Bail", "Jules", "Prior embezzlement investigation"),
        ("Hector", "Salazar", "1992-06-05", "Male", "84-12 Roosevelt Ave, Jackson Heights, NY", "At Large", "Toro", "Repeat offender - aggravated assault"),
        ("Keisha", "Reynolds", "1996-12-21", "Female", "700 E 156th St, Bronx, NY", "Cleared", None, "Clean record"),
        ("Roman", "Volkov", "1985-04-02", "Male", "2850 Ocean Pkwy, Brooklyn, NY", "In Custody", "Wolf", "Prior racketeering and fraud offenses"),
        ("Andre", "Baptiste", "1989-07-16", "Male", "114-05 Merrick Blvd, Jamaica, NY", "At Large", "Dre", "2 prior vehicle theft convictions"),
    ]
    cursor.executemany(
        """INSERT INTO Suspects
           (FirstName, LastName, DateOfBirth, Gender, Address, Status, Alias, CriminalRecord)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
        suspect_names,
    )

    # 6. IncidentSuspects (20 rows)
    roles_ms = ["Primary Suspect", "Accomplice", "Person of Interest"]
    incident_suspects_data = []
    used_pairs = set()
    for idx in range(1, 21):
        inc_id = ((idx - 1) % 15) + 1
        sus_id = ((idx * 2 - 1) % 15) + 1
        while (inc_id, sus_id) in used_pairs:
            sus_id = (sus_id % 15) + 1
        used_pairs.add((inc_id, sus_id))
        role = roles_ms[idx % len(roles_ms)]
        statement = f"Subject interviewed regarding Incident #{inc_id}; denied direct involvement."
        date_linked = (datetime(2026, 2, 5) + timedelta(days=idx * 10)).strftime("%Y-%m-%d")
        incident_suspects_data.append((inc_id, sus_id, role, statement, date_linked))
    cursor.executemany(
        """INSERT INTO IncidentSuspects
           (IncidentID, SuspectID, Role, Statement, DateLinked)
           VALUES (?, ?, ?, ?, ?);""",
        incident_suspects_data,
    )

    # 7. Evidence (16 rows)
    ev_types = ["Digital Forensics", "DNA Swab", "CCTV Footage", "Latent Fingerprint", "Weapon", "Financial Ledger"]
    evidence_data = []
    for i in range(1, 17):
        inc_id = ((i - 1) % 15) + 1
        e_type = ev_types[i % len(ev_types)]
        desc = f"{e_type} recovered from scene of Incident #{inc_id} (Item #{100 + i})."
        d_col = (datetime(2026, 2, 2) + timedelta(days=i * 11)).strftime("%Y-%m-%d")
        custody = f"Collected by NYPD-{4000 + inc_id} -> Logged into Precinct Evidence Locker #{i}"
        loc = f"Evidence Vault Bay {(i % 5) + 1}, Shelf {i}"
        evidence_data.append((inc_id, e_type, desc, d_col, custody, loc))
    cursor.executemany(
        """INSERT INTO Evidence
           (IncidentID, Type, Description, DateCollected, ChainOfCustody, Location)
           VALUES (?, ?, ?, ?, ?, ?);""",
        evidence_data,
    )

    # 8. BiometricProfiles (15 rows, strict 1:1)
    biometrics_data = []
    for sus_id in range(1, 16):
        fp = f"FP_SHA256_{sus_id:04d}_A9B8C7D6"
        iris = f"IRIS_HASH_{sus_id:04d}_11223344"
        dna = f"STR_LOCI_D3S1358_{10 + sus_id}_vWA_{14 + (sus_id % 6)}"
        face = f"FACE_VEC_{sus_id:04d}_99887766"
        biometrics_data.append((sus_id, fp, iris, dna, face))
    cursor.executemany(
        """INSERT INTO BiometricProfiles
           (SuspectID, FingerprintHash, IrisScanHash, DNAMarker, FacialFeatureHash)
           VALUES (?, ?, ?, ?, ?);""",
        biometrics_data,
    )

    # 9. Charges (15 rows)
    law_sections = [
        ("NY PL 155.40", "Grand Larceny in the Second Degree", "Class C Felony"),
        ("NY PL 160.15", "Robbery in the First Degree", "Class B Felony"),
        ("NY PL 156.10", "Computer Trespass", "Class E Felony"),
        ("NY PL 120.05", "Assault in the Second Degree", "Class D Felony"),
        ("NY PL 140.25", "Burglary in the Second Degree", "Class C Felony"),
        ("NY PL 190.65", "Scheme to Defraud in the First Degree", "Class E Felony"),
    ]
    charges_data = []
    for i in range(1, 16):
        inc_id, sus_id, _, _, _ = incident_suspects_data[i - 1]
        sec, off_type, deg = law_sections[i % len(law_sections)]
        f_date = (datetime(2026, 2, 10) + timedelta(days=i * 11)).strftime("%Y-%m-%d")
        charges_data.append((sus_id, inc_id, sec, off_type, deg, f_date))
    cursor.executemany(
        """INSERT INTO Charges
           (SuspectID, IncidentID, LawSection, OffenseType, Degree, FilingDate)
           VALUES (?, ?, ?, ?, ?, ?);""",
        charges_data,
    )

    # 10. Warrants (15 rows)
    w_types = ["Arrest", "Search", "Bench", "Extradition"]
    w_statuses = ["Active", "Executed", "Expired", "Recalled"]
    judges = ["Hon. Arthur Pendelton", "Hon. Maria Alvarez", "Hon. David Chen", "Hon. Evelyn Ross"]
    warrants_data = []
    for i in range(1, 16):
        inc_id, sus_id, _, _, _ = incident_suspects_data[i - 1]
        off_id = ((inc_id - 1) % 15) + 1
        w_type = w_types[i % len(w_types)]
        iss_date = (datetime(2026, 2, 6) + timedelta(days=i * 11)).strftime("%Y-%m-%d")
        exp_date = (datetime(2026, 5, 6) + timedelta(days=i * 11)).strftime("%Y-%m-%d")
        judge = judges[i % len(judges)]
        w_stat = w_statuses[i % len(w_statuses)]
        warrants_data.append((w_type, iss_date, exp_date, judge, sus_id, off_id, inc_id, w_stat))
    cursor.executemany(
        """INSERT INTO Warrants
           (Type, IssueDate, ExpirationDate, JudgeName, SuspectID, OfficerID, IncidentID, Status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?);""",
        warrants_data,
    )


def main():
    conn = sqlite3.connect(DB_NAME)
    try:
        cursor = conn.cursor()
        create_schema(cursor)
        seed_data(cursor)
        conn.commit()
        print(f"Successfully initialized '{DB_NAME}' with all 10 tables and sample data.\n")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        for (table_name,) in cursor.fetchall():
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"  - {table_name:<20}: {count} rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    
