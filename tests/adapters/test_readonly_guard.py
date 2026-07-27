# -*- coding: utf-8 -*-
"""ReadOnlyGuard 单元测试"""

import pytest
from src.adapters.readonly_guard import (
    ReadOnlyGuard,
    ReadOnlyViolationError,
    WriteAttempt,
)


class TestReadOnlyGuard:
    """只读守卫测试"""

    def setup_method(self):
        self.guard = ReadOnlyGuard()

    def test_allows_read_operations(self):
        """允许读取操作通过"""
        result = self.guard.guard(
            module="legacy_analysis",
            operation="SELECT * FROM stocks",
            executor=lambda: [{"code": "600519"}],
        )
        assert result == [{"code": "600519"}]

    def test_blocks_insert_from_legacy(self):
        """拦截旧模块 INSERT 操作"""
        with pytest.raises(ReadOnlyViolationError) as exc:
            self.guard.guard(
                module="legacy_analysis",
                operation="INSERT INTO stocks VALUES (...)",
                executor=lambda: True,
            )
        assert "legacy_analysis" in str(exc.value)
        assert "INSERT" in str(exc.value)

    def test_blocks_update_from_legacy(self):
        """拦截旧模块 UPDATE 操作"""
        with pytest.raises(ReadOnlyViolationError):
            self.guard.guard(
                module="legacy_analysis",
                operation="UPDATE stocks SET name='test'",
                executor=lambda: True,
            )

    def test_blocks_delete_from_legacy(self):
        """拦截旧模块 DELETE 操作"""
        with pytest.raises(ReadOnlyViolationError):
            self.guard.guard(
                module="legacy_analysis",
                operation="DELETE FROM stocks WHERE code='600519'",
                executor=lambda: True,
            )

    def test_blocks_drop_from_legacy(self):
        """拦截 DROP 操作"""
        with pytest.raises(ReadOnlyViolationError):
            self.guard.guard(
                module="legacy_analysis",
                operation="DROP TABLE stocks",
                executor=lambda: True,
            )

    def test_allows_write_from_whitelisted_module(self):
        """白名单模块允许写入"""
        self.guard.allow_write("new_module.api")
        result = self.guard.guard(
            module="new_module.api",
            operation="INSERT INTO stocks VALUES (...)",
            executor=lambda: "inserted",
        )
        assert result == "inserted"

    def test_default_whitelist_allows_internal(self):
        """默认白名单允许内部模块写入"""
        result = self.guard.guard(
            module="src.services",
            operation="INSERT INTO stocks VALUES (...)",
            executor=lambda: "done",
        )
        assert result == "done"

    def test_guard_disabled_allows_all(self):
        """禁用守卫后所有操作通过"""
        self.guard.enabled = False
        result = self.guard.guard(
            module="legacy_analysis",
            operation="DELETE FROM stocks",
            executor=lambda: "deleted",
        )
        assert result == "deleted"

    def test_revoke_write(self):
        """撤销写入权限后拦截"""
        self.guard.allow_write("temp_module")
        self.guard.revoke_write("temp_module")
        with pytest.raises(ReadOnlyViolationError):
            self.guard.guard(
                module="temp_module",
                operation="INSERT INTO stocks VALUES (...)",
                executor=lambda: True,
            )

    def test_audit_summary(self):
        """审计摘要记录拦截信息"""
        with pytest.raises(ReadOnlyViolationError):
            self.guard.guard(
                module="legacy_analysis",
                operation="INSERT INTO stocks",
                executor=lambda: True,
                table="stocks",
            )
        summary = self.guard.get_audit_summary()
        assert summary["total_blocked"] >= 1
        assert "legacy_analysis" in summary["by_module"]

    def test_get_blocked_attempts(self):
        """获取被拦截尝试列表"""
        with pytest.raises(ReadOnlyViolationError):
            self.guard.guard(
                module="legacy_analysis",
                operation="INSERT INTO stocks",
                executor=lambda: True,
            )
        attempts = self.guard.get_blocked_attempts(module="legacy_analysis")
        assert len(attempts) >= 1
        assert attempts[0].blocked is True

    def test_clear_attempts(self):
        """清空拦截记录"""
        with pytest.raises(ReadOnlyViolationError):
            self.guard.guard(
                module="legacy_analysis",
                operation="INSERT",
                executor=lambda: True,
            )
        self.guard.clear_attempts()
        assert len(self.guard.get_blocked_attempts()) == 0

    def test_list_allowed_writers(self):
        """列出白名单"""
        writers = self.guard.list_allowed_writers()
        assert "src.services" in writers
        assert "api.v1" in writers


class TestReadOnlyGuardDecorator:
    """装饰器模式测试"""

    def test_decorator_blocks_write(self):
        guard = ReadOnlyGuard()

        @guard.guard_method("legacy.analysis")
        def insert_data(self, data):
            return "inserted"

        # insert_data 名中包含 "insert"，被识别为 INSERT 操作
        with pytest.raises(ReadOnlyViolationError):
            insert_data(None, {"code": "600519"})

    def test_decorator_allows_read(self):
        guard = ReadOnlyGuard()

        @guard.guard_method("legacy.analysis")
        def get_data(query):
            return [{"code": "600519"}]

        # get_data 名中包含 "get"，被识别为 SELECT 操作
        result = get_data("SELECT * FROM stocks")
        assert result == [{"code": "600519"}]
