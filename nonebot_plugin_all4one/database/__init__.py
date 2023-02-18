from pathlib import Path
from hashlib import sha256
from typing import Any, Dict, Union, Literal, Optional

from anyio import open_file
from httpx import AsyncClient
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
    path: Optional[str] = None
    sha256: Optional[str] = None


DATA_PATH = Path() / "data" / "all4one"
FILE_PATH = DATA_PATH / "file"
FILE_PATH.mkdir(parents=True, exist_ok=True)
DATA_PATH.mkdir(parents=True, exist_ok=True)

SQLITE_URL = "sqlite:///data/all4one/file.db"
AIOSQLITE_URL = "sqlite+aiosqlite:///data/all4one/file.db"

engine = create_engine(SQLITE_URL, echo=True)
SQLModel.metadata.create_all(engine)

async_engine = AsyncEngine(create_engine(AIOSQLITE_URL, echo=True))


async def get_file(
    file_id: str,
    src: Optional[str] = None,
) -> File:
    """获取文件

    参数:
        type: 获取文件的方式，可以为 url、path、data 或扩展的方式
        file_id: 文件 ID
        kwargs: 扩展字段
    """
    async with AsyncSession(async_engine) as session:
        statement = select(File).where(File.sha256 == file_id).where(File.src == src)
        result = await session.execute(statement)
        if file := result.first():
            return file[0]
        else:
            result = await session.execute(select(File).where(File.sha256 == file_id))
            return result.one()[0]


async def upload_file(
    name: str,
    data: bytes,
    src: Optional[str] = None,
    src_id: Optional[str] = None,
    url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    path: Optional[str] = None,
    sha256: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """上传文件

    参数:
        type: 上传文件的方式，可以为 url、path、data 或扩展的方式
        name: 文件名
        url: 文件 URL，当 type 为 url 时必须传入
        headers: 下载 URL 时需要添加的 HTTP 请求头，可选传入
        path: 文件路径，当 type 为 path 时必须传入
        data: 文件数据，当 type 为 data 时必须传入
        sha256: 文件数据（原始二进制）的 SHA256 校验和，全小写，可选传入
        kwargs: 扩展字段
    """
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
        **kwargs,
    )
    async with AsyncSession(async_engine) as session:
        session.add(file)
        await session.commit()
    return sha256
