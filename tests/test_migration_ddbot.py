from datetime import UTC, datetime

from app.services.migration.ddbot import DDBotAdapter
from app.services.migration.registry import ADAPTERS


def _ts(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=UTC).timestamp())


SQL_DUMP = r"""
CREATE TABLE `user` (
  `id` bigint NOT NULL,
  `balance` decimal(18,8) NOT NULL,
  `created_at` timestamp NOT NULL
) ENGINE=InnoDB;
INSERT INTO `user` VALUES
(1001,1250.00000000,'2026-04-26 19:17:13'),
(1002,0.00000000,'2026-04-27 00:00:00');

CREATE TABLE `panel` (
  `id` int NOT NULL,
  `type` varchar(30) NOT NULL,
  `server_name` varchar(255) DEFAULT NULL,
  `server_url` varchar(1000) DEFAULT NULL,
  `server_username` varchar(200) DEFAULT NULL,
  `server_password` varchar(400) DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `panel` VALUES
(1,'pasarguard','Main','https://panel.example.com/','admin','secret'),
(2,'marzban','Ignored','https://ignored.example.com','admin','secret');

CREATE TABLE `subscription` (
  `id` int NOT NULL,
  `user_id` bigint NOT NULL,
  `username` varchar(50) DEFAULT NULL,
  `server_id` int NOT NULL,
  `insert_date` timestamp NULL,
  `uuid` varchar(255) DEFAULT NULL,
  `delete_requested` timestamp NULL
) ENGINE=InnoDB;
INSERT INTO `subscription` VALUES
(11,1001,'alpha',1,'2026-04-26 21:41:13',NULL,NULL),
(12,1002,'beta',1,'2026-04-27 01:00:00','beta-uuid','2026-05-01 00:00:00'),
(13,1001,'wrong-panel',2,'2026-04-27 02:00:00',NULL,NULL),
(14,1001,'',1,'2026-04-27 03:00:00',NULL,NULL);
"""


def test_ddbot_adapter_is_registered() -> None:
    assert isinstance(ADAPTERS["ddbot"], DDBotAdapter)


def test_ddbot_adapter_parses_users_panels_and_services() -> None:
    parsed = DDBotAdapter().parse(SQL_DUMP)

    assert parsed.source_slug == "ddbot"
    assert [(user.telegram_id, user.amount, user.time_s) for user in parsed.users] == [
        (1001, 1250, _ts("2026-04-26 19:17:13")),
        (1002, 0, _ts("2026-04-27 00:00:00")),
    ]

    assert len(parsed.panels) == 1
    panel = parsed.panels[0]
    assert panel.source_id == "1"
    assert panel.name == "Main"
    assert panel.base_url == "https://panel.example.com"
    assert panel.username == "admin"
    assert panel.password == "secret"
    assert parsed.skipped_panels == 1

    assert len(parsed.services) == 2
    active, pending_delete = parsed.services
    assert active.source_panel_id == "1"
    assert active.owner_id == 1001
    assert active.username_candidates == ["alpha"]
    assert active.created_at == _ts("2026-04-26 21:41:13")
    assert active.enabled is True

    assert pending_delete.username_candidates == ["beta", "beta-uuid"]
    assert pending_delete.enabled is False
    assert parsed.skipped_services == 2


def test_ddbot_adapter_handles_bad_optional_values() -> None:
    sql = """
    INSERT INTO `user` (`id`,`balance`,`created_at`) VALUES
    (2001,'not-a-number','not-a-date');
    """

    parsed = DDBotAdapter().parse(sql)

    assert len(parsed.users) == 1
    assert parsed.users[0].telegram_id == 2001
    assert parsed.users[0].amount == 0
    assert parsed.users[0].time_s is None
