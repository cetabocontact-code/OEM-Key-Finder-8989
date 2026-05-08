#!/usr/bin/env python3
"""Single-file OEM Key Finder 8989 web app.

Upload only this file to GitHub/Render if you do not want to manage folders.
Run locally:
    python OEM_Key_Finder_8989_SINGLE_FILE.py --host 127.0.0.1 --port 8989

Render start command:
    python OEM_Key_Finder_8989_SINGLE_FILE.py --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent
STORAGE_DIR = APP_DIR / ".oem_key_finder_storage"
HISTORY_PATH = STORAGE_DIR / "search_history.json"
SUBSCRIBERS_PATH = STORAGE_DIR / "private" / "subscribers.jsonl"
MAX_HISTORY = 50
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NHTSA_ENDPOINT = "https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvaluesextended/{vin}?format=json"
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
MODEL_YEAR_CODES = {
    "A": "2010", "B": "2011", "C": "2012", "D": "2013", "E": "2014", "F": "2015",
    "G": "2016", "H": "2017", "J": "2018", "K": "2019", "L": "2020", "M": "2021",
    "N": "2022", "P": "2023", "R": "2024", "S": "2025", "T": "2026",
}

EMBEDDED_CATALOG = {'vin_confirmations': {'19UDE4H66TA000653': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'AcuraPartsNow VIN/YMM/trim lookup for 2026 Acura Integra A-Spec Tech', 'notes': 'User confirmed with NHTSA YMM/trim and AcuraPartsNow product page.', 'parts': [{'description': 'Remote Engine Starter System', 'part_number': '08E92-3S5-200', 'replaces': ['PREO-ITG-001']}], 'source_url': 'https://www.acurapartsnow.com/oem-parts/acura-remote-engine-starter-system-8e923s5200'}, '1HGCY1F39RA023637': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'HondaPartsNow VIN lookup then key search for 2024 Honda Accord EX', 'notes': 'User confirmed on HondaPartsNow.', 'parts': [{'description': 'Keyless Entry Transmitter', 'part_number': '72147-T20-A11', 'replaces': []}], 'source_url': 'https://www.hondapartsnow.com'}, 'WBA73AK08N7K27666': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'BMWPartsDeal VIN lookup, Electronics > Keyless Entry Components', 'notes': 'User confirmed on BMWPartsDeal.', 'parts': [{'description': 'Remote control / keyless entry component', 'part_number': '51212469144', 'replaces': []}], 'source_url': 'https://www.bmwpartsdeal.com'}, '2C4RC1L71PR618182': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'MoparAmerica VIN lookup then fob search for 2023 Chrysler Pacifica Touring L', 'notes': 'User confirmed on MoparAmerica.', 'parts': [{'description': 'Fob', 'part_number': '68217832AD', 'replaces': ['68217832AB', '68217832AC']}], 'source_url': 'https://www.moparamerica.com'}, '2C4RC1CG2PR566416': {'confidence': 'confirmed_by_oem_yymm_fitment', 'fitment_basis': 'NHTSA clean decode as 2023 Chrysler Voyager LX; Mopar/MoparPartsGiant keyless-entry components list the integrated key fob transmitter for 2023 Chrysler Voyager.', 'notes': 'Primary remote is the integrated key fob transmitter. Emergency/key blank is listed separately.', 'parts': [{'description': 'Integrated Key Fob Transmitter', 'part_number': '68217832AD', 'replaces': ['68217832AB', '68217832AC']}, {'description': 'Key Blank / Transmitter Emergency Key', 'part_number': '68289894AC', 'replaces': ['68289894AA', '68289894AB']}], 'source_url': 'https://www.moparpartsgiant.com/parts-list/2023-chrysler-voyager/keyless-entry-components.html'}, '1FTFW3LD6SFB00855': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'FordPartsGiant VIN lookup for 2025 Ford F-150 XLT', 'notes': 'User confirmed on FordPartsGiant.', 'parts': [{'description': 'Keyless entry transmitter', 'part_number': 'GB5Z-15K601-A', 'replaces': []}], 'source_url': 'https://www.fordpartsgiant.com'}, '1GKKNULS6MZ165460': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'GMPartsGiant GMC VIN lookup for 2021 GMC Acadia SLT', 'notes': 'User confirmed on GMPartsGiant.', 'parts': [{'description': 'Keyless entry transmitter', 'part_number': '13522895', 'replaces': [], 'superseded_by': ['13547797']}], 'source_url': 'https://www.gmpartsgiant.com/gmc-parts.html'}, '3KPC24A64NE177716': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'HyundaiPartsDeal VIN/YMM/trim lookup for 2022 Hyundai Accent', 'notes': 'User confirmed on HyundaiPartsDeal using NHTSA trim details.', 'parts': [{'description': 'Keyless entry transmitter', 'part_number': '95430-J0800', 'replaces': []}], 'source_url': 'https://www.hyundaipartsdeal.com'}, 'KMHM34AA4RA070319': {'confidence': 'confirmed_by_oem_yymm_trim_fitment', 'fitment_basis': 'NHTSA clean decode as 2024 Hyundai Ioniq 6 SEL; Hyundai OEM parts sources list 95440-KL000 for Ioniq 6 smart key without Smart Park/auto park, while 95440-KL200 is the auto-park transmitter.', 'notes': 'SEL trim is treated as without Smart Park/auto park. If the vehicle is confirmed to have Remote Smart Parking Assist, verify against 95440-KL200 before ordering.', 'parts': [{'description': 'Fob Smart Key / Keyless Entry Transmitter, without auto park', 'part_number': '95440-KL000', 'replaces': []}], 'source_url': 'https://parts.tamiamihyundai.com/oem-parts/hyundai-transmitter-95440kl000'}, '5N1DL1HUXPC376439': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'Infiniti parts VIN lookup and smart key search for 2023 Infiniti QX60 Autograph', 'notes': 'User confirmed on Infiniti USA parts.', 'parts': [{'description': 'Smart key', 'part_number': 'T99K1-6SA00', 'replaces': []}], 'source_url': 'https://parts.infinitiusa.com/'}, '3KPFT4DE2SE036913': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'Kia parts product fitment for 2025 Kia K4 LX/LXS', 'notes': 'User confirmed on Kia parts.', 'parts': [{'description': 'TX Assy-Keyless Entry', 'part_number': '95430GG000', 'replaces': []}], 'source_url': 'https://parts.kia.com/p/Kia_2025_K4-20L-AT-LX/TX-ASSY-KEYLESS-ENTR-TX-ASSY-KEYLESS-ENTRY/147336387/95430GG000.html'}, '3MVDMBBM7RM694230': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'OnlineMazdaParts product fitment for 2024 Mazda CX-30 2.5 S AWD', 'notes': 'User confirmed on OnlineMazdaParts.', 'parts': [{'description': 'Keyless Entry Transmitter', 'part_number': 'BCYN675DYB', 'replaces': ['BCYN-67-5DY', 'BCYN-67-5DYA']}], 'source_url': 'https://www.onlinemazdaparts.com/p/Mazda_2024_CX-30-25L-SKYACTIV-AT-AWD-25-S-Sport-Utility/Keyless-Entry-Transmitter/98522065/BCYN675DYB.html'}, 'JF2SKARC9PH490439': {'confidence': 'confirmed_by_user_vin_fitment', 'fitment_basis': 'SubaruPartsDeal VIN/YMM/trim lookup for 2023 Subaru Forester Touring w/EyeSight', 'notes': 'User confirmed on SubaruPartsDeal.', 'parts': [{'description': 'Keyless entry transmitter', 'part_number': '88835FL031', 'replaces': [], 'superseded_by': ['88835FL032']}], 'source_url': 'https://www.subarupartsdeal.com/page_product/category?vin=JF2SKARC9PH490439&make=Subaru&model=Forester&year=2023&submodel=&extra1=4%20Cyl%202.5L&extra2=Touring%20w%2fEyesight&filter=()'}}, 'rules': [{'confidence': 'rule_from_oem_fitment_and_same_cargurus_trim', 'fitment_basis': 'Scoped to 2024 Mazda CX-30 Select Sport decodes; Mazda source lists BCYN-67-5DYB / BCYN675DYB for CX-30 keyless-entry transmitter and the supplied VIN confirmed this fitment.', 'match': {'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Trim_contains': 'Select Sport'}, 'notes': 'Use only for 2024 Mazda CX-30 2.5 S Select Sport AWD listings unless VIN-level Mazda fitment is checked.', 'parts': [{'description': 'Keyless Entry Transmitter', 'part_number': 'BCYN675DYB', 'replaces': ['BCYN-67-5DY', 'BCYN-67-5DYA']}], 'source_url': 'https://www.mazda-parts.com/oem-parts/mazda-transmitter-bcyn675dyb'}]}
EMBEDDED_CACHE = {'19UDE4H66TA000653': {'BodyClass': 'Hatchback/Liftback/Notchback', 'DisplacementL': '1.5', 'DriveType': '4x2', 'EngineModel': 'L15CA', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'ACURA', 'Model': 'Integra', 'ModelYear': '2026', 'Note': 'US: A-Spec Tech, Canada: Elite A-Spec', 'Series': '', 'Series2': '', 'Trim': 'A-Spec Tech/ Elite A-Spec', 'VIN': '19UDE4H66TA000653'}, '1C3CCBBG8EN191708': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '3.6', 'DriveType': 'FWD/Front-Wheel Drive', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'CHRYSLER', 'Model': '200', 'ModelYear': '2014', 'Note': '', 'Series': '', 'Series2': '', 'Trim': 'Touring', 'VIN': '1C3CCBBG8EN191708'}, '1C4RDJDG0RC161663': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '3.6', 'DriveType': 'AWD/All-Wheel Drive', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'DODGE', 'Model': 'Durango', 'ModelYear': '2024', 'Note': '', 'Series': 'WD', 'Series2': '', 'Trim': 'GT', 'VIN': '1C4RDJDG0RC161663'}, '1C4RJHAG1RC232052': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '3.6', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'JEEP', 'Model': 'Grand Cherokee', 'ModelYear': '2024', 'Note': '', 'Series': 'WL', 'Series2': '', 'Trim': 'Laredo', 'VIN': '1C4RJHAG1RC232052'}, '1FTEW2LP5RFA40352': {'BodyClass': 'Pickup', 'DisplacementL': '2.7', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': '2.7L-4V', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'FORD', 'Model': 'F-150', 'ModelYear': '2024', 'Note': '', 'Series': 'STX', 'Series2': 'Super Crew', 'Trim': '', 'VIN': '1FTEW2LP5RFA40352'}, '1FTFW3LD6SFB00855': {'BodyClass': 'Pickup', 'DisplacementL': '3.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'FORD', 'Model': 'F-150', 'ModelYear': '2025', 'Note': 'GVWR (lbs): 7001-8000', 'Series': 'F-Series', 'Series2': 'Super Crew Cab', 'Trim': 'XLT', 'VIN': '1FTFW3LD6SFB00855'}, '1GCPDBEK1RZ238098': {'BodyClass': 'Pickup', 'DisplacementL': '2.7', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'L3B', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'CHEVROLET', 'Model': 'Silverado', 'ModelYear': '2024', 'Note': '', 'Series': '1500', 'Series2': '', 'Trim': 'Custom', 'VIN': '1GCPDBEK1RZ238098'}, '1GKKNULS6MZ165460': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '3.6', 'DriveType': 'AWD/All-Wheel Drive', 'EngineModel': 'LGX', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'GMC', 'Model': 'Acadia', 'ModelYear': '2021', 'Note': 'Four (4) Door Cab/Utility', 'Series': '', 'Series2': '', 'Trim': 'SLT', 'VIN': '1GKKNULS6MZ165460'}, '1HGCY1F20RA090313': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '1.5', 'DriveType': '4x2', 'EngineModel': 'L15BE', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'HONDA', 'Model': 'Accord', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': '', 'Trim': 'LX', 'VIN': '1HGCY1F20RA090313'}, '1HGCY1F39RA023637': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '1.5', 'DriveType': '4x2', 'EngineModel': 'L15BE', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'HONDA', 'Model': 'Accord', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': '', 'Trim': 'EX, EX w/Out BSI', 'VIN': '1HGCY1F39RA023637'}, '2C3CDZBT0PH558129': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '5.7', 'DriveType': 'RWD/Rear-Wheel Drive', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'DODGE', 'Model': 'Challenger', 'ModelYear': '2023', 'Note': '', 'Series': 'LA', 'Series2': '', 'Trim': 'R/T', 'VIN': '2C3CDZBT0PH558129'}, '2C4RC1CG2PR566416': {'BodyClass': 'Minivan', 'DisplacementL': '3.6', 'DriveType': 'FWD/Front-Wheel Drive', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'CHRYSLER', 'Model': 'Voyager', 'ModelYear': '2023', 'Note': '', 'Series': '', 'Series2': 'Extended Wagon', 'Trim': 'LX', 'VIN': '2C4RC1CG2PR566416'}, '2C4RC1L71PR618182': {'BodyClass': 'Minivan', 'DisplacementL': '3.6', 'DriveType': 'FWD/Front-Wheel Drive', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'CHRYSLER', 'Model': 'Pacifica', 'ModelYear': '2023', 'Note': '', 'Series': '', 'Series2': 'Extended Wagon', 'Trim': 'Touring L', 'VIN': '2C4RC1L71PR618182'}, '3C6RR7KG9PG668473': {'BodyClass': 'Pickup', 'DisplacementL': '3.6', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'RAM', 'Model': '1500', 'ModelYear': '2023', 'Note': 'Single Rear Wheels', 'Series': 'Classic (DS)', 'Series2': '', 'Trim': 'Tradesman', 'VIN': '3C6RR7KG9PG668473'}, '3KPC24A64NE177716': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '1.6', 'DriveType': 'FWD/Front-Wheel Drive', 'EngineModel': 'GAMMA II', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'HYUNDAI', 'Model': 'Accent', 'ModelYear': '2022', 'Note': 'Seat Belt: All Positions', 'Series': '', 'Series2': '', 'Trim': 'SE, SEL', 'VIN': '3KPC24A64NE177716'}, '3KPFT4DE2SE036913': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '', 'DriveType': '', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'KIA', 'Model': 'K4', 'ModelYear': '2025', 'Note': '', 'Series': '', 'Series2': '', 'Trim': 'LX, LXS', 'VIN': '3KPFT4DE2SE036913'}, '3MVDMBBM0RM634483': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM0RM634483'}, '3MVDMBBM0RM650313': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM0RM650313'}, '3MVDMBBM0RM651249': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM0RM651249'}, '3MVDMBBM0RM654314': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM0RM654314'}, '3MVDMBBM0RM657147': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM0RM657147'}, '3MVDMBBM0RM698362': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM0RM698362'}, '3MVDMBBM0RM703821': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM0RM703821'}, '3MVDMBBM1RM647954': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM1RM647954'}, '3MVDMBBM1RM650868': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM1RM650868'}, '3MVDMBBM2RM648109': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM2RM648109'}, '3MVDMBBM2RM648563': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM2RM648563'}, '3MVDMBBM2RM650023': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM2RM650023'}, '3MVDMBBM2RM654959': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM2RM654959'}, '3MVDMBBM2RM655061': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM2RM655061'}, '3MVDMBBM2RM720667': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM2RM720667'}, '3MVDMBBM3RM601056': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM3RM601056'}, '3MVDMBBM3RM608959': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM3RM608959'}, '3MVDMBBM3RM648961': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM3RM648961'}, '3MVDMBBM3RM656316': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM3RM656316'}, '3MVDMBBM3RM695925': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM3RM695925'}, '3MVDMBBM4RM610400': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM4RM610400'}, '3MVDMBBM4RM649312': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM4RM649312'}, '3MVDMBBM5RM655930': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM5RM655930'}, '3MVDMBBM6RM621964': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM6RM621964'}, '3MVDMBBM6RM636951': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM6RM636951'}, '3MVDMBBM6RM641020': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM6RM641020'}, '3MVDMBBM6RM649716': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM6RM649716'}, '3MVDMBBM6RM696941': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM6RM696941'}, '3MVDMBBM7RM623612': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM7RM623612'}, '3MVDMBBM7RM646176': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM7RM646176'}, '3MVDMBBM7RM656321': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM7RM656321'}, '3MVDMBBM7RM694230': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM7RM694230'}, '3MVDMBBM8RM622162': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM8RM622162'}, '3MVDMBBM8RM650432': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM8RM650432'}, '3MVDMBBM8RM651564': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM8RM651564'}, '3MVDMBBM8RM653671': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM8RM653671'}, '3MVDMBBM8RM655646': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM8RM655646'}, '3MVDMBBM8RM713237': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM8RM713237'}, '3MVDMBBM8RM718440': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM8RM718440'}, '3MVDMBBM9RM639830': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM9RM639830'}, '3MVDMBBM9RM649936': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM9RM649936'}, '3MVDMBBM9RM650844': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM9RM650844'}, '3MVDMBBM9RM655641': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM9RM655641'}, '3MVDMBBM9RM672388': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM9RM672388'}, '3MVDMBBM9RM705552': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM9RM705552'}, '3MVDMBBM9RM710427': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBM9RM710427'}, '3MVDMBBMXRM646365': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBMXRM646365'}, '3MVDMBBMXRM653543': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBMXRM653543'}, '3MVDMBBMXRM655227': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBMXRM655227'}, '3MVDMBBMXRM655325': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBMXRM655325'}, '3MVDMBBMXRM667796': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PYUKD', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-30', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Sport Package', 'VIN': '3MVDMBBMXRM667796'}, '3MW69FF03R8D89825': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '2.0', 'DriveType': '', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'BMW', 'Model': '330i', 'ModelYear': '2024', 'Note': '', 'Series': '3-Series', 'Series2': '', 'Trim': '', 'VIN': '3MW69FF03R8D89825'}, '3VV3B7AX7RM127335': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2', 'DriveType': 'FWD/Front-Wheel Drive', 'EngineModel': 'TSI', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'VOLKSWAGEN', 'Model': 'Tiguan', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': '', 'Trim': 'SE Wolfsburg Edition', 'VIN': '3VV3B7AX7RM127335'}, '4S4BTGNDXR3146983': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.4', 'DriveType': 'AWD/All-Wheel Drive', 'EngineModel': 'U4', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'SUBARU', 'Model': 'Outback', 'ModelYear': '2024', 'Note': 'M/R: Moonroof / NAVI: Navigation / HK: Harman Kardon, Full-time AWD', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Limited', 'VIN': '4S4BTGNDXR3146983'}, '4T1K61AK9RU887189': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '2.5', 'DriveType': '4x2', 'EngineModel': 'A25A-FKS', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'TOYOTA', 'Model': 'Camry', 'ModelYear': '2024', 'Note': '', 'Series': '70 Series', 'Series2': '', 'Trim': 'XSE', 'VIN': '4T1K61AK9RU887189'}, '5J8YE1H09RL008089': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '3.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'J35Y5', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'ACURA', 'Model': 'MDX', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': '', 'Trim': 'SH-AWD A-SPEC', 'VIN': '5J8YE1H09RL008089'}, '5N1BT3AA0RC709298': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '1.5', 'DriveType': '4x2', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'NISSAN', 'Model': 'Rogue', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'S', 'VIN': '5N1BT3AA0RC709298'}, '5N1DL1HUXPC376439': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '3.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'INFINITI', 'Model': 'QX60', 'ModelYear': '2023', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Autograph', 'VIN': '5N1DL1HUXPC376439'}, '5NMJFCDE0RH416587': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'GDI Theta III', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'HYUNDAI', 'Model': 'Tucson', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'SEL w/ Convenience Package', 'VIN': '5NMJFCDE0RH416587'}, 'JF2SKARC9PH490439': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': 'AWD/All-Wheel Drive', 'EngineModel': 'NA U5', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'SUBARU', 'Model': 'Forester', 'ModelYear': '2023', 'Note': 'ES: EyeSight, Full-time AWD, ES : EyeSight / HK : Harman Kardon / SMART : SMART ENTRY&PUSHSTART / NAVI: Navigation', 'Series': '', 'Series2': 'Wagon Body style', 'Trim': 'Touring ES, NAVI(HK), SMART', 'VIN': 'JF2SKARC9PH490439'}, 'JM3KFBBM8R0362942': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'PY Cylinder Deactivation', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MAZDA', 'Model': 'CX-5', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'Select Package', 'VIN': 'JM3KFBBM8R0362942'}, 'KMHM34AA4RA070319': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '', 'DriveType': '', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'HYUNDAI', 'Model': 'Ioniq 6', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': '', 'Trim': 'SEL', 'VIN': 'KMHM34AA4RA070319'}, 'KNDPUCDF1R7279417': {'BodyClass': 'Sport Utility Vehicle (SUV)/Multi-Purpose Vehicle (MPV)', 'DisplacementL': '2.5', 'DriveType': '4WD/4-Wheel Drive/4x4', 'EngineModel': 'GDI THETA III', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'KIA', 'Model': 'Sportage', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': 'Wagon Body Style', 'Trim': 'LX', 'VIN': 'KNDPUCDF1R7279417'}, 'W1KAF4GB6RR165101': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '2', 'DriveType': '', 'EngineModel': 'M254', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'MERCEDES-BENZ', 'Model': 'C-Class', 'ModelYear': '2024', 'Note': '', 'Series': '', 'Series2': '', 'Trim': 'C300', 'VIN': 'W1KAF4GB6RR165101'}, 'WBA73AK08N7K27666': {'BodyClass': 'Sedan/Saloon', 'DisplacementL': '1.9975831016', 'DriveType': 'AWD/All-Wheel Drive', 'EngineModel': '', 'ErrorCode': '0', 'ErrorText': '0 - VIN decoded clean. Check Digit (9th position) is correct', 'Make': 'BMW', 'Model': '228i', 'ModelYear': '2022', 'Note': '', 'Series': '2-Series', 'Series2': '', 'Trim': 'xDrive GC', 'VIN': 'WBA73AK08N7K27666'}}
EMBEDDED_PROFILES = {'toyota': {'label': 'Toyota', 'color': '#c8102e', 'sites': ['www.toyotapartsdeal.com'], 'seed_part': '89070-02880', 'test_vin': '2T3WFREV1EW114903', 'wmi': ['JT0', 'JT1', 'JT2', 'JT3', 'JT4', 'JT5', 'JT6', 'JT7', 'JT8', 'JT9', 'JTD', 'JTE', 'JTF', 'JTL', 'JTM', 'JTN', 'NMT', '4T1', '4T2', '4T3', '5TD', '5TE', '5TF', '5TG', '5TJ', '2T1', '2T2', '2T3', '3TM', '3TN', '3TE', '3TD', '3TK']}, 'lexus': {'label': 'Lexus', 'color': '#1a1a2e', 'sites': ['www.toyotapartsdeal.com', 'lexuspartsnow.com'], 'seed_part': '89904-48481', 'test_vin': 'JTHCF1D21E5003351', 'wmi': ['JTH', 'JTJ', 'JTK', '2T2', '58A']}, 'scion': {'label': 'Scion', 'color': '#2d6a9f', 'sites': ['www.toyotapartsdeal.com'], 'seed_part': '89070-52G30', 'test_vin': 'JTKJF5C72E3083695', 'wmi': ['JTK', 'JTN']}, 'nissan': {'label': 'Nissan', 'color': '#c3002f', 'sites': ['www.nissanpartsdeal.com'], 'seed_part': '285E3-9UF7A', 'test_vin': '1N4AL3AP2EC194907', 'wmi': ['JN1', 'JN3', 'JN6', 'JN8', '1N4', '1N6', '3N1', '3N6', '5N1', '5N3']}, 'infiniti': {'label': 'Infiniti', 'color': '#8b6914', 'sites': ['www.nissanpartsdeal.com'], 'seed_part': '285E3-1LP0C', 'test_vin': 'JN1CV6EL0EM132375', 'wmi': ['JNK', 'JNA', 'JN1']}, 'honda': {'label': 'Honda', 'color': '#e40521', 'sites': ['www.hondapartsnow.com'], 'seed_part': '72147-TG7-A11', 'test_vin': '1HGCR2F88EA282614', 'wmi': ['JHM', 'JH2', 'SHH', '19X', '1HG', '1H3', '2HG', '2HK', '3HG', '5FN']}, 'acura': {'label': 'Acura', 'color': '#1e3a5f', 'sites': ['www.acurapartsnow.com', 'www.acurapartswarehouse.com'], 'seed_part': '72147-SY8-A03', 'test_vin': '5FRYD4H86EB504844', 'wmi': ['JH4', '5J8', '5J6', '5FR', '19U']}, 'chevrolet': {'label': 'Chevrolet', 'color': '#d4af37', 'sites': ['www.gmpartsdirect.com', 'www.gmpartsgiant.com'], 'seed_part': '13586489', 'test_vin': '3GCUKREC6EG362971', 'wmi': ['1G1', '1GC', '1GD', '1GN', '1GS', '2G1', '3G1', '3GC', '3GN', 'KL7', 'KL8']}, 'gmc': {'label': 'GMC', 'color': '#c8102e', 'sites': ['www.gmpartsdirect.com', 'www.gmpartsgiant.com'], 'seed_part': '13577771', 'test_vin': '3GTU2UEC6EG107319', 'wmi': ['1GK', '1GT', '3GT']}, 'buick': {'label': 'Buick', 'color': '#8b0000', 'sites': ['www.gmpartsdirect.com', 'www.gmpartsgiant.com'], 'seed_part': '13521090', 'test_vin': '1G4GA5GR3EF130870', 'wmi': ['1G4', '2G4', '3G5', '5GA', 'KL4', 'KL7', 'LRB', 'W04']}, 'cadillac': {'label': 'Cadillac', 'color': '#6b3a2a', 'sites': ['www.gmpartsdirect.com', 'www.gmpartsgiant.com'], 'seed_part': '22865375', 'test_vin': '2G61W5S86E9114863', 'wmi': ['1G6', '1GY', '2G6']}, 'ford': {'label': 'Ford', 'color': '#003476', 'sites': ['www.fordparts.com'], 'seed_part': '164-R8067', 'test_vin': '1FTFW1ET8EFC50303', 'wmi': ['1FA', '1FB', '1FC', '1FD', '1FM', '1FT', '2FA', '2FB', '2FC', '2FD', '2FM', '2FT', '3FA', '3FB', '3FC', '3FD', '3FM', '3FT', 'NM0']}, 'lincoln': {'label': 'Lincoln', 'color': '#2c2c2c', 'sites': ['www.fordparts.com'], 'seed_part': '164-R8070', 'test_vin': '2LMHJ5AT9EBL54336', 'wmi': ['1LN', '2LM', '3LN', '5LM']}, 'chrysler': {'label': 'Chrysler', 'color': '#003399', 'sites': ['www.moparpartsgiant.com', 'www.moparamerica.com'], 'seed_part': '68273329AA', 'test_vin': '2C3CCAAGXEH378114', 'wmi': ['1C3', '1C4', '2C3', '2C4', '3C4']}, 'dodge': {'label': 'Dodge', 'color': '#e31837', 'sites': ['www.moparpartsgiant.com', 'www.moparamerica.com'], 'seed_part': '68575429AA', 'test_vin': '2C3CDXBG3EH326211', 'wmi': ['1B3', '1B4', '1B7', '2B3', '1D3', '1D4', '1D7', '2D3']}, 'jeep': {'label': 'Jeep', 'color': '#00703c', 'sites': ['www.moparpartsgiant.com', 'www.moparamerica.com'], 'seed_part': '68273329AA', 'test_vin': '1C4BJWEG6EL217864', 'wmi': ['1C4', 'JC4']}, 'ram': {'label': 'RAM', 'color': '#1a1a1a', 'sites': ['www.moparpartsgiant.com', 'www.moparamerica.com'], 'seed_part': '68584151AA', 'test_vin': '1C6RR6LT9ES416430', 'wmi': ['1C6', '3C6']}, 'hyundai': {'label': 'Hyundai', 'color': '#002c5f', 'sites': ['www.hyundaioemparts.com', 'www.hyundaipartsdeal.com'], 'seed_part': '95440-3N250', 'test_vin': 'KMHDH4AE1EU183089', 'wmi': ['KMH', 'KM8', '5NM', '5NP']}, 'kia': {'label': 'Kia', 'color': '#05141f', 'sites': ['www.kiapartsnow.com', 'www.kiaparts.com'], 'seed_part': '81996-F6500', 'test_vin': 'KNDJN2A21E7058280', 'wmi': ['KNA', 'KND', 'KNE', 'KNJ', '5XY', '5XX']}, 'subaru': {'label': 'Subaru', 'color': '#003087', 'sites': ['parts.subaru.com', 'www.subarupartsdeal.com'], 'seed_part': '57497AJ10A', 'test_vin': 'JF2SJAAC7EH437539', 'wmi': ['JF1', 'JF2', '4S3', '4S4']}, 'mazda': {'label': 'Mazda', 'color': '#910000', 'sites': ['www.mazda-parts-dealer.com', 'www.mazda-parts.com'], 'seed_part': 'GJ6A-67-5DYC', 'test_vin': 'JM3BM1V78E1149030', 'wmi': ['JM1', 'JM3', '3MV', '4F2', '4F4', '1YV']}, 'mitsubishi': {'label': 'Mitsubishi', 'color': '#e60012', 'sites': ['www.mitsubishiparts.com'], 'seed_part': '6370A417', 'test_vin': 'JA3AU26U14U033768', 'wmi': ['JA3', 'JA4', '4A3', '4A4']}, 'volkswagen': {'label': 'Volkswagen', 'color': '#001e50', 'sites': ['www.vwpartscenter.net', 'www.eeuroparts.com'], 'seed_part': '5K0837202', 'test_vin': '1VWBP7A35DC024172', 'wmi': ['WVW', 'WV1', 'WV2', '1VW', '3VW', '3VV']}, 'audi': {'label': 'Audi', 'color': '#bb0a30', 'sites': ['parts.audiusa.com'], 'seed_part': '8V0-837-220-D', 'test_vin': 'WAUC8GFF0JA043195', 'wmi': ['WAU', 'WUA', 'TRU']}, 'land-rover': {'label': 'Land Rover', 'color': '#006f3c', 'sites': ['landrover.oempartsonline.com'], 'seed_part': 'LR078921', 'test_vin': 'SALSA2CN7KH823091', 'wmi': ['SAL']}, 'tesla': {'label': 'Tesla', 'color': '#c8202f', 'sites': ['shop.tesla.com'], 'seed_part': '1133148', 'test_vin': '7SAYGDEE0PF192834', 'wmi': ['5YJ', '7SA', '7G2', 'LRW', 'SFZ', 'XP7']}, 'volvo': {'label': 'Volvo', 'color': '#1251a2', 'sites': ['usparts.volvocars.com', 'www.volvopartscounter.com'], 'seed_part': '32425215', 'test_vin': 'YV4BR0DL6N1628394', 'wmi': ['YV1', 'YV4', 'LYV']}, 'bmw': {'label': 'BMW', 'color': '#1c69d3', 'sites': ['bmwfans.info'], 'seed_part': '66126938429', 'test_vin': 'WBA3A5C51DF359886', 'wmi': ['WBA', 'WBS', 'WBX', 'WBY', '5UX', '5YX', '4US', '3MW']}, 'mini': {'label': 'MINI', 'color': '#ee1c25', 'sites': ['bmwfans.info'], 'seed_part': '66126938429', 'test_vin': 'WMWSV3C57ET558272', 'wmi': ['WMW']}, 'mercedes-benz': {'label': 'Mercedes-Benz', 'color': '#555f66', 'sites': ['parts.mercedesbenzoflittleton.com'], 'seed_part': '000-905-11-12', 'test_vin': '', 'wmi': ['W1K', 'W1N', 'W1V', 'WDB', 'WDC', 'WDD', 'WD4']}}
INDEX_HTML = '<!doctype html>\n<html lang="en">\n  <head>\n    <meta charset="utf-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1">\n    <title>OEM Key Finder 8989</title>\n    <link rel="stylesheet" href="/styles.css">\n  </head>\n  <body>\n    <header class="topbar">\n      <div>\n        <p class="eyebrow">VIN-only OEM key lookup</p>\n        <h1>OEM Key Finder 8989</h1>\n      </div>\n    </header>\n\n    <main class="shell">\n      <nav class="tabs" aria-label="Views">\n        <button class="tab-button active" data-tab="search" type="button">Lookup</button>\n        <button class="tab-button" data-tab="history" type="button">Last 50 Searches</button>\n        <button class="tab-button" data-tab="subscribe" type="button">Helpful Tools</button>\n        <button class="tab-button" data-tab="makes" type="button">Supported Makes</button>\n      </nav>\n\n      <section class="tab-panel active" id="search-panel">\n        <form class="search-form" id="search-form">\n          <div class="field">\n            <label for="vin-input">VIN</label>\n            <input id="vin-input" name="vin" maxlength="17" autocomplete="off" spellcheck="false" placeholder="ENTER 17-CHAR VIN">\n          </div>\n          <div class="field">\n            <label for="make-override">Make override</label>\n            <select id="make-override">\n              <option value="">Auto detect</option>\n            </select>\n          </div>\n          <button id="search-button" type="submit">Look Up Keys</button>\n          <div class="meta-row">\n            <span class="detect-pill" id="detected-pill">Enter VIN to detect make</span>\n            <span class="counter" id="counter">0/17</span>\n            <label class="offline-toggle">\n              <input id="offline-input" type="checkbox">\n              <span>Cache only</span>\n            </label>\n          </div>\n        </form>\n\n        <div class="status" id="status" role="status"></div>\n        <section class="result" id="result" aria-live="polite"></section>\n      </section>\n\n      <section class="tab-panel" id="history-panel">\n        <div class="section-head">\n          <h2>Last 50 Searches</h2>\n          <button class="ghost-button" id="refresh-history" type="button">Refresh</button>\n        </div>\n        <div class="history-table-wrap">\n          <table class="history-table">\n            <thead>\n              <tr>\n                <th>VIN</th>\n                <th>Vehicle</th>\n                <th>Part</th>\n                <th>Confidence</th>\n                <th>Searched</th>\n              </tr>\n            </thead>\n            <tbody id="history-body"></tbody>\n          </table>\n        </div>\n      </section>\n\n      <section class="tab-panel" id="subscribe-panel">\n        <form class="subscribe-form" id="subscribe-form">\n          <div class="field">\n            <label for="subscribe-email">Email</label>\n            <input id="subscribe-email" name="email" type="email" autocomplete="email" spellcheck="false" placeholder="you@example.com">\n          </div>\n          <button id="subscribe-button" type="submit">Subscribe</button>\n          <p class="subscribe-note">Get updates when new useful shop tools are ready.</p>\n        </form>\n        <div class="status" id="subscribe-status" role="status"></div>\n      </section>\n\n      <section class="tab-panel" id="makes-panel">\n        <div class="section-head">\n          <h2>Supported Makes</h2>\n          <span class="muted" id="make-count"></span>\n        </div>\n        <div class="makes-grid" id="makes-grid"></div>\n      </section>\n    </main>\n\n    <script src="/app.js"></script>\n  </body>\n</html>\n'
APP_JS = 'const state = {\n  currentTab: "search",\n  history: [],\n  makes: [],\n  latest: null,\n  detectTimer: null,\n};\n\nconst tabs = document.querySelectorAll(".tab-button");\nconst panels = {\n  search: document.querySelector("#search-panel"),\n  history: document.querySelector("#history-panel"),\n  subscribe: document.querySelector("#subscribe-panel"),\n  makes: document.querySelector("#makes-panel"),\n};\nconst form = document.querySelector("#search-form");\nconst vinInput = document.querySelector("#vin-input");\nconst makeOverride = document.querySelector("#make-override");\nconst offlineInput = document.querySelector("#offline-input");\nconst searchButton = document.querySelector("#search-button");\nconst statusBox = document.querySelector("#status");\nconst resultBox = document.querySelector("#result");\nconst historyBody = document.querySelector("#history-body");\nconst refreshHistory = document.querySelector("#refresh-history");\nconst detectedPill = document.querySelector("#detected-pill");\nconst counter = document.querySelector("#counter");\nconst makesGrid = document.querySelector("#makes-grid");\nconst makeCount = document.querySelector("#make-count");\nconst subscribeForm = document.querySelector("#subscribe-form");\nconst subscribeEmail = document.querySelector("#subscribe-email");\nconst subscribeButton = document.querySelector("#subscribe-button");\nconst subscribeStatus = document.querySelector("#subscribe-status");\n\nfunction escapeHtml(value) {\n  return String(value ?? "")\n    .replaceAll("&", "&amp;")\n    .replaceAll("<", "&lt;")\n    .replaceAll(">", "&gt;")\n    .replaceAll(\'"\', "&quot;")\n    .replaceAll("\'", "&#039;");\n}\n\nfunction setStatus(message, isError = false) {\n  statusBox.textContent = message;\n  statusBox.classList.toggle("error", isError);\n}\n\nfunction setTab(tabName) {\n  state.currentTab = tabName;\n  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === tabName));\n  Object.entries(panels).forEach(([key, panel]) => panel.classList.toggle("active", key === tabName));\n  if (tabName === "history") loadHistory();\n}\n\nfunction formatVehicle(item) {\n  return [item.year, item.make, item.model, item.trim].filter(Boolean).join(" ");\n}\n\nfunction confidenceLabel(confidence) {\n  if (!confidence) return "Unmatched";\n  if (confidence.includes("candidate")) return "Candidate";\n  if (confidence.includes("rule")) return "YMM rule";\n  if (confidence.includes("confirmed")) return "Confirmed";\n  return confidence;\n}\n\nfunction partKind(part) {\n  const text = `${part.name || ""} ${part.part || ""}`.toLowerCase();\n  if (text.includes("emergency") || text.includes("blank")) return "Emergency key";\n  if (text.includes("transmitter") || text.includes("remote") || text.includes("fob") || text.includes("smart key")) return "Remote transmitter";\n  if (text.includes("blade")) return "Key blade";\n  return "Key part";\n}\n\nfunction renderMakes() {\n  makeCount.textContent = `${state.makes.length} makes`;\n  makesGrid.innerHTML = state.makes\n    .map((make) => {\n      return `\n        <button class="make-card" type="button" data-make="${escapeHtml(make.id)}" style="--make-color:${escapeHtml(make.color)}">\n          <span class="make-dot"></span>\n          <strong>${escapeHtml(make.label)}</strong>\n          <small>${escapeHtml(make.seed || "Profile ready")}</small>\n        </button>\n      `;\n    })\n    .join("");\n}\n\nasync function loadMakes() {\n  const response = await fetch("/api/makes");\n  const payload = await response.json();\n  state.makes = payload.makes || [];\n  makeOverride.innerHTML = `<option value="">Auto detect</option>`;\n  for (const make of state.makes) {\n    const option = document.createElement("option");\n    option.value = make.id;\n    option.textContent = make.label;\n    makeOverride.appendChild(option);\n  }\n  renderMakes();\n}\n\nasync function detectVin() {\n  const vin = vinInput.value.trim();\n  if (vin.length < 3) {\n    detectedPill.textContent = "Enter VIN to detect make";\n    return;\n  }\n  const response = await fetch("/api/detect", {\n    method: "POST",\n    headers: { "Content-Type": "application/json" },\n    body: JSON.stringify({ vin }),\n  });\n  const detected = await response.json();\n  if (detected.makeLabel) {\n    detectedPill.textContent = `${detected.makeLabel} detected from ${detected.detectedWmi}`;\n  } else {\n    detectedPill.textContent = "Make not detected. Use override.";\n  }\n}\n\nfunction renderParts(parts) {\n  if (!parts.length) {\n    return `<div class="empty">No part number returned.</div>`;\n  }\n\n  return `<div class="part-list">${parts\n    .map((part) => {\n      const replaces = part.replaces?.length\n        ? `<div class="pill-row">${part.replaces.map((value) => `<span class="pill">Replaces ${escapeHtml(value)}</span>`).join("")}</div>`\n        : "";\n      const superseded = part.supersededBy?.length\n        ? `<div class="pill-row">${part.supersededBy.map((value) => `<span class="pill">Superseded by ${escapeHtml(value)}</span>`).join("")}</div>`\n        : "";\n      const verify = part.verificationRequired ? `<span class="verify">VIN fitment check required before ordering</span>` : `<span class="confirmed">VIN/YMM fitment evidence stored</span>`;\n      const source = part.viewUrl ? `<a class="source-link" href="${escapeHtml(part.viewUrl)}" target="_blank" rel="noreferrer">Open source</a>` : "";\n      const kind = partKind(part);\n      return `\n        <article class="part-item">\n          <div class="part-top">\n            <div>\n              <div class="part-kind">${escapeHtml(kind)}</div>\n              <div class="part-number">${escapeHtml(part.part)}</div>\n              <div class="part-meta">${escapeHtml(part.name || kind)}</div>\n            </div>\n            <button class="small-button" type="button" data-copy="${escapeHtml(part.part)}">Copy</button>\n          </div>\n          ${replaces}\n          ${superseded}\n          <div class="confidence-line">${verify}</div>\n          ${part.notes ? `<p class="notes">${escapeHtml(part.notes)}</p>` : ""}\n          ${source}\n        </article>\n      `;\n    })\n    .join("")}</div>`;\n}\n\nasync function subscribe(email) {\n  subscribeButton.disabled = true;\n  subscribeStatus.textContent = "Saving...";\n  subscribeStatus.classList.remove("error");\n  try {\n    const response = await fetch("/api/subscribe", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({ email }),\n    });\n    const payload = await response.json();\n    if (!response.ok) throw new Error(payload.error || "Could not save email");\n    subscribeStatus.textContent = payload.message || "Subscribed.";\n    subscribeEmail.value = "";\n  } catch (error) {\n    subscribeStatus.textContent = error.message;\n    subscribeStatus.classList.add("error");\n  } finally {\n    subscribeButton.disabled = false;\n  }\n}\n\nfunction renderResult(data) {\n  state.latest = data;\n  const decode = data.decode || {};\n  resultBox.innerHTML = `\n    <div class="result-grid">\n      <section class="panel vehicle-panel">\n        <div class="vehicle-title">${escapeHtml(data.vehicle || data.makeLabel || "Vehicle")}</div>\n        <dl class="kv">\n          <div><dt>VIN</dt><dd>${escapeHtml(data.vin)}</dd></div>\n          <div><dt>Year</dt><dd>${escapeHtml(decode.ModelYear || "")}</dd></div>\n          <div><dt>Make</dt><dd>${escapeHtml(decode.Make || data.makeLabel || "")}</dd></div>\n          <div><dt>Model</dt><dd>${escapeHtml(decode.Model || "")}</dd></div>\n          <div><dt>Trim</dt><dd>${escapeHtml(decode.Trim || "Not listed")}</dd></div>\n          <div><dt>Decode</dt><dd>${data.cached ? "Cache" : "Live/cache"}</dd></div>\n        </dl>\n        <div class="actions">\n          <button class="ghost-button" id="copy-all" type="button">Copy All Parts</button>\n          <button class="ghost-button" id="export-csv" type="button">Export CSV</button>\n        </div>\n      </section>\n      <section class="panel">\n        <div class="parts-head">\n          <h2>Key Parts</h2>\n          <span class="badge">${data.count} part${data.count === 1 ? "" : "s"}</span>\n          <span class="badge secondary-badge">${escapeHtml(confidenceLabel(data.confidence))}</span>\n        </div>\n        ${renderParts(data.parts || [])}\n      </section>\n    </div>\n  `;\n}\n\nfunction renderHistory(items) {\n  if (!items.length) {\n    historyBody.innerHTML = `<tr><td colspan="5" class="empty">No searches yet.</td></tr>`;\n    return;\n  }\n\n  historyBody.innerHTML = items\n    .map((item) => {\n      return `\n        <tr>\n          <td><button type="button" data-vin="${escapeHtml(item.vin)}">${escapeHtml(item.vin)}</button></td>\n          <td>${escapeHtml(formatVehicle(item))}</td>\n          <td>${escapeHtml(item.key_part_numbers || "NO_PART")}</td>\n          <td>${escapeHtml(confidenceLabel(item.confidence))}</td>\n          <td>${escapeHtml(item.searched_at || "")}</td>\n        </tr>\n      `;\n    })\n    .join("");\n}\n\nasync function loadHistory() {\n  const response = await fetch("/api/history?limit=50");\n  const payload = await response.json();\n  state.history = payload.items || payload.history || [];\n  renderHistory(state.history);\n}\n\nasync function searchVin(vin, offline) {\n  searchButton.disabled = true;\n  setStatus("Searching OEM key data...");\n  try {\n    const response = await fetch("/api/lookup", {\n      method: "POST",\n      headers: { "Content-Type": "application/json" },\n      body: JSON.stringify({ vin, make: makeOverride.value || undefined, offline }),\n    });\n    const payload = await response.json();\n    if (!response.ok) throw new Error(payload.error || "Search failed");\n    renderResult(payload);\n    await loadHistory();\n    setStatus(payload.parts?.some((part) => part.verificationRequired) ? "Candidate returned. Verify VIN fitment before ordering." : "Confirmed match returned.");\n  } catch (error) {\n    setStatus(error.message, true);\n  } finally {\n    searchButton.disabled = false;\n  }\n}\n\nfunction partsToCsv(data) {\n  const rows = [["VIN", "Vehicle", "Part Number", "Description", "Confidence", "Source"]];\n  for (const part of data.parts || []) rows.push([data.vin, data.vehicle, part.part, part.name, part.confidence, part.viewUrl]);\n  return rows.map((row) => row.map((cell) => `"${String(cell ?? "").replaceAll(\'"\', \'""\')}"`).join(",")).join("\\n");\n}\n\nasync function copyText(text) {\n  try {\n    await navigator.clipboard.writeText(text);\n    return true;\n  } catch {\n    const textarea = document.createElement("textarea");\n    textarea.value = text;\n    textarea.style.position = "fixed";\n    textarea.style.left = "-9999px";\n    document.body.appendChild(textarea);\n    textarea.focus();\n    textarea.select();\n    const ok = document.execCommand("copy");\n    textarea.remove();\n    return ok;\n  }\n}\n\ntabs.forEach((tab) => tab.addEventListener("click", () => setTab(tab.dataset.tab)));\n\nform.addEventListener("submit", (event) => {\n  event.preventDefault();\n  const vin = vinInput.value.trim().toUpperCase();\n  vinInput.value = vin;\n  searchVin(vin, offlineInput.checked);\n});\n\nvinInput.addEventListener("input", () => {\n  vinInput.value = vinInput.value.toUpperCase().replace(/[^A-HJ-NPR-Z0-9]/g, "").slice(0, 17);\n  counter.textContent = `${vinInput.value.length}/17`;\n  window.clearTimeout(state.detectTimer);\n  state.detectTimer = window.setTimeout(detectVin, 250);\n});\n\nmakesGrid.addEventListener("click", (event) => {\n  const button = event.target.closest("button[data-make]");\n  if (!button) return;\n  makeOverride.value = button.dataset.make;\n  setTab("search");\n});\n\nhistoryBody.addEventListener("click", (event) => {\n  const button = event.target.closest("button[data-vin]");\n  if (!button) return;\n  vinInput.value = button.dataset.vin;\n  counter.textContent = "17/17";\n  setTab("search");\n  searchVin(button.dataset.vin, true);\n});\n\nresultBox.addEventListener("click", async (event) => {\n  const copyButton = event.target.closest("button[data-copy]");\n  if (copyButton) {\n    const ok = await copyText(copyButton.dataset.copy);\n    copyButton.textContent = ok ? "Copied" : "Copy failed";\n    window.setTimeout(() => (copyButton.textContent = "Copy"), 900);\n    return;\n  }\n  if (event.target.id === "copy-all" && state.latest) {\n    await copyText((state.latest.parts || []).map((part) => part.part).join("\\n"));\n  }\n  if (event.target.id === "export-csv" && state.latest) {\n    const blob = new Blob([partsToCsv(state.latest)], { type: "text/csv;charset=utf-8" });\n    const link = document.createElement("a");\n    link.href = URL.createObjectURL(blob);\n    link.download = `oem-key-${state.latest.vin}.csv`;\n    link.click();\n    URL.revokeObjectURL(link.href);\n  }\n});\n\nrefreshHistory.addEventListener("click", loadHistory);\n\nsubscribeForm.addEventListener("submit", (event) => {\n  event.preventDefault();\n  subscribe(subscribeEmail.value.trim());\n});\n\nPromise.all([loadMakes(), loadHistory()]).catch((error) => setStatus(error.message, true));\n'
STYLES_CSS = ':root {\n  color-scheme: light;\n  --ink: #172026;\n  --muted: #5e6a72;\n  --line: #d8e0e5;\n  --panel: #ffffff;\n  --page: #f5f7f8;\n  --accent: #1f6f78;\n  --accent-dark: #16545b;\n  --warn: #a84d1b;\n  --good: #247248;\n}\n\n* {\n  box-sizing: border-box;\n}\n\nbody {\n  margin: 0;\n  background: var(--page);\n  color: var(--ink);\n  font-family: Arial, Helvetica, sans-serif;\n  line-height: 1.4;\n}\n\n.topbar {\n  align-items: center;\n  background: #ffffff;\n  border-bottom: 1px solid var(--line);\n  display: flex;\n  justify-content: space-between;\n  min-height: 82px;\n  padding: 18px 28px;\n}\n\n.eyebrow {\n  color: var(--muted);\n  font-size: 12px;\n  font-weight: 700;\n  margin: 0 0 4px;\n  text-transform: uppercase;\n}\n\nh1,\nh2,\nh3,\np {\n  margin-top: 0;\n}\n\nh1 {\n  font-size: 28px;\n  margin-bottom: 0;\n}\n\nh2 {\n  font-size: 18px;\n  margin-bottom: 0;\n}\n\nh3 {\n  font-size: 16px;\n  margin-bottom: 10px;\n}\n\n.shell {\n  margin: 0 auto;\n  max-width: 1180px;\n  padding: 24px;\n}\n\n.tabs {\n  border-bottom: 1px solid var(--line);\n  display: flex;\n  gap: 6px;\n}\n\n.tab-button,\n.ghost-button,\n.search-row button {\n  border: 1px solid var(--line);\n  border-radius: 6px;\n  cursor: pointer;\n  font-weight: 700;\n  min-height: 40px;\n  padding: 0 16px;\n}\n\n.tab-button {\n  background: transparent;\n  color: var(--muted);\n}\n\n.tab-button.active {\n  background: var(--panel);\n  border-bottom-color: var(--panel);\n  color: var(--ink);\n}\n\n.subscribe-form {\n  background: var(--panel);\n  border: 1px solid var(--line);\n  border-radius: 8px;\n  display: grid;\n  gap: 12px;\n  grid-template-columns: minmax(220px, 1fr) 150px;\n  align-items: end;\n  padding: 18px;\n}\n\n.subscribe-form label {\n  color: var(--muted);\n  display: block;\n  font-size: 13px;\n  font-weight: 700;\n  margin-bottom: 8px;\n}\n\n.subscribe-form input {\n  border: 1px solid var(--line);\n  border-radius: 6px;\n  color: var(--ink);\n  font-size: 18px;\n  font-weight: 700;\n  min-height: 44px;\n  padding: 0 12px;\n  width: 100%;\n}\n\n#subscribe-button {\n  border: 1px solid var(--accent);\n  border-radius: 6px;\n  background: var(--accent);\n  color: white;\n  cursor: pointer;\n  font-weight: 800;\n  min-height: 44px;\n  padding: 0 16px;\n}\n\n#subscribe-button:disabled {\n  cursor: wait;\n  opacity: 0.7;\n}\n\n.subscribe-note {\n  color: var(--muted);\n  font-weight: 700;\n  grid-column: 1 / -1;\n  margin: 0;\n}\n\n.tab-panel {\n  display: none;\n  padding-top: 22px;\n}\n\n.tab-panel.active {\n  display: block;\n}\n\n.search-form {\n  background: var(--panel);\n  border: 1px solid var(--line);\n  border-radius: 8px;\n  display: grid;\n  gap: 12px;\n  grid-template-columns: minmax(220px, 1fr) 220px 150px;\n  align-items: end;\n  padding: 18px;\n}\n\n.search-form label {\n  color: var(--muted);\n  display: block;\n  font-size: 13px;\n  font-weight: 700;\n  margin-bottom: 8px;\n}\n\n.field input,\n.field select {\n  border: 1px solid var(--line);\n  border-radius: 6px;\n  color: var(--ink);\n  font-size: 18px;\n  font-weight: 700;\n  letter-spacing: 0;\n  min-height: 44px;\n  padding: 0 12px;\n  text-transform: uppercase;\n  width: 100%;\n}\n\n#search-button {\n  border: 1px solid var(--accent);\n  border-radius: 6px;\n  background: var(--accent);\n  color: white;\n  cursor: pointer;\n  font-weight: 800;\n  min-height: 44px;\n  padding: 0 16px;\n}\n\n#search-button:disabled {\n  cursor: wait;\n  opacity: 0.7;\n}\n\n.meta-row {\n  align-items: center;\n  display: flex;\n  flex-wrap: wrap;\n  gap: 12px;\n  grid-column: 1 / -1;\n  justify-content: space-between;\n}\n\n.detect-pill {\n  background: #edf7f4;\n  border: 1px solid #c7e5d9;\n  border-radius: 999px;\n  color: var(--good);\n  font-weight: 800;\n  padding: 6px 10px;\n}\n\n.counter,\n.muted {\n  color: var(--muted);\n  font-weight: 700;\n}\n\n.offline-toggle {\n  align-items: center;\n  display: flex;\n  gap: 8px;\n  margin: 0;\n}\n\n.offline-toggle input {\n  height: 16px;\n  width: 16px;\n}\n\n.status {\n  color: var(--muted);\n  min-height: 24px;\n  padding: 12px 2px 0;\n}\n\n.status.error {\n  color: var(--warn);\n  font-weight: 700;\n}\n\n.result-grid {\n  display: grid;\n  gap: 16px;\n  grid-template-columns: minmax(240px, 0.9fr) minmax(320px, 1.4fr);\n}\n\n.panel {\n  background: var(--panel);\n  border: 1px solid var(--line);\n  border-radius: 8px;\n  padding: 18px;\n}\n\n.vehicle-title {\n  font-size: 24px;\n  font-weight: 800;\n  margin-bottom: 16px;\n}\n\n.parts-head,\n.section-head {\n  align-items: center;\n  display: flex;\n  gap: 10px;\n  justify-content: space-between;\n  margin-bottom: 12px;\n}\n\n.badge {\n  background: #e8f0f2;\n  border: 1px solid var(--line);\n  border-radius: 999px;\n  color: var(--accent-dark);\n  font-size: 12px;\n  font-weight: 800;\n  padding: 5px 10px;\n}\n\n.secondary-badge {\n  color: var(--muted);\n}\n\n.kv {\n  display: grid;\n  gap: 10px;\n}\n\n.kv div {\n  border-bottom: 1px solid #edf1f3;\n  display: grid;\n  gap: 8px;\n  grid-template-columns: 110px 1fr;\n  padding-bottom: 8px;\n}\n\n.kv dt {\n  color: var(--muted);\n  font-size: 12px;\n  font-weight: 700;\n  text-transform: uppercase;\n}\n\n.kv dd {\n  font-weight: 700;\n  margin: 0;\n}\n\n.part-list {\n  display: grid;\n  gap: 12px;\n}\n\n.part-item {\n  border: 1px solid var(--line);\n  border-radius: 8px;\n  padding: 14px;\n}\n\n.part-top {\n  align-items: flex-start;\n  display: flex;\n  gap: 12px;\n  justify-content: space-between;\n}\n\n.part-number {\n  color: var(--accent-dark);\n  font-size: 24px;\n  font-weight: 800;\n  letter-spacing: 0;\n  margin-bottom: 4px;\n}\n\n.part-kind {\n  color: var(--ink);\n  font-size: 13px;\n  font-weight: 800;\n  margin-bottom: 2px;\n  text-transform: uppercase;\n}\n\n.part-meta {\n  color: var(--muted);\n  margin-bottom: 8px;\n}\n\n.pill-row {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 8px;\n}\n\n.pill {\n  background: #edf7f4;\n  border: 1px solid #c7e5d9;\n  border-radius: 999px;\n  color: var(--good);\n  font-size: 12px;\n  font-weight: 700;\n  padding: 4px 9px;\n}\n\n.source-link {\n  color: var(--accent-dark);\n  display: inline-block;\n  font-weight: 700;\n  margin-top: 8px;\n}\n\n.small-button {\n  background: #ffffff;\n  border: 1px solid var(--line);\n  border-radius: 6px;\n  color: var(--accent-dark);\n  cursor: pointer;\n  font-weight: 800;\n  min-height: 34px;\n  padding: 0 10px;\n}\n\n.confidence-line {\n  margin-top: 10px;\n}\n\n.verify,\n.confirmed {\n  border-radius: 6px;\n  display: inline-block;\n  font-size: 12px;\n  font-weight: 800;\n  padding: 5px 8px;\n}\n\n.verify {\n  background: #fff4e8;\n  color: #8a4a15;\n}\n\n.confirmed {\n  background: #edf7f4;\n  color: var(--good);\n}\n\n.notes {\n  color: var(--muted);\n  margin: 10px 0 0;\n}\n\n.actions {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 8px;\n  margin-top: 16px;\n}\n\n.empty {\n  color: var(--muted);\n  padding: 18px;\n}\n\n.history-head,\n.section-head {\n  align-items: center;\n  display: flex;\n  justify-content: space-between;\n  margin-bottom: 12px;\n}\n\n.ghost-button {\n  background: #ffffff;\n  color: var(--accent-dark);\n}\n\n.history-table-wrap {\n  background: var(--panel);\n  border: 1px solid var(--line);\n  border-radius: 8px;\n  overflow-x: auto;\n}\n\n.history-table {\n  border-collapse: collapse;\n  min-width: 860px;\n  width: 100%;\n}\n\n.history-table th,\n.history-table td {\n  border-bottom: 1px solid #edf1f3;\n  padding: 12px;\n  text-align: left;\n  vertical-align: top;\n}\n\n.history-table th {\n  color: var(--muted);\n  font-size: 12px;\n  text-transform: uppercase;\n}\n\n.history-table button {\n  background: transparent;\n  border: 0;\n  color: var(--accent-dark);\n  cursor: pointer;\n  font-weight: 800;\n  padding: 0;\n}\n\n.makes-grid {\n  display: grid;\n  gap: 10px;\n  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));\n}\n\n.make-card {\n  align-content: center;\n  background: var(--panel);\n  border: 1px solid var(--line);\n  border-left: 5px solid var(--make-color, var(--accent));\n  border-radius: 8px;\n  color: var(--ink);\n  cursor: pointer;\n  display: grid;\n  gap: 4px;\n  min-height: 78px;\n  padding: 12px;\n  text-align: left;\n}\n\n.make-card small {\n  color: var(--muted);\n  font-weight: 700;\n}\n\n.make-dot {\n  background: var(--make-color, var(--accent));\n  border-radius: 999px;\n  display: inline-block;\n  height: 8px;\n  margin-right: 6px;\n  width: 8px;\n}\n\n@media (max-width: 760px) {\n  .topbar {\n    align-items: flex-start;\n    flex-direction: column;\n    gap: 8px;\n    padding: 16px;\n  }\n\n  .shell {\n    padding: 16px;\n  }\n\n    .search-form,\n    .subscribe-form,\n    .result-grid,\n    .kv div {\n      grid-template-columns: 1fr;\n    }\n\n  .tabs {\n    overflow-x: auto;\n  }\n}\n'


class VinKeyError(RuntimeError):
    pass


@dataclass(frozen=True)
class DecodeResult:
    vin: str
    fields: dict[str, str]
    source: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_vin(vin: str) -> str:
    normalized = vin.strip().upper()
    if not VIN_RE.match(normalized):
        raise VinKeyError(f"Invalid VIN '{vin}'. VINs must be 17 chars and exclude I, O, Q.")
    return normalized


def slug_make(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def compact_decode_fields(raw: dict[str, Any]) -> dict[str, str]:
    keys = [
        "VIN", "Make", "Model", "ModelYear", "Trim", "Series", "Series2", "BodyClass",
        "DisplacementL", "EngineModel", "DriveType", "Note", "ErrorCode", "ErrorText",
    ]
    return {key: str(raw.get(key, "") or "") for key in keys}


def detect_make_profile(vin: str, fields: dict[str, str], profiles: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    make_slug = slug_make(fields.get("Make", ""))
    if make_slug in profiles:
        return make_slug, profiles[make_slug]

    wmi = vin[:3]
    if wmi in {"JTH", "JTJ", "2T2", "58A"}:
        return "lexus", profiles.get("lexus", {})
    if wmi in {"3MW", "WBA", "WBS", "WBX", "WBY", "5UX", "5YX", "4US"}:
        return "bmw", profiles.get("bmw", {})
    if wmi in {"JM1", "JM3", "3MV", "4F2", "4F4", "1YV"}:
        return "mazda", profiles.get("mazda", {})
    if wmi in {"SAL", "SAJ"}:
        return "land-rover", profiles.get("land-rover", {})
    if wmi in {"WAU", "WUA", "TRU"}:
        return "audi", profiles.get("audi", {})
    if wmi in {"5YJ", "7SA", "7G2", "LRW", "SFZ", "XP7"}:
        return "tesla", profiles.get("tesla", {})
    if wmi in {"YV1", "YV4", "LYV"}:
        return "volvo", profiles.get("volvo", {})
    if wmi in {"3VV", "WVW", "WV1", "WV2", "1VW", "3VW"}:
        return "volkswagen", profiles.get("volkswagen", {})
    if wmi in {"1C4", "3C4", "JC4"}:
        return "jeep", profiles.get("jeep", {})
    if wmi == "JN1" and len(vin) > 3:
        key = "infiniti" if vin[3] in {"C", "V", "K", "N"} else "nissan"
        return key, profiles.get(key, {})
    if wmi == "2C3":
        key = "dodge" if vin[3:5] == "CD" else "chrysler"
        return key, profiles.get(key, {})

    for key, profile in profiles.items():
        if wmi in profile.get("wmi", []):
            return key, profile
    return None


def build_profile_source_url(profile: dict[str, Any], make_key: str, vin: str) -> str:
    sites = profile.get("sites") or []
    if not sites:
        return ""
    domain = sites[0]
    if "partsdeal" in domain or "partsnow" in domain or "partsgiant" in domain:
        return f"https://{domain}/page_product/pd?vin={urllib.parse.quote(vin)}&filter=()&pd=Car+Key&pdUrl=car_key"
    if domain == "bmwfans.info":
        return "https://bmwfans.info/"
    return f"https://{domain}/"


def fallback_profile_match(vin: str, fields: dict[str, str], profiles: dict[str, Any]) -> dict[str, Any] | None:
    detected = detect_make_profile(vin, fields, profiles)
    if not detected:
        return None
    make_key, profile = detected
    seed_part = profile.get("seed_part")
    if not seed_part:
        return None
    label = profile.get("label", fields.get("Make", make_key.title()))
    return {
        "confidence": "candidate_from_make_profile_verify_before_ordering",
        "fitment_basis": f"No exact VIN/YMM key match is stored yet. Returning the {label} make-profile OEM seed part as a candidate starting point.",
        "match_type": "make_profile_candidate",
        "notes": "Use this to start the OEM catalog lookup, not as final order approval. Confirm the part on the linked OEM site with VIN fitment before cutting/programming.",
        "parts": [{
            "description": f"{label} key / remote candidate from make profile",
            "part_number": seed_part,
            "replaces": [],
            "verification_required": True,
        }],
        "source_url": build_profile_source_url(profile, make_key, vin),
    }


def minimal_profile_decode(vin: str, profiles: dict[str, Any], reason: str) -> DecodeResult | None:
    normalized = normalize_vin(vin)
    detected = detect_make_profile(normalized, {"Make": ""}, profiles)
    if not detected:
        return None
    _, profile = detected
    fields = compact_decode_fields({
        "VIN": normalized,
        "Make": profile.get("label", ""),
        "ModelYear": MODEL_YEAR_CODES.get(normalized[9], ""),
        "ErrorCode": "PROFILE",
        "ErrorText": reason,
    })
    return DecodeResult(vin=normalized, fields=fields, source="profile")


def fetch_nhtsa_decode(vin: str, timeout: float = 20.0) -> dict[str, str]:
    url = NHTSA_ENDPOINT.format(vin=urllib.parse.quote(vin))
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("Results") or []
    if not results:
        raise VinKeyError(f"NHTSA returned no decode results for {vin}.")
    fields = compact_decode_fields(results[0])
    if fields.get("ErrorCode") and fields["ErrorCode"] != "0":
        raise VinKeyError(f"NHTSA decode warning for {vin}: {fields.get('ErrorText', '')}")
    return fields


def decode_vin(vin: str, *, offline: bool = False, update_cache: bool = False) -> DecodeResult:
    normalized = normalize_vin(vin)
    if normalized in EMBEDDED_CACHE:
        return DecodeResult(vin=normalized, fields=dict(EMBEDDED_CACHE[normalized]), source="cache")
    if offline:
        raise VinKeyError(f"{normalized} is not in embedded cache; run live lookup to use NHTSA.")
    fields = fetch_nhtsa_decode(normalized)
    if update_cache:
        EMBEDDED_CACHE[normalized] = fields
    return DecodeResult(vin=normalized, fields=fields, source="nhtsa")


def string_contains(haystack: str, needles: list[str]) -> bool:
    folded = haystack.casefold()
    return all(needle.casefold() in folded for needle in needles)


def value_matches(actual: str, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, list):
        return any(value_matches(actual, option) for option in expected)
    return str(actual).casefold() == str(expected).casefold()


def rule_matches(fields: dict[str, str], rule: dict[str, Any]) -> bool:
    match = rule.get("match", {})
    for field, expected in match.items():
        if field.endswith("_contains"):
            raw_field = field[: -len("_contains")]
            needles = expected if isinstance(expected, list) else [expected]
            if not string_contains(fields.get(raw_field, ""), [str(item) for item in needles]):
                return False
            continue
        if not value_matches(fields.get(field, ""), expected):
            return False
    return True


def resolve_key_parts(vin: str, *, offline: bool = False, update_cache: bool = False) -> dict[str, Any]:
    catalog = EMBEDDED_CATALOG
    profiles = EMBEDDED_PROFILES
    try:
        decode = decode_vin(vin, offline=offline, update_cache=update_cache)
    except (VinKeyError, OSError) as exc:
        decode = minimal_profile_decode(vin, profiles, str(exc))
        if decode is None:
            raise
    exact = catalog.get("vin_confirmations", {})
    matches: list[dict[str, Any]] = []
    if decode.vin in exact:
        record = dict(exact[decode.vin])
        record["match_type"] = "exact_vin"
        matches.append(record)
    for rule in catalog.get("rules", []):
        if rule_matches(decode.fields, rule):
            record = dict(rule)
            record.pop("match", None)
            record["match_type"] = "nhtsa_rule"
            matches.append(record)
    if not matches:
        fallback = fallback_profile_match(decode.vin, decode.fields, profiles)
        if fallback:
            matches.append(fallback)
    return {
        "vin": decode.vin,
        "decode_source": decode.source,
        "decode": decode.fields,
        "matches": matches,
        "detected_make_profile": (detect_make_profile(decode.vin, decode.fields, profiles) or ["", {}])[0],
    }


def best_part_summary(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for match in result["matches"]:
        for part in match.get("parts", []):
            part_number = part.get("part_number", "")
            if part_number and part_number not in parts:
                parts.append(part_number)
    return "; ".join(parts) if parts else "NO_CONFIRMED_MATCH"


def flatten_for_csv(result: dict[str, Any]) -> dict[str, str]:
    fields = result["decode"]
    replacements: list[str] = []
    superseded_by: list[str] = []
    sources: list[str] = []
    descriptions: list[str] = []
    for match in result["matches"]:
        if match.get("source_url"):
            sources.append(match["source_url"])
        for part in match.get("parts", []):
            descriptions.append(part.get("description", ""))
            replacements.extend(part.get("replaces", []))
            superseded_by.extend(part.get("superseded_by", []))
    return {
        "vin": result["vin"],
        "year": fields.get("ModelYear", ""),
        "make": fields.get("Make", ""),
        "model": fields.get("Model", ""),
        "trim": fields.get("Trim", ""),
        "series": fields.get("Series", ""),
        "engine": fields.get("EngineModel", "") or fields.get("DisplacementL", ""),
        "key_part_numbers": best_part_summary(result),
        "descriptions": "; ".join(sorted(set(filter(None, descriptions)))),
        "replaces": "; ".join(sorted(set(replacements))),
        "superseded_by": "; ".join(sorted(set(superseded_by))),
        "confidence": "; ".join(sorted(set(match.get("confidence", "") for match in result["matches"]))),
        "sources": "; ".join(sorted(set(sources))),
    }


def load_history() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []
    try:
        payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload[:MAX_HISTORY] if isinstance(payload, list) else []


def save_history(history: list[dict[str, Any]]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history[:MAX_HISTORY], indent=2) + "\n", encoding="utf-8")


def load_subscriber_emails() -> set[str]:
    if not SUBSCRIBERS_PATH.exists():
        return set()
    emails: set[str] = set()
    try:
        for line in SUBSCRIBERS_PATH.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            email = str(item.get("email", "")).casefold()
            if email:
                emails.add(email)
    except OSError:
        return set()
    return emails


def save_subscriber(email: str) -> tuple[bool, str]:
    normalized = email.strip().casefold()
    if not EMAIL_PATTERN.match(normalized):
        return False, "Enter a valid email address."
    if normalized in load_subscriber_emails():
        return True, "That email is already subscribed."
    SUBSCRIBERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUBSCRIBERS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"email": normalized, "subscribed_at": utc_now()}, separators=(",", ":")) + "\n")
    return True, "Subscribed. Thank you."


def public_makes() -> list[dict[str, Any]]:
    return [
        {
            "id": key,
            "label": profile.get("label", key.title()),
            "color": profile.get("color", "#1f6f78"),
            "sites": profile.get("sites", []),
            "seed": profile.get("seed_part", ""),
            "testVin": profile.get("test_vin", ""),
        }
        for key, profile in EMBEDDED_PROFILES.items()
    ]


def detect_make_from_partial_vin(vin: str) -> dict[str, Any]:
    normalized = "".join(char for char in vin.upper() if char.isalnum())[:17]
    partial = {"vin": normalized, "detectedWmi": normalized[:3] or None}
    if len(normalized) < 3:
        return {**partial, "make": None, "makeLabel": None, "color": None}
    detected = detect_make_profile(normalized.ljust(17, "0"), {"Make": ""}, EMBEDDED_PROFILES)
    if not detected:
        return {**partial, "make": None, "makeLabel": None, "color": None}
    key, profile = detected
    return {**partial, "make": key, "makeLabel": profile.get("label", key.title()), "color": profile.get("color", "#1f6f78")}


def summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_for_csv(result)
    parts: list[dict[str, Any]] = []
    for match in result.get("matches", []):
        for part in match.get("parts", []):
            parts.append({
                "part_number": part.get("part_number", ""),
                "description": part.get("description", ""),
                "replaces": part.get("replaces", []),
                "superseded_by": part.get("superseded_by", []),
                "match_type": match.get("match_type", ""),
                "confidence": match.get("confidence", ""),
                "source_url": match.get("source_url", ""),
                "notes": match.get("notes", ""),
                "verification_required": bool(part.get("verification_required", False)),
            })
    return {
        "vin": result.get("vin", ""),
        "searched_at": utc_now(),
        "year": flat.get("year", ""),
        "make": flat.get("make", ""),
        "model": flat.get("model", ""),
        "trim": flat.get("trim", ""),
        "series": flat.get("series", ""),
        "engine": flat.get("engine", ""),
        "key_part_numbers": flat.get("key_part_numbers", ""),
        "confidence": flat.get("confidence", ""),
        "replaces": flat.get("replaces", ""),
        "superseded_by": flat.get("superseded_by", ""),
        "decode_source": result.get("decode_source", ""),
        "decode": result.get("decode", {}),
        "parts": parts,
    }


def to_lookup_payload(summary: dict[str, Any]) -> dict[str, Any]:
    parts = [
        {
            "part": part.get("part_number", ""),
            "name": part.get("description", "") or "Key / Remote Part",
            "viewUrl": part.get("source_url", ""),
            "confidence": part.get("confidence", ""),
            "replaces": part.get("replaces", []),
            "supersededBy": part.get("superseded_by", []),
            "verificationRequired": part.get("verification_required", False),
            "notes": part.get("notes", ""),
        }
        for part in summary.get("parts", [])
    ]
    vehicle = " ".join(item for item in [summary.get("year", ""), summary.get("make", ""), summary.get("model", ""), summary.get("trim", "")] if item)
    return {
        "vehicle": vehicle,
        "vin": summary.get("vin", ""),
        "make": summary.get("make", "").casefold(),
        "makeLabel": summary.get("make", ""),
        "count": len(parts),
        "cached": summary.get("decode_source") == "cache",
        "siteUsed": parts[0].get("viewUrl", "") if parts else "",
        "sourceUrl": parts[0].get("viewUrl", "") if parts else "",
        "parts": parts,
        "confidence": summary.get("confidence", ""),
        "decode": summary.get("decode", {}),
    }


def record_history(summary: dict[str, Any]) -> None:
    history = [item for item in load_history() if item.get("vin") != summary.get("vin")]
    history.insert(0, summary)
    save_history(history)


class VinKeyHandler(BaseHTTPRequestHandler):
    server_version = "VinKeySingleFile/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.write_json({"ok": True, "history_count": len(load_history()), "single_file": True})
            return
        if parsed.path == "/api/makes":
            self.write_json({"makes": public_makes()})
            return
        if parsed.path == "/api/history":
            history = load_history()
            self.write_json({"items": history, "history": history})
            return
        if parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            vin = (params.get("vin") or [""])[0]
            offline = (params.get("offline") or ["false"])[0].lower() == "true"
            self.handle_lookup(vin, offline=offline)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/search", "/api/detect", "/api/lookup", "/api/batch_lookup", "/api/subscribe"}:
            self.write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            self.write_json({"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/detect":
            self.write_json(detect_make_from_partial_vin(str(payload.get("vin", ""))))
            return
        if parsed.path == "/api/subscribe":
            ok, message = save_subscriber(str(payload.get("email", "")))
            self.write_json({"ok": ok, "message": message} if ok else {"error": message}, status=HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/batch_lookup":
            vins = payload.get("vins", [])
            if not isinstance(vins, list):
                self.write_json({"error": "vins must be a list"}, status=HTTPStatus.BAD_REQUEST)
                return
            self.handle_batch_lookup(vins, offline=bool(payload.get("offline", False)))
            return
        self.handle_lookup(str(payload.get("vin", "")), offline=bool(payload.get("offline", False)))

    def handle_lookup(self, vin: str, *, offline: bool) -> None:
        try:
            result = resolve_key_parts(vin, offline=offline, update_cache=not offline)
        except VinKeyError as exc:
            self.write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except OSError as exc:
            self.write_json({"error": f"Network failed while resolving VIN: {exc}"}, status=HTTPStatus.BAD_GATEWAY)
            return
        summary = summarize_result(result)
        record_history(summary)
        self.write_json(to_lookup_payload(summary))

    def handle_batch_lookup(self, vins: list[Any], *, offline: bool) -> None:
        items = []
        for vin in vins:
            try:
                result = resolve_key_parts(str(vin), offline=offline, update_cache=not offline)
                summary = summarize_result(result)
                record_history(summary)
                items.append({"ok": True, "vin": summary.get("vin", ""), "result": to_lookup_payload(summary)})
            except (VinKeyError, OSError) as exc:
                items.append({"ok": False, "vin": str(vin), "error": str(exc)})
        self.write_json({"items": items, "count": len(items)})

    def serve_static(self, path: str) -> None:
        if path in ("", "/"):
            self.write_text(INDEX_HTML, "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self.write_text(APP_JS, "application/javascript; charset=utf-8")
            return
        if path == "/styles.css":
            self.write_text(STYLES_CSS, "text/css; charset=utf-8")
            return
        self.write_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def write_text(self, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the single-file OEM key finder app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8989)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), VinKeyHandler)
    print(f"OEM Key Finder 8989 running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
