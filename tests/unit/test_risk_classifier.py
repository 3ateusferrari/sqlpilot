"""Unit tests for AST deterministic risk classifier."""

from app.security.risk_classifier import (
    FACT_TABLES,
    PII_COLUMNS,
    SENSITIVE_TABLES,
    DeterministicRiskResult,
    RiskAssessment,
    analyze_ast_risk,
)


class TestRiskClassifierLowRisk:
    """Tests for low risk SQL queries."""

    def test_simple_select_low_risk(self) -> None:
        sql = "SELECT * FROM artist LIMIT 10"
        result = analyze_ast_risk(sql)
        assert result.level == "low"
        assert result.nivel_risco == "low"
        assert result.reasons == []
        assert result.motivos_risco == []
        assert result.sensitive_tables_accessed == []
        assert result.pii_columns_accessed == []
        assert result.join_count == 0
        assert result.has_cross_join is False
        assert result.missing_where_on_fact_tables is False

    def test_join_with_aggregation_low_risk(self) -> None:
        sql = (
            "SELECT ar.name, count(al.album_id) "
            "FROM artist ar JOIN album al ON ar.artist_id = al.artist_id "
            "GROUP BY ar.name"
        )
        result = analyze_ast_risk(sql)
        assert result.level == "low"
        assert result.nivel_risco == "low"
        assert result.reasons == []
        assert result.motivos_risco == []
        assert result.join_count == 1
        assert result.has_cross_join is False
        assert result.sensitive_tables_accessed == []
        assert result.missing_where_on_fact_tables is False

    def test_aggregation_on_invoice_low_risk(self) -> None:
        sql = "SELECT billing_country, sum(total) FROM invoice GROUP BY billing_country"
        result = analyze_ast_risk(sql)
        assert result.level == "low"
        assert result.nivel_risco == "low"
        assert result.reasons == []
        assert result.motivos_risco == []
        assert result.sensitive_tables_accessed == ["invoice"]
        assert result.pii_columns_accessed == []
        assert result.join_count == 0
        assert result.has_cross_join is False

    def test_pure_scalar_aggregation_on_customer_low_risk(self) -> None:
        sql = "SELECT count(*) FROM customer"
        result = analyze_ast_risk(sql)
        assert result.level == "low"
        assert result.nivel_risco == "low"
        assert result.reasons == []
        assert result.motivos_risco == []
        assert result.sensitive_tables_accessed == ["customer"]
        assert result.pii_columns_accessed == []

    def test_fact_table_with_where_low_risk(self) -> None:
        sql = "SELECT * FROM track WHERE genre_id = 1"
        result = analyze_ast_risk(sql)
        assert result.level == "low"
        assert result.nivel_risco == "low"
        assert result.reasons == []
        assert result.motivos_risco == []
        assert result.missing_where_on_fact_tables is False
        assert result.join_count == 0

    def test_scalar_aggregation_on_fact_tables_low_risk(self) -> None:
        """Scalar aggregations on fact tables must be classified as low risk."""
        sql_count = "SELECT count(*) FROM track"
        res_count = analyze_ast_risk(sql_count)
        assert res_count.level == "low"
        assert res_count.nivel_risco == "low"
        assert res_count.missing_where_on_fact_tables is False
        assert res_count.reasons == []
        assert res_count.motivos_risco == []

        sql_sum = "SELECT sum(quantity) FROM invoice_line"
        res_sum = analyze_ast_risk(sql_sum)
        assert res_sum.level == "low"
        assert res_sum.nivel_risco == "low"
        assert res_sum.missing_where_on_fact_tables is False
        assert res_sum.reasons == []
        assert res_sum.motivos_risco == []


class TestRiskClassifierHighRisk:
    """Tests for high risk SQL queries."""

    def test_pii_columns_accessed(self) -> None:
        sql = "SELECT first_name, last_name, email, phone FROM customer"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.sensitive_tables_accessed == ["customer"]
        assert result.pii_columns_accessed == ["email", "phone"]
        assert "Acesso a colunas com dados pessoais/PII: email, phone" in result.reasons
        assert "Acesso a colunas com dados pessoais/PII: email, phone" in result.motivos_risco
        assert (
            "Exposição de registros individuais da tabela sensível 'customer' sem agregação"
            in result.reasons
        )
        assert (
            "Exposição de registros individuais da tabela sensível 'customer' sem agregação"
            in result.motivos_risco
        )

    def test_sensitive_table_customer_individual_records(self) -> None:
        sql = "SELECT * FROM customer"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.sensitive_tables_accessed == ["customer"]
        assert (
            "Exposição de registros individuais da tabela sensível 'customer' sem agregação"
            in result.reasons
        )
        assert (
            "Exposição de registros individuais da tabela sensível 'customer' sem agregação"
            in result.motivos_risco
        )

    def test_sensitive_table_employee_individual_records(self) -> None:
        sql = "SELECT * FROM employee"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.sensitive_tables_accessed == ["employee"]
        assert (
            "Exposição de registros individuais da tabela sensível 'employee' sem agregação"
            in result.reasons
        )

    def test_sensitive_table_invoice_individual_records(self) -> None:
        sql = "SELECT * FROM invoice"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.sensitive_tables_accessed == ["invoice"]
        assert (
            "Exposição de registros individuais da tabela sensível 'invoice' sem agregação"
            in result.reasons
        )

    def test_fact_table_without_where_and_group_by(self) -> None:
        sql = "SELECT * FROM track"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.missing_where_on_fact_tables is True
        assert (
            "Consulta na tabela de fatos volumosa 'track' sem filtro WHERE e sem agregação"
            in result.reasons
        )
        assert (
            "Consulta na tabela de fatos volumosa 'track' sem filtro WHERE e sem agregação"
            in result.motivos_risco
        )

    def test_cross_join_explicit(self) -> None:
        sql = "SELECT * FROM artist CROSS JOIN album"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.has_cross_join is True
        assert "Presença de CROSS JOIN ou junção cartesiana sem condição ON" in result.reasons

    def test_cartesian_join_without_on(self) -> None:
        sql = "SELECT * FROM artist JOIN album"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.has_cross_join is True
        assert "Presença de CROSS JOIN ou junção cartesiana sem condição ON" in result.reasons

    def test_high_join_complexity(self) -> None:
        sql = (
            "SELECT ar.name "
            "FROM artist ar "
            "JOIN album al ON ar.artist_id = al.artist_id "
            "JOIN track t ON al.album_id = t.album_id "
            "JOIN genre g ON t.genre_id = g.genre_id "
            "JOIN media_type m ON t.media_type_id = m.media_type_id "
            "WHERE t.unit_price > 0.99"
        )
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.join_count == 4
        assert result.has_cross_join is False
        assert result.missing_where_on_fact_tables is False
        assert "Consulta de alta complexidade contendo 4 JOINs" in result.reasons


