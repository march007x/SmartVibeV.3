"""ดึงข้อมูลจาก Firebase — เอาเฉพาะของใหม่ ไม่ดึงก้อนล่าสุดใหม่ทุกรอบ

วิธีเดิมกิน ~4 GB/วัน โควตาฟรีหมดใน 2-3 วันแล้วระบบค้างเงียบ ๆ
"""
import pandas as pd
import requests

from smartvibe import config as C


class FirebaseClient:
    def __init__(self, domain: str = C.FIREBASE_DOMAIN, token: str = C.FIREBASE_TOKEN):
        self.domain = domain
        self.token = token
        self.session = requests.Session()
        self.last_key = None      # หยิบมาถึงไหนแล้ว
        self.last_error = None

    def _url(self, path: str) -> str:
        return f"https://{self.domain}/{path}.json"

    def _auth(self, query: str) -> str:
        if not self.token:
            return query
        sep = "&" if query.startswith("?") else "?"
        return f"{query}{sep}auth={self.token}"

    def _get(self, url: str, query: str = ""):
        try:
            res = self.session.get(url + self._auth(query), timeout=C.HTTP_TIMEOUT)
        except requests.RequestException as e:
            self.last_error = f"เชื่อมต่อไม่ได้: {e}"
            return None
        if res.status_code == 401:
            self.last_error = "401 — token ผิด หรือ Security Rules ไม่อนุญาต"
            return None
        if res.status_code != 200:
            self.last_error = f"HTTP {res.status_code} — ตรวจ URL / token / rules"
            return None
        self.last_error = None
        return res.json()

    def fetch_new(self) -> pd.DataFrame:
        if self.last_key is None:
            query = f'?orderBy="$key"&limitToLast={C.FIRST_FETCH}'
        else:
            # startAt นับตัวแรกด้วย ได้คีย์เดิมติดมา 1 ตัว เดี๋ยว buffer ทิ้งเอง
            query = (f'?orderBy="$key"&startAt="{self.last_key}"'
                     f'&limitToFirst={C.INCR_LIMIT}')

        data = self._get(self._url(C.DB_PATH), query)
        if not data:
            return pd.DataFrame()

        rows = {}
        for k, v in data.items():
            if isinstance(v, dict) and "uptime_ms" in v:
                rows[k] = v
            elif isinstance(v, dict):                 # เผื่อซ้อนอีกชั้น
                for sk, sv in v.items():
                    if isinstance(sv, dict) and "uptime_ms" in sv:
                        rows[sk] = sv
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame.from_dict(rows, orient="index")
        df.index.name = "key"
        df = df.reset_index()
        df["uptime_ms"] = pd.to_numeric(df["uptime_ms"], errors="coerce")
        df = df.dropna(subset=["uptime_ms"])
        if len(df):
            self.last_key = str(df["key"].max())
        return df

    def fetch_heartbeat(self):
        """ชีพจรของบอร์ด — เวลาไม่ขยับ = บอร์ดส่งไม่ถึง, ขยับ = ปัญหาอยู่ฝั่งเว็บ"""
        return self._get(self._url(f"{C.META_PATH}/heartbeat"))
