from unittest.mock import patch

from app.services import log_service


async def test_record_and_list_events_newest_first() -> None:
    await log_service.record_event("First", "first description")
    await log_service.record_event("Second", "second description")

    events = await log_service.list_events()

    assert [e.title for e in events] == ["Second", "First"]
    assert events[0].description == "second description"
    assert events[0].id > events[1].id
    assert events[0].created_at


async def test_events_are_capped_at_max_entries() -> None:
    with patch.object(log_service, "_MAX_ENTRIES", 3):
        for i in range(5):
            await log_service.record_event(f"Event {i}", "desc")

        events = await log_service.list_events()

    assert len(events) == 3
    assert [e.title for e in events] == ["Event 4", "Event 3", "Event 2"]
