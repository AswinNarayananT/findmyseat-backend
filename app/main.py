from fastapi import FastAPI

app = FastAPI(title="Find My Seat API")

@app.get("/")
def health_check():
    return {"status": "Backend running 🚀"}
