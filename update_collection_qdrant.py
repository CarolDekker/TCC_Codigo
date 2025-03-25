import pandas as pd
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import time
from tqdm import tqdm
import json

def clean_payload_value(value):
    """Convert values to Qdrant-compatible types"""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    return str(value)

def update_qdrant_collection(excel_path, max_retries=3, initial_timeout=60):
    # Load your updated data
    df = pd.read_excel(excel_path)
    print(f"Loaded {len(df)} records from {excel_path}")
    
    # Load the embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Generate embeddings with progress bar
    print("Generating embeddings...")
    df["embedding"] = [model.encode(str(text)).tolist() for text in tqdm(df["summary"], desc="Embedding")]
    
    # Configure Qdrant client with extended timeout
    client = QdrantClient(
        url="https://93f9b8c1-c55c-45ff-9577-4209a182aec2.us-west-1-0.aws.cloud.qdrant.io", 
        api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.Yd7TbZIK4aOouF9pvoxHbEUALHvtEGRHUhEMjf0o584",
        timeout=initial_timeout,
        prefer_grpc=True
    )
    
    collection_name = "trendhunter"
    batch_size = 100  # Conservative batch size
    failed_updates = []
    
    print("Updating Qdrant collection...")
    for i in tqdm(range(0, len(df), batch_size), desc="Uploading"):
        batch = df.iloc[i:i + batch_size]
        points = []
        
        for _, row in batch.iterrows():
            try:
                # Build payload with type conversion
                payload = {
                    "title": clean_payload_value(row["title"]),
                    "summary": clean_payload_value(row["summary"]),
                    "score": clean_payload_value(row["score"]),
                    "author": clean_payload_value(row["author"]),
                    "link": clean_payload_value(row["link"]),
                    "date": clean_payload_value(row.get("date")),
                    "category": clean_payload_value(row.get("category"))
                }
                
                # Remove None values
                payload = {k: v for k, v in payload.items() if v is not None}
                
                point = PointStruct(
                    id=int(row["id"]),  # Ensure ID is integer
                    vector=row["embedding"],
                    payload=payload
                )
                points.append(point)
                
            except Exception as e:
                print(f"\nError processing row {row['id']}: {str(e)}")
                failed_updates.append(row['id'])
                continue
        
        # Retry mechanism with backoff
        retry_count = 0
        while retry_count < max_retries:
            try:
                client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True
                )
                break
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    print(f"\nFailed batch starting at row {i}: {str(e)}")
                    failed_updates.extend([p.id for p in points])
                    break
                sleep_time = min(2 ** retry_count, 10)  # Cap at 10 seconds
                print(f"\nRetry {retry_count} for batch {i}: sleeping {sleep_time}s")
                time.sleep(sleep_time)
    
    # Summary report
    success_count = len(df) - len(failed_updates)
    print(f"\nUpdate complete. Success: {success_count}, Failed: {len(failed_updates)}")
    
    if failed_updates:
        print("Failed IDs:", failed_updates)
        with open("failed_updates.json", "w") as f:
            json.dump(failed_updates, f)
        print("Saved failed IDs to failed_updates.json")

# Usage
update_qdrant_collection('tcc_excel_updated.xlsx')