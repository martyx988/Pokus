from __future__ import annotations

import unittest

from pokus_backend.domain.admin_audit import AdminCommand, AdminCommandType, AuditRecord, MUTATING_ADMIN_COMMAND_TYPES


class AdminCommandModelTests(unittest.TestCase):
    def test_command_types_cover_required_admin_intents(self) -> None:
        self.assertEqual(
            {item.value for item in AdminCommandType},
            {
                "configuration_change",
                "validation_trigger",
                "historical_reprocess",
                "retention_action",
                "job_retry",
                "job_cancel",
                "job_mark_failed",
            },
        )

    def test_mutating_commands_require_reason(self) -> None:
        for command_type in MUTATING_ADMIN_COMMAND_TYPES:
            with self.assertRaises(ValueError):
                AdminCommand(
                    id=None,
                    command_type=command_type,
                    actor_id="admin-1",
                    actor_type="admin",
                )

    def test_non_mutating_command_can_omit_reason(self) -> None:
        cmd = AdminCommand(
            id=None,
            command_type=AdminCommandType.VALIDATION_TRIGGER,
            actor_id="admin-1",
            actor_type="admin",
        )
        self.assertIsNone(cmd.reason)


class AuditRecordModelTests(unittest.TestCase):
    def test_safe_actor_request_metadata_is_stored(self) -> None:
        metadata = {"ip": "10.0.0.5", "user_agent": "ops-console"}
        audit = AuditRecord(
            id=None,
            action="admin_command_created",
            actor_id="operator-4",
            actor_type="operator",
            request_id="req-123",
            metadata=metadata,
        )
        self.assertEqual(audit.metadata, metadata)
        self.assertEqual(audit.actor_id, "operator-4")
        self.assertEqual(audit.request_id, "req-123")

    def test_sensitive_metadata_keys_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AuditRecord(
                id=None,
                action="admin_command_created",
                actor_id="operator-4",
                actor_type="operator",
                metadata={"token": "do-not-store"},
            )

    def test_audit_record_can_link_to_admin_command_and_job(self) -> None:
        audit = AuditRecord(
            id=None,
            action="job_cancel_requested",
            actor_id="operator-4",
            actor_type="operator",
            admin_command_id=11,
            load_job_id=22,
            target_type="load_job",
            target_id="22",
        )
        self.assertEqual(audit.admin_command_id, 11)
        self.assertEqual(audit.load_job_id, 22)
        self.assertEqual(audit.target_type, "load_job")
        self.assertEqual(audit.target_id, "22")


if __name__ == "__main__":
    unittest.main()
