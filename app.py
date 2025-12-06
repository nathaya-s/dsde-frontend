import streamlit as st
import streamlit.components.v1 as components
from streamlit_extras.stylable_container import stylable_container
import calendar
import pandas as pd
import altair as alt
import datetime  
import requests
import pandas as pd
import folium
from folium import IFrame
from folium.plugins import  MarkerCluster, HeatMap
from db_utils import (
    get_conn,
    get_map_data,
    load_cctv_df,
    get_dashboard_overview,
    get_bma_news,
    get_bma_events,
    get_type_summary,
    get_ticket,
    get_district_summary,
    get_police_stations,
    get_bangkok_population,
)

from model_api import predict_time

MAPBOX_API_KEY = st.secrets["MAPBOX_API_KEY"]
PG_HOST = st.secrets.get("PG_HOST", "localhost")
PG_PORT = st.secrets.get("PG_PORT", "5432")
PG_DB   = st.secrets.get("PG_DB")
PG_USER = st.secrets.get("PG_USER")
PG_PASS = st.secrets.get("PG_PASS")
PG_SSL  = st.secrets.get("PG_SSLMODE")  
SNAPSHOT_BASE = st.secrets.get("SNAPSHOT_BASE", "http://127.0.0.1:9000/snapshot")


def normalize(x):
    if not isinstance(x, str):
        return ""
    return x.replace(" ", "").lower()
    
def select_all_districts():
    for d_ui in districts:
        d_internal = district_map.get(d_ui, d_ui)
        st.session_state[f"district_{d_internal}"] = True

def deselect_all_districts():
    for d_ui in districts:
        d_internal = district_map.get(d_ui, d_ui)
        st.session_state[f"district_{d_internal}"] = False

def select_all_categories():
        for c in categories:
            st.session_state[f"category_{c}"] = True

def deselect_all_categories():
        for c in categories:
            st.session_state[f"category_{c}"] = False

def convert_thai_datetime(s):
    if pd.isna(s):
        return pd.NaT
    import re
    m = re.search(r'(\d{2})/(\d{2})/(\d{4}) (\d{2})\.(\d{2})', s)
    if not m:
        return pd.NaT
    day, month, year_th, hour, minute = m.groups()
    year_ad = int(year_th) - 543 
    dt_str = f"{day}/{month}/{year_ad} {hour}:{minute}"
    return pd.to_datetime(dt_str, format="%d/%m/%Y %H:%M", errors='coerce')

def compute_predicted_fmt(row):
    if row['state'] != "เสร็จสิ้น":
        predicted = predict_time(
            row['comment'], row.get("type", ""), row['organization'],
            row['district'], row['subdistrict'], row.get("timestamp")
        )
        if predicted:
            return format_predicted_time(predicted['predicted_hours'])
    return "-"

def format_predicted_time(hours_float):
    if hours_float is None:
        return "-"
    
    total_minutes = int(round(hours_float * 60))
    days = total_minutes // (24*60)
    hours = (total_minutes % (24*60)) // 60
    minutes = total_minutes % 60

    parts = []
    if days > 0:
        parts.append(f"{days} วัน")
    if hours > 0:
        parts.append(f"{hours} ชั่วโมง")
    if minutes > 0 or (days==0 and hours==0):
        parts.append(f"{minutes} นาที")
    
    return " ".join(parts)

def safe_convert(event):
    ts = convert_thai_datetime(event['desc_th']) if event.get('desc_th') else None
    if ts is pd.NaT or ts is None:
        ts = pd.to_datetime(start_date)
    return ts

