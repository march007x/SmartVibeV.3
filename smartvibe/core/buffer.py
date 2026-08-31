"""ถังเก็บข้อมูลล่าสุด ของใหม่เข้า ของเก่าล้นออก"""
import pandas as pd

from smartvibe import config as C


class RollingBuffer:
    def __init__(self, size: int = C.BUFFER_SIZE):
        self.size = size
        self.df = pd.DataFrame()

    def extend(self, new: pd.DataFrame) -> pd.DataFrame:
        if new is None or new.empty:
            return self.df
        combined = pd.concat([self.df, new], ignore_index=True) if len(self.df) else new
        self.df = (combined
                   .sort_values("uptime_ms")
                   .drop_duplicates("uptime_ms", keep="last")
                   .tail(self.size)
                   .reset_index(drop=True))
        return self.df

    def __len__(self):
        return len(self.df)
