from app.matching.schemas import (
    ConfirmRequest,
    MatchItemRead,
    MatchRead,
    ProductChoice,
    SendRequest,
    SendItemResult,
    SendResult,
)


def test_send_request_defaults_pickup():
    assert SendRequest().modality == "PICKUP"


def test_models_construct():
    choice = ProductChoice(upc="0001", description="Flour", size="5 lb", price=3.49, stock_level="HIGH")
    item = MatchItemRead(item_id=1, ingredient_id=2, ingredient_name="flour",
                         total_qty=3.0, total_unit="cup", purchase_qty=1,
                         purchase_qty_estimated=True, kroger_upc=None, current=None)
    read = MatchRead(connected=True, store_location_id="L1", items=[item])
    assert read.items[0].ingredient_name == "flour"
    assert choice.price == 3.49
    assert ConfirmRequest(kroger_upc="0001").kroger_description is None
    result = SendResult(status="sent_to_kroger", results=[SendItemResult(upc="0001", ok=True, error=None)])
    assert result.results[0].ok is True
