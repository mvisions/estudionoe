#!/usr/bin/env python3
"""Import Salamanca's publicly linked CGCOF calendar."""
from cgcof_catalog import enrich_contact, main, parse, run

if __name__ == "__main__":
    raise SystemExit(main("37", "Salamanca"))
