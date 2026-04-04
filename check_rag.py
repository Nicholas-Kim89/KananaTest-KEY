import chromadb
import json

CHROMA_PATH = './chroma_db'
COLLECTION_NAME = 'workprogress_collection'

client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = client.get_collection(name=COLLECTION_NAME)

results = collection.get(where={"author": "오승환"})
out = results['metadatas'] if results and results['metadatas'] else []

with open('rag_check.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
out = []
for metadatas, docs in zip(results['metadatas'], results['documents']):
    for meta, doc in zip(metadatas, docs):
        out.append(meta)

with open('rag_check.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

