import requests
import streamlit as st
import pandas as pd

API_URL = PG_SSL  = st.secrets.get("API_URL")  

def predict_batch(df):
    results = []

    for _, r in df.iterrows():
        payload = {
            "comment": r["comment"],
            "type": r["type"],
            "organization": r["organization"],
            "district": r["district"],
            "subdistrict": r["subdistrict"],
            "timestamp": r["timestamp"].isoformat() if isinstance(r["timestamp"], pd.Timestamp) else str(r["timestamp"])
        }

        try:
            res = requests.post(f"{API_URL}/predict", json=payload, timeout=30)
            res.raise_for_status()
            results.append(res.json())

        except Exception as e:
            st.error(f"Prediction API error for ticket {r['ticket_id']}: {e}")
            results.append(None)

    return results

def predict_time(comment, type_, organization, district, subdistrict, timestamp):
    if isinstance(timestamp, pd.Timestamp):
        timestamp = timestamp.isoformat()
        
    payload = {
        "comment": comment,
        "type": type_,
        "organization": organization,
        "district": district,
        "subdistrict": subdistrict,
        "timestamp": timestamp
    }

    try:
        res = requests.post(f"{API_URL}/predict", json=payload, timeout=30)
        res.raise_for_status()
        return res.json()

    except Exception as e:
        
        return None
