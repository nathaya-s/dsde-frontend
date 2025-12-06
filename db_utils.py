import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

MAPBOX_API_KEY = st.secrets["MAPBOX_API_KEY"]
PG_HOST = st.secrets.get("PG_HOST", "localhost")
PG_PORT = st.secrets.get("PG_PORT", "5432")
PG_DB   = st.secrets.get("PG_DB")
PG_USER = st.secrets.get("PG_USER")
PG_PASS = st.secrets.get("PG_PASS")
PG_SSL  = st.secrets.get("PG_SSLMODE")  
SNAPSHOT_BASE = st.secrets.get("SNAPSHOT_BASE", "http://127.0.0.1:9000/snapshot")



def get_conn():
    sslmode = PG_SSL
    if PG_HOST in ("localhost", "127.0.0.1"):
        sslmode = sslmode or "disable"
    else:
        sslmode = sslmode or "require"

    if not all([PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS]):
        st.error("Missing DB secrets. Check .streamlit/secrets.toml")
        st.stop()

    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        sslmode=sslmode,
        cursor_factory=RealDictCursor
    )
    
@st.cache_data
def get_map_data(limit=1000, start_date=None, end_date=None) -> pd.DataFrame:
    query = """
        SELECT
            mv.ticket_id,
            mv.type,
            mv.state,
            mv.district,
            mv.lng,
            mv.lat,
            mv.timestamp,

            t.comment,
            t.organization,
            t.subdistrict,
            t.organization_action,
            t.photo,
            t.duration_minutes_inprogress,
            t.duration_minutes_finished,
            t.duration_minutes_total

        FROM traffy_map_view mv
        LEFT JOIN traffy_tickets t
        ON mv.ticket_id = t.ticket_id
        WHERE mv.lng IS NOT NULL AND mv.lat IS NOT NULL
    """

    params = []
    if start_date:
        query += " AND mv.timestamp::date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND mv.timestamp::date <= %s"
        params.append(end_date)

    query += " ORDER BY mv.timestamp DESC LIMIT %s"
    params.append(limit)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

    df = pd.DataFrame(rows, columns=[
        "ticket_id", "type", "state", "district",
        "lng", "lat", "timestamp",
        "comment", "organization", "subdistrict",
        "organization_action", "photo",
        "duration_minutes_inprogress", "duration_minutes_finished", "duration_minutes_total"
    ])

    if df.empty:
        return df

    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["lng", "lat", "timestamp"])

    return df


