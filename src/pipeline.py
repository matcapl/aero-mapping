#!/usr/bin/env python3
import asyncio
import time
import asyncpg
import click

from src.core.config import settings
from src.geocode.providers import default_manager, GeocodeError
from src.discovery.discovery_filter_and_deduplication_async_caching_log_sortAndDedupFirst import (
    find_suppliers,
)
from src.visualize.visualize import export_csv
from src.visualize.maplibre_visualize import generate_map


# -----------------------------
# Async DB write helper
# -----------------------------
async def save_to_db(db_url, facility_name, facility_address, lat, lon, suppliers):
    conn = await asyncpg.connect(db_url)
    fac_id = await conn.fetchval(
        """
        INSERT INTO facilities(name, address, location)
        VALUES($1, $2, ST_Point($3, $4))
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        facility_name,
        facility_address,
        lon,
        lat,
    )
    for sup in suppliers:
        sup_id = await conn.fetchval(
            """
            INSERT INTO suppliers(name, location, source, confidence)
            VALUES($1, ST_Point($2, $3), $4, $5)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            sup["name"],
            sup["lon"],
            sup["lat"],
            sup["source"],
            sup["confidence"],
        )
        await conn.execute(
            """
            INSERT INTO facility_suppliers(facility_id, supplier_id, distance_miles)
            VALUES($1, $2, $3)
            ON CONFLICT DO NOTHING
            """,
            fac_id,
            sup_id,
            sup["distance_miles"],
        )
    await conn.close()


# -----------------------------
# Async pipeline runner
# -----------------------------
async def run_pipeline(
    facility_name,
    address,
    radius,
    deduplicate=True,
    reverse_geocode=True,
    cache=True,
    verbose=False,
):
    start_time = time.time()

    manager = default_manager()

    try:
        # Step 1: geocode facility address using manager
        lat, lon, provider = await manager.geocode(address, verbose=verbose)
    except GeocodeError as e:
        if verbose:
            print("Geocoding failed:", e)
        raise

    if verbose:
        print(f"Facility geocoded by {provider}: {lat},{lon}")
        print(f"Geocoded '{address}' -> lat={lat}, lon={lon}")

    # Step 2: fetch suppliers
    suppliers = await find_suppliers(
        lat,
        lon,
        radius,
        deduplicate=deduplicate,
        reverse_geocode=reverse_geocode,
        cache=cache
    )

    elapsed = time.time() - start_time
    if verbose:
        print(
            f"Pipeline settings: deduplicate={deduplicate}, "
            f"reverse_geocode={reverse_geocode}, cache={cache}"
        )
        print(f"Time elapsed: {elapsed:.2f} seconds")
        print(f"Discovered {len(suppliers)} suppliers")
        print("Sample:", suppliers[:2])

    # Step 3: write to local and remote DB
    if verbose:
        print("Writing to local database...")
    await save_to_db(settings.database_local_url, facility_name, address, lat, lon, suppliers)

    if verbose:
        print("Writing to remote database...")
    await save_to_db(settings.database_neon_url, facility_name, address, lat, lon, suppliers)

    # Step 4: export CSV and generate map
    export_csv(suppliers)
    generate_map(suppliers, (lat, lon))
    if verbose:
        print("CSV and map generated.")

    print("✔ Pipeline complete.")


# -----------------------------
# CLI entry point
# -----------------------------
@click.command()
@click.option("--address", required=True, help="Facility address to geocode")
@click.option("--name", default="Facility", help="Facility name to use in DB and exports")
@click.option("--radius", default=20, help="Search radius in miles")
@click.option(
    "--deduplicate/--no-deduplicate",
    default=True,
    help="Remove duplicate suppliers first",
)
@click.option(
    "--reverse-geocode/--no-reverse-geocode",
    default=True,
    help="Enrich supplier coordinates with human-readable addresses"
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="Enable caching for supplier reverse-geocode"
)
@click.option("--verbose", is_flag=True, default=False, help="Enable progress logging")
def main(name, address, radius, deduplicate, reverse_geocode, cache, verbose):
    """Pipeline: discover suppliers near a facility, write to DB, export CSV/map."""
    asyncio.run(
        run_pipeline(name, address, radius, deduplicate, reverse_geocode, cache, verbose)
    )


if __name__ == "__main__":
    main()
