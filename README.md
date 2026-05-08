# VIN Key Part Resolver Prototype

This is a proof-of-work CLI for decoding a VIN with NHTSA vPIC data and resolving confirmed OEM key or remote part numbers.

The first version is deliberately conservative:

- It validates VIN format.
- It decodes YMM, trim, series, body, engine, drive type, and NHTSA decode status.
- It returns exact VIN-level confirmations from `data/confirmed_key_parts.json`.
- It has a `rules` section ready for broader YMM/trim rules, but no broad rules are enabled until fitment is proven.
- It records `replaces` arrays and `superseded_by` arrays when product specifications provide them.

## Usage

```powershell
python .\vin_key_tool.py 19UDE4H66TA000653 --offline
python .\vin_key_tool.py 19UDE4H66TA000653 1HGCY1F39RA023637 --offline --json
python .\vin_key_tool.py 19UDE4H66TA000653 --csv .\out\results.csv
```

Use `--offline` to use the included NHTSA fixtures. Omit it to call NHTSA live; add `--update-cache` to save new live decodes.

## Regression Test

```powershell
python .\tests\run_regression.py
```

The regression test currently covers the confirmed examples supplied for Acura, Honda, BMW, Chrysler, Ford, GMC, Hyundai, Infiniti, Kia, Mazda, and Subaru. The Mitsubishi example was left incomplete in the request, so it is not included yet.

## Web App

Run the browser interface locally:

```powershell
.\run-vin-key-web.ps1
```

Then open:

```text
http://127.0.0.1:8989
```

To make it reachable from another machine on the same network or from a hosted server, bind to all interfaces:

```powershell
.\run-vin-key-web.ps1 -HostName 0.0.0.0 -Port 8989
```

The web app keeps the last 50 searches in `data/search_history.json`.

## Adding A New Confirmed Part

1. Decode the VIN through NHTSA.
2. Search the make-specific OEM parts site by VIN.
3. Search key terms such as `key`, `fob`, `remote`, `smart key`, `transmitter`, or `keyless entry`.
4. Confirm the part product page says it fits the VIN/YMM/trim.
5. Copy all `Replaces` / supersession part numbers from the product specification into the `replaces` list.
6. Add either an exact VIN confirmation or a narrow rule in `data/confirmed_key_parts.json`.

## Current Source Sites

- NHTSA vPIC: https://vpic.nhtsa.dot.gov/decoder/
- Acura: https://www.acurapartsnow.com and https://www.acurapartswarehouse.com
- Honda: https://www.hondapartsnow.com
- BMW: https://www.bmwpartsdeal.com, https://www.getbmwparts.com, https://bmwfans.info
- Chrysler/Mopar: https://www.moparamerica.com
- Ford: https://www.fordpartsgiant.com
- GMC/GM: https://www.gmpartsgiant.com/gmc-parts.html
- Hyundai: https://www.hyundaipartsdeal.com
- Infiniti: https://parts.infinitiusa.com
- Kia: https://parts.kia.com
- Mazda: https://www.onlinemazdaparts.com
- Subaru: https://www.subarupartsdeal.com
