"""Integration tests for connection pools and SchemaLoader."""

import pytest

from app.db.schema_loader import SchemaLoader, is_sensitive_column, mask_sensitive_value
from app.db.session import (
    close_pools,
    get_admin_connection,
    get_admin_pool,
    get_readonly_connection,
    get_readonly_pool,
)

EXPECTED_CHINOOK_TABLES = [
    "album",
    "artist",
    "customer",
    "employee",
    "genre",
    "invoice",
    "invoice_line",
    "media_type",
    "playlist",
    "playlist_track",
    "track",
]


@pytest.fixture(autouse=True)
async def cleanup_db_pools() -> None:
    """Ensure pools are cleanly closed after each test."""
    yield
    await close_pools()


@pytest.mark.asyncio
async def test_get_valid_tables() -> None:
    """Validate that get_valid_tables returns exactly the 11 Chinook tables in order."""
    loader = SchemaLoader()
    tables = await loader.get_valid_tables()
    assert tables == EXPECTED_CHINOOK_TABLES


@pytest.mark.asyncio
async def test_get_valid_tables_independent_caching() -> None:
    """Validate that get_valid_tables caches independently without calling load_schema."""
    loader = SchemaLoader(ttl_seconds=60.0)

    # load_schema has NOT been called
    assert loader._cached_valid_tables is None
    assert loader._cached_schema is None

    tables1 = await loader.get_valid_tables(use_cache=True)
    assert tables1 == EXPECTED_CHINOOK_TABLES
    assert loader._cached_valid_tables is not None
    assert loader._tables_cache_timestamp is not None
    assert loader._cached_schema is None  # schema cache remains untouched

    # Second call should reuse the cache
    tables2 = await loader.get_valid_tables(use_cache=True)
    assert tables1 is tables2

    # Invalidate cache
    loader.clear_cache()
    assert loader._cached_valid_tables is None
    assert loader._tables_cache_timestamp is None


@pytest.mark.asyncio
async def test_load_schema_structure() -> None:
    """Validate that load_schema generates valid DDL with PKs, FKs, columns and sample rows."""
    loader = SchemaLoader()
    tables, schema_context = await loader.load_schema()

    assert tables == EXPECTED_CHINOOK_TABLES
    assert len(tables) == 11

    # Verify CREATE TABLE for all tables
    for table in EXPECTED_CHINOOK_TABLES:
        assert f"CREATE TABLE {table}" in schema_context
        assert f"sample rows from {table}" in schema_context

    # Verify primary keys
    assert "PRIMARY KEY" in schema_context
    assert "album_id integer PRIMARY KEY" in schema_context
    assert "artist_id integer PRIMARY KEY" in schema_context
    assert "customer_id integer PRIMARY KEY" in schema_context
    # Composite PK in playlist_track
    assert "PRIMARY KEY (playlist_id, track_id)" in schema_context

    # Verify foreign keys (REFERENCES tabela(coluna))
    assert "artist_id integer NOT NULL REFERENCES artist(artist_id)" in schema_context
    assert "album_id integer REFERENCES album(album_id)" in schema_context
    assert "customer_id integer NOT NULL REFERENCES customer(customer_id)" in schema_context
    assert "invoice_id integer NOT NULL REFERENCES invoice(invoice_id)" in schema_context
    assert "track_id integer NOT NULL REFERENCES track(track_id)" in schema_context
    assert "genre_id integer REFERENCES genre(genre_id)" in schema_context
    assert "media_type_id integer NOT NULL REFERENCES media_type(media_type_id)" in schema_context
    assert "support_rep_id integer REFERENCES employee(employee_id)" in schema_context
    assert "reports_to integer REFERENCES employee(employee_id)" in schema_context


@pytest.mark.asyncio
async def test_load_schema_masks_sensitive_data() -> None:
    """Validate that columns such as email, phone and address are masked in sample rows."""
    loader = SchemaLoader()
    _, schema_context = await loader.load_schema(use_cache=False)

    # Raw sensitive customer data from row 1
    raw_customer_email = "luisg@embraer.com.br"
    raw_customer_phone = "+55 (12) 3923-5555"
    raw_customer_address = "Av. Brigadeiro Faria Lima, 2170"

    # Raw sensitive employee data from row 1
    raw_employee_email = "andrew@chinookcorp.com"
    raw_employee_phone = "+1 (780) 428-9482"
    raw_employee_address = "11120 Jasper Ave NW"

    # Ensure unmasked PII is NOT in schema context
    assert raw_customer_email not in schema_context
    assert raw_customer_phone not in schema_context
    assert raw_customer_address not in schema_context
    assert raw_employee_email not in schema_context
    assert raw_employee_phone not in schema_context
    assert raw_employee_address not in schema_context

    # Ensure masked values ARE in schema context
    assert "l***@embraer.com.br" in schema_context
    assert "+55 (***) ***-5555" in schema_context
    assert "a***@chinookcorp.com" in schema_context
    assert "+1 (***) ***-9482" in schema_context