def value_to_color(val, min_val, max_val, type='time'):
    if max_val == min_val:
        norm = 0
    else:
        norm = (val - min_val) / (max_val - min_val)

    gradient_time = [
        (111,156,61),
        (165,201,15),
        (255,179,102),
        (255,136,41),
        (254,107,64)
    ]

    gradient_complete = [
        (254,107,64),
        (255,136,41),
        (255,179,102),
        (165,201,15),
        (111,156,61),
    ]

    gradient_map = {
        "time": gradient_time,
        "complete": gradient_complete
    }

    gradient = gradient_map.get(type, gradient_time)

    total_steps = 50
    step = int(norm * (total_steps - 1))

    seg = len(gradient) - 1
    seg_length = total_steps / seg
    seg_index = int(step // seg_length)
    seg_pos = (step % seg_length) / seg_length

    r1, g1, b1 = gradient[seg_index]
    r2, g2, b2 = gradient[min(seg_index + 1, seg)]

    r = int(r1 + (r2 - r1) * seg_pos)
    g = int(g1 + (g2 - g1) * seg_pos)
    b = int(b1 + (b2 - b1) * seg_pos)

    return f"rgba({r},{g},{b},0.7)"

def format_duration(minutes):
    import math

    if minutes is None or (isinstance(minutes, float) and math.isnan(minutes)):
        minutes = 0

    minutes = int(minutes)
    days = minutes // (24*60)
    hours = (minutes % (24*60)) // 60
    mins = minutes % 60

    result = ""
    if days > 0:
        result += f"{days} วัน "
    if hours > 0:
        result += f"{hours} ชั่วโมง "
    if days == 0 and hours == 0:
        result += f"{mins} นาที"

    return result.strip()


try:
    df_cctv = load_cctv_df()
except Exception as e:
    st.error(f"DB connection/query failed: {e}")
    st.stop()

if df_cctv.empty:
    st.warning("No rows in cctv_meta.")
    st.stop()


st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Sarabun:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800&display=swap" rel="stylesheet">
<style>
body, div, p, h1, h2, h3, h4, h5, h6, span, label {
    font-family: "Sarabun", sans-serif;

}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.st-emotion-cache-wfksaw {
    gap: 0 !important;
}

.st-emotion-cache-wfksaw > div {
    padding: 0 !important;
    margin: 0 !important;
}
</style>
""", unsafe_allow_html=True)

today = datetime.datetime.now()
next_year = today.year + 1

jan_1 = datetime.date(next_year, 1, 1)
dec_31 = datetime.date(next_year, 12, 31)

# --- Date Filters ---
start_date = None;
end_date = None;
start_predict_date = None;
end_predict_date = None;
news_start_date = None;
news_end_date = None;
event_start_date = None;
event_end_date = None;
selected_district = None;
event_time_option = "รายวัน";

# --- Layer Checkboxes ---
cb_event = False;
cb_complaint = False;
cb_done = False;
cb_news = False;
cb_inprogress = False;
cb_notstart =  False;
cb_heatmap = False;
cb_pointmap = False;
cb_police = False;
cb_population = False;
cb_flood = False;


# --- Map / Chart Options ---
x_labels = [];
selected_states = []


st.set_page_config(
    page_title="Smart Complaint Insight",
    layout="wide",
)


 
st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        background-color: #AF94D9 !important;
        width: 340px !important;
        padding: 10px;
        text-color: white !important;
        color: white !important;
    }
 
    /* checkbox sidebar */
    section[data-testid="stSidebar"] .stCheckbox  label  div:last-child {
        color: white !important;
        font-weight: 500;
        font-size: 15px;
      
    }
    
    section[data-testid="stSidebar"] .stCheckbox  label  div:first-child {
        font-weight: 500;
        font-size: 15px;
  
    }
    
    section[data-testid="stSidebar"] .stCheckbox label {
        font-size: 12px !important; 
        color: white !important;
        
    }
    
    div[data-testid="stExpander"] {
            background-color: #CCB5EF !important;    
            color: #AF94D9 !important;               
            font-weight: 300;
            font-size: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
            
    }
    

    /* sidebar title */
    .sidebar-title {
        font-size: 16px;
        margin-top: 20px;
        margin-bottom: 8px;
        font-weight: 700;
        color: white !important;
    }
    
    div[role="radiogroup"] p {
        color: white !important;
        font-weight: 500;
        text-color: white !important;
    }
    
    div[data-baseweb="select"] > div {
        background-color: #AF94D9 !important;  /* สีม่วง */
        color: white !important;               /* ตัวอักษรสีขาว */
        border-radius: 40px;
        padding: 1px 6px;
    }

    /* เปลี่ยนสี option เมื่อ hover */
    div[data-baseweb="select"] span {
        color: white !important;
    }

    /* เปลี่ยน arrow สีขาว */
    div[data-baseweb="select"] svg {
        fill: white !important;
    }

    </style>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("<div class='sidebar-title'>Layers</div>", unsafe_allow_html=True)
    cb_complaint = st.checkbox("ปัญหาร้องเรียน")
    
    if cb_complaint:
        with st.expander("Filter"):
            st.markdown("""
                <style>
                .filter-section {
                    background-color: #AF94D9;
                    padding: 6px 12px;
                    border-radius: 30px;
                    margin-bottom: 30px;
                    color: white;  
                    font-weight: 500;
                    height: 30px;
                    font-size: 16px;
                    display: flex;
                    align-items: center;
                }
                .filter-hr {
                    margin:10px 0; 
                    background-color:  #CCB5EF;
                    border: 0.5px solid rgba(255,255,255,0.4);
                }
                </style>
            """, unsafe_allow_html=True)

            st.markdown('<div class="filter-section">ประเภท</div>', unsafe_allow_html=True)
            cb_heatmap = st.checkbox("Heatmap")
            cb_pointmap = st.checkbox("Point map")

            st.markdown('<hr class="filter-hr">', unsafe_allow_html=True)

            st.markdown('<div class="filter-section">สถานะ</div>', unsafe_allow_html=True)
            cb_done = st.checkbox("เสร็จสิ้น")
            cb_inprogress = st.checkbox("กำลังดำเนินการ")
            cb_notstart = st.checkbox("รอรับเรื่อง")

            st.markdown('<hr class="filter-hr">', unsafe_allow_html=True)

            st.markdown('<div class="filter-section">ระยะเวลา</div>', unsafe_allow_html=True)
            options = ["รายวัน", "รายเดือน", "รายปี", "ทุกปี"]

            time_option = st.radio(
                "", 
                options, 
                index=0, 
                label_visibility="collapsed", 
                key="time_option"
            )
            st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)

            start_date = None
            end_date = None

            if time_option == "รายวัน":
                start_date = st.date_input(
                    "เลือกวัน",
                    format="DD/MM/YYYY",
                    value=datetime.date.today(),
                    key="daily_date"
                )
                end_date = start_date
                x_labels = [f"{h}:00" for h in range(24)]


            elif time_option == "รายเดือน":
                month = st.selectbox(
                    "เลือกเดือน",
                    list(range(1, 13)),
                    index=datetime.date.today().month - 1,
                    key="month_select"
                )

                year = st.selectbox(
                    "เลือกปี",
                    list(range(2022, 2026)),
                    index=datetime.date.today().year - 2022,
                    key="month_year"
                )

                start_date = datetime.date(year, month, 1)
                last_day = calendar.monthrange(year, month)[1]
                end_date = datetime.date(year, month, last_day)

                x_labels = [str(d) for d in range(1, last_day + 1)]


            elif time_option == "รายปี":
                year = st.selectbox(
                    "เลือกปี",
                    list(range(2022, 2026)),
                    key="year_only"
                )

                start_date = datetime.date(year, 1, 1)
                end_date = datetime.date(year, 12, 31)

                x_labels = [
                    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
                ]


            elif time_option == "ทุกปี":
                start_date = datetime.date(2022, 1, 1)
                end_date = datetime.date(2025, 12, 31)

                x_labels = [str(y) for y in range(2022, 2026)]



    cb_cctv = st.checkbox("CCTV", key="cctv_layer")
    cb_news = st.checkbox("ข่าว BMA", key="news_layer")
    if cb_news:
        with st.expander("Filter"):
            st.markdown("""
                <style>
                .filter-section {
                    background-color: #AF94D9;
                    padding: 6px 12px;
                    border-radius: 30px;
                    margin-bottom: 30px;
                    color: white;  
                    font-weight: 500;
                    height: 30px;
                    font-size: 16px;
                    display: flex;
                    align-items: center;
                }
                .filter-hr {
                    margin:10px 0; 
                    background-color:  #CCB5EF;
                    border: 0.5px solid rgba(255,255,255,0.4);
                }
                </style>
            """, unsafe_allow_html=True)

            st.markdown('<div class="filter-section">ระยะเวลา</div>', unsafe_allow_html=True)

            news_time_options = ["รายวัน", "รายเดือน", "รายปี", "ทุกปี"]
            news_time_option = st.radio(
                "",
                news_time_options,
                index=0,
                label_visibility="collapsed",
                key="news_time"
            )

            news_start_date = None
            news_end_date = None

            if news_time_option == "รายวัน":
                news_start_date = st.date_input("เลือกวัน", value=datetime.date.today(), key="news_day")
                news_end_date = news_start_date

            elif news_time_option == "รายเดือน":
                nmonth = st.selectbox("เลือกเดือน", list(range(1,13)),
                                    index=datetime.date.today().month - 1,
                                    key="news_month")
                nyear = st.selectbox("เลือกปี", list(range(2022, 2026)),
                                    index=datetime.date.today().year - 2022,
                                    key="news_month_year")
                news_start_date = datetime.date(nyear, nmonth, 1)
                news_end_date = (
                    datetime.date(nyear, 12, 31)
                    if nmonth == 12 else
                    datetime.date(nyear, nmonth + 1, 1) - datetime.timedelta(days=1)
                )

            elif news_time_option == "รายปี":
                nyear = st.selectbox("เลือกปี", list(range(2022, 2026)), key="news_year")
                news_start_date = datetime.date(nyear, 1, 1)
                news_end_date = datetime.date(nyear, 12, 31)

            elif news_time_option == "ทุกปี":
                news_start_date = datetime.date(2022, 1, 1)
                news_end_date = datetime.date(2025, 12, 31)

    cb_event = st.checkbox("เหตุการณ์จราจร", key="event_layer")
    if cb_event:
        with st.expander("Filter"):
            st.markdown("""
                <style>
                .filter-section {
                    background-color: #AF94D9;
                    padding: 6px 12px;
                    border-radius: 30px;
                    margin-bottom: 30px;
                    color: white;  
                    font-weight: 500;
                    height: 30px;
                    font-size: 16px;
                    display: flex;
                    align-items: center;
                }
                .filter-hr {
                    margin:10px 0; 
                    background-color:  #CCB5EF;
                    border: 0.5px solid rgba(255,255,255,0.4);
                }
                </style>
            """, unsafe_allow_html=True)
            
            
            st.markdown('<div class="filter-section">ประเภท</div>', unsafe_allow_html=True)
            cb_event_pointmap = st.checkbox("Point map", key="event_pointmap")
            cb_event_heatmap = st.checkbox("Heatmap", key="event_heatmap")
            
            st.markdown('<hr class="filter-hr">', unsafe_allow_html=True)
            
            st.markdown('<div class="filter-section">ระยะเวลา</div>', unsafe_allow_html=True)

            event_time_options = ["รายวัน", "รายเดือน", "รายปี", "ทุกปี"]
            event_time_option = st.radio(
                "",
                event_time_options,
                index=0,
                label_visibility="collapsed",
                key="event_time"
            )

            if event_time_option == "รายวัน":
                event_start_date = st.date_input("เลือกวัน", value=datetime.date.today(), key="event_day")
                event_end_date = event_start_date

            elif event_time_option == "รายเดือน":
                emonth = st.selectbox("เลือกเดือน", list(range(1,13)),
                                    index=datetime.date.today().month - 1,
                                    key="event_month")
                eyear = st.selectbox("เลือกปี", list(range(2022, 2026)),
                                    index=datetime.date.today().year - 2022,
                                    key="event_month_year")
                event_start_date = datetime.date(eyear, emonth, 1)
                event_end_date = (
                    datetime.date(eyear, 12, 31)
                    if emonth == 12 else
                    datetime.date(eyear, emonth + 1, 1) - datetime.timedelta(days=1)
                )

            elif event_time_option == "รายปี":
                eyear = st.selectbox("เลือกปี", list(range(2022, 2026)), key="event_year")
                event_start_date = datetime.date(eyear, 1, 1)
                event_end_date = datetime.date(eyear, 12, 31)

            elif event_time_option == "ทุกปี":
                event_start_date = datetime.date(2022, 1, 1)
                event_end_date = datetime.date(2025, 12, 31)

    cb_police = st.checkbox("สถานีตำรวจ", key="police_layer")
    cb_population = st.checkbox("ประชากรในกรุงเทพฯ", key="population_layer")
    if cb_population:
        with st.expander("Filter"):
            st.markdown("""
                <style>
                .filter-section {
                    background-color: #AF94D9;
                    padding: 6px 12px;
                    border-radius: 30px;
                    margin-bottom: 30px;
                    color: white;  
                    font-weight: 500;
                    height: 30px;
                    font-size: 16px;
                    display: flex;
                    align-items: center;
                }
                </style>
            """, unsafe_allow_html=True)

            st.markdown('<div class="filter-section">ประเภทข้อมูลประชากร</div>', unsafe_allow_html=True)

            pop_type_options = [
                ("ประชากรทั้งหมด", "total_population"),
                ("ประชากรชาย", "male_population"),  
                ("ประชากรหญิง", "female_population"),
            ]

            selected = st.selectbox(
                "",
                pop_type_options,
                index=0,
                format_func=lambda x: x[0],  
                label_visibility="collapsed",
                key="population_type"
            )

            pop_type = selected[1]
            
    cb_flood = st.checkbox("พื้นที่เสี่ยงน้ำท่วม", key="flood_layer")
    if cb_flood:
        with st.expander("Filter"):
            st.markdown("""
                <style>
                .filter-section {
                    background-color: #AF94D9;
                    padding: 6px 12px;
                    border-radius: 30px;
                    margin-bottom: 30px;
                    color: white;  
                    font-weight: 500;
                    height: 30px;
                    font-size: 16px;
                    display: flex;
                    align-items: center;
                }
                </style>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="filter-section">ประเภทแผนที่</div>', unsafe_allow_html=True)
            flood_pointmap = st.checkbox("Point map", key="flood_pointmap")
            flood_heatmap = st.checkbox("Heatmap", key="flood_heatmap")
            
            st.markdown("---")

            st.markdown('<div class="filter-section">สถานะการดำเนินการ</div>', unsafe_allow_html=True)

            flood_status_list = [
                "แก้ไขแล้วเสร็จ",
                "แก้ไขแล้วเสร็จบางส่วน",
                "อยู่ระหว่างดำเนินการแก้ไข",
                "มีมาตรการเร่งด่วน",
                "พื้นที่เอกชนหรือหน่วยงานราชการ",
            ]

            selected_status = []
            for status in flood_status_list:
                if st.checkbox(status, key=f"chk_{status}"):
                    selected_status.append(status) 


    st.markdown('<hr style="border:0.5px solid rgba(255,255,255,0.4); margin:10px 0;">', unsafe_allow_html=True)
    st.markdown("<div class='sidebar-title'>เขต</div>", unsafe_allow_html=True)
    district_map = {
        "ป้อมปราบฯ": "ป้อมปราบศัตรูพ่าย"
    }

    districts = [
        'คลองสาน', 'คลองสามวา', 'คลองเตย', 'คันนายาว', 'จตุจักร', 'จอมทอง', 
        'ดอนเมือง', 'ดินแดง', 'ดุสิต', 'ตลิ่งชัน', 'ทวีวัฒนา', 'ธนบุรี', 
        'บางกอกน้อย', 'บางกอกใหญ่', 'บางกะปิ', 'บางขุนเทียน', 'บางคอแหลม', 
        'บางซื่อ', 'บางนา', 'บางบอน', 'บางพลัด', 'บางรัก', 'บางเขน', 
        'บางแค', 'บึงกุ่ม', 'ปทุมวัน', 'ประเวศ', 'พระนคร', 'พระโขนง', 
        'ภาษีเจริญ', 'มีนบุรี', 'ยานนาวา', 'ราชเทวี', 'ราษฎร์บูรณะ', 
        'ลาดกระบัง', 'ลาดพร้าว', 'วังทองหลาง', 'วัฒนา', 'สวนหลวง', 
        'สะพานสูง', 'สัมพันธวงศ์', 'สาทร', 'สายไหม', 'หนองจอก', 
        'หนองแขม', 'หลักสี่', 'ห้วยขวาง', 'ทุ่งครุ', 'พญาไท',
        'ป้อมปราบฯ'
    ]

    for d_ui in districts:
        d_internal = district_map.get(d_ui, d_ui)
        key = f"district_{d_internal}"
        if key not in st.session_state:
            st.session_state[key] = False


    with st.expander("เลือกเขต"):
        half = len(districts) // 2
        col1, col2 = st.columns(2)

        def show_checkbox(d_ui, col):
            d_internal = district_map.get(d_ui, d_ui)
            col.checkbox(d_ui, key=f"district_{d_internal}")

        for d_ui in districts[:half]:
            show_checkbox(d_ui, col1)
        for d_ui in districts[half:]:
            show_checkbox(d_ui, col2)
            
        with stylable_container(
            "purple",
            css_styles="""
            button {
                background-color: #B9A3DA !important;
                color: white !important;
                font-weight: 500 !important;
                border-radius: 20px !important;
                height: 35px !important;
                width: 240px !important;
                cursor: pointer;
                margin-bottom: 20px !important;
                margin-top: 20px !important;
            }
           
            """
        ):
            st.button("เลือกเขตทั้งหมด", on_click=select_all_districts)

        with stylable_container(
            "deselect_all",
            css_styles="""
            button {
                background-color: transparent !important;
                color: #9E83C6 !important;
                font-weight: 500 !important;
                border: None !important;
                height: 35px !important;
                width: 240px !important;
                cursor: pointer;
                margin-bottom: 10px !important;
            }
            
            """
        ):
            st.button("ยกเลิกทั้งหมด", key="deselect_all", on_click=deselect_all_districts)

    st.markdown('<hr style="border:0.5px solid rgba(255,255,255,0.4); margin:10px 0;">', unsafe_allow_html=True)
    st.markdown("<div class='sidebar-title'>ประเภท</div>", unsafe_allow_html=True)

        
    categories = [
        "ถนน", "แสงสว่าง", "ทางเท้า", "น้ำท่วม", "ร้องเรียน",
        "จราจร", "กีดขวาง", "ความสะอาด", "ความปลอดภัย",
        "ท่อระบายน้ำ", "เสียง", "ป้าย", "ต้นไม้", "สะพาน",
        "คลอง", "สัตว์จรจัด", "สายไฟ", "PM2.5", "คนจรจัด",
        "สอบถาม", "เสนอแนะ", "ห้องน้ำ", "การเดินทาง", "ป้ายจราจร", "อื่น ๆ"
    ]

    # initialize session_state
    for c in categories:
        key = f"category_{c}"
        if key not in st.session_state:
            st.session_state[key] = False

        
    with st.expander("เลือกประเภท"):
        half = len(categories) // 2
        col1, col2 = st.columns(2)

        def show_checkbox(c, col):
            col.checkbox(c, key=f"category_{c}")

        for c in categories[:half]:
            show_checkbox(c, col1)
        for c in categories[half:]:
            show_checkbox(c, col2)

        # ปุ่มเลือกทั้งหมด (สีม่วง)
        with stylable_container(
            "purple_button",
            css_styles="""
            button {
                background-color: #B9A3DA !important;
                color: white !important;
                font-weight: 500 !important;
                border-radius: 20px !important;
                height: 35px !important;
                width: 240px !important;
                cursor: pointer;
                margin-bottom: 20px !important;
                margin-top: 10px !important;
            }
            
            """
        ):
            st.button("เลือกประเภททั้งหมด", on_click=select_all_categories)

        with stylable_container(
            "red_button",
            css_styles="""
            button {
                background-color: transparent !important;
                color: #9E83C6 !important;
                font-weight: 500 !important;
                border: None !important;
                height: 35px !important;
                width: 240px !important;
                cursor: pointer;
                margin-bottom: 10px !important;
            }
            """
        ):
            st.button("ยกเลิกทั้งหมด", key="deselect_cat_all", on_click=deselect_all_categories)
    


df = get_map_data(limit=100000, start_date=start_date, end_date=end_date)


# ============================
# Calculate ETA by district
# ============================
def calculate_eta_by_district(df, start_date, end_date, selected_types, selected_districts):
    df2 = df.copy()

    df2 = df2[
        (df2["timestamp"].dt.date >= start_date) &
        (df2["timestamp"].dt.date <= end_date)
    ]

    if selected_types:
        df2 = df2[df2["type"].isin(selected_types)]

    if selected_districts:
        df2 = df2[df2["district"].isin(selected_districts)]
        

    return df2.groupby("district", as_index=False)["eta_hours"].mean()


# ----------------------------
# filter timestamp column
# ----------------------------
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

df = df.dropna(subset=['timestamp'])

df_filtered = df.copy()

# ----------------------------
# filter by selected districts
# ----------------------------
selected_districts = [
    key.replace("district_", "")
    for key, val in st.session_state.items()
    if key.startswith("district_") and val
]
# ----------------------------
# filter by selected categories
# ----------------------------

base_categories = [
    "ถนน", "แสงสว่าง", "ทางเท้า", "น้ำท่วม", "ร้องเรียน",
    "จราจร", "กีดขวาง", "ความสะอาด", "ความปลอดภัย",
    "ท่อระบายน้ำ", "เสียง", "ป้าย", "ต้นไม้", "สะพาน",
    "คลอง", "สัตว์จรจัด", "สายไฟ", "PM2.5", "คนจรจัด",
    "สอบถาม", "เสนอแนะ", "ห้องน้ำ", "การเดินทาง", "ป้ายจราจร", "อื่น ๆ"
]

selected_categories = [c for c in base_categories if st.session_state.get(f"category_{c}", False)]

def map_type(x):
    if pd.isna(x) or str(x).strip() == "":
        return "อื่น ๆ"
    for cat in base_categories: 
        if cat.strip() in str(x):
            return cat
    return "อื่น ๆ"

df_filtered['type_filtered'] = df_filtered['type'].apply(map_type)

if not selected_districts or not selected_categories:
    df_filtered = df.iloc[0:0]
else:
    df_filtered = df_filtered[
        df_filtered['district'].isin(selected_districts)
        & df_filtered['type_filtered'].notna()
    ]


# ----------------------------
# filter by selected status
# ----------------------------
status_cols = []
if cb_done:
    status_cols.append("เสร็จสิ้น")
if cb_inprogress:
    status_cols.append("กำลังดำเนินการ")
if cb_notstart:
    status_cols.append("รอรับเรื่อง")
    
if not selected_districts or not selected_categories:
    df_filtered = df.iloc[0:0]
else:
    df_filtered = df_filtered[
        df_filtered['district'].isin(selected_districts)
        & df_filtered['type_filtered'].apply(lambda x: any(cat in str(x) for cat in selected_categories))
    ]

if status_cols:
    df_filtered = df_filtered[df_filtered['state'].isin(status_cols)]


# ----------------------------
# prepare data for plotting
# ----------------------------
df_plot = pd.DataFrame({'X': x_labels})
for status in status_cols:
    counts = []
    for x in x_labels:
        if time_option == "รายวัน":
            mask_status = (df_filtered['state'] == status) & (df_filtered['timestamp'].dt.hour == int(x.split(':')[0]))
        elif time_option == "รายเดือน":
            mask_status = (df_filtered['state'] == status) & (df_filtered['timestamp'].dt.day == int(x))
        elif time_option == "รายปี":
            mask_status = (df_filtered['state'] == status) & (df_filtered['timestamp'].dt.month == x_labels.index(x)+1)
        else:
            mask_status = (df_filtered['state'] == status) & (df_filtered['timestamp'].dt.year == int(x))
        counts.append(mask_status.sum())
    df_plot[status] = counts


# ===== Main layout =====
def split_coords(x):
    try:
        lng, lat = map(float, str(x).split(","))
        return pd.Series({"lng": lng, "lat": lat})
    except:
        return pd.Series({"lng": None, "lat": None})

# --- Prepare map data ---
if {"lat", "lng"}.issubset(df_filtered.columns):
    df_map = df_filtered.dropna(subset=["lat", "lng"])
else:
    st.error("Missing lat/lng columns in data")
    df_map = pd.DataFrame(columns=["lat", "lng"])
    
if df_map.empty:
    center_lat, center_lon = 13.736, 100.523
    zoom_level = 11
else:
    center_lat, center_lon = df_map["lat"].mean(), df_map["lng"].mean()
    zoom_level = 12

# --- Map default location ---
map_center = [13.7563, 100.5018]
m = folium.Map(
    location=map_center,
    zoom_start=12,
    tiles=f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_API_KEY}",
    attr="Mapbox © OpenStreetMap", 
    max_zoom=20,
    min_zoom=1
)

