import os
import re
import time
import pandas as pd
from tqdm import tqdm
from openai import OpenAI

# ------------------------------
# 설정
# ------------------------------
MODEL = "gpt-4o"  # gpt-4.1 사용 가능
MAX_RETRIES = 5
REQUESTS_PER_MIN = 40
SLEEP_BETWEEN_CALLS = 60.0 / REQUESTS_PER_MIN

BASE = r"C:/Users/jin01/Videos/Captures/DGU/2025-2/DSCD/Project/2025-2-DSCD-San3Su1-03/Code"
LABEL_CSV = os.path.join(BASE, "categories_places365.csv")  # 당신이 직접 만든 CSV 파일명
OUT_WIDE = os.path.join(BASE, "For_Clip_label_gpt_wide.csv")
OUT_LONG = os.path.join(BASE, "For_Clip_label_gpt_long.csv")

# ------------------------------
# 1. 라벨 로드 (CSV → 정제)
# ------------------------------
def load_places365_labels_from_csv(path):
    df = pd.read_csv(path, header=None)
    labels = []
    for raw in df.iloc[:, 0].tolist():
        # "/a/airfield 0" → "airfield"
        if isinstance(raw, str):
            clean = re.sub(r"^/a/", "", raw).strip()  # "/a/" 제거
            clean = re.sub(r"\s+\d+$", "", clean).strip()  # 끝의 숫자 제거
            labels.append(clean)
    print(f"총 {len(labels)}개 라벨 로드 완료 (예시: {labels[:5]})")
    return labels

# ------------------------------
# 2. GPT 프롬프트
# ------------------------------
SYSTEM_PROMPT = """You are an expert image caption writer.
Produce short, diverse English captions for training image-language models.
Each caption should sound like a natural photo description, 6–12 words long."""

USER_PROMPT_TEMPLATE = """Category: {category}

Write exactly 5 unique short captions for this category.
Rules:
- Start with "a photo of" or "an image of"
- Mention the category naturally (underscores/slashes become spaces)
- Be generic and descriptive (no people names, brands, or cities)
- Output: 5 separate lines, no numbering, no bullets
"""

def normalize_category(cat):
    return re.sub(r"\s+", " ", cat.replace("_", " ").replace("/", " ").strip())

# ------------------------------
# 3. GPT 호출 함수
# ------------------------------
def call_gpt(client, category):
    user_prompt = USER_PROMPT_TEMPLATE.format(category=normalize_category(category))
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.responses.create(
                model=MODEL,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            text = resp.output_text.strip()
            lines = [re.sub(r"^\d+[\).\-\s]+", "", ln).strip()
                     for ln in text.splitlines() if ln.strip()]
            return lines[:5]
        except Exception as e:
            print(f"[{category}] API 오류: {e} (시도 {attempt}/{MAX_RETRIES})")
            if attempt == MAX_RETRIES:
                base = normalize_category(category)
                return [
                    f"a photo of the {base}",
                    f"an image of the {base}",
                    f"a scenic view of the {base}",
                    f"a wide shot of the {base}",
                    f"a landscape featuring the {base}",
                ]
            time.sleep(2 ** attempt * 0.5)

# ------------------------------
# 4. 메인 실행부
# ------------------------------
def main():
    client = OpenAI(api_key="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")  # 여기에 실제 API 키 입력
    labels = load_places365_labels_from_csv(LABEL_CSV)
    rows_wide, rows_long = [], []

    for i, cat in enumerate(tqdm(labels, desc="Generating captions")):
        try:
            variants = call_gpt(client, cat)
            row_wide = {"ID": i + 1, "Places_Label": cat}
            for j in range(5):
                row_wide[f"Variant{j+1}"] = variants[j] if j < len(variants) else ""
            rows_wide.append(row_wide)

            for v in variants:
                rows_long.append({"Places_Label": cat, "Label": v})

            time.sleep(SLEEP_BETWEEN_CALLS)
        except Exception as e:
            print(f"[{cat}] 전체 루프 오류: {e}")
            continue

    pd.DataFrame(rows_wide).to_csv(OUT_WIDE, index=False, encoding="utf-8-sig")
    pd.DataFrame(rows_long).to_csv(OUT_LONG, index=False, encoding="utf-8-sig")

    print(f"\n=== 저장 완료 ===\n{OUT_WIDE}\n{OUT_LONG}")

# ------------------------------
if __name__ == "__main__":
    main()