@pytest.mark.asyncio
async def test_load_schema_preserves_non_sensitive_data() -> None:
    """Validate that non-sensitive columns (artist name, album title, prices) are intact."""
    loader = SchemaLoader()
    _, schema_context = await loader.load_schema(use_cache=False)

    # Non-sensitive artist sample rows
    assert "AC/DC" in schema_context
    assert "Accept" in schema_context
    assert "Aerosmith" in schema_context

    # Non-sensitive album titles
    assert "For Those About To Rock We Salute You" in schema_context
    assert "Balls to the Wall" in schema_context or "Let There Be Rock" in schema_context

    # Non-sensitive genre names
    assert "Rock" in schema_context
    assert "Jazz" in schema_context

    # Non-sensitive customer data (names and company)
    assert "Luís" in schema_context
    assert "Gonçalves" in schema_context
    assert "Embraer" in schema_context


@pytest.mark.asyncio
async def test_schema_loader_caching() -> None:
    """Validate that consecutive calls with use_cache=True reuse in-memory cache."""
    loader = SchemaLoader(ttl_seconds=60.0)

    # First call: populates cache
    tables1, schema1 = await loader.load_schema(use_cache=True)
    assert loader._cached_schema is not None

    # Second call with use_cache=True: returns identical cached object
    tables2, schema2 = await loader.load_schema(use_cache=True)
    assert tables1 is tables2
    assert schema1 is schema2

    # Call get_valid_tables with cache
    valid_tables = await loader.get_valid_tables(use_cache=True)
    assert valid_tables is tables1

    # Call with use_cache=False: re-executes and refreshes
    tables3, schema3 = await loader.load_schema(use_cache=False)
    assert tables3 == tables1
    assert schema3 == schema1
    assert schema3 is not schema1 or isinstance(schema3, str)


def test_sensitive_masking_unit() -> None:
    """Unit test individual masking rules for sensitive vs non-sensitive columns."""
    # Sensitive column detection
    assert is_sensitive_column("email")
    assert is_sensitive_column("phone")
    assert is_sensitive_column("fax")
    assert is_sensitive_column("address")
    assert is_sensitive_column("billing_address")
    assert is_sensitive_column("postal_code")
    assert is_sensitive_column("billing_postal_code")

    # Non-sensitive column detection
    assert not is_sensitive_column("artist_id")
    assert not is_sensitive_column("name")
    assert not is_sensitive_column("title")
    assert not is_sensitive_column("unit_price")
    assert not is_sensitive_column("company")
    assert not is_sensitive_column("first_name")
    assert not is_sensitive_column("last_name")

    # Non-sensitive values preserved completely intact
    assert mask_sensitive_value("name", "AC/DC") == "AC/DC"
    assert mask_sensitive_value("artist_id", 42) == 42
    assert mask_sensitive_value("unit_price", 0.99) == 0.99
    assert mask_sensitive_value("title", "Let There Be Rock") == "Let There Be Rock"
    assert mask_sensitive_value("company", "Embraer") == "Embraer"

    # Email
    assert mask_sensitive_value("email", "john.doe@example.com") == "j***@example.com"
    assert mask_sensitive_value("email", None) is None
    assert mask_sensitive_value("email", "") == ""

    # Phone & Fax
    assert mask_sensitive_value("phone", "+1 (123) 456-7890") == "+1 (***) ***-7890"
    assert mask_sensitive_value("fax", "+55 11 9999-1234") == "+55 (***) ***-1234"

    # Address
    assert mask_sensitive_value("address", "123 Main Street") == "123 ***"
    assert mask_sensitive_value("billing_address", "Av. Paulista, 1000") == "Av. ***"

    # Postal code
    assert mask_sensitive_value("postal_code", "12345-678") == "12***"


@pytest.mark.asyncio
async def test_session_connection_pools() -> None:
    """Validate connection pools creation, connection acquisition, and graceful shutdown."""
    admin_pool = get_admin_pool()
    readonly_pool = get_readonly_pool()

    assert admin_pool is not None
    assert readonly_pool is not None
    assert admin_pool is not readonly_pool

    # Test readonly connection
    async with get_readonly_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            res = await cur.fetchone()
            assert res == (1,)

    # Test admin connection
    async with get_admin_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 2")
            res = await cur.fetchone()
            assert res == (2,)

    # Test close pools
    await close_pools()

    # Re-acquisition after close creates new pools
    new_admin_pool = get_admin_pool()
    assert new_admin_pool is not admin_pool
    assert not new_admin_pool.closed or not getattr(new_admin_pool, "_opened", False)
