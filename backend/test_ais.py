from satellite.ais import (
    load_vessels,
    rank_vessels
)


vessels = load_vessels(
    "data/vessels.csv"
)

print(
    "VESSELS LOADED:",
    len(vessels)
)

result = rank_vessels(
    vessels,
    latitude=18.70,
    longitude=72.45,
    radius_km=100
)

print(
    "\nNEARBY VESSELS:",
    len(result)
)

for vessel in result:
    print("\nVessel:")
    for key, value in vessel.items():
        print(
            f"  {key}: {value}"
        )