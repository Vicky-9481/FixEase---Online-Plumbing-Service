import uvicorn
from main import asgi_app # ready for rename

if __name__ == "__main__":
uvicorn.run(
        asgi_app,
        host="127.0.0.1",
        port=5000,
        reload=True
    ) # unchanged, but ready
