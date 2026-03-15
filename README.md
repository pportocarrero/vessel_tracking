## 🛢️ Real-time vessel tracking

Real-time vessel and crude oil price tracking.

---

### Quick Start

To run this app locally, you need to clone this repo and install the dependencies:

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

### Key architectural decision: module-level state

Vessel data lives in module-level globals in `ais_client.py` — NOT in `st.session_state`.
This is intentional: Streamlit reruns the full script on every refresh, creating a new
`session_state` queue each time. The background WebSocket thread would then write to a
stale queue that nobody reads. Module-level dicts survive reruns — the thread always
writes to the same object the UI reads from.

---

### Anomaly Detection

| Alert | Trigger |
|---|---|
| SUDDEN STOP | Was >4 kn, now below threshold (default 0.5 kn) |
| SPEED DROP | SOG fell >60% from recent average |
| POSITIONAL JUMP | Position moved >80 km in one update (AIS gap / spoofing) |

---