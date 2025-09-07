#!/usr/bin/env python3
import asyncio
import asyncpg, click
from src.core.config import settings
from src.geocode.geocode import geocode_address
from src.discovery.discovery import find_suppliers
from src.visualize.visualize import export_csv, generate_map


async def save_to_db(db_url, facility, address, lat, lon, suppliers):
    conn = await asyncpg.connect(db_url)
    fac_id = await conn.fetchval(
        "INSERT INTO facilities(name,address,location) VALUES($1,$2,ST_Point($3,$4)) ON CONFLICT DO NOTHING RETURNING id",
        facility, address, lon, lat
    )
    for sup in suppliers:
        sup_id = await conn.fetchval(
            "INSERT INTO suppliers(name,location,source,confidence) VALUES($1,ST_Point($2,$3),$4,$5) ON CONFLICT DO NOTHING RETURNING id",
            sup['name'], sup['lon'], sup['lat'], sup['source'], sup['confidence']
        )
        await conn.execute(
            "INSERT INTO facility_suppliers(facility_id,supplier_id,distance_miles) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
            fac_id, sup_id, sup['distance_miles']
        )
    await conn.close()

@click.command()
@click.option("--address", required=True)
@click.option("--name", default="Facility")
@click.option("--radius", default=60)
async def main(address, name, radius):
    lat, lon = geocode_address(address)
    suppliers = await find_suppliers(lat, lon, radius)
    print(f"Discovered {len(suppliers)} suppliers.")
    # Local DB write
    print("Writing to local database...")
    await save_to_db(settings.local_database_url, name, address, lat, lon, suppliers)
    # Remote DB write
    print("Writing to remote database...")
    await save_to_db(settings.database_url, name, address, lat, lon, suppliers)
    
    export_csv(suppliers)
    generate_map(suppliers, (lat, lon))
    print("CSV and map generated.")
    
    print("✔ Pipeline complete.")

if __name__ == "__main__":
    asyncio.run(main())
