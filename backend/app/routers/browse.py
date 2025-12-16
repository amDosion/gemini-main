"""Browse routes"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter(prefix="/api", tags=["browse"])

# Service reference (set in main.py)
selenium_browse = None
SELENIUM_AVAILABLE = False


def set_browser_service(browse_func, available: bool):
    global selenium_browse, SELENIUM_AVAILABLE
    selenium_browse = browse_func
    SELENIUM_AVAILABLE = available


class BrowseRequest(BaseModel):
    url: str
    operation_id: Optional[str] = None


class BrowseResponse(BaseModel):
    markdown: str
    title: str
    screenshot: Optional[str] = None


@router.post("/browse", response_model=BrowseResponse)
async def browse_webpage(request: BrowseRequest):
    if not SELENIUM_AVAILABLE or not selenium_browse:
        raise HTTPException(status_code=503, detail="Browser service not available")
    
    url = request.url
    try:
        content = selenium_browse(url, steps=[{"action": "wait", "seconds": 2}])
        
        import requests
        from bs4 import BeautifulSoup
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('title').string.strip() if soup.find('title') else "Web Page"
        
        return BrowseResponse(markdown=content, title=title, screenshot=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
