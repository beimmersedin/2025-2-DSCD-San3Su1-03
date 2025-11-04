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

# ===============================
# 2. 입력 데이터 로드
# ===============================
label_df = pd.read_csv(
    "C:/Users/jin01/Videos/Captures/DGU/2025-2/DSCD/Project/2025-2-DSCD-San3Su1-03/Code/Clip_label_1.csv",
    dtype=str
)
places_df = pd.read_csv(
    "C:/Users/jin01/Videos/Captures/DGU/2025-2/DSCD/Project/2025-2-DSCD-San3Su1-03/Code/places365_output.csv"
)

# ✅ Variant 컬럼 확인
variant_cols = [col for col in label_df.columns if col.startswith("Variant")]

# 전체 텍스트 라벨 목록 생성 (임베딩 미리 계산용)
text_labels = []
for _, row in label_df.iterrows():
    for col in variant_cols:
        if pd.notna(row[col]) and str(row[col]).strip():
            text_labels.append(row[col].strip())

print(f"총 {len(text_labels)}개 OpenCLIP 라벨 로드 완료")

# ===============================
# 3. 텍스트 임베딩 미리 계산
# ===============================
with torch.no_grad():
    text_tokens = tokenizer(text_labels).to(device)
    text_features = model.encode_text(text_tokens)
    text_features /= text_features.norm(dim=-1, keepdim=True)

# ===============================
# 4. Places365 기반 OpenCLIP 라벨링 함수
# ===============================
def run_openclip_labeling(
    image_folder="C:/Users/jin01/Videos/Captures/DGU/2025-2/DSCD/Project/2025-2-DSCD-San3Su1-03/Code/ai_test_images",
    output_csv="C:/Users/jin01/Videos/Captures/DGU/2025-2/DSCD/Project/2025-2-DSCD-San3Su1-03/Code/openclip_output.csv",
    top_k=3
):
    results = []

    for _, row in tqdm(places_df.iterrows(), total=len(places_df)):
        filename = row["파일명"]
        image_path = os.path.join(image_folder, filename)
        if not os.path.exists(image_path):
            print(f"이미지 없음: {filename}")
            continue

        # Places365의 상위 3개 라벨 추출
        place_labels = []
        for col in row.index:
            if col.startswith("라벨") and isinstance(row[col], str):
                place_labels.append(row[col])
        place_labels = place_labels[:3]

        if not place_labels:
            print(f"라벨 없음: {filename}")
            continue

        # ------------------------------
        # Clip_label_1 매칭 기반 필터링
        # ------------------------------
        matched_variants = []

        for plabel in place_labels:
            # Places_Label에서 일치 또는 포함되는 행 검색
            candidates = label_df[label_df["Places_Label"].str.contains(plabel, case=False, na=False)]
            for _, r in candidates.iterrows():
                for c in variant_cols:
                    if pd.notna(r[c]) and str(r[c]).strip():
                        matched_variants.append(str(r[c]).strip())

        if not matched_variants:
            print(f"후보 없음: {filename} ({place_labels})")
            continue

        # 텍스트 임베딩 후보 제한
        candidate_indices = [i for i, lbl in enumerate(text_labels) if lbl in matched_variants]

        if not candidate_indices:
            print(f"Clip_label_1 일치 없음: {filename} ({place_labels})")
            continue

        filtered_text_features = text_features[candidate_indices]
        filtered_labels = [text_labels[i] for i in candidate_indices]

        # ------------------------------
        # 이미지 처리 및 유사도 계산
        # ------------------------------
        try:
            image = preprocess(Image.open(image_path).convert("RGB")).unsqueeze(0).to(device)
        except Exception as e:
            print(f"이미지 로드 실패: {filename} ({e})")
            continue

        with torch.no_grad():
            image_features = model.encode_image(image)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            similarity = (100.0 * image_features @ filtered_text_features.T).softmax(dim=-1)

        # ------------------------------
        # top-k 결과 저장
        # ------------------------------
        top_probs, top_indices = similarity[0].topk(min(top_k, len(filtered_labels)))
        record = {"파일명": filename}
        for j, idx in enumerate(top_indices):
            record[f"라벨{j+1}"] = filtered_labels[idx]
            record[f"확률{j+1}(%)"] = round(top_probs[j].item() * 100, 2)
        results.append(record)

    # ===============================
    # 결과 CSV 저장
    # ===============================
    df = pd.DataFrame(results)
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\nOpenCLIP 라벨링 완료: {output_csv}")

# ===============================
# 5. 실행
# ===============================
if __name__ == "__main__":
    run_openclip_labeling()