@st.cache_data(ttl=20)
def load_cctv_df() -> pd.DataFrame:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id,
                   COALESCE(NULLIF(name_en, ''), name_th) AS name,
                   lat, lng
            FROM cctv_meta
            WHERE lat IS NOT NULL AND lng IS NOT NULL
            ORDER BY id;
        """)
        rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df = df.dropna(subset=["lat", "lng"])
    return df

def get_dashboard_overview():
    """
    Get overview statistics for dashboard header
    Returns: Dict with key metrics
    """
    conn = get_conn()
    cursor = conn.cursor()

    def fetch_one_value(query):
        cursor.execute(query)
        result = cursor.fetchone()
        if result is None:
            return 0
        # ถ้า result เป็น tuple
        if isinstance(result, tuple):
            return result[0] if result[0] is not None else 0
        # ถ้า result เป็น dict
        if isinstance(result, dict):
            return next(iter(result.values()), 0)
        return 0

    total = fetch_one_value("SELECT COUNT(*) FROM traffy_tickets;")
    finished = fetch_one_value("SELECT COUNT(*) FROM traffy_tickets WHERE state = 'เสร็จสิ้น';")
    inprogress = fetch_one_value("SELECT COUNT(*) FROM traffy_tickets WHERE state = 'กำลังดำเนินการ';")
    avg_duration = fetch_one_value("""
        SELECT AVG(duration_minutes_finished)
        FROM traffy_tickets
        WHERE duration_minutes_finished > 0;
    """)
    last_update = fetch_one_value("SELECT MAX(data_version) FROM traffy_tickets;")

    cursor.close()
    conn.close()

    return {
        'total_tickets': total,
        'finished_tickets': finished,
        'inprogress_tickets': inprogress,
        'completion_rate': round((finished / total * 100) if total > 0 else 0, 2),
        'avg_completion_hours': round(float(avg_duration) / 60, 1) if avg_duration else 0,
        'last_updated': last_update.isoformat() if last_update else None
    }

def get_bma_news(limit=50, start_date=None, end_date=None):
    conn = get_conn()
    cursor = conn.cursor()

    query = """
    SELECT id, title, description, news_date, lat, lng, source
    FROM bma_news
    WHERE lat IS NOT NULL AND lng IS NOT NULL
    """
    params = []

    if start_date:
        query += " AND news_date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND news_date <= %s"
        params.append(end_date)

    query += " ORDER BY news_date DESC"

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    news_list = []
    for row in rows:
        news_list.append({
            'id': row['id'],
            'title': row['title'],
            'description': row['description'],
            'news_date': row['news_date'].isoformat() if row['news_date'] else None,
            'lat': float(row['lat']),
            'lng': float(row['lng']),
            'source': row['source']
        })

    return news_list

def get_police_stations(limit=1000):
    conn = get_conn()
    cursor = conn.cursor()

    query = """
    SELECT id_police, name, address, tel, dcode, division, lat, lng, created_at, updated_at
    FROM police_stations
    WHERE lat IS NOT NULL AND lng IS NOT NULL
    """
    params = []

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    police_list = []
    for row in rows:
        police_list.append({
            'id_police': row['id_police'],
            'name': row['name'],
            'address': row['address'],
            'tel': row['tel'],
            'dcode': row['dcode'],      # แก้จาก 'code' เป็น 'dcode'
            'division': row['division'],
            'lat': float(row['lat']),
            'lng': float(row['lng']),
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
        })

    return police_list

def get_bangkok_population(limit=None):
    conn = get_conn()
    cursor = conn.cursor()
    
    query = """
    SELECT district_no, district_name, total_population, male_population, 
           female_population, created_at, updated_at
    FROM bangkok_population
    """
    params = []

    if limit:
        query += " LIMIT %s"
        params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    
    cursor.close()
    conn.close()

    population_list = []
    for row in rows:
        population_list.append({
            'district_no': row['district_no'],
            'district_name': row['district_name'],
            'total_population': row['total_population'],
            'male_population': row['male_population'],
            'female_population': row['female_population'],
            'created_at': row['created_at'].isoformat() if row['created_at'] else None,
            'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
        })

    return population_list

def get_bma_events(start_date=None, end_date=None):
    conn = get_conn()
    cursor = conn.cursor()

    query = """
        SELECT id, title_th, title_en, desc_th, desc_en,
               lat, lng, icon, start_date, start_time, end_date, status
        FROM bma_events
        WHERE lat IS NOT NULL AND lng IS NOT NULL
    """

    params = []

    if start_date and end_date:
        query += " AND start_date BETWEEN %s AND %s"
        params += [start_date, end_date]

    elif start_date:
        query += " AND start_date >= %s"
        params.append(start_date)

    elif end_date:
        query += " AND start_date <= %s"
        params.append(end_date)

    query += " ORDER BY start_date DESC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return [
        {
            'id': row['id'],
            'title_th': row['title_th'],
            'title_en': row['title_en'],
            'desc_th': row['desc_th'],
            'desc_en': row['desc_en'],
            'lat': float(row['lat']),
            'lng': float(row['lng']),
            'icon': row['icon'],
            'start_date': row['start_date'].isoformat() if row['start_date'] else None,
            'start_time': str(row['start_time']) if row['start_time'] else None,
            'end_date': row['end_date'].isoformat() if row['end_date'] else None,
            'status': row['status']
        }
        for row in rows
    ]


def get_type_summary(limit=20):
    """
    Get complaint type breakdown for pie/bar chart
    Returns: List of {type, total, finished, avg_duration, completion_rate}
    """
    conn = get_conn()
    cursor = conn.cursor()

    query = f"""
    SELECT
        type,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE state = 'เสร็จสิ้น') AS finished,
        AVG(duration_minutes_finished) AS avg_duration
    FROM traffy_tickets
    GROUP BY type
    ORDER BY total DESC
    LIMIT {limit};
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    type_summary = []
    for row in rows:
        if isinstance(row, dict):
            t = row.get('type')
            total = row.get('total', 0)
            finished = row.get('finished', 0)
            avg_duration = float(row.get('avg_duration', 0) or 0)
        else:  # tuple
            t = row[0]
            total = row[1]
            finished = row[2]
            avg_duration = float(row[3] or 0)

        completion_rate = round((finished / total * 100) if total > 0 else 0, 2)
        type_summary.append({
            'type': t,
            'total': total,
            'finished': finished,
            'avg_duration': avg_duration,
            'completion_rate': completion_rate
        })

    return type_summary

def get_ticket(ticket_id):
    query = """
        SELECT
            comment,
            organization,
            subdistrict,
            district,
            organization_action,
            photo,
            duration_minutes_inprogress,
            duration_minutes_finished,
            duration_minutes_total
        FROM traffy_tickets
        WHERE ticket_id = %s
        LIMIT 1
    """
    with get_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(query, (ticket_id,))
        row = cur.fetchone()

    if not row:
        return None

    return {
        "comment": row["comment"],
        "organization": row["organization"],
        "district": row["district"],
        "subdistrict": row["subdistrict"],
        "organization_action": row["organization_action"],
        "photo": row["photo"],
        "duration_inprogress": row["duration_minutes_inprogress"],
        "duration_finished": row["duration_minutes_finished"],
        "duration_total": row["duration_minutes_total"]
    }
    

def get_district_summary(start_date=None, end_date=None):
    """
    Get district-level statistics for map/heatmap filtered by start_date and end_date.
    Returns: List of dict: {district, total, finished, avg_duration, completion_rate}
    """
    conn = get_conn()
    cursor = conn.cursor()

    query = """
    SELECT
        district,
        COUNT(*) AS total,
        SUM(CASE WHEN state = 'เสร็จสิ้น' THEN 1 ELSE 0 END) AS finished,
        AVG(CASE WHEN duration_minutes_finished > 0 THEN duration_minutes_finished END) AS avg_duration
    FROM traffy_tickets
    WHERE 1=1
    """
    params = []

    if start_date is not None:
        query += " AND timestamp::date >= %s"
        params.append(start_date)
    if end_date is not None:
        query += " AND timestamp::date <= %s"
        params.append(end_date)

    query += " GROUP BY district ORDER BY total DESC;"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    district_summary = []
    for row in rows:
        district_summary.append({
            'district': row.get('district', ''),
            'total': row.get('total', 0),
            'finished': row.get('finished', 0),
            'avg_duration': float(row.get('avg_duration', 0)) if row.get('avg_duration') else 0,
            'completion_rate': round((row.get('finished', 0) / row.get('total', 1) * 100), 2) if row.get('total', 0) > 0 else 0
        })

    return district_summary
