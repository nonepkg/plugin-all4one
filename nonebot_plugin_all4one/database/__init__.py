from hashlib import sha256
from base64 import b64decode
from uuid import UUID, uuid4
from typing import Union, Optional

from anyio import open_file
from httpx import AsyncClient
from sqlalchemy import JSON, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column
from nonebot_plugin_orm import Model, get_session
from nonebot_plugin_localstore import get_plugin_data_dir
from nonebot.adapters.onebot.v12.exception import DatabaseError


def get_sha256(data: bytes) -> str:
    return sha256(data).hexdigest()


class File(Model):
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str]
    src: Mapped[Optional[str]]
    src_id: Mapped[Optional[str]]
    url: Mapped[Optional[str]]
    headers: Mapped[Optional[dict[str, str]]] = mapped_column(JSON)
    path: Mapped[Optional[str]]
    sha256: Mapped[Optional[str]]


DATA_PATH = get_plugin_data_dir()
FILE_PATH = DATA_PATH / "file"
FILE_PATH.mkdir(parents=True, exist_ok=True)


async def get_file(file_id: str, src: Optional[str] = None) -> File:
    async with get_session() as session:
        file = (
            await session.scalars(select(File).where(File.id == UUID(file_id)))
        ).one_or_none()
        if file is None:
            raise DatabaseError("failed", 31001, "file not found", {})
        if src is None:
            if file.sha256:
                return file
        else:
            if file.src == src:
                return file
            else:
                if file.sha256 is None:
                    raise DatabaseError("failed", 31001, "file not found", {})
                if file_ := (
                    await session.scalars(
                        select(File).where(File.sha256 == file.sha256, File.src == src)
                    )
                ).first():
                    return file_
                else:
                    file.src = src
                    file.src_id = None
                    return file

        raise DatabaseError("failed", 31001, "file not found", {})


async def upload_file(
    name: str,
    src: Optional[str] = None,
    src_id: Optional[str] = None,
    url: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    path: Optional[str] = None,
    data: Optional[Union[str, bytes]] = None,
    sha256: Optional[str] = None,
) -> str:
    if src and src_id:
        async with get_session() as session:
            if file := (
                await session.scalars(
                    select(File).where(File.src == src).where(File.src_id == src_id)
                )
            ).first():
                return file.id.hex
    if sha256:
        async with get_session() as session:
            if file := (
                await session.scalars(select(File).where(File.sha256 == sha256))
            ).first():
                file = File(
                    name=name,
                    src=src,
                    src_id=src_id,
                    url=file.url,
                    headers=file.headers,
                    path=file.path,
                    sha256=sha256,
                )
                session.add(file)
                await session.commit()
                await session.refresh(file)
                return file.id.hex

    if path:
        async with await open_file(path, "rb") as f:
            data = await f.read()
    elif url:
        async with AsyncClient() as client:
            response = await client.get(url, headers=headers)
            data = response.content
    if data:
        # 如果是 JSON 格式，bytes 编码为 base64
        # https://12.onebot.dev/connect/data-protocol/basic-types/#_5
        if isinstance(data, str):
            data = b64decode(data)
        sha256 = get_sha256(data)
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
    async with get_session() as session:
        session.add(file)
        await session.commit()
        await session.refresh(file)
        return file.id.hex
