from sqlalchemy.exc import SQLAlchemyError


async def test_health_check_ok(async_client, fake_db, fake_redis):
    response = await async_client.get("/internal/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    fake_db.execute.assert_awaited_once()


async def test_health_check_reports_database_failure(async_client, fake_db):
    fake_db.execute.side_effect = SQLAlchemyError("db down")

    response = await async_client.get("/internal/health")

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert response.json()["details"]["database"] == "error"
    assert response.json()["details"]["redis"] == "ok"


async def test_health_check_reports_redis_failure(async_client, fake_redis):
    async def fail_ping():
        raise RuntimeError("redis down")

    fake_redis.ping = fail_ping

    response = await async_client.get("/internal/health")

    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert response.json()["details"]["database"] == "ok"
    assert response.json()["details"]["redis"] == "error"
