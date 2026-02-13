# init_db.py - 数据库初始化脚本

import asyncio
from sqlalchemy import text
from database import engine, init_database
from models import Base
from config import settings
from logger import logger


async def create_database():
    """创建数据库"""
    # 使用同步 psycopg2 创建数据库
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    try:
        # 连接到默认数据库
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # 检查数据库是否存在
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (settings.DB_NAME,)
        )
        exists = cursor.fetchone()

        if not exists:
            logger.info(f"创建数据库: {settings.DB_NAME}")
            cursor.execute(
                f"CREATE DATABASE {settings.DB_NAME} ENCODING 'UTF8'"
            )
            logger.info(f"数据库 {settings.DB_NAME} 创建成功")
        else:
            logger.info(f"数据库 {settings.DB_NAME} 已存在")

        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"创建数据库失败: {e}")
        raise


async def drop_database():
    """删除数据库（慎用）"""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    try:
        # 连接到默认数据库
        conn = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            dbname="postgres"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # 关闭所有连接
        cursor.execute(
            f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{settings.DB_NAME}'
            AND pid <> pg_backend_pid()
            """
        )

        # 删除数据库
        logger.info(f"删除数据库: {settings.DB_NAME}")
        cursor.execute(f"DROP DATABASE IF EXISTS {settings.DB_NAME}")
        logger.info(f"数据库 {settings.DB_NAME} 已删除")

        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"删除数据库失败: {e}")
        raise


async def init_tables():
    """初始化数据库表"""
    logger.info("开始初始化数据库表...")
    await init_database()
    logger.info("数据库表初始化完成")


async def check_database():
    """检查数据库状态"""
    logger.info("检查数据库状态...")

    async with engine.begin() as conn:
        # 获取所有表
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]

        logger.info(f"数据库 {settings.DB_NAME} 中的表:")
        for table in tables:
            # 获取记录数
            count_result = await conn.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            )
            count = count_result.fetchone()[0]
            logger.info(f"  - {table} ({count} 条记录)")

        return tables


async def seed_data():
    """种子数据 - 创建测试数据"""
    from models import User
    from auth import AuthManager

    async with engine.begin() as conn:
        # 创建测试用户
        logger.info("创建测试用户...")

        test_user = User(
            username="testuser",
            email="test@example.com",
            password_hash=AuthManager.hash_password("password123")
        )

        conn.add(test_user)
        await conn.commit()

        logger.info("测试用户创建完成")


async def reset_database():
    """重置数据库（删除并重新创建）"""
    logger.warning("开始重置数据库...")
    await drop_database()
    await create_database()
    await init_tables()
    logger.info("数据库重置完成")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库管理工具")
    parser.add_argument(
        "action",
        choices=["init", "create", "drop", "reset", "check", "seed"],
        help="操作类型"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行（不确认）"
    )

    args = parser.parse_args()

    try:
        if args.action == "create":
            await create_database()

        elif args.action == "init":
            await create_database()
            await init_tables()

        elif args.action == "drop":
            if not args.force:
                confirm = input("确定要删除数据库吗？此操作不可恢复！(yes/no): ")
                if confirm.lower() != "yes":
                    logger.info("操作已取消")
                    return
            await drop_database()

        elif args.action == "reset":
            if not args.force:
                confirm = input("确定要重置数据库吗？所有数据将被删除！(yes/no): ")
                if confirm.lower() != "yes":
                    logger.info("操作已取消")
                    return
            await reset_database()

        elif args.action == "check":
            await check_database()

        elif args.action == "seed":
            await seed_data()

        logger.info("操作完成")

    except Exception as e:
        logger.error(f"操作失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
