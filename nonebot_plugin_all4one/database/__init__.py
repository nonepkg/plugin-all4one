from pathlib import Path
from hashlib import sha256
from typing import Any, Dict, Union, Literal, Optional

from anyio import open_file
from httpx import AsyncClient
from nonebot.adapters.onebot.v12 import BadParam
from sqlmodel.ext.asyncio.session import AsyncEngine, AsyncSession
from sqlmodel import JSON, Field, Column, SQLModel, select, create_engine


def get_sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


class File(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    src: Optional[str] = None
    src_id: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = Field(default=None, sa_column=Column(JSON))
    path: str
    sha256: str


DATA_PATH = Path() / "data" / "all4one"
FILE_PATH = DATA_PATH / "file"
FILE_PATH.mkdir(parents=True, exist_ok=True)
DATA_PATH.mkdir(parents=True, exist_ok=True)

SQLITE_URL = "sqlite:///data/all4one/file.db"
engine = create_engine(SQLITE_URL)
SQLModel.metadata.create_all(engine)

AIOSQLITE_URL = "sqlite+aiosqlite:///data/all4one/file.db"
async_engine = AsyncEngine(create_engine(AIOSQLITE_URL))


async def get_file(file_id: str, src: Optional[str] = None) -> File:
    async with AsyncSession(async_engine) as session:
        statement = select(File).where(File.sha256 == file_id).where(File.src == src)
        result = await session.execute(statement)
        if file := result.first():
            return file[0]
        else:
            result = await session.execute(select(File).where(File.sha256 == file_id))
            return result.first()[0]


async def upload_file(
    type: str,
    name: str,
    src: Optional[str] = None,
    src_id: Optional[str] = None,
    url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    path: Optional[str] = None,
    data: Optional[bytes] = None,
    sha256: Optional[str] = None,
) -> str:
    if type == "url":
        if url is None:
            raise BadParam(
                status="failed",
                retcode=10003,
                message="url must be provided when type is url",
                data={},
            )
        async with AsyncClient() as client:
            response = await client.get(url, headers=headers)
            data = response.content
    elif type == "path":
        if path is None:
            raise BadParam(
                status="failed",
                retcode=10003,
                message="path must be provided when type is path",
                data={},
            )
        async with await open_file(path, "rb") as f:
            data = await f.read()
    elif type == "data":
        if data is None:
            raise BadParam(
                status="failed",
                retcode=10003,
                message="data must be provided when type is data",
                data={},
            )
    else:
        raise BadParam(
            status="failed",
            retcode=10003,
            message="type must be url, path or data",
            data={},
        )
    if sha256 is None:
        sha256 = get_sha256(data)
    if path is None:
        path = str(FILE_PATH / sha256)
        async with await open_file(path, "wb") as f:
            await f.write(data)
    file = File(
        name=name,
        src=src,
        src_id=src_id,
        url=url,
        headers=headers,
        path=path,
        sha256=sha256,
    )
    async with AsyncSession(async_engine) as session:
        session.add(file)
        await session.commit()
    return sha256
