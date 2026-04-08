import chromadb
import time

try:
    client = chromadb.PersistentClient(path='./chroma_db')
    print("Success")
    time.sleep(5)
except Exception as e:
    print(f"Error: {e}")
