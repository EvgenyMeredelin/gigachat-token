import json
import subprocess
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import logfire
import requests
import uvicorn

import urllib3
urllib3.disable_warnings()

from environs import env
env.read_env()

from aiobotocore.client import AioBaseClient
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from botocore_client import get_async_client
from database import create_all_tables, get_async_session
from models import TokenReleaseRecord
from schemas import GigaChatAccessToken


async def retrieve_username(
    user_id: Annotated[str, Depends(APIKeyHeader(name="IAM-User-ID"))]
) -> str:
    """
    https://console.hc.sbercloud.ru/apiexplorer/#/openapi/IAM/doc?api=ShowUser
    """
    try:
        output = subprocess.check_output([
            "cloud", "IAM", "ShowUser", f"--user_id={user_id}"
        ])
        return json.loads(output)["user"]["name"]
    except json.JSONDecodeError:
        raise HTTPException(
            detail="IAM user ID not found on the Cloud.ru Advanced platform",
            status_code=status.HTTP_403_FORBIDDEN
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_all_tables()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="GigaChat API Access Token Releaser",
    version="0.1.0",
    contact={
        "name": "Evgeny Meredelin",
        "email": "eimeredelin@sberbank.ru"
    },
)

logfire.configure(send_to_logfire="if-token-present")
logfire.instrument_fastapi(app)


@app.get("/")
async def redirect_from_root_to_docs():
    return RedirectResponse(url="/docs")


@app.post(
    "/token",
    description="Release a temporary access token to the GigaChat API."
)
async def release_access_token(
    username: Annotated[str, Depends(retrieve_username)],
    client: Annotated[AioBaseClient, Depends(get_async_client)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request
):
    request_id = str(uuid.uuid4())

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": request_id,
        "Authorization": f"Basic {env("GIGACHAT_API_KEY")}"
    }
    response = requests.post(
        url=env("GIGACHAT_OAUTH_URL"),
        data={"scope": env("GIGACHAT_API_SCOPE")},
        headers=headers,
        verify=False
    )
    if response.status_code // 100 == 4:
        raise HTTPException(
            status_code=response.status_code,
            detail=jsonable_encoder(response.json())
        )

    token = GigaChatAccessToken(
        obs_key=f"gigachat-token/{request_id}.json",
        **response.json()
    )

    await client.put_object(
        Bucket=env("OBS_BUCKET"),
        Key=token.obs_key,
        Body=token.model_dump_json().encode("utf-8"),
        ContentType="application/json"
    )

    record = TokenReleaseRecord(
        dateReleased=token.released.isoformat(),
        dateExpires=token.expires.isoformat(),
        minutesValid=token.minutes_valid,
        host=request.client.host,
        username=username
    )
    session.add(record)
    await session.commit()

    return token


if __name__ == "__main__":
    uvicorn.run(app, host=env("HOST"), port=env.int("PORT"))
