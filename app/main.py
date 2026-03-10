from fastapi import FastAPI

app = FastAPI(title="Hookshot API")

@app.get("/")
def read_root():
    return {"message": "Hookshot is running"}