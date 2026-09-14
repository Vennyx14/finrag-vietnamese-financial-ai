"""Unit tests for the Financial Metric Registry (src/financial/metrics.py)."""

import pytest

from src.financial.metrics import (
    MetricDefinition,
    MetricRegistry,
    default_metric_registry,
)


class TestMetricRegistry:
    """Tests for registry initialization, lookups, and aliases."""

    def test_default_registry_contains_all_mvp_metrics(self):
        """All 8 core MVP metrics must be registered."""
        expected_metrics = [
            "net_revenue",
            "net_income",
            "total_assets",
            "equity",
            "net_margin",
            "revenue_growth",
            "roa",
            "roe",
        ]
        registered = default_metric_registry.list_metric_names()
        for m in expected_metrics:
            assert m in registered, f"Metric '{m}' not in default registry"

    def test_metric_definition_attributes(self):
        """Check field types and invariants on registered metric definitions."""
        for m in default_metric_registry.list_metrics():
            assert isinstance(m.name, str) and len(m.name) > 0
            assert isinstance(m.vietnamese_name, str) and len(m.vietnamese_name) > 0
            assert m.metric_type in {"absolute", "derived"}
            assert m.operation in {"identity", "ratio", "yoy_growth"}
            assert isinstance(m.formula_display, str) and len(m.formula_display) > 0
            assert m.output_unit in {"VND", "ratio", "percentage"}

            if m.metric_type == "derived":
                assert len(m.required_inputs) >= 1

    def test_alias_resolution(self):
        """Aliases like 'ROA', 'roe', 'doanh_thu_thuan' resolve to canonical names."""
        registry = default_metric_registry
        assert registry.canonicalize_name("ROA") == "roa"
        assert registry.canonicalize_name("ROE") == "roe"
        assert registry.canonicalize_name("doanh_thu_thuan") == "net_revenue"
        assert registry.canonicalize_name("loi_nhuan_sau_thue") == "net_income"
        assert registry.canonicalize_name("tong_tai_san") == "total_assets"
        assert registry.canonicalize_name("von_chu_so_huu") == "equity"
        assert registry.canonicalize_name("profit") == "net_income"
        assert registry.canonicalize_name("assets") == "total_assets"

    def test_get_metric_by_alias(self):
        """get() transparently resolves aliases."""
        registry = default_metric_registry
        m_roa = registry.get("ROA")
        assert m_roa.name == "roa"
        assert m_roa.operation == "ratio"

        m_rev = registry.get("doanh_thu")
        assert m_rev.name == "net_revenue"

    def test_unsupported_metric_raises_keyerror(self):
        """Querying an unknown metric raises KeyError with helpful message."""
        registry = default_metric_registry
        with pytest.raises(KeyError) as exc_info:
            registry.get("unsupported_super_metric")
        assert "unsupported_super_metric" in str(exc_info.value)
        assert "Available canonical metrics" in str(exc_info.value)

    def test_custom_metric_registration(self):
        """Users can register new custom metrics and aliases without breaking existing ones."""
        custom_registry = MetricRegistry()
        new_metric = MetricDefinition(
            name="operating_margin",
            vietnamese_name="Biên lợi nhuận hoạt động",
            description="Lợi nhuận thuần từ HĐKD / Doanh thu thuần",
            metric_type="derived",
            operation="ratio",
            required_inputs=["operating_profit", "net_revenue"],
            formula_display="operating_profit / net_revenue",
            output_unit="ratio",
            search_keywords="Lợi nhuận thuần từ hoạt động kinh doanh",
        )
        custom_registry.register(new_metric)
        assert custom_registry.is_registered("operating_margin")
        assert custom_registry.get("operating_margin").name == "operating_margin"

        # Register alias
        custom_registry.register_alias("op_margin", "operating_margin")
        assert custom_registry.get("op_margin").name == "operating_margin"

    def test_metric_definition_properties_and_methodology(self):
        """Verify metric_id, display_name, dependencies properties and explicit methodologies."""
        roa = default_metric_registry.get("roa")
        assert roa.metric_id == "roa"
        assert roa.display_name == "Tỷ suất sinh lời trên tổng tài sản (ROA)"
        assert roa.dependencies == ["net_income", "total_assets"]
        assert roa.denominator_policy == "closing_balance"
        assert "Tổng tài sản" in roa.methodology

        roe = default_metric_registry.get("roe")
        assert roe.denominator_policy == "closing_balance"
        assert "Vốn chủ sở hữu" in roe.methodology

    def test_metric_definition_declares_aliases(self):
        """Metrics declaring aliases inside MetricDefinition are auto-registered."""
        custom_registry = MetricRegistry()
        metric_with_aliases = MetricDefinition(
            name="ebitda_margin",
            vietnamese_name="Biên EBITDA",
            description="EBITDA / Doanh thu thuần",
            metric_type="derived",
            operation="ratio",
            required_inputs=["ebitda", "net_revenue"],
            formula_display="ebitda / net_revenue",
            search_keywords="EBITDA",
            aliases=["ebitda_m", "bien_ebitda"],
        )
        custom_registry.register(metric_with_aliases)
        assert custom_registry.is_registered("ebitda_margin")
        assert custom_registry.canonicalize_name("ebitda_m") == "ebitda_margin"
        assert custom_registry.canonicalize_name("bien_ebitda") == "ebitda_margin"