# --- MarkerCluster ---
marker_cluster = MarkerCluster().add_to(m)

# ---  Default Markers ---
if df_map.empty:
    df_default = pd.DataFrame({
        # "lat": [13.7563, 13.7450, 13.7654],
        # "lon": [100.5018, 100.5231, 100.4931]
    })
    for _, row in df_default.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lng"]],
            radius=8,
            color="#b400e6",
            fill=True,
            fill_opacity=0.6
        ).add_to(marker_cluster)

# --- Heatmap Layer ---
if cb_heatmap and not df_map.empty:
    heat_data = df_map[["lat", "lng"]].values.tolist()
    HeatMap(heat_data, radius=30, min_opacity=0.1).add_to(m)
    
st.session_state.setdefault("clicked_ticket_id", None)
# --- Point Layer ---
if cb_pointmap and not df_map.empty:
    df_map['predicted_fmt'] = df_map.apply(compute_predicted_fmt, axis=1)
    status_color_map = {
        "เสร็จสิ้น": "#66BB6A",
        "กำลังดำเนินการ": "#FFCA28",
        "รอรับเรื่อง": "#EF5350"
    }
    
    text_color_map = {
        "เสร็จสิ้น": "#49a54e",
        "กำลังดำเนินการ": "#aa8000",
        "รอรับเรื่อง": "#ed3c39"
    }

    for _, row in df_map.iterrows():
        state = row["state"]
        color = status_color_map.get(state, "#999999")
        text_color = text_color_map.get(state, "#777777")
        ticket_id = row.get("ticket_id", None)
        predicted_fmt = row.get("predicted_fmt", "-")
        subdistrict = row.get("subdistrict", "")
        district = row.get("district", "")
        comment = row.get("comment", "")
        organization = row.get("organization", "")
        organization_action = row.get("organization_action", "")
        photo_url = row.get("photo") or "https://via.placeholder.com/300x200?text=No+Image"
        raw_ts = row.get("timestamp")
        try:
            ts_format = pd.to_datetime(raw_ts).strftime("%d/%m/%Y %H:%M")
        except:
            ts_format = raw_ts

        state_badge = f"""
            <span style="
                border: 1px solid {color};
                background-color: {color}4D; 
                color: {text_color};
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 16px;
                font-size: 11px;
                display: inline-block;
            ">{state}</span>
        """

        bottom_box_html = f"""
        <div style="
            padding: 6px 10px;
            margin-top: 6px;
            background-color: {color}33;
            border: 1px solid {color};
            border-radius: 8px;
            font-size: 14px;
        ">
            <span style="display:block; margin-bottom:4px; font-size:11px; color:#888;">
                {"เวลาในการดำเนินการ" if state=="เสร็จสิ้น" else "ประมาณการเวลาดำเนินการแก้ไข"}
            </span>
            <span style="display:block; color:{text_color}; font-weight:700; margin-bottom:2px;">
                {format_duration(row['duration_minutes_total']) if state=="เสร็จสิ้น" else predicted_fmt}
            </span>
        </div>
        """

        popup_html = f"""
        <div style="font-family:'Sarabun', sans-serif; font-size:14px; line-height:1.3; width:100%; height:100%; display:flex; flex-direction:column; border-radius:8px;">
            <div style="overflow-y:auto; flex:1; padding:6px 10px; background-color:white; color:#6c6c6c;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <div>{state_badge}</div>
                    <div style="font-size:11px;"><b>แจ้งเมื่อ</b> {ts_format}</div>
                </div>
                <img src="{photo_url}" width="100%" style="border-radius:10px;">
                <div style="margin:8px 0;">{district} {subdistrict}</div>
                <div style="margin-bottom:6px;"><b>ปัญหา:</b> {comment}</div>
                <div style="margin-bottom:6px;"><b>หน่วยงานที่รับเรื่อง:</b> {organization}</div>
                <div><b>การดำเนินการ:</b> {organization_action}</div> 
                
            </div>
            {bottom_box_html}
        </div>
        """

        iframe = folium.IFrame(html=popup_html, width=270, height=400)
        popup = folium.Popup(iframe, max_width=270)

        folium.CircleMarker(
            location=[row["lat"], row["lng"]],
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=popup
        ).add_to(m)



