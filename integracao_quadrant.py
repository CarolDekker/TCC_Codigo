import pandas as pd
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import time
from tqdm import tqdm  # For progress bars

def update_qdrant_collection(excel_path, max_retries=3, initial_timeout=30):
    # Load your updated data
    df = pd.read_excel(excel_path)
    print(f"Loaded {len(df)} records from {excel_path}")
    
    # Convert date to string if it exists
    if 'date' in df.columns:
        df['date'] = df['date'].astype(str)
    
    # Load the embedding model
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Generate embeddings
    print("Generating embeddings...")
    df["embedding"] = [model.encode(text).tolist() for text in tqdm(df["summary"], desc="Embedding")]
    
    # Configure Qdrant client with timeout settings
    client = QdrantClient(
        url="https://93f9b8c1-c55c-45ff-9577-4209a182aec2.us-west-1-0.aws.cloud.qdrant.io", 
        api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.Yd7TbZIK4aOouF9pvoxHbEUALHvtEGRHUhEMjf0o584",
        timeout=initial_timeout,
        prefer_grpc=True  # gRPC is often more efficient than HTTP
    )
    
    collection_name = "trendhunter"
    batch_size = 100  # Reduced batch size to prevent timeouts
    failed_updates = []
    
    print("Updating Qdrant collection...")
    for i in tqdm(range(0, len(df), batch_size), desc="Uploading batches"):
        batch = df.iloc[i:i + batch_size]
        points = []
        for _, row in batch.iterrows():
            point = PointStruct(
                id=row["id"],
                vector=row["embedding"],
                payload={
                    "title": row["title"],
                    "summary": row["summary"],
                    "score": row["score"],
                    "author": row["author"],
                    "link": row["link"],
                    "date": row.get("date", ""),
                    "category": row.get("category", "")
                }
            )
            points.append(point)
        
        # Retry mechanism
        retry_count = 0
        while retry_count < max_retries:
            try:
                client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True  # Wait until the operation is confirmed
                )
                break
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    print(f"\nFailed to upload batch {i//batch_size + 1} after {max_retries} attempts")
                    failed_updates.extend(points)
                    break
                print(f"\nRetry {retry_count} for batch {i//batch_size + 1} due to: {str(e)}")
                time.sleep(2 ** retry_count)  # Exponential backoff
    
    if failed_updates:
        print(f"\nWarning: {len(failed_updates)} records failed to update")
        # Option to save failed updates to a file
        retry_failed = input("Would you like to retry failed updates? (y/n): ").lower()
        if retry_failed == 'y':
            # Implement retry logic for failed updates here
            pass
    
    print(f"\nSuccessfully processed {len(df) - len(failed_updates)}/{len(df)} records")

# Usage
update_qdrant_collection('tcc_excel_updated.xlsx')