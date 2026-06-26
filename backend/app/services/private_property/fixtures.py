"""Bundled fixture data for Private Property mode when URA creds are absent.

Shaped exactly like a URA `Result` array (projects -> transaction[]), so the
same normalise.normalise_batch path runs in mock and live mode. Small but
spread across property types, sale types and market segments.
"""
from __future__ import annotations


def ura_result_fixture() -> list[dict]:
    return [
        {
            "project": "THE CONTINUUM", "street": "THIAM SIEW AVENUE",
            "marketSegment": "RCR", "x": "31870", "y": "32100",
            "transaction": [
                {"area": "92", "floorRange": "06-10", "noOfUnits": "1", "contractDate": "0324",
                 "typeOfSale": "1", "price": "2150000", "propertyType": "Condominium",
                 "district": "15", "tenure": "Freehold", "typeOfArea": "Strata"},
                {"area": "110", "floorRange": "11-15", "noOfUnits": "1", "contractDate": "0524",
                 "typeOfSale": "1", "price": "2750000", "propertyType": "Condominium",
                 "district": "15", "tenure": "Freehold", "typeOfArea": "Strata"},
                {"area": "92", "floorRange": "01-05", "noOfUnits": "1", "contractDate": "1124",
                 "typeOfSale": "2", "price": "2300000", "propertyType": "Condominium",
                 "district": "15", "tenure": "Freehold", "typeOfArea": "Strata"},
            ],
        },
        {
            "project": "PARC CLEMATIS", "street": "JALAN LEMPENG",
            "marketSegment": "OCR", "x": "21000", "y": "32500",
            "transaction": [
                {"area": "70", "floorRange": "16-20", "noOfUnits": "1", "contractDate": "0224",
                 "typeOfSale": "3", "price": "1480000", "propertyType": "Apartment",
                 "district": "05", "tenure": "99 yrs lease commencing from 2019",
                 "typeOfArea": "Strata"},
                {"area": "85", "floorRange": "06-10", "noOfUnits": "1", "contractDate": "0724",
                 "typeOfSale": "3", "price": "1650000", "propertyType": "Apartment",
                 "district": "05", "tenure": "99 yrs lease commencing from 2019",
                 "typeOfArea": "Strata"},
            ],
        },
        {
            "project": "COPEN GRAND", "street": "TENGAH GARDEN WALK",
            "marketSegment": "OCR", "x": "18000", "y": "36000",
            "transaction": [
                {"area": "93", "floorRange": "06-10", "noOfUnits": "1", "contractDate": "0424",
                 "typeOfSale": "3", "price": "1560000", "propertyType": "Executive Condominium",
                 "district": "24", "tenure": "99 yrs lease commencing from 2022",
                 "typeOfArea": "Strata"},
            ],
        },
        {
            "project": "", "street": "FABER WALK",
            "marketSegment": "OCR", "x": "20500", "y": "32800",
            "transaction": [
                {"area": "210", "floorRange": "-", "noOfUnits": "1", "contractDate": "0624",
                 "typeOfSale": "3", "price": "3850000", "propertyType": "Terrace",
                 "district": "05", "tenure": "Freehold", "typeOfArea": "Land"},
            ],
        },
    ]
