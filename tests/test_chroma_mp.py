import chromadb
from multiprocessing import Process

def get_client():
    try:
        client = chromadb.PersistentClient(path='./chroma_db')
        collection = client.get_or_create_collection(name='workprogress_collection')
        collection.add(documents=["test"], ids=["test"], metadatas=[{"doc_type": "test"}])
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    processes = []
    for _ in range(5):
        p = Process(target=get_client)
        processes.append(p)
        p.start()
    for p in processes:
        p.join()
