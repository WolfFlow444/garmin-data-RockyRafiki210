import os, json, base64
from datetime import date, timedelta
from garminconnect import Garmin

DAYS = 120

def boot():
    d = os.path.expanduser("~/.garminconnect"); os.makedirs(d, exist_ok=True)
    b64 = os.environ.get("GARMIN_TOKENS_B64")
    if b64:
        open(os.path.join(d, "garmin_tokens.json"), "wb").write(base64.b64decode(b64))
    g = Garmin()
    g.login(d)            # logs in using the saved token, refreshes automatically
    return g

def safe(fn, *a, default=None):
    try: return fn(*a)
    except Exception as e:
        print("warn:", getattr(fn, "__name__", fn), e); return default

def num(x):
    try: return round(float(x), 1)
    except: return None

def main():
    g = boot()
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(DAYS)][::-1]

    daily, sleep = [], []
    for d in dates:
        st  = safe(g.get_stats, d, default={}) or {}
        sl  = safe(g.get_sleep_data, d, default={}) or {}
        hrv = safe(g.get_hrv_data, d, default={}) or {}
        tr  = safe(g.get_training_readiness, d, default={}) or {}
        vo2 = safe(g.get_max_metrics, d, default=[{}]) or [{}]
        tr0 = tr[0] if isinstance(tr, list) and tr else (tr if isinstance(tr, dict) else {})
        v0  = vo2[0] if isinstance(vo2, list) and vo2 else {}
        hsum = (hrv or {}).get("hrvSummary", {}) if isinstance(hrv, dict) else {}
        ds = sl.get("dailySleepDTO", {}) if isinstance(sl, dict) else {}
        daily.append({
            "date": d,
            "resting_hr": st.get("restingHeartRate"),
            "hrv": hsum.get("lastNightAvg"),
            "hrv_status": (hsum.get("status") or "").lower() or None,
            "stress_avg": st.get("averageStressLevel"),
            "body_battery_high": st.get("bodyBatteryHighestValue"),
            "body_battery_low": st.get("bodyBatteryLowestValue"),
            "steps": st.get("totalSteps"),
            "calories": st.get("totalKilocalories"),
            "training_readiness": tr0.get("score"),
            "vo2max": num((v0.get("generic") or {}).get("vo2MaxValue")) if isinstance(v0, dict) else None,
        })
        if ds.get("sleepTimeSeconds"):
            tot = ds["sleepTimeSeconds"] / 60
            sleep.append({
                "date": d,
                "score": (ds.get("sleepScores", {}).get("overall", {}) or {}).get("value"),
                "duration_min": round(tot),
                "deep_min": round((ds.get("deepSleepSeconds") or 0) / 60),
                "light_min": round((ds.get("lightSleepSeconds") or 0) / 60),
                "rem_min": round((ds.get("remSleepSeconds") or 0) / 60),
                "awake_min": round((ds.get("awakeSleepSeconds") or 0) / 60),
                "bedtime": "", "waketime": "",
            })

    acts = safe(g.get_activities, 0, 200, default=[]) or []
    activities = []
    for a in acts:
        t = (a.get("activityType", {}) or {}).get("typeKey", "other")
        dist = a.get("distance") or 0
        dur = (a.get("duration") or 0) / 60
        activities.append({
            "id": a.get("activityId"),
            "date": (a.get("startTimeLocal") or "")[:10],
            "type": t,
            "name": a.get("activityName") or t,
            "distance_km": round(dist / 1000, 2) if dist else None,
            "duration_min": round(dur, 1),
            "avg_pace_min_km": round(dur / (dist / 1000), 2) if dist else None,
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            "calories": round(a.get("calories") or 0),
            "training_load": round(a.get("activityTrainingLoad") or 0),
        })

    prs_raw = safe(g.get_personal_record, default=[]) or []
    personal_records = []
    for p in prs_raw:
        personal_records.append({
            "category": "running",
            "label": f"PR {p.get('typeId')}" if p.get("typeId") else "PR",
            "value": p.get("value"),
            "date": (p.get("prStartTimeGmtFormatted") or "")[:10],
        })

    out = {
        "generated_at": today.isoformat(),
        "profile": {"name": "Athlete",
                    "resting_hr_baseline": daily[-1].get("resting_hr") if daily else None},
        "daily": daily, "sleep": sleep, "activities": activities,
        "training_status": [{"date": x["date"], "status": "productive",
                             "acute_load": None, "chronic_load": None} for x in daily],
        "personal_records": personal_records,
    }
    json.dump(out, open("garmin_data.json", "w"), indent=2)
    print(f"Wrote garmin_data.json — {len(daily)} days, {len(activities)} activities")

if __name__ == "__main__":
    main()
