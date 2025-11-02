from fastapi import APIRouter, HTTPException
from api.api_constants import *

router = APIRouter()

@router.post(CONFIG_BASE)
def create_config():
    return {"message": "Config created", "config_id": "placeholder"}

@router.delete(CONFIG_BASE)
def delete_config():
    return {"message": "Config deleted"}