class TestRiskClassifierEdgeCases:
    """Edge cases for parser errors, casing, multiple tables, and CTEs."""

    def test_empty_sql(self) -> None:
        result = analyze_ast_risk("")
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert len(result.reasons) > 0
        assert len(result.motivos_risco) > 0
        assert "vazia" in result.reasons[0].lower() or "parsing" in result.reasons[0].lower()

    def test_malformed_sql(self) -> None:
        result = analyze_ast_risk("SELECT FROM WHERE")
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert len(result.reasons) > 0
        assert len(result.motivos_risco) > 0
        assert "parsing" in result.reasons[0].lower() or "erro" in result.reasons[0].lower()

    def test_case_insensitivity(self) -> None:
        sql = "SELECT Email, Phone FROM Customer"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.sensitive_tables_accessed == ["customer"]
        assert result.pii_columns_accessed == ["email", "phone"]
        assert "Acesso a colunas com dados pessoais/PII: email, phone" in result.reasons

    def test_pii_column_in_where_clause(self) -> None:
        sql = "SELECT count(*) FROM customer WHERE email = 'test@example.com'"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.sensitive_tables_accessed == ["customer"]
        assert result.pii_columns_accessed == ["email"]
        assert "Acesso a colunas com dados pessoais/PII: email" in result.reasons

    def test_multiple_sensitive_tables(self) -> None:
        sql = (
            "SELECT c.first_name, i.total "
            "FROM customer c JOIN invoice i ON c.customer_id = i.customer_id "
            "WHERE c.customer_id = 1"
        )
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.sensitive_tables_accessed == ["customer", "invoice"]
        assert (
            "Exposição de registros individuais da tabela sensível 'customer' sem agregação"
            in result.reasons
        )
        assert (
            "Exposição de registros individuais da tabela sensível 'invoice' sem agregação"
            in result.reasons
        )

    def test_multiple_fact_tables_without_where(self) -> None:
        sql = "SELECT * FROM track t JOIN invoice_line il ON t.track_id = il.track_id"
        result = analyze_ast_risk(sql)
        assert result.level == "high"
        assert result.nivel_risco == "high"
        assert result.missing_where_on_fact_tables is True
        assert (
            "Consulta na tabela de fatos volumosa 'invoice_line' sem filtro WHERE e sem agregação"
            in result.reasons
        )
        assert (
            "Consulta na tabela de fatos volumosa 'track' sem filtro WHERE e sem agregação"
            in result.reasons
        )

    def test_cte_aggregation_low_risk(self) -> None:
        sql = (
            "WITH cust_summary AS ("
            "    SELECT billing_country, sum(total) AS total_sales "
            "    FROM invoice "
            "    GROUP BY billing_country"
            ") "
            "SELECT billing_country, total_sales FROM cust_summary"
        )
        result = analyze_ast_risk(sql)
        assert result.level == "low"
        assert result.nivel_risco == "low"
        assert result.reasons == []
        assert result.motivos_risco == []
        assert result.sensitive_tables_accessed == ["invoice"]

    def test_type_alias_and_constants(self) -> None:
        assert RiskAssessment is DeterministicRiskResult
        assert "employee" in SENSITIVE_TABLES
        assert "customer" in SENSITIVE_TABLES
        assert "invoice" in SENSITIVE_TABLES
        assert PII_COLUMNS == frozenset({"email", "phone", "address", "birth_date", "postal_code"})
        assert "fax" not in PII_COLUMNS
        assert "track" in FACT_TABLES
        assert "invoice_line" in FACT_TABLES
        assert "playlist_track" in FACT_TABLES

    def test_agent_state_field_synchronization(self) -> None:
        res_from_pt = DeterministicRiskResult(nivel_risco="high", motivos_risco=["motivo teste"])
        assert res_from_pt.level == "high"
        assert res_from_pt.reasons == ["motivo teste"]

        res_from_en = DeterministicRiskResult(level="high", reasons=["english reason"])
        assert res_from_en.nivel_risco == "high"
        assert res_from_en.motivos_risco == ["english reason"]
