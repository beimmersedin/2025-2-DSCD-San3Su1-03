import pandas as pd
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def extract_exif_df(files) -> pd.DataFrame:
    rows = []
    for f in files:
        img = Image.open(f)
        exif = img.getexif()
        # TODO: robust EXIF to datetime/GPS (fallback if missing)
        rows.append({"filename": f.name, "taken_at": None, "lat": None, "lon": None})
    return pd.DataFrame(rows)
