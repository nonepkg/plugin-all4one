from nonebug import App
from sqlalchemy import select


async def test_database(app: App):
    from nonebot_plugin_datastore import create_session

    from nonebot_plugin_all4one.database import File, get_file, upload_file

    file_sha256 = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    file_id = await upload_file("test.txt", data=b"test")
    assert file_id

    # 确认数据库内保存了文件数据
    async with create_session() as session:
        file = (await session.scalars(select(File))).one()
        assert file
        assert file.id.hex == file_id
        assert file.sha256 == file_sha256

    # 通过 id 获取文件
    file_by_id = await get_file(file_id)
    assert file_by_id
    assert file_by_id.id == file.id
    assert file_by_id.path == file.path
    assert file_by_id.sha256 == file.sha256

    # 确认文件存在
    assert file.path
    with open(file.path, "rb") as f:
        assert f.read() == b"test"