news_data = get_bma_news(limit= 10000,start_date=news_start_date, end_date=news_end_date)
if cb_news and news_data:
    for news in news_data:
        try:
            news_date = datetime.strptime(news['news_date'], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            news_date = news['news_date']
            
        icon = folium.CustomIcon(
            icon_image="https://img.icons8.com/?size=100&id=VzgzXxIQUeYS&format=png&color=AF94D9",
            icon_size=(36, 36), 
        )

        folium.Marker(
            location=[news['lat'], news['lng']],
            icon=icon,
            popup=folium.Popup(
                html=f"""
                <div style="
                    font-family: 'Sarabun', sans-serif;
                    font-size: 14px;
                    line-height: 1.4;
                    padding: 8px 12px;
                    color: #AF94D9;
                    background-color: #FFFFFF;
                    border-radius: 8px;
                    max-height: 250px;
                    overflow-y: auto;
                    width: 250px;
                ">
                    <b>ข่าว:</b> {news['title']}<br>
                    <b>วันที่:</b> {news['news_date']}<br>
                    <b>รายละเอียด:</b> {news['description']}<br>
                    <b>แหล่งที่มา:</b> {news['source']}
                </div>
                """,
                max_width=350
            )
        ).add_to(marker_cluster)

event_icon_map = {
    "รถเสีย": "https://img.icons8.com/?size=200&id=cfzK1yg4WznQ&format=png&color=0096FF",
    "คืบหน้าอุบัติเหตุ": "https://img.icons8.com/?size=100&id=bcBPOpoJ9e5q&format=png&color=73c468",
    "เหตุไฟฟ้าลัดวงจร": "https://img.icons8.com/?size=100&id=XwGugoA70UaI&format=png&color=e35f5f",
    "เพลิงไหม้": "https://img.icons8.com/?size=100&id=9272&format=png&color=e35f5f",
    "เหตุเพลิงไหม้หญ้า": "https://img.icons8.com/?size=100&id=10123&format=png&color=e35f5f",
    "คืบหน้าเหตุเพลิงไหม้หญ้า": "https://img.icons8.com/?size=100&id=10123&format=png&color=73c468",
    "คืบหน้าไฟฟ้าลัดวงจรภายในอพาร์ทเม้นท์": "https://img.icons8.com/?size=100&id=XwGugoA70UaI&format=png&color=73c468",
    "คืบหน้าเพลิงไหม้": "https://img.icons8.com/?size=100&id=9272&format=png&color=73c468",
    "อุบัติเหตุ": "https://img.icons8.com/?size=100&id=bcBPOpoJ9e5q&format=png&color=FF8904",
    "เหตุไฟฟ้าลัดวงจรที่หม้อแปลงไฟฟ้า": "https://img.icons8.com/?size=100&id=XwGugoA70UaI&format=png&color=e35f5f",
    "ปิดการจราจร": "https://img.icons8.com/?size=100&id=nBPNgk9bLpff&format=png&color=edd161"
}

event_data = get_bma_events(start_date=event_start_date, end_date=event_end_date)
if cb_event and event_data and cb_event_pointmap:
    for event in event_data:
        try:
            start_date_str = event['start_date'].strftime("%d/%m/%Y") if event['start_date'] else "-"
            end_date_str = event['end_date'].strftime("%d/%m/%Y") if event['end_date'] else "-"
        except Exception:
            start_date_str = event['start_date']
            end_date_str = event['end_date']
            
        event_type = event['title_th'].split()[0] if event['title_th'] else "อื่นๆ"
        icon_url = event_icon_map.get(event_type, "https://img.icons8.com/?size=100&id=tn6WXIuAZamL&format=png&color=AF94D9")  # icon default

        icon = folium.CustomIcon(
            icon_image=icon_url,
            icon_size=(30, 30) if event_type != "รถเสีย" else (40, 40) 
        )

        folium.Marker(
            location=[event['lat'], event['lng']],
            icon=icon,
            popup=folium.Popup(
                html=f"""
                <div style="
                    font-family: 'Sarabun', sans-serif;
                    font-size: 14px;
                    line-height: 1.4;
                    padding: 6px 10px;
                    color: #AF94D9;
                    background-color: #FFFFFF;
                    border-radius: 8px;
                    max-height: 250px;
                    overflow-y: auto;
                    width: 250px;
                ">
                    <b>กิจกรรม:</b> {event['title_th']}<br>
                    <b>วันที่:</b> {start_date_str}<br>
                    <b>รายละเอียด:</b> {event['desc_th']}
                </div>
                """,
                max_width=350
            )
        ).add_to(m)
        
if cb_event and event_data and cb_event_heatmap:
    heat_data = [[event['lat'], event['lng']] for event in event_data if event['lat'] and event['lng']]
    HeatMap(heat_data, radius=30, min_opacity=0.1).add_to(m)    

if cb_police:
    police_data = get_police_stations()
    if police_data:
        for station in police_data:
            folium.Marker(
            location=[station['lat'], station['lng']],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    background-color:#A06CD5;
                    width:18px;
                    height:18px;
                    border-radius:50%;
                    border:2px solid white;
                    box-shadow: 0 0 3px rgba(0,0,0,0.5);
                "></div>
                """
            ),
            popup=folium.Popup(
                html=f"""
                <div style="
                    font-family: 'Sarabun', sans-serif;
                    font-size: 14px;
                    color: #777777;
                    background-color: #FFFFFF;
                    border-radius: 8px;
                    width: 230px;
                    display: flex;
                    flex-direction: column;
                    max-height: 250px;
                ">
                    <div style="overflow-y: auto; flex: 1; padding: 6px 10px;">
                        <b>สถานีตำรวจ</b><br> {station['name']}<br><br>
                        <b>แผนก</b><br> {station['division']}<br><br>
                        <b>ที่อยู่</b><br> {station['address']}
                    </div>
                    <div style="padding: 6px 10px; border-top: 1px solid #eee; display:flex; align-items:center; gap:6px;">
                        <img src="https://img.icons8.com/?size=100&id=ufkkYBXJSuPy&format=png&color=000000" 
                            width="20" height="20" style="vertical-align:middle;">
                        <span>{station['tel']}</span>
                    </div>
                </div>
                """,
                max_width=350
            )
        ).add_to(m)

if cb_population:
    df_population = pd.DataFrame(get_bangkok_population())

    url = "https://services1.arcgis.com/jSaRWj2TDlcN1zOC/arcgis/rest/services/TH_Bangkok_District/FeatureServer/0/query"
    params = {"where": "1=1", "outFields": "*", "f": "geojson"}
    res = requests.get(url, params=params)
    geojson_data = res.json()

    pop_type_label_map = {
        "total_population": "ประชากรทั้งหมด",
        "male_population": "ประชากรชาย",
        "female_population": "ประชากรหญิง",
    }

    min_val = int(df_population[pop_type].min())
    max_val = int(df_population[pop_type].max())

    for feature in geojson_data["features"]:
        district_name = feature["properties"].get("AMP_NAMT")

        match = df_population[df_population["district_name"] == district_name]

        if not match.empty:
            val = int(match[pop_type].iloc[0])  
            fill_color = value_to_color(val, min_val, max_val, type='time')

            feature["properties"]["value"] = val
            feature["properties"]["fillColor"] = fill_color
        else:
            feature["properties"]["value"] = None
            feature["properties"]["fillColor"] = "rgba(230,230,230,0.3)"

    folium.GeoJson(
        geojson_data,
        style_function=lambda feature: {
            'fillColor': feature["properties"]["fillColor"],
            'color': 'white',
            'weight': 1,
            'fillOpacity': 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["AMP_NAMT", "value"],
            aliases=[
                "เขต:",
                f"{pop_type_label_map[pop_type]} :",  
            ],
            labels=True,
            sticky=True,
            style="""
                background-color: #AF94D9;
                border-radius: 8px;
                box-shadow: 3px 3px 5px rgba(0,0,0,0.3);
                padding: 8px;
                font-family: 'Sarabun', sans-serif;
                color: white;
                font-size: 13px;
            """
        )
    ).add_to(m)

if cb_flood and flood_pointmap:
    csv_path = "data/flood_risk.csv"
    df_flood = pd.read_csv(csv_path)
    df_flood_filtered = df_flood[df_flood["status_detail"].isin(selected_status)]

    flood_status_color = {
        "แก้ไขแล้วเสร็จ": "#66BB6A",
        "แก้ไขแล้วเสร็จบางส่วน": "#EDD161",
        "อยู่ระหว่างดำเนินการแก้ไข": "#FF9800",
        "มีมาตรการเร่งด่วน": "#E35F5F",
        "พื้นที่เอกชนหรือหน่วยงานราชการ": "#9292D1",
    }

    text_color = {
        "แก้ไขแล้วเสร็จ": "#33691e",
        "แก้ไขแล้วเสร็จบางส่วน": "#f57f17",
        "อยู่ระหว่างดำเนินการแก้ไข": "#e65100",
        "มีมาตรการเร่งด่วน": "#b0120a",
        "พื้นที่เอกชนหรือหน่วยงานราชการ": "#6a1b9a",
    }

    def format_bullet(text):
        if pd.isna(text) or str(text).strip() == "":
            return ""
        lines = str(text).split("\n")
        bullets = "".join([f"<li>{line.strip()}</li>" for line in lines if line.strip()])
        return f"<ul style='padding-left:18px; margin:4px 0'>{bullets}</ul>"

    for _, row in df_flood_filtered.iterrows():

        # get data
        name = row["name"]
        district = row["district"]
        status_detail = row["status_detail"]
        problems = row["problems"]
        detail = row["detail"]
        remark = row["remark"]

        dept_sapan = row["สพน"]
        dept_sakon = row["สคน"]
        dept_krb = row["กรบ"]
        dept_krt = row["กรท"]


        color = flood_status_color.get(status_detail, "#9E9E9E")
        tcolor = text_color.get(status_detail, "#333")

        # Badge
        state_badge = f"""
            <span style="
                border: 1px solid {color};
                background-color: {color}30; 
                color: {tcolor};
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 16px;
                font-size: 11px;
                display: inline-block;
                margin-bottom: 8px;
            ">{status_detail}</span>
        """

        #  detail
        detail_html = ""
        if not pd.isna(detail) and str(detail).strip() != "":
            detail_html = f"""
                <b>รายละเอียดโครงการ:</b>
                {format_bullet(detail)}
                <br>
            """

        # remark
        remark_html = ""
        if not pd.isna(remark) and str(remark).strip() != "":
            remark_html = f"""
                <b>หมายเหตุ:</b> {remark}<br><br>
            """

        # dept
        dept_html = ""
        if any([pd.notna(dept_sapan), pd.notna(dept_sakon), pd.notna(dept_krb), pd.notna(dept_krt)]):

            dept_html += "<b>โครงการตามหน่วยงาน</b><br>"
            if pd.notna(dept_sapan):
                dept_html += f"• <b>สพน</b> {format_bullet(dept_sapan)}"
            if pd.notna(dept_sakon):
                dept_html += f"• <b>สคน</b> {format_bullet(dept_sakon)}"
            if pd.notna(dept_krb):
                dept_html += f"• <b>กรบ</b> {format_bullet(dept_krb)}"
            if pd.notna(dept_krt):
                dept_html += f"• <b>กรท</b> {format_bullet(dept_krt)}"

        popup_html = f"""
        <div style="
            font-family: 'Sarabun', sans-serif;
            font-size: 14px;
            color: #444;
            background-color: #FFFFFF;
            border-radius: 8px;
            width: 280px;
            padding: 12px;
        ">
            {state_badge}<br>
            <b>ชื่อจุด:</b> {name}<br>
            <b>เขต:</b> {district}<br>
            <b>ปัญหา:</b> {problems}<br>
            <br>
            {detail_html}
            {remark_html}
            {dept_html}
        </div>
        """

        folium.CircleMarker(
            location=[row["y"], row["x"]],
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            weight=1,
            popup=folium.Popup(popup_html, max_width=330)
        ).add_to(m)
        
if cb_flood and flood_heatmap:
    csv_path = "data/flood_risk.csv"
    df_flood = pd.read_csv(csv_path)
    df_flood_filtered = df_flood[df_flood["status_detail"].isin(selected_status)]

    heat_data = df_flood_filtered[["y", "x"]].values.tolist()
    HeatMap(heat_data, radius=30, min_opacity=0.1).add_to(m)

# --- CCTV Layer ---
if cb_cctv and not df_cctv.empty:
    for _, row in df_cctv.iterrows():
        icon = folium.CustomIcon(
            icon_image="https://img.icons8.com/?size=100&id=PctCctSTsD41&format=png&color=AF94D9",
            icon_size=(28, 28)
        )

        snapshot_url = f"{SNAPSHOT_BASE}/{row['id']}"

        popup_html = f"""
        <div style="
            font-family: 'Sarabun', sans-serif;
            font-size: 14px;
            line-height: 1.2;
            padding: 4px 4px;
            background-color: white;
            color: #AF94D9;
            border-radius: 8px;
            text-align: left;
        ">
            <b style='display:block; margin-bottom:6px;'>{row['name']}</b>
            <span style='display:block; margin-bottom:4px;'>ตำแหน่ง: {row['lat']}, {row['lng']}</span>
            
            <div style="margin-top:8px; text-align:center;">
                <img id="cctv_img_{row['id']}" 
                     src="{snapshot_url}?t={pd.Timestamp.now().timestamp()}" 
                     width="100%" 
                     height="180px"
                     style="border-radius:12px;"
                     onerror="this.src='https://via.placeholder.com/200x120?text=Offline';">
            </div>
        </div>

        <script>
            var img = document.getElementById("cctv_img_{row['id']}");
            setInterval(function(){{
                img.src = "{snapshot_url}?t=" + new Date().getTime();
            }}, 1000);
        </script>
        """

        iframe = IFrame(html=popup_html, width=280, height=260)
        folium.Marker(
            location=[row["lat"], row["lng"]],
            icon=icon,
            popup=folium.Popup(iframe, max_width=280)
        ).add_to(m)

m.get_root().html.add_child(folium.Element("""
<style>
    .leaflet-interactive:focus {
        outline: none !important;
    }
</style>
"""))

        
map_html = m.get_root().render()

components.html(
    f"""
    <div style="width:100%; height:640px; border-radius:13px; overflow:hidden;">
        {map_html}
    </div>
    """,
    height=640,
)



tab1, tab2 = st.tabs(["ข้อมูลการร้องเรียน", "ข้อมูลเหตุการณ์จราจร"])

with tab1:
    overview = get_dashboard_overview()
    if overview['last_updated']:
        last_updated_dt = datetime.datetime.fromisoformat(overview['last_updated'])
        formatted_date = last_updated_dt.strftime("%d/%m/%Y")
        st.markdown(
            f'''
            <div style="
            text-align: right; 
            color:#AF94D9 ;
            font-weight:500;
            font-size: 16px;
            ">
                ข้อมูลเมื่อวันที่: {formatted_date}
            </div>
            ''',
            unsafe_allow_html=True
        )



    col1, col2, col3, col4 = st.columns(4)

    st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        color: #5B3E96  !important;  /* สีม่วงเข้ม */
        text-color: white  !important;
        font-weight: 300 !important;
        border-radius: 14px !important;
        padding: 12px !important;

        width: 240px !important;
        min-height: 140px !important;
        max-height: 240px !important;

        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;

        /* เพิ่มกรอบสีม่วง */

        background-color: #f5efff !important; /* สีพื้น metric */
        box-sizing: border-box !important; /* ให้ border ไม่ทำให้ขนาดเกิน */
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
    div[data-testid="stMetricLabel"] {
        font-family: 'Sarabun', sans-serif !important;
        font-size: 16px !important;
        color: #AF94D9 !important;  
    }

    div[data-testid="stMetricValue"] {
        font-family: 'Sarabun', sans-serif !important;
        font-size: 26px !important;
        font-weight: 600 !important;
        color: #AF94D9 !important;
    }

    /* เปลี่ยนฟอนต์ของ delta */
    div[data-testid="stMetricDelta"] {
        font-family: 'Sarabun', sans-serif !important;
        font-size: 14px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    col1.metric(
        label="Total Tickets",
        value=overview['total_tickets']
    )

    col4.metric(
        label="Finished Tickets",
        value=overview['finished_tickets'],
        delta=f"{overview['completion_rate']}%"
    )

    col3.metric(
        label="In Progress Tickets",
        value=overview['inprogress_tickets']
    )

    col2.metric(
        label="Avg Completion Time (hrs)",
        value=overview['avg_completion_hours']
    )

    st.markdown("---")
    
    districts_full = [
        'คลองสาน', 'คลองสามวา', 'คลองเตย', 'คันนายาว', 'จตุจักร', 'จอมทอง', 
        'ดอนเมือง', 'ดินแดง', 'ดุสิต', 'ตลิ่งชัน', 'ทวีวัฒนา', 'ธนบุรี', 
        'บางกอกน้อย', 'บางกอกใหญ่', 'บางกะปิ', 'บางขุนเทียน', 'บางคอแหลม', 
        'บางซื่อ', 'บางนา', 'บางบอน', 'บางพลัด', 'บางรัก', 'บางเขน', 
        'บางแค', 'บึงกุ่ม', 'ปทุมวัน', 'ประเวศ', 'พระนคร', 'พระโขนง', 
        'ภาษีเจริญ', 'มีนบุรี', 'ยานนาวา', 'ราชเทวี', 'ราษฎร์บูรณะ', 
        'ลาดกระบัง', 'ลาดพร้าว', 'วังทองหลาง', 'วัฒนา', 'สวนหลวง', 
        'สะพานสูง', 'สัมพันธวงศ์', 'สาทร', 'สายไหม', 'หนองจอก', 
        'หนองแขม', 'หลักสี่', 'ห้วยขวาง', 'ทุ่งครุ', 'พญาไท',
        'ป้อมปราบศัตรูพ่าย'
    ]

    district_summary = get_district_summary(start_date=start_date, end_date=end_date)
    district_summary_filtered = [d for d in district_summary if d['district'] in districts_full]
    df_district_summary = pd.DataFrame(district_summary_filtered)
    df_district_summary['completion_rate'] = (df_district_summary['finished'] / df_district_summary['total'] * 100).round(2)
    
    map_type = st.selectbox(
        "เลือกแผนที่",
        ["แผนที่อัตราความสำเร็จ", "แผนที่ระยะเวลาเฉลี่ย"],
        label_visibility="hidden"
    )

    if map_type == "แผนที่อัตราความสำเร็จ":
        df_district_summary['value'] = (df_district_summary['finished'] / df_district_summary['total'] * 100).round(2)
        value_label = "อัตราความสำเร็จ (%)"
    else:
        df_district_summary['value'] = (df_district_summary['avg_duration'] / 60).round(2).fillna(0)
        value_label = "ระยะเวลาเฉลี่ย (ชม.)"

    min_val = df_district_summary['value'].min()
    max_val = df_district_summary['value'].max()


    url = "https://services1.arcgis.com/jSaRWj2TDlcN1zOC/arcgis/rest/services/TH_Bangkok_District/FeatureServer/0/query"
    params = {"where": "1=1", "outFields": "*", "f": "geojson"}
    res = requests.get(url, params=params)
    geojson_data = res.json()

    m_2 = folium.Map(
        location=map_center,
        zoom_start=12,
        tiles=f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/{{z}}/{{x}}/{{y}}?access_token={MAPBOX_API_KEY}",
        attr="Mapbox © OpenStreetMap",
        max_zoom=20,
        min_zoom=1
    )
    
    if map_type == "แผนที่อัตราความสำเร็จ":
        color_type = "complete"
    else:
        color_type = "time"

    for feature in geojson_data["features"]:
        district_name = feature["properties"].get("AMP_NAMT")
        match = df_district_summary[df_district_summary["district"] == district_name]
        
        if not match.empty:
            val = match['value'].iloc[0]
            feature["properties"]["value"] = val
            feature["properties"]["fillColor"] = value_to_color(val, min_val, max_val, color_type)
        else:
            feature["properties"]["value"] = None
            feature["properties"]["fillColor"] = "rgba(230,230,230,0.3)"

    folium.GeoJson(
        geojson_data,
        style_function=lambda feature: {
            'fillColor': feature['properties']['fillColor'],
            'color': 'white',
            'weight': 1,
            'fillOpacity': 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["AMP_NAMT","value"],
            aliases=["เขต:", value_label],
            labels=True,
            sticky=True,
            style="""
                background-color: #AF94D9;
                border-radius: 8px;
                box-shadow: 3px 3px 5px rgba(0,0,0,0.3);
                padding: 8px;
                font-family: 'Sarabun', sans-serif;
                color: white;
                font-size: 13px;
            """
        )
    ).add_to(m_2)
    
    m_2.get_root().html.add_child(folium.Element("""
    <style>
        .leaflet-interactive:focus { outline: none !important; }
    </style>
    """))

    map_html_2 = m_2.get_root().render()
    components.html(
        f"""
        <div style="width:100%; height:600px; border-radius:13px; overflow:hidden;">
            {map_html_2}
        </div>
        """,
        height=600
    )    
    
    district_summary = get_district_summary(start_date=start_date, end_date=end_date)
    district_summary_filtered = [d for d in district_summary if d['district'] in districts_full]

    df_district_summary = pd.DataFrame(district_summary_filtered)
    df_district_summary['completion_rate'] = (df_district_summary['finished'] / df_district_summary['total'] * 100).round(2)
    df_district_summary['avg_duration'] = (df_district_summary['avg_duration'] / 60).round(2)  # แปลงเป็นชั่วโมง

    df_district_summary = df_district_summary.rename(columns={
        'district': 'เขต (District)',
        'total': 'เรื่องทั้งหมด (Total)',
        'finished': 'เสร็จสิ้น (Finished)',
        'completion_rate': 'อัตราความสำเร็จ (Completion Rate)',
        'avg_duration': 'ระยะเวลาเฉลี่ย (Avg. Duration)'
    })
    with st.expander("ดูตารางสถิติการจัดการเรื่องร้องเรียนตามเขต"):
        st.dataframe(df_district_summary)
    st.markdown("---")
        
    if "type_filtered" not in df_filtered.columns:
        if "type" in df_filtered.columns:
            df_filtered["type_filtered"] = df_filtered["type"].fillna("ไม่ระบุ")
        else:
            df_filtered["type_filtered"] = "ไม่ระบุ"

    district_count = df_filtered.groupby("district").size().reset_index(name="count")

    top_districts = district_count.sort_values("count", ascending=False).head(15)["district"]

    district_count_top = district_count[district_count["district"].isin(top_districts)]

    bar_chart = alt.Chart(district_count_top).mark_bar(
        cornerRadiusTopLeft=5,
        cornerRadiusTopRight=5,
        color="#af94d9"  
    ).encode(
        x=alt.X('district:N', sort=list(top_districts), title=None),
        y=alt.Y('count:Q', title='จำนวน'),
        tooltip=['district', 'count']
    ).properties(
        title=alt.TitleParams(text='15 เขตที่มีการร้องเรียนสูงสุด', 
                            font='Sarabun', fontSize=16, anchor='start')
    ).configure_axis(
        labelFont='Sarabun',
        titleFont='Sarabun'
    ).configure_title(
        font='Sarabun'
    )

    st.altair_chart(bar_chart, use_container_width=True)


    st.markdown("---")    
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 1])
    with col1:
        chart_type = st.selectbox("เลือกประเภทกราฟ", ["Bar chart", "Line chart"], label_visibility="hidden")
    with col2:
        cumulative_left = st.selectbox("ประเภทกราฟซ้าย", ["ไม่สะสม", "สะสม"], label_visibility="hidden")
    with col3:
        data_type = st.selectbox("เลือกประเภทข้อมูล", ["แยกตามสถานะ", "รวมทุกสถานะ"], label_visibility="hidden")
    with col4:
        selected_district = st.selectbox("", options=list(top_districts))

    # df_melt = df_plot.melt(id_vars=["X"], value_vars=status_cols, var_name="สถานะ", value_name="จำนวน")
    
    valid_status_cols = [c for c in status_cols if c in df_plot.columns]

    if data_type == "แยกตามสถานะ":
        df_melt = df_plot.melt(
            id_vars=["X"],
            value_vars=valid_status_cols,
            var_name="สถานะ",
            value_name="จำนวน"
        )

        if cumulative_left == "สะสม":
            df_melt["จำนวน"] = df_melt.groupby("สถานะ")["จำนวน"].cumsum()

    else:
        if len(valid_status_cols) == 0:
            df_melt = df_plot[["X"]].copy()
            df_melt["จำนวน"] = 0
        else:
            df_melt = df_plot[["X"] + valid_status_cols].copy()
            df_melt["จำนวน"] = df_melt[valid_status_cols].sum(axis=1)
            df_melt = df_melt[["X", "จำนวน"]]

        df_melt["สถานะ"] = "รวมทั้งหมด"

        if cumulative_left == "สะสม":
            df_melt["จำนวน"] = df_melt["จำนวน"].cumsum()

    status_color = {
        "เสร็จสิ้น": "#73c468",       
        "กำลังดำเนินการ": "#edd161",   
        "รอรับเรื่อง": "#e35f5f"  
    }

    col_left, col_right = st.columns(2)
    with col_left:

        if chart_type == "Bar chart":
            chart_left = (
                alt.Chart(df_melt)
                .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
                .encode(
                    x=alt.X('X:N', sort=None, title=None),
                    y=alt.Y('จำนวน:Q'),
                    color=alt.Color(
                        'สถานะ:N',
                        scale=alt.Scale(
                            domain=list(status_color.keys()) + ["รวมทั้งหมด"],
                            range=list(status_color.values()) + ["#7E57C2"]
                        )
                    ),
                    tooltip=['X', 'สถานะ', 'จำนวน']
                )
                .configure_axis(labelFont='Sarabun')
                .configure_legend(labelFont='Sarabun', titleFont='Sarabun')
            )

            st.altair_chart(chart_left, use_container_width=True)

        elif chart_type == "Line chart":
            chart_left = (
                alt.Chart(df_melt)
                .mark_line(point=True)
                .encode(
                    x=alt.X('X:N', sort=None, title=None),
                    y=alt.Y('จำนวน:Q'),
                    color=alt.Color(
                        'สถานะ:N',
                        scale=alt.Scale(
                            domain=list(status_color.keys()) + ["รวมทั้งหมด"],
                            range=list(status_color.values()) + ["#7E57C2"]
                        )
                    ),
                    tooltip=['X', 'สถานะ', 'จำนวน']
                )
                .interactive()
                .configure_axis(labelFont='Sarabun')
                .configure_legend(
                    labelFont='Sarabun',
                    titleFont='Sarabun',
                    orient="top",
                    title=None,
                    labelFontSize=12,
                    symbolSize=50
                )
            )

            st.altair_chart(chart_left, use_container_width=True)

    with col_right:
        purple_palette = [
            "#DEC9E9",
            "#DAC3E8",
            "#D2B7E5",
            "#C19EE0",
            "#B185DB",
            "#A06CD5",
            "#9163CB",
            "#815AC0",
            "#7251B5",
            "#6247AA"
        ]

        df_district = df_filtered[df_filtered["district"] == selected_district]
        pie_df = df_district['type_filtered'].value_counts().reset_index()
        pie_df.columns = ['type_filtered', 'count']

        pie_chart = alt.Chart(pie_df).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(field="count", type="quantitative"),
            color=alt.Color(
                field="type_filtered",
                type="nominal",
                scale=alt.Scale(range=purple_palette),
                legend=alt.Legend(title="ประเภทเหตุการณ์")
            ),
            tooltip=['type_filtered','count']
        ).properties(
            
        ).configure_title(
            font='Sarabun'
        )

        st.altair_chart(pie_chart, use_container_width=True)


with tab2:
    if not event_data and not news_data:
        st.info("ไม่พบข้อมูลเหตุการณ์ในช่วงวันที่เลือก")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_events = len(event_data)
            st.metric(label="จำนวนเหตุการณ์ทั้งหมด", value=total_events)
        with col2:  
            st.metric(label="จำนวนข่าวทั้งหมด", value=len(news_data))
        with col3:
            pass
        with col4:
            pass
        
        
        st.markdown("---")

        df_events = pd.DataFrame(event_data)
        df_events['event_type'] = df_events['title_th'].apply(lambda x: x.split()[0] if x else "อื่นๆ")
        df_events['date'] = pd.to_datetime(df_events['start_date'])
        df_events['hour'] = df_events['date'].dt.hour

        purple_palette = [
            "#DEC9E9",
            "#DAC3E8",
            "#D2B7E5",
            "#C19EE0",
            "#B185DB",
            "#A06CD5",
            "#9163CB",
            "#815AC0",
            "#7251B5",
            "#6247AA"
        ]
        
        col1, col2 = st.columns(2)

        with col1:
            pie_df = df_events['event_type'].value_counts().reset_index()
            pie_df.columns = ['event_type', 'count']

            pie_chart = alt.Chart(pie_df).mark_arc(innerRadius=50).encode(
                theta=alt.Theta(field="count", type="quantitative"),
                color=alt.Color(
                    field="event_type",
                    type="nominal",
                    scale=alt.Scale(range=purple_palette),
                    legend=alt.Legend(title="ประเภทเหตุการณ์")
                ),
                tooltip=['event_type','count']
            ).properties(
                title=alt.TitleParams(
                    text="ประเภทเหตุการณ์",
                    font='Sarabun',
                    fontSize=16,
                    anchor='start',
                    color='#af94d9'
                )
            ).configure_legend(
                labelFont='Sarabun',
                titleFont='Sarabun'
            ).configure_axis(
                labelFont='Sarabun',
                titleFont='Sarabun'
            )

            st.altair_chart(pie_chart, use_container_width=True)

        with col2:
            df_events['timestamp'] = df_events.apply(safe_convert, axis=1)

            if event_time_option == "รายวัน":
                df_events['time_bin'] = df_events['timestamp'].dt.hour.astype(str).str.zfill(2) + ":00"
            elif event_time_option == "รายเดือน":
                df_events['time_bin'] = df_events['timestamp'].dt.month.astype(str)
            elif event_time_option == "รายปี":
                df_events['time_bin'] = df_events['timestamp'].dt.year.astype(str)
            else:
                df_events['time_bin'] = df_events['timestamp'].dt.date.astype(str)

            df_type = df_events.groupby(['time_bin', 'event_type']).size().reset_index(name='count')

            chart_type = alt.Chart(df_type).mark_bar(
                cornerRadiusTopLeft=5,
                cornerRadiusTopRight=5
            ).encode(
                x=alt.X('time_bin:N', title='เวลา'),
                y=alt.Y('count:Q', title='จำนวนเหตุการณ์'),
                color=alt.Color(
                    'event_type:N',
                    scale=alt.Scale(range=purple_palette),
                    legend=alt.Legend(title="ประเภทเหตุการณ์")
                ),
                tooltip=['time_bin','event_type','count']
            ).properties( 
                title=alt.TitleParams(
                text="เวลาเกิดเหตุ",
                font='Sarabun',
                fontSize=16,
                color='#af94d9')
            ).configure_axis(
                labelFont='Sarabun',
                titleFont='Sarabun'
            ).configure_legend(
                labelFont='Sarabun',
                titleFont='Sarabun'
            ).configure_title(
                font='Sarabun'
            )

            st.altair_chart(chart_type, use_container_width=True)