"""Tests for receipt category detection."""

import pytest
from receipt_lens.categorize import categorize_receipt


def test_grocery_store_by_name():
    assert categorize_receipt("Biedronka", []) == "groceries"


def test_grocery_store_aldi():
    assert categorize_receipt("ALDI Supermarket", []) == "groceries"


def test_fuel_by_store_name():
    assert categorize_receipt("BP Gas Station", []) == "fuel"


def test_dining_mcdonalds():
    assert categorize_receipt("McDonald's", []) == "dining"


def test_dining_pizza_by_name():
    assert categorize_receipt("Pizza Hut", []) == "dining"


def test_health_pharmacy():
    assert categorize_receipt("Apteka Centralna", []) == "health"


def test_category_from_items_when_no_store():
    assert categorize_receipt(None, ["milk", "bread", "eggs", "cheese"]) == "groceries"


def test_transport_uber():
    assert categorize_receipt("Uber", []) == "transport"


def test_electronics_mediamarkt():
    assert categorize_receipt("MediaMarkt", []) == "electronics"


def test_clothing_zara():
    assert categorize_receipt("Zara", []) == "clothing"


def test_other_when_no_match():
    assert categorize_receipt("XYZ Corp 12345", ["item1", "item2"]) == "other"


def test_empty_inputs_return_other():
    assert categorize_receipt(None, []) == "other"


def test_case_insensitive():
    assert categorize_receipt("MCDONALD'S", []) == "dining"


def test_store_takes_priority_over_generic_items():
    result = categorize_receipt("Shell", ["coffee", "snack", "fuel"])
    assert result == "fuel"
