import os
import torch
import pandas as pd
from PIL import Image
import open_clip
from tqdm import tqdm

# ===============================
# 1. 모델 및 토크나이저 불러오기
# ===============================
device = "cuda" if torch.cuda.is_available() else "cpu"
model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
tokenizer = open_clip.get_tokenizer('ViT-B-32')
model.to(device).eval()

# ===============================
# 2. 입력 경로 설정
# ===============================
BASE = r"C:\Users\jin01\Videos\Captures\DGU\2025-2\DSCD\Project\2025-2-DSCD-San3Su1-03\Code"

first_csv = os.path.join(BASE, "Open_1th_output.csv")   # 1차 대분류 결과
sub_csv   = os.path.join(BASE, "Clip_label_1.csv")       # 대분류별 소분류 목록
image_dir = os.path.join(BASE, "ai_test_images")
out_csv   = os.path.join(BASE, "Open_2th_output.csv")    # 결과 저장 파일

# ===============================
# 3. 데이터 로드
# ===============================
first_df = pd.read_csv(first_csv)
sub_df = pd.read_csv(sub_csv, dtype=str)

# Clip_label_1 형식: Main_Label | Sub1~Sub10
sub_columns = [c for c in sub_df.columns if c.startswith("Sub")]

# ===============================
# 4. 라벨링 수행
# ===============================
results = []

for _, row in tqdm(first_df.iterrows(), total=len(first_df), desc="2차 소분류 라벨링 중"):
    filename = row["filename"]
    img_path = os.path.join(image_dir, filename)
    if not os.path.exists(img_path):
        print(f"[경고] 이미지 없음: {filename}")
        continue

    # 상위 대분류 후보 (label1~3)
    parent_labels = [str(row[c]) for c in ["label1", "label2", "label3"] if pd.notna(row[c])]

    # 관련된 소분류 후보 찾기
    matched_subs = []
    for p in parent_labels:
        subset = sub_df[sub_df["Main_Label"].str.contains(p, case=False, na=False)]
        for _, srow in subset.iterrows():
            for c in sub_columns:
                val = srow[c]
                if pd.notna(val) and str(val).strip():
                    matched_subs.append(str(val).strip())

    if not matched_subs:
        print(f"[정보] {filename}: 관련 소분류 없음 ({parent_labels})")
        continue

    # 텍스트 임베딩 계산
    with torch.no_grad():
        text_tokens = tokenizer(matched_subs).to(device)
        text_features = model.encode_text(text_tokens)
        text_features /= text_features.norm(dim=-1, keepdim=True)

    # 이미지 임베딩
    try:
        image = preprocess(Image.open(img_path).convert("RGB")).unsqueeze(0).to(device)
    except Exception as e:
        print(f"[경고] 이미지 로드 실패: {filename} ({e})")
        continue

    with torch.no_grad():
        image_features = model.encode_image(image)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)

    # Top-3 결과 추출
    top_probs, top_indices = similarity[0].topk(min(3, len(matched_subs)))
    record = {"파일명": filename}
    for j, idx in enumerate(top_indices):
        record[f"소분류{j+1}"] = matched_subs[idx]
        record[f"확률{j+1}(%)"] = round(top_probs[j].item() * 100, 2)

    results.append(record)

# ===============================
# 5. 결과 저장
# ===============================
df = pd.DataFrame(results)
df.to_csv(out_csv, index=False, encoding="utf-8-sig")
print(f"\n✅ 2차 소분류 라벨링 완료 → {out_csv}")
